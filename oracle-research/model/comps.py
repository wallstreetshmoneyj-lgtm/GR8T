"""Comparable-company analysis. SINGLE SOURCE: stockanalysis.com, pulled 2026-08-27/28.
Every cell is tagged [C] = consensus/reported from source, or [E] = analyst (my) estimate."""
import json, re, datetime
D=json.load(open('comps_raw.json'))
PULL_DATE="2026-08-27 close (estimates as displayed 2026-08-28)"
TK=["ORCL","MSFT","CRM","SAP","IBM","NOW","WDAY","AMZN","GOOGL","CRWV","NBIS"]
SET_SW  =["ORCL","MSFT","CRM","SAP","IBM","NOW","WDAY"]
SET_AI  =["ORCL","MSFT","AMZN","GOOGL","CRWV","NBIS"]
FYE={"ORCL":5,"MSFT":6,"CRM":1,"SAP":12,"IBM":12,"NOW":12,"WDAY":1,"AMZN":12,"GOOGL":12,"CRWV":12,"NBIS":12}
def num(s):
    if s is None: return None
    s=str(s).strip().replace(',','').replace('$','')
    if s in ('n/a','-','','Upgrade','Pro','*'): return None
    neg=s.startswith('-') or s.startswith('(')
    s=s.lstrip('-').strip('()'); pct=s.endswith('%')
    if pct: s=s[:-1]
    m=re.match(r'^([\d\.]+)\s*([BMTK]?)$',s)
    if not m: return None
    v=float(m.group(1))*{'T':1e6,'B':1e3,'M':1.0,'K':1e-3,'':1.0}[m.group(2)]
    if pct: v=v/100.0
    return -v if neg else v
def stat(t,k): return num(D[t]['stats'].get(k))
def fc(t,row,col): return num(D[t]['fc'].get(row,{}).get(col))
def cols(t):
    h=D[t]['fc']['_hdr'][1:]; p=D[t]['fc']['_per'][1:]
    yrs=[int(x.split(',')[-1].strip()) for x in p]
    # FY0 = last column with a reported Revenue that is not a paywall token
    idx=[i for i,c in enumerate(h) if fc(t,'Revenue',c) is not None]
    return h, p, yrs, idx[-2], idx[-1]   # (fy0_index, fy1_index)

# ---------------- assemble ----------------
rows={}
for t in TK:
    h,p,yrs,i0,i1=cols(t)
    c0,c1=h[i0],h[i1]
    r=dict(ticker=t, fye_month=FYE[t], fy0_label=p[i0], fy1_label=p[i1],
           price=None, mcap=stat(t,'Market Cap'), ev=stat(t,'Enterprise Value'),
           shares=stat(t,'Shares Outstanding'), net_cash=stat(t,'Net Cash'),
           total_debt=stat(t,'Total Debt'), book=stat(t,'Equity (Book Value)'),
           rev0=fc(t,'Revenue',c0), rev1=fc(t,'Revenue',c1),
           g1=fc(t,'Revenue Growth',c1), gm0=fc(t,'Gross Margin',c0), gm1=fc(t,'Gross Margin',c1),
           oi0=fc(t,'Operating Income',c0), oi1=fc(t,'Operating Income',c1),
           ni1=fc(t,'Net Income',c1), eps0=fc(t,'EPS',c0), eps1=fc(t,'EPS',c1),
           epsg1=fc(t,'EPS Growth',c1), fcf0=fc(t,'Free Cash Flow',c0), fcf1=fc(t,'Free Cash Flow',c1),
           ebitda0=stat(t,'EBITDA'), ebit0=stat(t,'EBIT'), capex0=stat(t,'Capital Expenditures'),
           ocf0=stat(t,'Operating Cash Flow'), pb=stat(t,'PB Ratio'), roic=stat(t,'Return on Invested Capital (ROIC)'),
           fwd_pe=stat(t,'Forward PE'), ev_ebitda_ttm=stat(t,'EV / EBITDA'), ev_ebit_ttm=stat(t,'EV / EBIT'),
           ev_sales_ttm=stat(t,'EV / Sales'), nd_ebitda=stat(t,'Debt / EBITDA'), n_analysts=fc(t,'No. Analysts',c1),
           pt_avg=num(D[t]['fc'].get('_pt_Price',{}).get('Average')))
    r['price']=r['mcap']/r['shares'] if r['mcap'] and r['shares'] else None
    r['net_debt']=-r['net_cash'] if r['net_cash'] is not None else None
    rows[t]=r

