import openpyxl, json
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import column_index_from_string as CIX
import model as M
wb=openpyxl.load_workbook('ORCL_model.xlsx')
IR=json.load(open('xlsx_rows.json'))['ROW']; P2=json.load(open('xlsx_rows2.json'))
BLUE=Font(name='Arial',size=10,color='0000FF'); BLACK=Font(name='Arial',size=10)
GREEN=Font(name='Arial',size=10,color='008000'); HDR=Font(name='Arial',size=10,bold=True)
TITLE=Font(name='Arial',size=13,bold=True); SUB=Font(name='Arial',size=10,bold=True,color='444444')
NOTE=Font(name='Arial',size=8,italic=True,color='666666'); WHDR=Font(name='Arial',size=10,bold=True,color='FFFFFF')
YFILL=PatternFill('solid',fgColor='FFFF00'); GFILL=PatternFill('solid',fgColor='E8E8E8'); HFILL=PatternFill('solid',fgColor='1F3864')
CUR='$#,##0;($#,##0);-'; CUR2='$#,##0.00;($#,##0.00);-'; PCT='0.0%;(0.0%);-'; PCT2='0.00%;(0.00%);-'
MULT='0.0x'; NUM='#,##0;(#,##0);-'; RAT='0.00'
CO=['C','D','E','F','G']; FY=[2027,2028,2029,2030,2031]
def sh(n):
    ws=wb.create_sheet(n); ws.sheet_view.showGridLines=False
    ws.column_dimensions['A'].width=52
    for c in 'BCDEFGH': ws.column_dimensions[c].width=13
    ws.column_dimensions['J'].width=78
    return ws
def T(ws,t,s=None):
    ws['A1']=t; ws['A1'].font=TITLE
    if s: ws['A2']=s; ws['A2'].font=NOTE; ws['A2'].alignment=Alignment(wrap_text=False)
def H(ws,r,lab):
    for i,l in enumerate(lab):
        c=ws.cell(row=r,column=1+i,value=l); c.font=WHDR; c.fill=HFILL
        c.alignment=Alignment(horizontal='center' if i else 'left')
def sec(ws,r,l):
    ws.cell(row=r,column=1,value=l).font=SUB
    for cc in range(1,9): ws.cell(row=r,column=cc).fill=GFILL
def line(ws,r,label,f,fmt=CUR,font=BLACK,note=None,bold=False,fill=None):
    c=ws.cell(row=r,column=1,value=label); c.font=HDR if bold else BLACK
    for i,col in enumerate(CO):
        cc=ws.cell(row=r,column=CIX(col),value=(f[i] if isinstance(f,(list,tuple)) else f))
        cc.font=font; cc.number_format=fmt
        if fill: cc.fill=fill
    if note:
        n=ws.cell(row=r,column=10,value=note); n.font=NOTE; n.alignment=Alignment(wrap_text=True,vertical='top')
def IN(k,c=None): return f"Inputs!$B${IR[k]}" if c is None else f"Inputs!{c}${IR[k]}"
HD=['$ millions','','FY2027E','FY2028E','FY2029E','FY2030E','FY2031E','','','Note']

# ==================================================== CAPEX / DEPRECIATION
ws=sh('Capex_Depreciation')
T(ws,'CAPEX -> CIP -> IN-SERVICE -> DEPRECIATION WATERFALL',
  'Capex is LINKED to the IaaS revenue it must serve, not set as a % of revenue. 32.6% of gross PP&E at 5/31/26 ($39,973m) was construction in progress and NOT YET DEPRECIATING.')
H(ws,4,HD); r=6
sec(ws,r,'CAPACITY REQUIREMENT'); r+=1
line(ws,r,'IaaS revenue',[f"=RPO_Schedule!{c}{P2['R_IAAS']}" for c in CO],CUR,GREEN); R_IA=r; r+=1
line(ws,r,'IaaS revenue, following year',[f'=D{R_IA}',f'=E{R_IA}',f'=F{R_IA}',f'=G{R_IA}',f'=G{R_IA}*(1+{IN("iaas_gterm")})'],CUR,BLACK,
     'FY32 is required to size FY31 capex.'); R_NXT=r; r+=1
line(ws,r,'Effective asset turn (turn x utilisation)',[f'={IN("turn_full")}*{IN("util",c)}' for c in CO],RAT,BLACK,
     'KEY LEVER. IaaS revenue generated per $1 of gross PP&E. Not disclosed by Oracle anywhere.',fill=YFILL); R_TN=r; r+=1
