"""ORCL valuation: (1) RPO contract-level NPV [PRIMARY], (2) DCF cross-check, (3) sensitivities,
(4) ROIC breakeven. Imports the forecast engine from model.py."""
import json, math, copy
import model as M

FY=[2027,2028,2029,2030,2031]
PRICE=M.MKT['price']; SHARES_OUT=M.MKT['sh_out']; MCAP=PRICE*SHARES_OUT

# =========================================================== WACC
ERP=0.050                      # ANALYST INPUT: mature-market equity risk premium
RF=M.MKT['rf']                 # 10y UST 4.672% (^TNX, 8/27/26)
BETA_5Y=M.MKT['beta']          # 1.72 (stockanalysis, 5y)
BETA_NORM=1.28                 # ANALYST ESTIMATE: pre-AI-repricing / peer-normalised
KD_MARGINAL=0.0675             # marginal pre-tax cost of new debt post S&P BBB- (July 2026);
                               # Oracle's Feb-2026 30y priced 6.70%, 40y 6.85% (10-K note 6)
TAX_MARG=0.20
D_MKT=167430.0                 # total debt incl. capitalised leases (single-source, 8/27/26)
E_MKT=MCAP
def wacc(beta):
    ke=RF+beta*ERP; kd=KD_MARGINAL*(1-TAX_MARG)
    w=E_MKT/(E_MKT+D_MKT)
    return w*ke+(1-w)*kd, ke
W_HI,KE_HI = wacc(BETA_5Y); W_LO,KE_LO = wacc(BETA_NORM)
BETA_BASE=(BETA_5Y+BETA_NORM)/2
W_BASE,KE_BASE = wacc(BETA_BASE)
WACC={'Base':round(W_BASE,4),'Bull':round(W_LO,4),'Bear':round(W_HI,4)}

NET_DEBT_0 = (M.BS26['debt_cur']+M.BS26['debt_nc']) - (M.BS26['cash']+M.BS26['mkt_sec'])
PREF_0 = M.PREF['face']
NCI_0  = M.BS26['nci']

