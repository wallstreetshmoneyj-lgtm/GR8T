import openpyxl, json, io, contextlib
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import column_index_from_string as CIX, get_column_letter as CL
import model as M
with contextlib.redirect_stdout(io.StringIO()):
    import valuation as V
CMP=json.load(open('comps_out.json'))
wb=openpyxl.load_workbook('ORCL_model.xlsx')
IR=json.load(open('xlsx_rows.json'))['ROW']
P2=json.load(open('xlsx_rows2.json')); P3=json.load(open('xlsx_rows3.json')); P4=json.load(open('xlsx_rows4.json'))
P5=json.load(open('xlsx_rows5.json')); P6=json.load(open('xlsx_rows6.json'))
BLUE=Font(name='Arial',size=10,color='0000FF'); BLACK=Font(name='Arial',size=10)
GREEN=Font(name='Arial',size=10,color='008000'); HDR=Font(name='Arial',size=10,bold=True)
TITLE=Font(name='Arial',size=13,bold=True); SUB=Font(name='Arial',size=10,bold=True,color='444444')
NOTE=Font(name='Arial',size=8,italic=True,color='666666'); WHDR=Font(name='Arial',size=10,bold=True,color='FFFFFF')
YFILL=PatternFill('solid',fgColor='FFFF00'); GFILL=PatternFill('solid',fgColor='E8E8E8'); HFILL=PatternFill('solid',fgColor='1F3864')
CUR='$#,##0;($#,##0);-'; CUR2='$#,##0.00;($#,##0.00);-'; PCT='0.0%;(0.0%);-'; PCT2='0.00%;(0.00%);-'
NUM='#,##0;(#,##0);-'; MULT='0.0x'; RAT='0.00'
CO=['C','D','E','F','G']
def sh(n,w1=52,nc=14):
    ws=wb.create_sheet(n); ws.sheet_view.showGridLines=False
    ws.column_dimensions['A'].width=w1
    for i in range(2,nc): ws.column_dimensions[CL(i)].width=12
    ws.column_dimensions[CL(nc+1)].width=76
    return ws
def T(ws,t,s=None):
    ws['A1']=t; ws['A1'].font=TITLE
    if s: ws['A2']=s; ws['A2'].font=NOTE
def sec(ws,r,l,n=14):
    ws.cell(row=r,column=1,value=l).font=SUB
    for cc in range(1,n): ws.cell(row=r,column=cc).fill=GFILL
def IN(k,c=None): return f"Inputs!$B${IR[k]}" if c is None else f"Inputs!{c}${IR[k]}"

