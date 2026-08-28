import openpyxl, json
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
import model as M

wb=openpyxl.load_workbook('ORCL_model.xlsx')
IR=json.load(open('xlsx_rows.json'))['ROW']
BLUE=Font(name='Arial',size=10,color='0000FF'); BLACK=Font(name='Arial',size=10)
GREEN=Font(name='Arial',size=10,color='008000'); HDR=Font(name='Arial',size=10,bold=True)
TITLE=Font(name='Arial',size=13,bold=True); SUB=Font(name='Arial',size=10,bold=True,color='444444')
NOTE=Font(name='Arial',size=8,italic=True,color='666666'); WHDR=Font(name='Arial',size=10,bold=True,color='FFFFFF')
YFILL=PatternFill('solid',fgColor='FFFF00'); GFILL=PatternFill('solid',fgColor='E8E8E8')
HFILL=PatternFill('solid',fgColor='1F3864'); BFILL=PatternFill('solid',fgColor='DCE6F1')
CUR='$#,##0;($#,##0);-'; CUR2='$#,##0.00;($#,##0.00);-'; PCT='0.0%;(0.0%);-'
PCT2='0.00%;(0.00%);-'; MULT='0.0x'; NUM='#,##0;(#,##0);-'; RAT='0.00'
FY=[2027,2028,2029,2030,2031]; CO=['C','D','E','F','G']       # forecast cols
def sh(n):
    ws=wb.create_sheet(n); ws.sheet_view.showGridLines=False
    ws.column_dimensions['A'].width=52
    for c in 'BCDEFGH': ws.column_dimensions[c].width=13
    ws.column_dimensions['J'].width=78
    return ws
def T(ws,t,s=None):
    ws['A1']=t; ws['A1'].font=TITLE
    if s: ws['A2']=s; ws['A2'].font=NOTE
def H(ws,r,labels,start=1):
    for i,l in enumerate(labels):
        c=ws.cell(row=r,column=start+i,value=l); c.font=WHDR; c.fill=HFILL
        c.alignment=Alignment(horizontal='center' if i else 'left')
def sec(ws,r,label):
    ws.cell(row=r,column=1,value=label).font=SUB
    for cc in range(1,9): ws.cell(row=r,column=cc).fill=GFILL