# =========================================================== (1) RPO CONTRACT NPV  [PRIMARY]
# Value the 5/31/2026 backlog as a self-liquidating contract portfolio. NO renewal assumed.
BACKLOG_ASSUMP={
 'Base':dict(ebitda_margin=[0.36,0.42,0.46,0.49,0.51,0.52,0.52,0.52,0.52,0.52],
             tail_shape=[0.30,0.25,0.20,0.15,0.10], cust_funded=0.22, eff_turn=0.36,
             maint_rate=0.35, tax=0.19, recovery=0.75),
 'Bull':dict(ebitda_margin=[0.40,0.47,0.52,0.55,0.57,0.58,0.58,0.58,0.58,0.58],
             tail_shape=[0.28,0.24,0.20,0.16,0.12], cust_funded=0.26, eff_turn=0.44,
             maint_rate=0.35, tax=0.19, recovery=0.85),
 'Bear':dict(ebitda_margin=[0.30,0.33,0.34,0.35,0.35,0.35,0.35,0.35,0.35,0.35],
             tail_shape=[0.32,0.26,0.20,0.13,0.09], cust_funded=0.18, eff_turn=0.28,
             maint_rate=0.35, tax=0.19, recovery=0.45),
}
MIX_EQ,MIX_BLDG,MIX_LAND=0.62,0.30,0.08
LIFE_EQ,LIFE_BLDG=6.0,25.0
def backlog_npv(scen, res, w=None, turn=None, margin_shift=0.0, haircut=None):
    A=BACKLOG_ASSUMP[scen]; w = w if w is not None else WACC[scen]
    turn = turn if turn is not None else A['eff_turn']
    hc = 1-(haircut if haircut is not None else M.S_BY[scen]['rpo_haircut'])
    rev=list(res['rpo_runoff'])
    tail_total=M.RPO_SCHED['thereafter']*M.RPO26*hc
    rev+= [tail_total*x for x in A['tail_shape']]
    yrs=len(rev); peak=max(rev)
    # Capacity is built to the CONTRACTED schedule; the haircut is a counterparty failure that
    # happens after the capex is sunk. Sizing capex off the post-haircut path would assume
    # Oracle sees the default coming -- which would make counterparty risk look value-accretive.
    rev_contracted=[r/hc for r in rev] if hc>0 else rev
    prev=rev_contracted[0]*0.72
    gcap=[]
    for t in range(yrs):
        g=max(0.0, rev_contracted[t]-prev)/turn*(1-A['cust_funded']); gcap.append(g); prev=max(prev,rev_contracted[t])
    # depreciate vintages straight line over LIFE_BL, half-year in year placed
    dep=[0.0]*yrs; capex=list(gcap)
    for _ in range(40):
        d=[0.0]*yrs
        for t in range(yrs):
            for j in range(t+1):
                d[t]+= (capex[j]*MIX_EQ/LIFE_EQ + capex[j]*MIX_BLDG/LIFE_BLDG)*(0.5 if j==t else 1.0)
        newcapex=[gcap[t]+d[t]*A['maint_rate']*(rev[t]/peak) for t in range(yrs)]
        if max(abs(newcapex[t]-capex[t]) for t in range(yrs))<1.0:
            capex, dep = newcapex, d; break
        capex, dep = newcapex, d
    gross=sum(capex); accum=sum(dep); nbv=max(0.0, gross-accum)   # land + long-lived shell survive the horizon
    rows=[]; pv=0.0
    for t in range(yrs):
        m=(A['ebitda_margin'][t] if t<len(A['ebitda_margin']) else A['ebitda_margin'][-1])+margin_shift
        ebitda=rev[t]*m; ebit=ebitda-dep[t]; tax=max(0.0,ebit)*A['tax']
        fcf=ebitda-tax-capex[t]; df=1/((1+w)**(t+0.5)); pv+=fcf*df
        rows.append(dict(fy=2027+t, rev=rev[t], ebitda=ebitda, dep=dep[t], ebit=ebit,
                         tax=tax, capex=capex[t], fcf=fcf, df=df, pv=fcf*df))
    residual=nbv*A['recovery']; pv_res=residual/((1+w)**yrs)
    return dict(rows=rows, pv_ops=pv, gross_capex=gross, nbv_end=nbv, residual=residual,
                pv_residual=pv_res, total=pv+pv_res, rev_total=sum(rev))

# ---- (1b) Legacy (non-backlog) business: software support/license, SaaS, services, hardware
LEGACY={'Base':dict(rev=51000, ebitda_m=0.44, g=0.015, capex_pct=0.03, tax=0.19),
        'Bull':dict(rev=51500, ebitda_m=0.46, g=0.020, capex_pct=0.03, tax=0.19),
        'Bear':dict(rev=50000, ebitda_m=0.41, g=-0.010,capex_pct=0.03, tax=0.19)}
def legacy_value(scen, w=None):
    L=LEGACY[scen]; w=w if w is not None else WACC[scen]
    nopat=L['rev']*L['ebitda_m']*(1-L['tax'])
    fcf=nopat-L['rev']*L['capex_pct']
    return fcf/(w-L['g']), fcf

# =========================================================== (2) DCF CROSS-CHECK
def dcf(scen,res,w=None,g=None):
    S=M.S_BY[scen]; w=w if w is not None else WACC[scen]; g=g if g is not None else S['terminal_growth']
    u=res['ufcf']; pv=sum(u[i]/((1+w)**(i+0.5)) for i in range(5))
    tv_fcf=u[4]*(1+g)
    tv=tv_fcf/(w-g); pv_tv=tv/((1+w)**5)
    ev=pv+pv_tv
    eq=ev-res['net_debt'][4]/((1+w)**0)  # use terminal-year net debt? no: use today's
    eq=ev-NET_DEBT_0-PREF_0-NCI_0
    return dict(pv_explicit=pv, pv_tv=pv_tv, ev=ev, equity=eq,
                px=eq/res['shares_diluted'][4], tv_share=pv_tv/ev)