line(ws,r,'Gross capacity to add',[f'=MAX(0,{c}{R_NXT}-{c}{R_IA})/{c}{R_TN}' for c in CO]); R_GC=r; r+=1
line(ws,r,'  funded by customers (prepay + customer GPUs)',[f'={c}{R_GC}*{IN("cust_fund",c)}' for c in CO],CUR,BLACK,
     'Anchored to management: prepaid + customer-supplied hardware "now total $75 billion" (press release 6/10/26).'); R_CF=r; r+=1
line(ws,r,'ORACLE-FUNDED GROWTH CAPEX',[f'={c}{R_GC}-{c}{R_CF}' for c in CO],CUR,BLACK,None,bold=True); R_GX=r; r+=2
sec(ws,r,'PASS 1 — provisional depreciation, used only to size maintenance capex'); r+=1
line(ws,r,'Annual depreciation rate on a $1 vintage',
     [f'={IN("mix_eq")}/{IN("life_eq")}+{IN("mix_bl")}/{IN("life_bl")}' for c in CO],'0.000',BLACK,
     'Equipment 6-yr (10-K R50: servers and networking equipment) + buildings 25-yr. Land does not depreciate.')
R_RATE=r; r+=1
line(ws,r,'CIP released into service',[f'={IN("cip_open")}*{IN("cip_rel1")}',f'={IN("cip_open")}*{IN("cip_rel2")}',0,0,0],CUR,BLACK,
     'The $39,973m CIP balance at 5/31/26 begins depreciating. This alone is the single largest driver of the FY27 margin guide-down.')
R_CIP=r; r+=1
line(ws,r,'Provisional in-service additions',
     [f'=C{R_CIP}+{IN("cx_isv1")}*C{R_GX}']+[f'={c}{R_CIP}+{IN("cx_isv1")}*{c}{R_GX}+{IN("cx_isv2")}*{CO[i-1]}{R_GX}' for i,c in enumerate(CO) if i>0])
R_PA=r; r+=1
line(ws,r,'Provisional depreciation on new vintages',
     ['='+'+'.join(f'${CO[j]}${R_PA}*${CO[0]}${R_RATE}*'+('0.5' if j==i else '1') for j in range(i+1)) for i in range(5)])
R_PD=r; r+=1
line(ws,r,'Depreciation on the existing in-service base',
     [f'=(({IN("cip_open")}*0+122651-{IN("cip_open")})-22694)/{IN("base_life")}' for c in CO],CUR,BLACK,
     'Gross PP&E $122,651m less CIP $39,973m = $82,678m in service; less accumulated depreciation $22,694m = $59,984m NBV (10-K R49), over 5 years.')
R_BD=r; r+=1
line(ws,r,'Provisional total depreciation',[f'={c}{R_PD}+{c}{R_BD}' for c in CO]); R_PT=r; r+=1
line(ws,r,'Maintenance capex',[f'={c}{R_PT}*{IN("maint_pct",c)}' for c in CO]); R_MX=r; r+=1
line(ws,r,'Committed capex floor',[f'={IN("capex_min",c)}' for c in CO],CUR,GREEN,
     'GPU/server orders and data-centre leases placed 12–18 months ahead. This is what turns a demand shortfall into a funding problem.')
R_MIN=r; r+=1
line(ws,r,'TOTAL CAPEX',[f'=MAX({c}{R_GX}+{c}{R_MX},{c}{R_MIN})' for c in CO],CUR,BLACK,None,bold=True); R_CX=r; r+=1
line(ws,r,'  3-year rolling average',['',f'=AVERAGE($C${R_CX}:D{R_CX})',f'=AVERAGE($C${R_CX}:E{R_CX})',f'=AVERAGE(D{R_CX}:F{R_CX})',f'=AVERAGE(E{R_CX}:G{R_CX})'],CUR,BLACK,
     'The annual path is lumpy BY CONSTRUCTION because the disclosed RPO conversion schedule is lumpy. Smoothing it would hide the mechanism.')
r+=2
sec(ws,r,'PASS 2 — final depreciation vintage waterfall'); r+=1
line(ws,r,'In-service additions',
     [f'=C{R_CIP}+{IN("cx_isv1")}*C{R_CX}']+[f'={c}{R_CIP}+{IN("cx_isv1")}*{c}{R_CX}+{IN("cx_isv2")}*{CO[i-1]}{R_CX}' for i,c in enumerate(CO) if i>0])