def line(ws,r,label,formulas,fmt=CUR,font=BLACK,note=None,cols=CO,bold=False):
    c=ws.cell(row=r,column=1,value=label); c.font=HDR if bold else BLACK
    for i,col in enumerate(cols):
        cc=ws.cell(row=r,column=openpyxl.utils.column_index_from_string(col),
                   value=(formulas[i] if isinstance(formulas,(list,tuple)) else formulas))
        cc.font=font; cc.number_format=fmt
    if note: n=ws.cell(row=r,column=10,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
def IN(key,col=None):
    r=IR[key]
    return f"Inputs!$B${r}" if col is None else f"Inputs!{col}${r}"

# =============================================================== HISTORICALS
ws=sh('Historicals'); T(ws,'HISTORICALS — FY2024 / FY2025 / FY2026 actuals',
  'Every line ties to the FY2026 Form 10-K (acc 0001193125-26-277521) or the Q4 FY26 press release (Ex-99.1 to the 8-K of 2026-06-10).')
H(ws,4,['$ millions','FY2024A','FY2025A','FY2026A','','','','','','Source'])
HIST=[('Cloud revenue','rev_cloud','10-K Consolidated Statements of Operations (R4)'),
 ('  Cloud infrastructure (IaaS)','rev_iaas','10-K Note 14, revenue by offering (R89)'),
 ('  Cloud applications (SaaS)','rev_saas','10-K Note 14 (R89)'),
 ('Software revenue','rev_software','10-K R4'),
 ('  Software licence','rev_license','10-K Note 14 (R89)'),
 ('  Software support','rev_support','10-K Note 14 (R89)'),
 ('Hardware revenue','rev_hardware','10-K R4'),
 ('Services revenue','rev_services','10-K R4'),
 ('TOTAL REVENUE','rev_total','10-K R4'),
 ('Cost of cloud & software (ex intangible amort.)','cor_cloudsw','10-K R4'),
 ('Cost of hardware','cor_hardware','10-K R4'),
 ('Cost of services','cor_services','10-K R4'),
 ('Sales & marketing','opex_sm','10-K R4'),
 ('Research & development','opex_rd','10-K R4'),
 ('General & administrative','opex_ga','10-K R4'),
 ('Amortisation of intangible assets','amort_intang','10-K R4'),
 ('Restructuring & other','restructuring','10-K R4 / Note 8 (R59)'),
 ('GAAP OPERATING INCOME','op_income','10-K R4'),
 ('Interest expense','interest_exp','10-K R4'),
 ('Non-operating income, net','nonop_net','10-K R4. FY26 includes +$2,811m of investment gains (Ampere sale, Bloom warrants).'),
 ('Income before income taxes','pretax','10-K R4'),
 ('Provision for income taxes','tax','10-K R4. Effective rate 12.6% (R80).'),
 ('NET INCOME','net_income','10-K R4'),
 ('Preferred stock dividends','pref_div','10-K R4. 6.50% Series D, issued Feb 2026.'),
 ('Net income available to common','ni_common','10-K R4'),
 ('Diluted EPS ($)','eps_diluted','10-K R4 / EPS note (R91)'),
 ('Diluted weighted-average shares (m)','waso_diluted','10-K EPS note (R91). USE THIS, not the cover-page count.'),
 ('Operating cash flow','ocf','10-K Statements of Cash Flows (R8)'),
 ('Depreciation','depreciation','10-K R8 / PP&E note (R51)'),
 ('Stock-based compensation','sbc','10-K R8'),
 ('Capital expenditures','capex','10-K R8'),
 ('Dividends paid','dividends_paid','10-K R8'),
 ('Share repurchases','buybacks','10-K R8. $95m in FY26 vs $1,202m FY24 — buybacks have effectively stopped.'),
]
r=5
for lab,key,src in HIST:
    v=M.H[key]
    c=ws.cell(row=r,column=1,value=lab); c.font=HDR if lab.isupper() else BLACK
    for j in range(3):
        cc=ws.cell(row=r,column=2+j,value=v[j]); cc.font=BLUE
        cc.number_format=CUR2 if 'EPS ($)' in lab else (NUM if 'shares' in lab else CUR)
    n=ws.cell(row=r,column=10,value=src); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
    r+=1
GP=r; line(ws,r,'GROSS PROFIT (derived)',[f'=B{5+8}-B{5+9}-B{5+10}-B{5+11}'],CUR,BLACK,
     'Revenue less the three cost-of-revenue lines. Excludes intangible amortisation, per Oracle presentation.',cols=['B'],bold=True)
for j,col in enumerate(['B','C','D']):
    ws[f'{col}{r}']=f'={col}{13}-{col}{14}-{col}{15}-{col}{16}'
    ws[f'{col}{r}'].font=BLACK; ws[f'{col}{r}'].number_format=CUR
r+=1
line(ws,r,'Gross margin %',[f'=B{GP}/B13',f'=C{GP}/C13',f'=D{GP}/D13'],PCT,BLACK,
     'FY22 79.08% -> FY23 72.85% -> FY24 71.41% -> FY25 70.51% -> FY26 65.82%. Five straight years of compression.',cols=['B','C','D'],bold=True)
r+=2
sec(ws,r,'DERIVED — IaaS gross margin (ANALYST ESTIMATE: Oracle does not disclose cost of revenue by offering)'); r+=1
for lab,val,src in [('Assumed software support gross margin',0.93,'E'),('Assumed software licence gross margin',0.98,'E'),('Assumed SaaS gross margin',0.78,'E')]:
    ws.cell(row=r,column=1,value=lab).font=BLACK
    c=ws.cell(row=r,column=4,value=val); c.font=BLUE; c.number_format=PCT; c.fill=YFILL
    ws.cell(row=r,column=10,value='Analyst estimate. Changes the derived IaaS margin one-for-one.').font=NOTE; r+=1
A1,A2,A3=r-3,r-2,r-1
ws.cell(row=r,column=1,value='Implied software cost of revenue').font=BLACK
for j,col in enumerate(['B','C','D']):
    ws[f'{col}{r}']=f'={col}{5+5}*(1-$D${A1})+{col}{5+4}*(1-$D${A2})'; ws[f'{col}{r}'].font=BLACK; ws[f'{col}{r}'].number_format=CUR
SWC=r; r+=1
ws.cell(row=r,column=1,value='Implied cloud cost of revenue').font=BLACK
for col in ['B','C','D']:
    ws[f'{col}{r}']=f'={col}{5+9}-{col}{SWC}'; ws[f'{col}{r}'].font=BLACK; ws[f'{col}{r}'].number_format=CUR
CLC=r; r+=1
ws.cell(row=r,column=1,value='Implied IaaS cost of revenue').font=BLACK
for col in ['B','C','D']:
    ws[f'{col}{r}']=f'={col}{CLC}-{col}{5+2}*(1-$D${A3})'; ws[f'{col}{r}'].font=BLACK; ws[f'{col}{r}'].number_format=CUR
IAC=r; r+=1
ws.cell(row=r,column=1,value='DERIVED IaaS GROSS MARGIN').font=HDR
for col in ['B','C','D']:
    ws[f'{col}{r}']=f'=1-{col}{IAC}/{col}{5+1}'; ws[f'{col}{r}'].font=BLACK; ws[f'{col}{r}'].number_format=PCT; ws[f'{col}{r}'].fill=YFILL
ws.cell(row=r,column=10,value='~30% in FY26A. This single number, and the asset turn, decide whether the buildout creates value.').font=NOTE
HIST_IAAS_GM=r

# =============================================================== RPO_SCHEDULE
ws=sh('RPO_Schedule'); T(ws,'RPO CONVERSION SCHEDULE — the disclosed 12 / 34 / 34 / 20 waterfall',
 'Oracle discloses the entire five-year conversion profile of the $638bn backlog in Note 1 of the FY26 10-K. '
 'Revenue through FY2031 is therefore largely a DISCLOSED SCHEDULE, not a forecast.')
H(ws,4,['$ millions','','FY2027E','FY2028E','FY2029E','FY2030E','FY2031E','','','Note'])
r=6; sec(ws,r,'DISCLOSED BACKLOG AND CONVERSION PROFILE (10-K Note 1, verbatim)'); r+=1
def one(label,formula,fmt=CUR,note=None,fill=None,font=BLACK):
    global r
    ws.cell(row=r,column=1,value=label).font=BLACK
    c=ws.cell(row=r,column=2,value=formula); c.font=font; c.number_format=fmt
    if fill: c.fill=fill
    if note: n=ws.cell(row=r,column=10,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
    r+=1; return r-1
R_RPO =one('Remaining performance obligations at 5/31/2026',f'={IN("rpo26")}',CUR,'DISCLOSED. Up 363% from $137.8bn.',None,GREEN)
R_Y1  =one('  expected in the next 12 months (12%)',f'=$B${IR["rpo26"]-0}*0',CUR); ws[f'B{R_Y1}']=f'={IN("rpo26")}*{IN("sch_y1")}'; ws[f'B{R_Y1}'].font=BLACK
R_Y23 =one('  expected in months 13–36 (34%)','',CUR); ws[f'B{R_Y23}']=f'={IN("rpo26")}*{IN("sch_y23")}'; ws[f'B{R_Y23}'].font=BLACK; ws[f'B{R_Y23}'].number_format=CUR
R_Y45 =one('  expected in months 37–60 (34%)','',CUR); ws[f'B{R_Y45}']=f'={IN("rpo26")}*{IN("sch_y45")}'; ws[f'B{R_Y45}'].font=BLACK; ws[f'B{R_Y45}'].number_format=CUR
R_TL  =one('  thereafter (20%)','',CUR); ws[f'B{R_TL}']=f'={IN("rpo26")}*{IN("sch_tail")}'; ws[f'B{R_TL}'].font=BLACK; ws[f'B{R_TL}'].number_format=CUR
r+=1; sec(ws,r,'DECOMPOSITION — legacy backlog vs the FY26 AI step-change (ANALYST CONSTRUCT)'); r+=1
R_LEG =one('"Legacy" (pre-AI) backlog',f'={IN("rpo_legacy")}',CUR,'≈ the 5/31/2025 RPO of $137.8bn.',None,GREEN)
R_AI  =one('AI backlog (the FY26 step-change)',f'=B{R_RPO}-B{R_LEG}',CUR,'RPO went $137.8bn -> $455.3bn in Q1 FY26 alone. Two-thirds of the backlog was signed in ONE quarter.')
R_HC  =one('Counterparty haircut applied to AI backlog',f'={IN("rpo_haircut")}',PCT,'KEY LEVER.',YFILL,GREEN)
r+=1
ws.cell(row=r,column=1,value='Legacy backlog conversion %').font=BLACK
for i,c in enumerate(CO):
    cc=ws.cell(row=r,column=openpyxl.utils.column_index_from_string(c),value=f'={IN("legacy_conv",c)}'); cc.font=GREEN; cc.number_format=PCT
R_LC=r; r+=1
line(ws,r,'Legacy backlog revenue',[f'=$B${R_LEG}*{c}{R_LC}' for c in CO]); R_LR=r; r+=1
line(ws,r,'AI conversion in the m0–12 bucket',[f'=$B${R_Y1}-C{R_LR}','','','',''])
ws[f'C{r}']=f'=$B${R_Y1}-C{R_LR}'; R_AI1=r; r+=1
line(ws,r,'AI conversion in the m13–36 bucket',[f'=$B${R_Y23}-D{R_LR}-E{R_LR}','','','',''])
ws[f'C{r}']=f'=$B${R_Y23}-D{R_LR}-E{R_LR}'; R_AI23=r; r+=1
line(ws,r,'AI conversion in the m37–60 bucket',[f'=$B${R_Y45}-F{R_LR}-G{R_LR}','','','',''])
ws[f'C{r}']=f'=$B${R_Y45}-F{R_LR}-G{R_LR}'; R_AI45=r; r+=1
line(ws,r,'AI backlog revenue (after haircut)',
     [f'=C{R_AI1}*(1-$B${R_HC})', f'=$C${R_AI23}*{IN("ai_y2_share")}*(1-$B${R_HC})',
      f'=$C${R_AI23}*(1-{IN("ai_y2_share")})*(1-$B${R_HC})', f'=$C${R_AI45}*{IN("ai_y4_share")}*(1-$B${R_HC})',
      f'=$C${R_AI45}*(1-{IN("ai_y4_share")})*(1-$B${R_HC})'])
R_AIR=r; r+=1
line(ws,r,'REVENUE FROM THE 5/31/26 BACKLOG',[f'={c}{R_LR}+{c}{R_AIR}' for c in CO],CUR,BLACK,
     'Note the shape: a step up into FY28 and then a PLATEAU. The disclosed schedule allocates the same 34% to '
     'months 13–36 and 37–60. Every dollar of growth after FY2028 must come from contracts not yet signed.',bold=True)
R_BL=r; r+=2
sec(ws,r,'NEW BOOKINGS SIGNED AFTER 5/31/2026 (PURE ANALYST ESTIMATE — dominates FY30–31)'); r+=1
ws.cell(row=r,column=1,value='New bookings').font=BLACK
for c in CO:
    cc=ws.cell(row=r,column=openpyxl.utils.column_index_from_string(c),value=f'={IN("new_bookings",c)}'); cc.font=GREEN; cc.number_format=CUR; cc.fill=YFILL
R_NB=r; r+=1
ws.cell(row=r,column=1,value='Conversion profile, year 1..5').font=BLACK
for c in CO:
    cc=ws.cell(row=r,column=openpyxl.utils.column_index_from_string(c),value=f'={IN("new_conv",c)}'); cc.font=GREEN; cc.number_format=PCT
R_NC=r; r+=1
conv=[]
for i in range(5):
    terms=[f'${CO[j]}${R_NB}*${CO[i-j]}${R_NC}' for j in range(i+1)]
    conv.append('='+'+'.join(terms))
line(ws,r,'Revenue from new bookings',conv); R_NR=r; r+=1
line(ws,r,'Revenue not covered by RPO',
     [f'={IN("nonrpo_base")}*(1+{IN("nonrpo_g")})^{i+1}' for i in range(5)],CUR,BLACK,
     'Hardware, non-committed consumption, some services and new licence.')
R_NON=r; r+=1
line(ws,r,'TOTAL REVENUE',[f'={c}{R_BL}+{c}{R_NR}+{c}{R_NON}' for c in CO],CUR,BLACK,None,bold=True); R_TOT=r; r+=1
line(ws,r,'  y/y growth',[f'={CO[0]}{R_TOT}/Historicals!D13-1']+[f'={CO[i]}{R_TOT}/{CO[i-1]}{R_TOT}-1' for i in range(1,5)],PCT)
r+=2
sec(ws,r,'SEGMENT BUILD — IaaS is the residual'); r+=1
segs=[('Cloud applications (SaaS)','saas_g',18),('Software licence','lic_g',9),('Software support','sup_g',10),
      ('Services','svc_g',12),('Hardware','hw_g',11)]
SEGR={}
for lab,key,hrow_ in segs:
    line(ws,r,lab,[f'=Historicals!D{hrow_}*(1+{IN(key,"C")})']+
         [f'={CO[i-1]}{r}*(1+{IN(key,CO[i])})' for i in range(1,5)])
    SEGR[key]=r; r+=1
line(ws,r,'Cloud infrastructure (IaaS) — RESIDUAL',
     [f'={c}{R_TOT}-'+'-'.join(f'{c}{SEGR[k]}' for _,k,_ in segs) for c in CO],CUR,BLACK,
     'IaaS = total revenue less the five modelled lines. FY26A $18,101m.',bold=True)
R_IAAS=r; r+=1
line(ws,r,'  IaaS y/y growth',[f'=C{R_IAAS}/Historicals!D6-1']+[f'={CO[i]}{R_IAAS}/{CO[i-1]}{R_IAAS}-1' for i in range(1,5)],PCT)
r+=1
line(ws,r,'MEMO: revenue guidance FY2027',[90000,'','','',''],CUR,BLUE,
     'DISCLOSED: "we confirm our prior revenue guidance of $90 billion total revenue" — press release 6/10/2026.')
r+=1
line(ws,r,'MEMO: consensus FY2027 revenue',[89340,'','','',''],CUR,BLUE,'stockanalysis.com, 42 analysts, pulled 8/27–28/2026.')
wb.save('ORCL_model.xlsx')
json.dump({'R_BL':R_BL,'R_TOT':R_TOT,'R_IAAS':R_IAAS,'SEGR':SEGR,'R_NON':R_NON,'R_NR':R_NR,
           'R_RPO':R_RPO,'R_TL':R_TL,'R_HC':R_HC,'HIST_IAAS_GM':HIST_IAAS_GM,'GP':GP},open('xlsx_rows2.json','w'))
print('part2a saved. RPO rows:',R_BL,R_TOT,R_IAAS)