def fcfe_val(scen,res,w=None,g=None):
    S=M.S_BY[scen]; ke=RF+BETA_BASE*ERP if w is None else w
    g=g if g is not None else S['terminal_growth']
    f=res['fcfe']; pv=sum(f[i]/((1+ke)**(i+0.5)) for i in range(5))
    tv=f[4]*(1+g)/(ke-g); pv_tv=tv/((1+ke)**5)
    eq=pv+pv_tv
    return dict(equity=eq, px=eq/res['shares_diluted'][4], ke=ke, tv_share=pv_tv/(pv+pv_tv))

# =========================================================== (4) ROIC BREAKEVEN
def breakeven_gm(wacc_, turn_full, util, life=7.0, opex=0.12, tax=0.20, ic_factor=0.55):
    """Required IaaS gross margin (depreciation INSIDE cost of revenue, as Oracle reports it)
       for the incremental buildout to earn exactly its cost of capital."""
    T=turn_full*util
    ebit_margin = wacc_*ic_factor/((1-tax)*T)
    return ebit_margin+opex, ebit_margin

# =========================================================== RUN
OUT={}
for scen in ('Base','Bull','Bear'):
    res=M.R[scen]; w=WACC[scen]
    b=backlog_npv(scen,res); lv,lfcf=legacy_value(scen)
    ev_contracted=b['total']+lv
    eq_contracted=ev_contracted-NET_DEBT_0-PREF_0-NCI_0
    px_contracted=eq_contracted/M.H['waso_diluted'][2]
    d=dcf(scen,res); f=fcfe_val(scen,res)
    OUT[scen]=dict(wacc=w, backlog=b, legacy_value=lv, legacy_fcf=lfcf,
                   ev_contracted=ev_contracted, eq_contracted=eq_contracted,
                   px_contracted=px_contracted, dcf=d, fcfe=f)

json.dump({k:{kk:(vv if not isinstance(vv,dict) else {k2:v2 for k2,v2 in vv.items() if k2!='rows'})
              for kk,vv in v.items()} for k,v in OUT.items()},
          open('valuation_out.json','w'), default=float)

print("="*100); print("WACC BUILD (all inputs shown)"); print("="*100)
print(f"  Risk-free (10y UST ^TNX, 8/27/26)      {RF*100:6.3f}%")
print(f"  Equity risk premium (analyst input)    {ERP*100:6.2f}%")
print(f"  Beta 5y (source) / normalised / base   {BETA_5Y:.2f} / {BETA_NORM:.2f} / {BETA_BASE:.2f}")
print(f"  Cost of equity  @1.72 / @1.50 / @1.28  {KE_HI*100:5.2f}% / {KE_BASE*100:5.2f}% / {KE_LO*100:5.2f}%")
print(f"  Pre-tax cost of NEW debt               {KD_MARGINAL*100:5.2f}%   (after-tax {KD_MARGINAL*(1-TAX_MARG)*100:.2f}%)")
print(f"  E / (D+E)                              {E_MKT/(E_MKT+D_MKT)*100:5.1f}%   (E ${E_MKT/1000:,.0f}bn, D ${D_MKT/1000:,.0f}bn)")
print(f"  WACC  Bull {WACC['Bull']*100:.2f}%  |  Base {WACC['Base']*100:.2f}%  |  Bear {WACC['Bear']*100:.2f}%")
print(f"  Net debt (5/31/26, ex-leases) ${NET_DEBT_0:,.0f}m   Preferred ${PREF_0:,.0f}m   NCI ${NCI_0:,.0f}m")

