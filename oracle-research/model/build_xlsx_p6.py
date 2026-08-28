import openpyxl, json
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import column_index_from_string as CIX, get_column_letter as CL
import model as M, valuation as V
wb=openpyxl.load_workbook('ORCL_model.xlsx')
IR=json.load(open('xlsx_rows.json'))['ROW']
P2=json.load(open('xlsx_rows2.json')); P3=json.load(open('xlsx_rows3.json'))
P4=json.load(open('xlsx_rows4.json')); P5=json.load(open('xlsx_rows5.json'))
BLUE=Font(name='Arial',size=10,color='0000FF'); BLACK=Font(name='Arial',size=10)
GREEN=Font(name='Arial',size=10,color='008000'); HDR=Font(name='Arial',size=10,bold=True)
TITLE=Font(name='Arial',size=13,bold=True); SUB=Font(name='Arial',size=10,bold=True,color='444444')
NOTE=Font(name='Arial',size=8,italic=True,color='666666'); WHDR=Font(name='Arial',size=10,bold=True,color='FFFFFF')
YFILL=PatternFill('solid',fgColor='FFFF00'); GFILL=PatternFill('solid',fgColor='E8E8E8'); HFILL=PatternFill('solid',fgColor='1F3864')
CUR='$#,##0;($#,##0);-'; CUR2='$#,##0.00;($#,##0.00);-'; PCT='0.0%;(0.0%);-'; PCT2='0.00%;(0.00%);-'
NUM='#,##0;(#,##0);-'; MULT='0.0x'; RAT='0.00'
CO=['C','D','E','F','G']; C10=[CL(3+i) for i in range(10)]
def sh(n,w1=52):
    ws=wb.create_sheet(n); ws.sheet_view.showGridLines=False
    ws.column_dimensions['A'].width=w1
    for i in range(2,14): ws.column_dimensions[CL(i)].width=12
    ws.column_dimensions['N'].width=76
    return ws
def T(ws,t,s=None):
    ws['A1']=t; ws['A1'].font=TITLE
    if s: ws['A2']=s; ws['A2'].font=NOTE
def sec(ws,r,l,n=13):
    ws.cell(row=r,column=1,value=l).font=SUB
    for cc in range(1,n): ws.cell(row=r,column=cc).fill=GFILL