# ---------------- FY2 = ANALYST ESTIMATE (mechanical rule, disclosed) ----------------
# g(FY2) = g(FY1) decayed 60% toward a 6% long-run rate; margins held at FY1; EPS grows at
# revenue growth + 300bp of operating leverage (150bp for the sub-scale AI names).
LONGRUN_G=0.06
def fy2(r):
    g1=r['g1'] if r['g1'] is not None else 0.08
    g2=0.60*g1+0.40*LONGRUN_G
    lev=0.015 if r['ticker'] in ('CRWV','NBIS') else 0.030
    r['g2_E']=g2
    r['rev2_E']=r['rev1']*(1+g2) if r['rev1'] else None
    r['eps2_E']=r['eps1']*(1+g2+lev) if r['eps1'] else None
    r['oi2_E']=r['oi1']*(1+g2+lev) if r['oi1'] else None
    r['fcf2_E']=r['fcf1']*(1+g2+lev) if (r['fcf1'] is not None) else None
    # EBITDA: hold FY0 EBITDA/EBIT relationship, scale EBIT by operating income growth
    r['d_and_a0']=(r['ebitda0']-r['ebit0']) if (r['ebitda0'] is not None and r['ebit0'] is not None) else None
    if r['oi1'] and r['d_and_a0'] is not None and r['oi0']:
        da_scale=(r['rev1']/r['rev0']) if r['rev0'] else 1.0
        r['ebitda1_E']=r['oi1']+r['d_and_a0']*da_scale
        r['ebitda2_E']=r['oi2_E']+r['d_and_a0']*da_scale*(1+g2)
    else:
        r['ebitda1_E']=r['ebitda2_E']=None
for t in TK: fy2(rows[t])

# ---------------- CALENDARISATION to NTM = 2026-08-28 .. 2027-08-27 ----------------
AS_OF=datetime.date(2026,8,28)
def fy_end(month, year): return datetime.date(year+(1 if month<12 else 0), month%12+1, 1)-datetime.timedelta(days=1)
def weights(t):
    """fraction of the NTM window falling in FY1 vs FY2"""
    r=rows[t]; m=r['fye_month']
    y=int(r['fy1_label'].split(',')[-1].strip())
    e1=fy_end(m,y) if m!=12 else datetime.date(y,12,31)
    e1=datetime.datetime.strptime(r['fy1_label'].strip(),"%b %d, %Y").date()
    days=(e1-AS_OF).days
    w1=max(0.0,min(1.0,days/365.0))
    return w1, 1-w1
for t in TK:
    w1,w2=weights(t); r=rows[t]; r['w_fy1'],r['w_fy2']=w1,w2
    def blend(a,b): return (w1*a+w2*b) if (a is not None and b is not None) else None
    r['ntm_rev']=blend(r['rev1'],r['rev2_E']); r['ntm_eps']=blend(r['eps1'],r['eps2_E'])
    r['ntm_ebitda']=blend(r['ebitda1_E'],r['ebitda2_E']); r['ntm_ebit']=blend(r['oi1'],r['oi2_E'])
    r['ntm_fcf']=blend(r['fcf1'],r['fcf2_E'])
    px=r['price']; ev=r['ev']
    r['ntm_pe']   = px/r['ntm_eps'] if (px and r['ntm_eps'] and r['ntm_eps']>0) else None
    r['ntm_evebitda']= ev/r['ntm_ebitda'] if (ev and r['ntm_ebitda'] and r['ntm_ebitda']>0) else None
    r['ntm_evebit']  = ev/r['ntm_ebit']  if (ev and r['ntm_ebit'] and r['ntm_ebit']>0) else None
    r['ntm_evsales'] = ev/r['ntm_rev']   if (ev and r['ntm_rev']) else None
    r['ntm_evfcf']   = ev/r['ntm_fcf']   if (ev and r['ntm_fcf'] and r['ntm_fcf']>0) else None
    r['ntm_fcf_margin']= r['ntm_fcf']/r['ntm_rev'] if (r['ntm_fcf'] is not None and r['ntm_rev']) else None
    r['capex_rev0']= (-r['capex0']/r['rev0']) if (r['capex0'] is not None and r['rev0']) else None
    r['fy1_pe']= px/r['eps1'] if (px and r['eps1'] and r['eps1']>0) else None
    # PEG variants
    r['peg_fy1']= (r['fy1_pe']/(r['epsg1']*100) if (r['fy1_pe'] and r['epsg1'] and r['epsg1']>0.005) else None)
    g_ntm=(r['eps2_E']/r['eps1']-1) if (r['eps1'] and r['eps2_E'] and r['eps1']>0) else None
    r['peg_ntm']= (r['ntm_pe']/(g_ntm*100) if (r['ntm_pe'] and g_ntm and g_ntm>0.005) else None)