print()
for scen in ('Base','Bull','Bear'):
    o=OUT[scen]; b=o['backlog']
    print("="*100); print(f"{scen.upper()}  --  RPO CONTRACT-LEVEL NPV (PRIMARY)   WACC {o['wacc']*100:.2f}%"); print("="*100)
    print(f"  {'FY':<6}{'BacklogRev':>12}{'EBITDA':>11}{'Dep':>10}{'Capex':>10}{'FCF':>11}{'PV':>11}")
    for r in b['rows']:
        print(f"  {r['fy']:<6}{r['rev']:>12,.0f}{r['ebitda']:>11,.0f}{r['dep']:>10,.0f}{r['capex']:>10,.0f}{r['fcf']:>11,.0f}{r['pv']:>11,.0f}")
    print(f"  {'':<6}{'total rev':>12}{b['rev_total']:>11,.0f}")
    print(f"  PV of backlog cash flows                 ${b['pv_ops']:>12,.0f}m")
    print(f"  PV of residual asset value               ${b['pv_residual']:>12,.0f}m")
    print(f"  = Backlog enterprise value               ${b['total']:>12,.0f}m")
    L=LEGACY[scen]; leb=L['rev']*L['ebitda_m']
    print(f"  + Legacy (non-backlog) business value    ${o['legacy_value']:>12,.0f}m"
          f"   [= {o['legacy_value']/leb:.1f}x its ${leb:,.0f}m EBITDA; peer range 17-19x]")
    for mult in (8.0,10.0,12.0):
        alt=leb*mult
        print(f"      cross-check @ {mult:4.1f}x EBITDA          ${alt:>12,.0f}m -> contracted px "
              f"${(o['backlog']['total']+alt-NET_DEBT_0-PREF_0-NCI_0)/M.H['waso_diluted'][2]:>7.2f}")
    print(f"  = Contracted enterprise value            ${o['ev_contracted']:>12,.0f}m")
    print(f"  - Net debt / preferred / NCI             ${-(NET_DEBT_0+PREF_0+NCI_0):>12,.0f}m")
    print(f"  = Contracted equity value                ${o['eq_contracted']:>12,.0f}m")
    print(f"  Per share (on 2,914m FY26 diluted)       ${o['px_contracted']:>12,.2f}")
    d=o['dcf']; f=o['fcfe']
    print(f"  [cross-check] UFCF DCF  EV ${d['ev']:,.0f}m  equity ${d['equity']:,.0f}m  px ${d['px']:.2f}  (TV = {d['tv_share']*100:.0f}% of EV)")
    print(f"  [cross-check] FCFE      equity ${f['equity']:,.0f}m  px ${f['px']:.2f}  @ Ke {f['ke']*100:.2f}%  (TV = {f['tv_share']*100:.0f}%)")
    print()

print("="*100); print("ROIC BREAKEVEN  --  required IaaS gross margin (dep. inside COGS) to earn exactly WACC")
print("="*100)
print(f"  Derived FY26 IaaS gross margin (analyst estimate, see model.py):  {M.H['iaas_gm'][2]*100:.1f}%")
hdr='util / asset turn'
print("  "+hdr.ljust(14)+"".join(f"{t:>10.2f}" for t in (0.40,0.45,0.50,0.55,0.60)))
for u in (0.65,0.75,0.85,0.95):
    row=f"  {u*100:>10.0f}%   "
    for t in (0.40,0.45,0.50,0.55,0.60):
        gmreq,_=breakeven_gm(WACC['Base'],t,u)
        row+=f"{gmreq*100:>9.1f}%"
    print(row)
print(f"  (WACC {WACC['Base']*100:.2f}%, 7y blended asset life, 12% opex allocation, 20% tax, IC = 55% of gross PP&E)")


# =========================================================== (3) SENSITIVITY
print(); print("="*100); print("SENSITIVITY  --  base case, contracted equity value per share"); print("="*100)
def px_from(scen,res,w=None,turn=None,mshift=0.0,legacy_w=None,haircut=None):
    b=backlog_npv(scen,res,w=w,turn=turn,margin_shift=mshift,haircut=haircut)
    lv,_=legacy_value(scen, w=(legacy_w if legacy_w is not None else w))
    return (b['total']+lv-NET_DEBT_0-PREF_0-NCI_0)/M.H['waso_diluted'][2]
resB=M.R['Base']
print("\nA. Backlog EBITDA margin (shift vs base path)  x  effective asset turn")
turns=[0.28,0.32,0.36,0.40,0.44]
print("     "+"margin".ljust(10)+"".join(f"{t:>10.2f}" for t in turns))
for ms in (-0.08,-0.04,0.0,0.04,0.08):
    print(f"   {ms*100:>+6.0f}pp   "+"".join(f"{px_from('Base',resB,turn=t,mshift=ms):>10.2f}" for t in turns))