R_ADD=r; r+=1
VST=r
for i,c in enumerate(CO):
    ws.cell(row=r,column=1,value=f'  depreciation on the FY{FY[i]} vintage').font=BLACK
    for j,c2 in enumerate(CO):
        if j<i: continue
        v=f'=${c}${R_ADD}*${CO[0]}${R_RATE}*'+('0.5' if j==i else '1')
        cc=ws.cell(row=r,column=CIX(c2),value=v); cc.font=BLACK; cc.number_format=CUR
    r+=1
line(ws,r,'Depreciation on the existing in-service base',[f'={c}{R_BD}' for c in CO],CUR,GREEN); R_BD2=r; r+=1
line(ws,r,'Less: relief from impaired assets',[f'=-SUM($C${IR["impair"]}:{c}{IR["impair"]})*0' for c in CO],CUR,BLACK)
for i,c in enumerate(CO):
    prev=','.join(f'Inputs!{CO[j]}${IR["impair"]}' for j in range(i))
    ws.cell(row=r,column=CIX(c)).value = ('=0' if i==0 else f'=-SUM({prev})/5')
R_IMP=r; r+=1
line(ws,r,'TOTAL DEPRECIATION',[f'=SUM({c}{VST}:{c}{VST+4})+{c}{R_BD2}+{c}{R_IMP}' for c in CO],CUR,BLACK,
     'FY2026A was $7,623m. The step-up is the mechanical core of the whole story.',bold=True)
R_DEP=r; r+=2
sec(ws,r,'PP&E ROLL-FORWARD'); r+=1
line(ws,r,'Gross PP&E, opening',[f'=122651']+[f'={CO[i-1]}{r+1}' for i in range(1,5)],CUR,BLACK); R_GO=r; r+=1
line(ws,r,'Gross PP&E, closing',[f'={c}{R_GO}+{c}{R_CX}' for c in CO]); R_GE=r; r+=1
line(ws,r,'Accumulated depreciation, closing',[f'=22694+SUM($C${R_DEP}:C{R_DEP})']+[f'=22694+SUM($C${R_DEP}:{c}{R_DEP})' for c in CO[1:]],CUR,BLACK); R_AC=r; r+=1
line(ws,r,'Cumulative impairment',[f'=SUM(Inputs!$C${IR["impair"]}:Inputs!{c}${IR["impair"]})' for c in CO]); R_CIMP=r; r+=1
line(ws,r,'NET PP&E',[f'={c}{R_GE}-{c}{R_AC}-{c}{R_CIMP}' for c in CO],CUR,BLACK,'FY2026A $99,957m (10-K R2).',bold=True); R_NP=r; r+=1
line(ws,r,'Construction in progress, closing',
     [f'=MAX(0,{IN("cip_open")}+C{R_CX}-C{R_ADD})']+[f'=MAX(0,{CO[i-1]}{r}+{c}{R_CX}-{c}{R_ADD})' for i,c in enumerate(CO) if i>0],CUR,BLACK,
     'FY2026A $39,973m (10-K R49).')
R_CIPE=r; r+=1
line(ws,r,'Cumulative capex FY27 onwards',[f'=SUM($C${R_CX}:{c}{R_CX})' for c in CO]); R_CUMX=r

# ==================================================== DEBT & SHARES
ws=sh('Debt_Shares'); T(ws,'DEBT SCHEDULE, INTEREST, AND SHARE COUNT',
  'Interest is charged on OPENING balances only, which removes the circular reference. See Formula_Audit for the size of that simplification.')
H(ws,4,HD); r=6
sec(ws,r,'DEBT'); r+=1
line(ws,r,'Total debt, opening',[f'={IN("debt_open")}']+[f'={CO[i-1]}{r+5}' for i in range(1,5)],CUR,BLACK,'10-K R2: $7,199m current + $122,342m non-current.'); D_OP=r; r+=1
line(ws,r,'Scheduled maturities',[f'=-{IN("debt_mat",c)}' for c in CO],CUR,GREEN,'DISCLOSED in full: 10-K R57.'); D_MAT=r; r+=1
line(ws,r,'Cumulative new debt, opening',[0]+[f'={CO[i-1]}{r+3}' for i in range(1,5)],CUR,BLACK); D_NO=r; r+=1
line(ws,r,'Interest expense',
     [f'=({c}{D_OP}-{c}{D_NO})*{IN("kd_exist")}+{c}{D_NO}*{IN("kd_new")}' for c in CO],CUR,BLACK,
     'FY2026A $4,599m. New debt raised during a year first bears interest in the following year.'); D_INT=r; r+=1