json.dump(rows, open('comps_out.json','w'), default=float)

def fmt(v,f="{:.1f}",na="n/m"): return na if v is None else f.format(v)
def table(name, tickers):
    print("\n"+"="*152); print(f"{name}   |  source: stockanalysis.com, {PULL_DATE}  |  [C]=consensus/reported  [E]=my estimate"); print("="*152)
    hdr=(f"{'Ticker':<7}{'FYE':>4}{'Price':>9}{'EV $bn':>9}{'NTM P/E':>9}{'EV/EBITDA':>10}{'EV/EBIT':>9}"
         f"{'EV/Sales':>9}{'EV/FCF':>9}{'P/B':>7}{'ND/EBITDA':>10}{'FCFmgn':>8}{'GM':>7}{'RevG':>7}{'Capex/Rev':>10}")
    print(hdr); print(f"{'':7}{'':4}{'[C]':>9}{'[C]':>9}{'[E]':>9}{'[E]':>10}{'[E]':>9}{'[E]':>9}{'[E]':>9}{'[C]':>7}{'[C]':>10}{'[E]':>8}{'[C]':>7}{'[C]':>7}{'[C]':>10}")
    print("-"*152)
    for t in tickers:
        r=rows[t]
        print(f"{t:<7}{r['fye_month']:>4}{fmt(r['price'],'{:.2f}'):>9}{fmt(r['ev']/1000,'{:,.0f}'):>9}"
              f"{fmt(r['ntm_pe'],'{:.1f}x'):>9}{fmt(r['ntm_evebitda'],'{:.1f}x'):>10}{fmt(r['ntm_evebit'],'{:.1f}x'):>9}"
              f"{fmt(r['ntm_evsales'],'{:.1f}x'):>9}{fmt(r['ntm_evfcf'],'{:.1f}x'):>9}{fmt(r['pb'],'{:.1f}x'):>7}"
              f"{fmt(r['nd_ebitda'],'{:.1f}x'):>10}{fmt(r['ntm_fcf_margin'],'{:.0%}'):>8}{fmt(r['gm1'],'{:.0%}'):>7}"
              f"{fmt(r['g1'],'{:.0%}'):>7}{fmt(r['capex_rev0'],'{:.0%}'):>10}")
table("SET 1 - ENTERPRISE SOFTWARE (calendarised to NTM 8/28/26-8/27/27)", SET_SW)
table("SET 2 - AI INFRASTRUCTURE / HYPERSCALE (calendarised to NTM 8/28/26-8/27/27)", SET_AI)
print("\n"+"="*152); print("NOT CALENDARISED - raw next-fiscal-year consensus, 100% source data, periods DO NOT match"); print("="*152)
print(f"{'Ticker':<7}{'FY1 period end':>16}{'NTM wgt FY1':>13}{'FY1 rev $bn':>13}{'FY1 EPS':>10}{'FY1 P/E':>10}{'#analysts':>11}")
print("-"*152)
for t in TK:
    r=rows[t]
    print(f"{t:<7}{r['fy1_label']:>16}{fmt(r['w_fy1'],'{:.0%}'):>13}{fmt(r['rev1']/1000,'{:,.1f}'):>13}"
          f"{fmt(r['eps1'],'{:.2f}'):>10}{fmt(r['fy1_pe'],'{:.1f}x'):>10}{fmt(r['n_analysts'],'{:.0f}'):>11}")
print("\n"+"="*152); print("PEG - THREE BASES (ORCL). Never publish one number."); print("="*152)
o=rows['ORCL']
p=o['price']
bases=[("FY27E growth off the $7.63 headline (contaminated by Ampere/Bloom gains)",8.05/7.63-1),
       ("FY27E growth off the $6.83 clean base (mgmt's own like-for-like)",8.05/6.83-1),
       ("FY27E->FY28E growth (my estimate; FY28 consensus is paywalled at source)",o['eps2_E']/o['eps1']-1)]
for lbl,g in bases:
    pe_fy1=p/8.05; pe_ntm=o['ntm_pe']
    print(f"  {lbl}")
    print(f"      growth {g*100:5.2f}%   PEG on FY27E P/E ({pe_fy1:.1f}x) = {pe_fy1/(g*100):.2f}"
          f"   |   PEG on NTM P/E ({pe_ntm:.1f}x) = {pe_ntm/(g*100):.2f}")
print("\n  Negative/near-zero growth is reported n/m, never as a printed PEG.")