print("\nB. WACC  x  legacy-business terminal growth")
gs=[-0.01,0.0,0.01,0.02,0.03]
print("     "+"WACC".ljust(10)+"".join(f"{g*100:>9.1f}%" for g in gs))
for w in (0.085,0.095,0.103,0.115,0.125):
    row=f"   {w*100:>5.2f}%   "
    for g in gs:
        Lb=copy.deepcopy(LEGACY['Base']); Lb['g']=g
        nopat=Lb['rev']*Lb['ebitda_m']*(1-Lb['tax']); fcf=nopat-Lb['rev']*Lb['capex_pct']
        lv=fcf/(w-g); b=backlog_npv('Base',resB,w=w)
        row+=f"{(b['total']+lv-NET_DEBT_0-PREF_0-NCI_0)/M.H['waso_diluted'][2]:>10.2f}"
    print(row)
print("\nC. RPO haircut (% of AI backlog never recognised)  x  WACC   [full model re-run]")
hs=[0.0,0.05,0.10,0.20,0.30]
print("     "+"WACC".ljust(10)+"".join(f"{h*100:>9.0f}%" for h in hs))
for w in (0.095,0.103,0.115):
    row=f"   {w*100:>5.2f}%   "
    for h in hs:
        S2=dict(M.BASE); S2['rpo_haircut']=h; r2=M.run(S2)
        row+=f"{px_from('Base',r2,w=w,haircut=h):>10.2f}"
    print(row)

print(); print("="*100); print("DRIVER RANKING  --  swing in base-case equity value per share"); print("="*100)
base_px=px_from('Base',resB)
def swing(label, lo_fn, hi_fn, lo_lbl, hi_lbl):
    return (label, lo_fn(), hi_fn(), lo_lbl, hi_lbl, abs(hi_fn()-lo_fn()))
tests=[]
tests.append(("Effective asset turn (capital intensity)", px_from('Base',resB,turn=0.28), px_from('Base',resB,turn=0.44),"0.28","0.44"))
tests.append(("Backlog EBITDA margin", px_from('Base',resB,mshift=-0.08), px_from('Base',resB,mshift=+0.08),"-8pp","+8pp"))
tests.append(("WACC", px_from('Base',resB,w=0.125), px_from('Base',resB,w=0.085),"12.5%","8.5%"))
_lo=copy.deepcopy(LEGACY['Base']); 
def legacy_px(g,m):
    L=dict(LEGACY['Base']); L['g']=g; L['ebitda_m']=m
    nopat=L['rev']*m*(1-L['tax']); fcf=nopat-L['rev']*L['capex_pct']
    lv=fcf/(WACC['Base']-g); b=backlog_npv('Base',resB)
    return (b['total']+lv-NET_DEBT_0-PREF_0-NCI_0)/M.H['waso_diluted'][2]
tests.append(("Legacy business terminal growth", legacy_px(-0.01,0.44), legacy_px(0.03,0.44),"-1%","+3%"))
tests.append(("Legacy business EBITDA margin", legacy_px(0.01,0.38), legacy_px(0.01,0.50),"38%","50%"))
def hair_px(h):
    S2=dict(M.BASE); S2['rpo_haircut']=h; return px_from('Base',M.run(S2),haircut=h)
tests.append(("RPO haircut / counterparty risk", hair_px(0.30), hair_px(0.0),"30%","0%"))
tests.sort(key=lambda x: abs(x[2]-x[1]), reverse=True)
print(f"  {'Driver':<42}{'low':>9}{'high':>9}{'swing $':>10}{'swing %':>9}   range")
for t in tests:
    sw=abs(t[2]-t[1])
    print(f"  {t[0]:<42}{t[1]:>9.2f}{t[2]:>9.2f}{sw:>10.2f}{sw/base_px*100:>8.0f}%   {t[3]} -> {t[4]}")
print(f"\n  Base contracted value per share: ${base_px:.2f}   |   market ${PRICE:.2f}")