line(ws,r,'New debt issued (plug)',[f"=MAX(0,Cash_Flow!{c}{'{FUND}'})" for c in CO],CUR,BLACK); D_ISS=r; r+=1
line(ws,r,'Cumulative new debt, closing',[f'={c}{D_NO}+{c}{D_ISS}' for c in CO]); D_NC=r; r+=1
line(ws,r,'TOTAL DEBT, CLOSING',[f'={c}{D_OP}+{c}{D_MAT}+{c}{D_ISS}' for c in CO],CUR,BLACK,None,bold=True); D_CL=r; r+=1
line(ws,r,'Cash & marketable securities, closing',[f"=Cash_Flow!{c}{'{CASH}'}" for c in CO],CUR,GREEN); D_CASH=r; r+=1
line(ws,r,'NET DEBT',[f'={c}{D_CL}-{c}{D_CASH}' for c in CO],CUR,BLACK,None,bold=True); D_ND=r; r+=1
line(ws,r,'Interest income',[f'={c}{D_CASH}*{IN("ki")}' for c in CO],CUR,BLACK,'FY2026A $780m.'); D_II=r; r+=2
sec(ws,r,'SHARE COUNT'); r+=1
line(ws,r,'Diluted shares, opening (m)',[2914]+[f'={CO[i-1]}{r+6}' for i in range(1,5)],NUM,BLACK,
     'FY2026A diluted weighted-average, 10-K EPS note (R91). NOT the cover-page count of 2,880.471m.'); S_OP=r; r+=1
line(ws,r,'Net dilution from stock awards',[f'={c}{S_OP}*{IN("dil_sbc")}' for c in CO],NUM,BLACK,
     'DISCLOSED: 10-K MD&A — cumulative potential dilution since 6/1/2023 has run at 1.0% p.a.'); S_D=r; r+=1
line(ws,r,'Shares issued under the $20bn ATM',[f'={IN("eq_raise",c)}/MAX(1,{IN("eq_price",c)})*{"0.5" if i==0 else "1"}' for i,c in enumerate(CO)],NUM,BLACK,
     'DISCLOSED: $20bn ATM entered 2/2/2026, ZERO drawn at 5/31/26 (10-K R70). At $151.94 a full $20bn draw is ~132m shares — '
     'four times the mandatory convertible. THIS, not the preferred, is the share-count story.',fill=YFILL); S_ATM=r; r+=1
line(ws,r,'Mandatory convertible conversion',[0,0,f'={IN("prefsh")}*4.5/12',f'={IN("prefsh")}',f'={IN("prefsh")}'],NUM,BLACK,
     'DISCLOSED: converts 1/15/2029 (10-K Note 10) — 4.5 of FY29\'s 12 months. At $151.94, below the $160.06 lower conversion price, '
     'the MAXIMUM ratio of 624.7657 applies: 31.2m shares.'); S_PC=r; r+=1
line(ws,r,'Buybacks',[0,0,0,0,0],NUM,BLUE,
     'FY2026A repurchases were $95m — 0.4m shares. Buybacks have effectively stopped; $6.3bn of authorisation remains unused (10-K R70).'); S_BB=r; r+=1
line(ws,r,'DILUTED SHARES, CLOSING (m)',[f'={c}{S_OP}+{c}{S_D}+{c}{S_ATM}+{c}{S_PC}-{c}{S_BB}' for c in CO],NUM,BLACK,None,bold=True); S_CL=r; r+=1
line(ws,r,'Basic shares (memo)',[f'={c}{S_CL}-55' for c in CO],NUM,BLACK,'FY26A gap between basic (2,860m) and diluted (2,914m) was 54m.'); S_BAS=r; r+=1
line(ws,r,'Preferred dividends',[f'={IN("prefdiv")}',f'={IN("prefdiv")}',f'={IN("prefdiv")}*7.5/12',0,0],CUR,BLACK,
     '6.50% on $5.0bn face = $325m p.a., ceasing on conversion.'); S_PD=r
wb.save('ORCL_model.xlsx')
json.dump(dict(R_IA=R_IA,R_CX=R_CX,R_DEP=R_DEP,R_NP=R_NP,R_GE=R_GE,R_CUMX=R_CUMX,R_ADD=R_ADD,R_CIPE=R_CIPE,
               D_INT=D_INT,D_ISS=D_ISS,D_CL=D_CL,D_ND=D_ND,D_II=D_II,D_CASH=D_CASH,D_MAT=D_MAT,
               S_CL=S_CL,S_BAS=S_BAS,S_PD=S_PD),open('xlsx_rows3.json','w'))
print('part3 saved: capex rows',R_CX,R_DEP,'debt',D_INT,D_ISS,'shares',S_CL)