def row(ws,r,label,vals,cols,fmt=CUR,font=BLACK,note=None,bold=False,fill=None):
    c=ws.cell(row=r,column=1,value=label); c.font=HDR if bold else BLACK
    for i,col in enumerate(cols):
        cc=ws.cell(row=r,column=CIX(col),value=(vals[i] if isinstance(vals,(list,tuple)) else vals))
        cc.font=font; cc.number_format=fmt
        if fill: cc.fill=fill
    if note:
        n=ws.cell(row=r,column=14,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
def IN(k,c=None): return f"Inputs!$B${IR[k]}" if c is None else f"Inputs!{c}${IR[k]}"

# ============================================ VALUATION: RPO CONTRACT NPV (PRIMARY)
ws=sh('Valuation_RPO_NPV')
T(ws,'PRIMARY VALUATION — contract-level NPV of the $638bn backlog',
  'No renewal assumed. This isolates what the CONTRACTED book is worth, so the residual against the share price is the part that requires business not yet signed.')
for i,y in enumerate(range(2027,2037)):
    c=ws.cell(row=4,column=3+i,value=f'FY{y}E'); c.font=WHDR; c.fill=HFILL; c.alignment=Alignment(horizontal='center')
ws.cell(row=4,column=1,value='$ millions').font=WHDR; ws.cell(row=4,column=1).fill=HFILL
ws.cell(row=4,column=2,value='').fill=HFILL
r=6
A=V.BACKLOG_ASSUMP['Base']
sec(ws,r,'ASSUMPTIONS — these do NOT switch with the Inputs scenario selector; set them from the reference table below'); r+=1
row(ws,r,'Backlog EBITDA margin',A['ebitda_margin'],C10,PCT,BLUE,
    'KEY LEVER. Oracle does not disclose OCI-level cost structure, so this is an analyst construct.',fill=YFILL); B_M=r; r+=1
row(ws,r,'Effective asset turn',[A['eff_turn']],['C'],RAT,BLUE,'KEY LEVER.',fill=YFILL); B_T=r; r+=1
row(ws,r,'Capacity funded by customers',[A['cust_funded']],['C'],PCT,BLUE); B_CF=r; r+=1
row(ws,r,'Maintenance capex, % of depreciation',[A['maint_rate']],['C'],PCT,BLUE); B_MR=r; r+=1
row(ws,r,'Cash tax rate on backlog EBIT',[A['tax']],['C'],PCT,BLUE); B_TX=r; r+=1
row(ws,r,'Residual recovery on remaining NBV',[A['recovery']],['C'],PCT,BLUE); B_RC=r; r+=1
row(ws,r,'Shape of the "thereafter" 20%',A['tail_shape'],C10[5:],PCT,BLUE); B_TS=r; r+=1
row(ws,r,'WACC',[f'={IN("wacc")}'],['C'],PCT2,GREEN); B_W=r; r+=1
row(ws,r,'Equipment / building / land mix, lives',
    [f'={IN("mix_eq")}',f'={IN("mix_bl")}',f'={IN("life_eq")}',f'={IN("life_bl")}'],['C','D','E','F'],RAT,GREEN); B_MX=r; r+=2
sec(ws,r,'BACKLOG CASH FLOWS'); r+=1
rev=[f'=RPO_Schedule!{c}{P2["R_BL"]}' for c in CO]+[f'=$C${B_TS+0}*0' for _ in range(5)]
row(ws,r,'Backlog revenue',rev,C10)
for i in range(5):
    ws.cell(row=r,column=8+i).value=f'=RPO_Schedule!$B${P2["R_TL"]}*(1-RPO_Schedule!$B${P2["R_HC"]})*{C10[5+i]}${B_TS}'
B_REV=r; r+=1
row(ws,r,'Contracted (pre-haircut) revenue',[f'={c}{B_REV}/(1-RPO_Schedule!$B${P2["R_HC"]})' for c in C10],C10,CUR,BLACK,
    'Capacity is built to the CONTRACTED schedule. A counterparty failure happens AFTER the capex is sunk — haircutting capex '
    'alongside revenue would assume Oracle sees the default coming, and would make counterparty risk look value-accretive.')
B_CREV=r; r+=1
row(ws,r,'Prior-year contracted revenue',[f'=$C${B_CREV}*0.72']+[f'=MAX({C10[i-1]}{B_CREV},{C10[i-1]}{r})' for i in range(1,10)],C10,CUR,BLACK,
    'FY26 backlog-served revenue, estimated at 72% of the FY27 figure.'); B_PREV=r; r+=1
row(ws,r,'Growth capex (Oracle-funded)',
    [f'=MAX(0,{c}{B_CREV}-{c}{B_PREV})/$C${B_T}*(1-$C${B_CF})' for c in C10],C10); B_GX=r; r+=1
row(ws,r,'Depreciation on backlog assets',
    ['='+'+'.join(f'(${C10[j]}${B_GX}+${C10[j]}${"XX"})' for j in range(i+1)) for i in range(10)],C10)
for i in range(10):
    terms='+'.join(f'({C10[j]}${B_GX}+{C10[j]}${r+2})*($C${B_MX}/$E${B_MX}+$D${B_MX}/$F${B_MX})*'+('0.5' if j==i else '1') for j in range(i+1))
    ws.cell(row=r,column=3+i).value='='+terms
B_DEP=r; r+=1
row(ws,r,'  memo: annual depreciation rate on a $1 vintage',[f'=$C${B_MX}/$E${B_MX}+$D${B_MX}/$F${B_MX}'],['C'],'0.000'); r+=1
row(ws,r,'Maintenance capex',[f'={c}{B_DEP}*$C${B_MR}*{c}{B_REV}/MAX($C${B_REV}:${C10[9]}${B_REV})' for c in C10],C10); B_MXC=r; r+=1
row(ws,r,'TOTAL CAPEX',[f'={c}{B_GX}+{c}{B_MXC}' for c in C10],C10,CUR,BLACK,None,bold=True); B_CX=r; r+=1
row(ws,r,'EBITDA',[f'={c}{B_REV}*{c}{B_M}' for c in C10],C10); B_EB=r; r+=1
row(ws,r,'EBIT',[f'={c}{B_EB}-{c}{B_DEP}' for c in C10],C10); B_EBIT=r; r+=1
row(ws,r,'Cash tax',[f'=-MAX(0,{c}{B_EBIT})*$C${B_TX}' for c in C10],C10); B_TAXR=r; r+=1
row(ws,r,'FREE CASH FLOW',[f'={c}{B_EB}+{c}{B_TAXR}-{c}{B_CX}' for c in C10],C10,CUR,BLACK,None,bold=True); B_FCF=r; r+=1
row(ws,r,'Discount factor',[f'=1/(1+$C${B_W})^{i+0.5}' for i in range(10)],C10,'0.000'); B_DF=r; r+=1
row(ws,r,'PV of free cash flow',[f'={c}{B_FCF}*{c}{B_DF}' for c in C10],C10); B_PV=r; r+=2
sec(ws,r,'BRIDGE TO EQUITY VALUE'); r+=1
def one(lab,f,fmt=CUR,font=BLACK,note=None,bold=False,fill=None):
    global r
    c=ws.cell(row=r,column=1,value=lab); c.font=HDR if bold else BLACK
    cc=ws.cell(row=r,column=3,value=f); cc.font=font; cc.number_format=fmt
    if fill: cc.fill=fill
    if note:
        n=ws.cell(row=r,column=14,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
    r+=1; return r-1
V_PVOPS=one('PV of backlog cash flows',f'=SUM($C${B_PV}:${C10[9]}${B_PV})')
V_GROSS=one('Gross backlog capex',f'=SUM($C${B_CX}:${C10[9]}${B_CX})')
V_ACC  =one('Accumulated depreciation on it',f'=SUM($C${B_DEP}:${C10[9]}${B_DEP})')
V_NBV  =one('Remaining net book value at FY2036',f'=MAX(0,C{V_GROSS}-C{V_ACC})','',BLACK,
            'Land and the long-lived shell survive the 10-year horizon; the servers do not.')
ws.cell(row=V_NBV,column=3).number_format=CUR
V_RES  =one('PV of residual asset value',f'=C{V_NBV}*$C${B_RC}/(1+$C${B_W})^10')
V_BLEV =one('BACKLOG ENTERPRISE VALUE',f'=C{V_PVOPS}+C{V_RES}',CUR,BLACK,None,True)
r+=1
sec(ws,r,'LEGACY (NON-BACKLOG) BUSINESS — software support, licence, SaaS, services, hardware'); r+=1
L=V.LEGACY['Base']
V_LREV=one('Steady-state revenue',L['rev'],CUR,BLUE,'Software support alone has been a flat $19.5–19.8bn annuity for three years (10-K R89).')
V_LM  =one('EBITDA margin',L['ebitda_m'],PCT,BLUE,None,False,YFILL)
V_LG  =one('Terminal growth',L['g'],PCT,BLUE,None,False,YFILL)
V_LCX =one('Capex, % of revenue',L['capex_pct'],PCT,BLUE)
V_LTX =one('Tax rate',L['tax'],PCT,BLUE)
V_LFCF=one('Free cash flow',f'=C{V_LREV}*C{V_LM}*(1-C{V_LTX})-C{V_LREV}*C{V_LCX}')
V_LV  =one('LEGACY BUSINESS VALUE',f'=C{V_LFCF}/($C${B_W}-C{V_LG})',CUR,BLACK,None,True)
V_LMU =one('  implied EV/EBITDA',f'=C{V_LV}/(C{V_LREV}*C{V_LM})',MULT,BLACK,
           'Cross-check: SAP trades at 18.7x, IBM 14.3x, MSFT 16.3x on the same calendarised basis. A perpetuity discounted at the '
           'group WACC values this annuity FAR below where the market prices comparable software annuities. Both readings are shown '
           'in the memo; the truth is between them.',False,YFILL)
r+=1
V_EV  =one('CONTRACTED ENTERPRISE VALUE',f'=C{V_BLEV}+C{V_LV}',CUR,BLACK,None,True)
V_ND  =one('Less: net debt at 5/31/2026',f'=-({IN("debt_open")}-{IN("cash_open")})',CUR,GREEN)
V_PF  =one('Less: mandatory convertible preferred',-5000,CUR,BLUE)
V_NCI =one('Less: non-controlling interests',-548,CUR,BLUE)
V_EQ  =one('CONTRACTED EQUITY VALUE',f'=C{V_EV}+C{V_ND}+C{V_PF}+C{V_NCI}',CUR,BLACK,None,True)
V_PS  =one('CONTRACTED VALUE PER SHARE',f'=C{V_EQ}/2914',CUR2,BLACK,None,True,YFILL)
V_MKT =one('Market price, 2026-08-27',151.94,CUR2,BLUE)
V_GAP =one('Share of the price NOT covered by contracted value',f'=1-C{V_PS}/C{V_MKT}',PCT,BLACK,
           'THE HEADLINE NUMBER. This is what the buyer at $151.94 is paying for business Oracle has not yet signed.',True,YFILL)
wb.save('ORCL_model.xlsx')
json.dump(dict(B_REV=B_REV,B_FCF=B_FCF,B_M=B_M,B_W=B_W,V_PS=V_PS,V_EQ=V_EQ,V_BLEV=V_BLEV,V_LV=V_LV,
               V_MKT=V_MKT,B_PV=B_PV,B_DF=B_DF,V_PVOPS=V_PVOPS,V_RES=V_RES,V_ND=V_ND,V_PF=V_PF,V_NCI=V_NCI,
               V_LREV=V_LREV,V_LM=V_LM,V_LG=V_LG,V_LCX=V_LCX,V_LTX=V_LTX),open('xlsx_rows6.json','w'))
print('part6 saved: contracted px row',V_PS)