# ==================================================== VALUATION_DCF
ws=sh('Valuation_DCF')
T(ws,'CROSS-CHECK — unlevered FCF DCF and FCFE','On five years of deeply negative free cash flow a growth-perpetuity DCF is mostly terminal assumption. The terminal share of EV is printed below so the reader can see exactly how much.')
r=4
def one(lab,f,fmt=CUR,font=BLACK,note=None,bold=False,fill=None,col=3):
    global r
    c=ws.cell(row=r,column=1,value=lab); c.font=HDR if bold else BLACK
    cc=ws.cell(row=r,column=col,value=f); cc.font=font; cc.number_format=fmt
    if fill: cc.fill=fill
    if note:
        n=ws.cell(row=r,column=15,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
    r+=1; return r-1
sec(ws,r,'WACC BUILD'); r+=1
W_RF =one('Risk-free rate (10y UST, ^TNX 8/27/26)',0.04672,PCT2,BLUE)
W_ERP=one('Equity risk premium',0.050,PCT2,BLUE,'Analyst input. Mature-market ERP.',False,YFILL)
W_B5 =one('Beta, 5-year (source)',1.72,RAT,BLUE,'stockanalysis.com. Reflects the AI-era repricing of the stock.')
W_BN =one('Beta, normalised',1.28,RAT,BLUE,'Analyst estimate: pre-AI / software-peer level.')
W_BB =one('Beta used',f'=AVERAGE(C{W_B5},C{W_BN})',RAT,BLACK,'The midpoint is a judgement call, and it is the single largest driver of the answer.',False,YFILL)
W_KE =one('Cost of equity',f'=C{W_RF}+C{W_BB}*C{W_ERP}',PCT2)
W_KD =one('Pre-tax cost of NEW debt',f'={IN("kd_new")}',PCT2,GREEN,"Oracle's Feb-2026 30-year priced 6.70%, 40-year 6.85% (10-K MD&A).")
W_TX =one('Marginal tax rate',0.20,PCT2,BLUE)
W_E  =one('Market value of equity ($m)',437660,CUR,BLUE,'2,880.471m shares (10-K cover) x $151.94.')
W_D  =one('Market value of debt incl. leases ($m)',167430,CUR,BLUE,'Single-source figure, 8/27/26. Includes capitalised operating and finance leases.')
W_W  =one('WACC',f'=C{W_E}/(C{W_E}+C{W_D})*C{W_KE}+C{W_D}/(C{W_E}+C{W_D})*C{W_KD}*(1-C{W_TX})',PCT2,BLACK,
          'At beta 1.72 this is 11.09%; at beta 1.28, 9.51%.',True,YFILL)
r+=1
sec(ws,r,'UNLEVERED FREE CASH FLOW'); r+=1
def line(r_,label,vals,fmt=CUR,font=BLACK,note=None,bold=False):
    c=ws.cell(row=r_,column=1,value=label); c.font=HDR if bold else BLACK
    for i,col in enumerate(CO):
        cc=ws.cell(row=r_,column=CIX(col),value=vals[i]); cc.font=font; cc.number_format=fmt
    if note:
        n=ws.cell(row=r_,column=15,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
for i,y in enumerate(range(2027,2032)):
    c=ws.cell(row=r,column=3+i,value=f'FY{y}E'); c.font=HDR; c.alignment=Alignment(horizontal='center')
r+=1
line(r,'GAAP operating income',[f'=Income_Statement!{c}{P4["I_OI"]}' for c in CO],CUR,GREEN); D_OI=r; r+=1
line(r,'NOPAT',[f'={c}{D_OI}*(1-{IN("tax_gaap",c)})' for c in CO]); D_NOPAT=r; r+=1
line(r,'+ Depreciation & amortisation',[f'=Capex_Depreciation!{c}{P3["R_DEP"]}+Income_Statement!{c}{P4["I_AM"]}' for c in CO],CUR,GREEN); D_DA=r; r+=1
line(r,'- Capital expenditure',[f'=-Capex_Depreciation!{c}{P3["R_CX"]}' for c in CO],CUR,GREEN); D_CX=r; r+=1
line(r,'- Increase in net working capital',[f'=Cash_Flow!{c}{P5["F_NWC"]}' for c in CO],CUR,GREEN); D_NWC=r; r+=1
line(r,'+ Customer prepayments',[f'=Cash_Flow!{c}{P5["F_CP"]}' for c in CO],CUR,GREEN); D_CP=r; r+=1
line(r,'UNLEVERED FREE CASH FLOW',[f'=SUM({c}{D_NOPAT}:{c}{D_CP})' for c in CO],CUR,BLACK,None,True); D_UF=r; r+=1
line(r,'Discount period (mid-year)',[0.5,1.5,2.5,3.5,4.5],'0.0',BLUE); D_T=r; r+=1
line(r,'Discount factor',[f'=1/(1+$C${W_W})^{c}{D_T}' for c in CO],'0.000'); D_DF=r; r+=1
line(r,'PV of UFCF',[f'={c}{D_UF}*{c}{D_DF}' for c in CO]); D_PV=r; r+=2
sec(ws,r,'TERMINAL VALUE AND EQUITY BRIDGE'); r+=1
D_G   =one('Terminal growth',f'={IN("tg")}',PCT,GREEN,None,False,YFILL)
D_TV  =one('Terminal value at FY2031',f'=G{D_UF}*(1+C{D_G})/($C${W_W}-C{D_G})')
D_PVTV=one('PV of terminal value',f'=C{D_TV}/(1+$C${W_W})^5')
D_PVE =one('PV of the explicit forecast',f'=SUM($C${D_PV}:$G${D_PV})')
D_EV  =one('ENTERPRISE VALUE',f'=C{D_PVE}+C{D_PVTV}',CUR,BLACK,None,True)
D_TVS =one('Terminal value as % of EV',f'=C{D_PVTV}/C{D_EV}',PCT,BLACK,
           'Above ~75% the DCF is an opinion about 2032+ dressed as arithmetic. That is exactly why the RPO contract NPV is the primary method here.',True,YFILL)
D_ND  =one('Less: net debt / preferred / NCI',f"=-({IN('debt_open')}-{IN('cash_open')})-5000-548",CUR,GREEN)
D_EQ  =one('EQUITY VALUE',f'=C{D_EV}+C{D_ND}',CUR,BLACK,None,True)
D_PS  =one('VALUE PER SHARE (UFCF DCF)',f'=C{D_EQ}/Debt_Shares!G{P3["S_CL"]}',CUR2,BLACK,None,True,YFILL)
r+=1
sec(ws,r,'FCFE CROSS-CHECK (given the leverage)'); r+=1
for i,y in enumerate(range(2027,2032)):
    c=ws.cell(row=r,column=3+i,value=f'FY{y}E'); c.font=HDR; c.alignment=Alignment(horizontal='center')
r+=1
line(r,'Operating cash flow',[f'=Cash_Flow!{c}{P5["F_OCF"]}' for c in CO],CUR,GREEN); E_OCF=r; r+=1
line(r,'- Capex + short-term capex financing',[f'=Cash_Flow!{c}{P5["F_CX"]}+Cash_Flow!{c}{P5["F_STF2"]}' for c in CO],CUR,GREEN); E_CX=r; r+=1
line(r,'+ Net debt issued / (repaid)',[f'=Cash_Flow!{c}{P5["F_NEW"]}+Cash_Flow!{c}{P5["F_MAT"]}' for c in CO],CUR,GREEN); E_D=r; r+=1
line(r,'FREE CASH FLOW TO EQUITY',[f'={c}{E_OCF}+{c}{E_CX}+{c}{E_D}' for c in CO],CUR,BLACK,None,True); E_F=r; r+=1
line(r,'Discount factor at cost of equity',[f'=1/(1+$C${W_KE})^{c}{D_T}' for c in CO],'0.000'); E_DF=r; r+=1
line(r,'PV of FCFE',[f'={c}{E_F}*{c}{E_DF}' for c in CO]); E_PV=r; r+=1
E_TV=one('Terminal value of FCFE',f'=G{E_F}*(1+C{D_G})/($C${W_KE}-C{D_G})')
E_EQ=one('EQUITY VALUE (FCFE)',f'=SUM($C${E_PV}:$G${E_PV})+C{E_TV}/(1+$C${W_KE})^5',CUR,BLACK,None,True)
E_PS=one('VALUE PER SHARE (FCFE)',f'=C{E_EQ}/Debt_Shares!G{P3["S_CL"]}',CUR2,BLACK,None,True,YFILL)

# ==================================================== SENSITIVITY
ws=sh('Sensitivity',46)
T(ws,'SENSITIVITY AND DRIVER RANKING','Tables A and B are LIVE. Table C requires a full model re-solve per cell and is written as values from valuation.py.')
r=4; sec(ws,r,'A. LIVE — UFCF DCF value per share: WACC x terminal growth'); r+=1
ws.cell(row=r,column=2,value='exponents ->').font=NOTE
for i,e in enumerate([0.5,1.5,2.5,3.5,4.5]):
    c=ws.cell(row=r,column=3+i,value=e); c.font=NOTE; c.number_format='0.0'
EXP=r; r+=1
gs=[0.01,0.02,0.03,0.04,0.05]
ws.cell(row=r,column=2,value='WACC \\ g').font=HDR
for i,g in enumerate(gs):
    c=ws.cell(row=r,column=3+i,value=g); c.font=BLUE; c.number_format=PCT
GH=r; r+=1
UF=f"Valuation_DCF!$C${D_UF}:$G${D_UF}"; UF5=f"Valuation_DCF!$G${D_UF}"
NDp=f"(-({IN('debt_open')}-{IN('cash_open')})-5000-548)"
SHp=f"Debt_Shares!$G${P3['S_CL']}"
for w in (0.085,0.095,0.103,0.115,0.125):
    c=ws.cell(row=r,column=2,value=w); c.font=BLUE; c.number_format=PCT2
    for i,g in enumerate(gs):
        f=(f"=(SUMPRODUCT({UF},1/(1+$B{r})^$C${EXP}:$G${EXP})"
           f"+{UF5}*(1+{CL(3+i)}${GH})/($B{r}-{CL(3+i)}${GH})/(1+$B{r})^5"
           f"+{NDp})/{SHp}")
        cc=ws.cell(row=r,column=3+i,value=f); cc.font=BLACK; cc.number_format=CUR2
    r+=1
r+=1
sec(ws,r,'B. LIVE — contracted (RPO NPV + legacy) value per share: WACC x backlog EBITDA margin shift'); r+=1
ms=[-0.08,-0.04,0.0,0.04,0.08]
ws.cell(row=r,column=2,value='WACC \\ margin').font=HDR
for i,m in enumerate(ms):
    c=ws.cell(row=r,column=3+i,value=m); c.font=BLUE; c.number_format='+0.0%;-0.0%;0.0%'
MH=r; r+=1
BREV=f"Valuation_RPO_NPV!$C${P6['B_REV']}:$L${P6['B_REV']}"
BFCF=f"Valuation_RPO_NPV!$C${P6['B_FCF']}:$L${P6['B_FCF']}"
BDFR=f"Valuation_RPO_NPV!$C${P6['B_DF']}:$L${P6['B_DF']}"
LFCF=f"Valuation_RPO_NPV!$C${P6['V_LREV']}*Valuation_RPO_NPV!$C${P6['V_LM']}*(1-Valuation_RPO_NPV!$C${P6['V_LTX']})-Valuation_RPO_NPV!$C${P6['V_LREV']}*Valuation_RPO_NPV!$C${P6['V_LCX']}"
LG=f"Valuation_RPO_NPV!$C${P6['V_LG']}"
ws.cell(row=r+6,column=1,value='exponents (yrs 1-10) ->').font=NOTE
for i in range(10):
    c=ws.cell(row=r+6,column=3+i,value=i+0.5); c.font=NOTE; c.number_format='0.0'
EXP10=r+6
for w in (0.085,0.095,0.103,0.115,0.125):
    c=ws.cell(row=r,column=2,value=w); c.font=BLUE; c.number_format=PCT2
    for i,m in enumerate(ms):
        f=(f"=(SUMPRODUCT({BFCF}+{BREV}*{CL(3+i)}${MH},1/(1+$B{r})^$C${EXP10}:$L${EXP10})"
           f"+({LFCF})/($B{r}-{LG})+{NDp})/2914")
        cc=ws.cell(row=r,column=3+i,value=f); cc.font=BLACK; cc.number_format=CUR2
    r+=1
r+=2
sec(ws,r,'C. VALUES — RPO haircut x WACC (each cell requires a full model re-solve; produced by valuation.py)'); r+=1
hs=[0.0,0.05,0.10,0.20,0.30]
ws.cell(row=r,column=2,value='WACC \\ haircut').font=HDR
for i,h in enumerate(hs):
    c=ws.cell(row=r,column=3+i,value=h); c.font=HDR; c.number_format=PCT
r+=1
for w in (0.095,0.103,0.115):
    c=ws.cell(row=r,column=2,value=w); c.font=HDR; c.number_format=PCT2
    for i,h in enumerate(hs):
        S2=dict(M.BASE); S2['rpo_haircut']=h; r2=M.run(S2)
        val=V.px_from('Base',r2,w=w,haircut=h)
        cc=ws.cell(row=r,column=3+i,value=val); cc.font=BLUE; cc.number_format=CUR2
    r+=1
r+=2
sec(ws,r,'DRIVER RANKING — swing in base-case contracted value per share'); r+=1
for i,h in enumerate(['Driver','','Low','High','Swing $','Swing %','Range tested']):
    c=ws.cell(row=r,column=1+i,value=h); c.font=WHDR; c.fill=HFILL
r+=1
resB=M.R['Base']; base_px=V.px_from('Base',resB)
def hp(h):
    S2=dict(M.BASE); S2['rpo_haircut']=h; return V.px_from('Base',M.run(S2),haircut=h)
def lg(g,m):
    L=dict(V.LEGACY['Base']); L['g']=g; L['ebitda_m']=m
    nopat=L['rev']*m*(1-L['tax']); f=nopat-L['rev']*L['capex_pct']
    lv=f/(V.WACC['Base']-g); b=V.backlog_npv('Base',resB)
    return (b['total']+lv-V.NET_DEBT_0-V.PREF_0-V.NCI_0)/2914
tests=[('WACC',V.px_from('Base',resB,w=0.125),V.px_from('Base',resB,w=0.085),'12.5% -> 8.5%'),
       ('Legacy business terminal growth',lg(-0.01,0.44),lg(0.03,0.44),'-1% -> +3%'),
       ('Backlog EBITDA margin',V.px_from('Base',resB,mshift=-0.08),V.px_from('Base',resB,mshift=0.08),'-8pp -> +8pp'),
       ('Legacy business EBITDA margin',lg(0.015,0.38),lg(0.015,0.50),'38% -> 50%'),
       ('Effective asset turn (capital intensity)',V.px_from('Base',resB,turn=0.28),V.px_from('Base',resB,turn=0.44),'0.28 -> 0.44'),
       ('RPO haircut / counterparty risk',hp(0.30),hp(0.0),'30% -> 0%')]
tests.sort(key=lambda t: abs(t[2]-t[1]),reverse=True)
for lab,lo,hi,rng in tests:
    ws.cell(row=r,column=1,value=lab).font=BLACK
    for j,(v,f) in enumerate([(lo,CUR2),(hi,CUR2),(abs(hi-lo),CUR2),(abs(hi-lo)/base_px,PCT)]):
        cc=ws.cell(row=r,column=3+j,value=v); cc.font=BLUE; cc.number_format=f
    ws.cell(row=r,column=7,value=rng).font=NOTE; r+=1
ws.cell(row=r+1,column=1,value=f'Base contracted value per share ${base_px:.2f}  |  market $151.94').font=HDR
ws.cell(row=r+2,column=1,value='The single largest driver of the answer is the discount rate, not anything about Oracle. '
        'That is the most important thing this table says.').font=NOTE

# ==================================================== ROIC BREAKEVEN
ws=sh('ROIC_Breakeven',52)
T(ws,'ROIC BREAKEVEN — the central question, answered as a breakeven rather than a point estimate',
  'Oracle does not disclose OCI revenue per dollar of plant, OCI utilisation, or OCI cost of revenue. A point estimate of incremental ROIC is therefore manufacturable but not defensible. The breakeven is.')
r=4
def one2(lab,f,fmt=PCT2,font=BLUE,note=None,fill=None):
    global r
    ws.cell(row=r,column=1,value=lab).font=BLACK
    c=ws.cell(row=r,column=3,value=f); c.font=font; c.number_format=fmt
    if fill: c.fill=fill
    if note:
        n=ws.cell(row=r,column=8,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
    r+=1; return r-1
ws.column_dimensions['H'].width=90
sec(ws,r,'INPUTS',9); r+=1
K_W =one2('WACC',f'={IN("wacc")}',PCT2,GREEN)
K_L =one2('Blended asset life (years)',7.0,'0.0',BLUE,'62% equipment at 6 years, 30% buildings at 25 years, 8% land.')
K_O =one2('Opex allocated to IaaS (% of IaaS revenue)',0.12,PCT,BLUE,'S&M + R&D + G&A allocated to the infrastructure business. Analyst estimate.',YFILL)
K_T =one2('Tax rate',0.20,PCT,BLUE)
K_IC=one2('Invested capital as % of gross PP&E',0.55,PCT,BLUE,'Average net book value over the asset life, plus working capital.')
r+=1
K_D =one2('DERIVED FY2026A IaaS gross margin',f'=Historicals!D{P2["HIST_IAAS_GM"]}',PCT,GREEN,
   'From the Historicals tab. Depends on the assumed support / licence / SaaS margins shown there.',YFILL)
r+=2
sec(ws,r,'REQUIRED IaaS GROSS MARGIN (depreciation INSIDE cost of revenue, as Oracle reports it) TO EARN EXACTLY WACC',9); r+=1
ws.cell(row=r,column=1,value='utilisation \\ asset turn at full utilisation').font=HDR
turns=[0.40,0.45,0.50,0.55,0.60]
for i,t in enumerate(turns):
    c=ws.cell(row=r,column=3+i,value=t); c.font=BLUE; c.number_format=RAT
TH=r; r+=1
for u in (0.65,0.75,0.85,0.95):
    c=ws.cell(row=r,column=2,value=u); c.font=BLUE; c.number_format=PCT
    for i in range(5):
        f=f'=$C${K_W}*$C${K_IC}/((1-$C${K_T})*{CL(3+i)}${TH}*$B{r})+$C${K_O}'
        cc=ws.cell(row=r,column=3+i,value=f); cc.font=BLACK; cc.number_format=PCT
    r+=1
r+=1
ws.cell(row=r,column=1,value='Reading this table').font=SUB; r+=1
for t in ['The derived FY2026 OCI gross margin is ~30%. The required margin ranges from ~24% to ~39% across the plausible grid.',
          'Oracle is therefore earning approximately its cost of capital on the infrastructure business — the sign of the answer',
          'depends on utilisation and asset turn, neither of which is disclosed by Oracle or derivable from public filings.',
          'What would settle it: OCI revenue per dollar of in-service plant; OCI utilisation; OCI cost of revenue; the contracted',
          'price per GPU-hour in the large AI agreements. None of the four is in the 10-K. The Investor Day of 28 October 2026 is',
          'the first realistic opportunity to obtain any of them.']:
    ws.cell(row=r,column=1,value=t).font=BLACK; r+=1
wb.save('ORCL_model.xlsx')
json.dump(dict(D_PS=D_PS,E_PS=E_PS,D_TVS=D_TVS,D_UF=D_UF,W_W=W_W,D_EV=D_EV),open('xlsx_rows7.json','w'))
print('part7 saved')
