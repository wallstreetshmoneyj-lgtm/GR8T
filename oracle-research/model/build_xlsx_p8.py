import openpyxl, json
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter as CL
wb=openpyxl.load_workbook('ORCL_model.xlsx'); R=json.load(open('comps_out.json'))
BLUE=Font(name='Arial',size=10,color='0000FF'); BLACK=Font(name='Arial',size=10)
HDR=Font(name='Arial',size=10,bold=True); TITLE=Font(name='Arial',size=13,bold=True)
SUB=Font(name='Arial',size=10,bold=True,color='444444'); NOTE=Font(name='Arial',size=8,italic=True,color='666666')
WHDR=Font(name='Arial',size=10,bold=True,color='FFFFFF'); ORCLF=Font(name='Arial',size=10,bold=True,color='C00000')
YFILL=PatternFill('solid',fgColor='FFFF00'); GFILL=PatternFill('solid',fgColor='E8E8E8'); HFILL=PatternFill('solid',fgColor='1F3864')
CUR='$#,##0;($#,##0);-'; CUR2='$#,##0.00'; PCT='0.0%;(0.0%);-'; MULT='0.0x'; RAT='0.00'
SW=["ORCL","MSFT","CRM","SAP","IBM","NOW","WDAY"]; AI=["ORCL","MSFT","AMZN","GOOGL","CRWV","NBIS"]
COLS=[('Ticker','ticker',None,'C'),('FYE mth','fye_month','0','C'),('Price','price',CUR2,'C'),
 ('EV $m','ev',CUR,'C'),('NTM P/E','ntm_pe',MULT,'E'),('NTM EV/EBITDA','ntm_evebitda',MULT,'E'),
 ('NTM EV/EBIT','ntm_evebit',MULT,'E'),('NTM EV/Sales','ntm_evsales',MULT,'E'),('NTM EV/FCF','ntm_evfcf',MULT,'E'),
 ('P/B','pb',MULT,'C'),('Net debt/EBITDA','nd_ebitda',MULT,'C'),('NTM FCF margin','ntm_fcf_margin',PCT,'E'),
 ('Gross margin','gm1',PCT,'C'),('Revenue growth','g1',PCT,'C'),('Capex/revenue','capex_rev0',PCT,'C'),
 ('ROIC','roic',PCT,'C'),('PEG (FY1 basis)','peg_fy1',RAT,'E'),('# analysts','n_analysts','0','C')]
def build(name,tk,title,lead):
    ws=wb.create_sheet(name); ws.sheet_view.showGridLines=False
    ws.sheet_view.showGridLines=False
    ws['A1']=title; ws['A1'].font=TITLE
    ws['A2']=('SOURCE: stockanalysis.com, single source, pulled 2026-08-27 close / 2026-08-28 estimates.  '
              'Calendarised to a common NTM window of 28 Aug 2026 – 27 Aug 2027.'); ws['A2'].font=NOTE
    ws['A3']=lead; ws['A3'].font=NOTE
    ws['A5']=('[C] = consensus or reported, taken directly from the source.   '
              '[E] = ANALYST ESTIMATE — the FY+2 leg of every calendarised metric is my own, because FY2028 consensus is paywalled at source.')
    ws['A5'].font=SUB
    for i,(h,k,f,tag) in enumerate(COLS):
        c=ws.cell(row=7,column=1+i,value=h); c.font=WHDR; c.fill=HFILL
        c.alignment=Alignment(horizontal='center',wrap_text=True)
        t=ws.cell(row=8,column=1+i,value=f'[{tag}]'); t.font=NOTE; t.alignment=Alignment(horizontal='center')
        ws.column_dimensions[CL(1+i)].width=13
    ws.column_dimensions['A'].width=9
    r=9
    for t in tk:
        d=R[t]
        for i,(h,k,f,tag) in enumerate(COLS):
            v=d.get(k)
            c=ws.cell(row=r,column=1+i,value=(v if v is not None else 'n/m'))
            c.font=ORCLF if t=='ORCL' else BLUE
            if f and v is not None: c.number_format=f
            if v is None: c.alignment=Alignment(horizontal='center')
        r+=1
    r+=1
    for i,(h,k,f,tag) in enumerate(COLS):
        if k in ('ntm_pe','ntm_evebitda','ntm_evebit','ntm_evsales','pb','nd_ebitda'):
            vals=[R[x][k] for x in tk[1:] if R[x].get(k) is not None]
            if vals:
                ws.cell(row=r,column=1,value='Peer median (ex-ORCL)').font=HDR
                c=ws.cell(row=r,column=1+i,value=sorted(vals)[len(vals)//2]); c.font=HDR; c.number_format=f
    return ws,r
ws,r=build('Comps_Software','Comps_Software'!=None and SW,
   'COMPARABLE COMPANIES — ENTERPRISE SOFTWARE',
   'Lead with EV/EBITDA and EV/EBIT. P/E is distorted by the buildout; ORCL P/B and ROE ARE usable (see note below).')
r+=2
notes=[('Metrics the capital structure DOES break for ORCL','EV/FCF and P/FCF — free cash flow is deeply negative, so both are n/m. FCF-based screens will simply drop Oracle.'),
 ('A correction to the brief','ORCL book equity is NOT negative. At 5/31/2026 total Oracle stockholders\' equity was $42,508m (10-K R2), up from $20,451m. '
  'P/B of 11.7x and ROE of 53.4% are computable and meaningful. Equity was restored by two years of retained earnings and the near-total halt in buybacks ($95m in FY26).'),
 ('What the table actually says','On EV/EBITDA — the metric to lead with — Oracle at 11.6x is the CHEAPEST large-cap in this set except CRM. '
  'It also carries by far the highest leverage (net debt/EBITDA 5.0x vs a peer median under 3x) and a capex/revenue ratio of 83% against a peer median of 2%. '
  'Those three facts together are the entire debate.')]
for a,b in notes:
    ws.cell(row=r,column=1,value=a).font=SUB
    c=ws.cell(row=r+1,column=1,value=b); c.font=BLACK; c.alignment=Alignment(wrap_text=True,vertical='top')
    ws.merge_cells(start_row=r+1,start_column=1,end_row=r+2,end_column=14); r+=4
ws2,r2=build('Comps_AI',AI,'COMPARABLE COMPANIES — AI INFRASTRUCTURE / HYPERSCALE',
   'CRWV and NBIS are shown for completeness but are NOT valuation comparables: both have negative NTM EPS, negative free cash flow and capex above 100% of revenue.')
r2+=2
for a,b in [('Why the multiples on CRWV and NBIS are meaningless',
  'CoreWeave and Nebius screen at ~5x EV/EBITDA, which looks cheap and is not. EV/EBIT is 54.6x and n/m respectively, NTM FCF margins are -217% and -542%, '
  'and capex is 401% and 2,103% of revenue. EBITDA before a capex line that large is not a proxy for anything.'),
 ('The comparison that does matter',
  'Capex as a percentage of revenue: ORCL 83%, GOOGL 33%, MSFT 35%, AMZN 24%. Oracle is spending more, relative to its own revenue base, '
  'than any established hyperscaler — while carrying materially more leverage and generating a fraction of the cash flow.')]:
    ws2.cell(row=r2,column=1,value=a).font=SUB
    c=ws2.cell(row=r2+1,column=1,value=b); c.font=BLACK; c.alignment=Alignment(wrap_text=True,vertical='top')
    ws2.merge_cells(start_row=r2+1,start_column=1,end_row=r2+2,end_column=14); r2+=4

# ==================================================== FORMULA AUDIT
ws=wb.create_sheet('Formula_Audit'); ws.sheet_view.showGridLines=False
ws['A1']='FORMULA AUDIT — every simplification, break and known limitation'; ws['A1'].font=TITLE
ws['A2']='Read this before defending any number in this workbook.'; ws['A2'].font=NOTE
ws.column_dimensions['A'].width=42; ws.column_dimensions['B'].width=118
items=[('CIRCULARITY BREAKS',''),
 ('Interest expense','Charged on OPENING debt balances only (Debt_Shares row 10). New debt raised during a year first bears interest in the '
  'following year. This removes the interest -> net income -> cash flow -> new debt -> interest loop, so the workbook contains NO circular '
  'references and needs no iterative calculation. It understates FY27 interest by roughly $400-900m versus the fixed-point solution in model.py '
  '(under 3% of pretax income). Turn on iterative calculation and change the formula to a mid-year average if you want the exact figure.'),
 ('Maintenance capex','Solved in two passes on Capex_Depreciation. Pass 1 computes provisional depreciation on GROWTH capex only; maintenance '
  'capex is set from that; total capex is then growth + maintenance; pass 2 recomputes depreciation on total capex. model.py iterates this to '
  'convergence; the two-pass version differs by well under 1%.'),
 ('KNOWN OMISSIONS IN THE WORKBOOK (present in model.py)',''),
 ('Prior-year capex ratchet','model.py also floors capex at a percentage of the prior year (bear case: 80% / 72% / 60% / 55%), representing '
  'orders that cannot be cancelled. The workbook applies only the absolute committed floor. This binds ONLY in the bear case.'),
 ('Backlog NPV scenario switching','The assumptions on Valuation_RPO_NPV do NOT follow the Inputs scenario selector. Bull: margin path '
  '0.40 rising to 0.58, turn 0.44, customer-funded 26%, recovery 85%. Bear: margin path 0.30 rising to 0.35, turn 0.28, customer-funded 18%, '
  'recovery 45%. Enter them by hand to switch the primary valuation.'),
 ('THINGS THAT ARE ESTIMATES, NOT DATA',''),
 ('IaaS gross margin','Oracle does NOT disclose cost of revenue by offering. The ~30% FY26 figure on the Historicals tab is DERIVED by assuming '
  'software support 93%, licence 98% and SaaS 78% gross margins and taking IaaS as the residual. Move any of those three and the IaaS margin moves '
  'one-for-one. Every conclusion about OCI profitability inherits this uncertainty.'),
 ('Asset turn and utilisation','Neither is disclosed anywhere. Together they set capex, depreciation, margins and ROIC. They are the reason the '
  'ROIC question is answered as a breakeven grid rather than a point estimate.'),
 ('New bookings after 5/31/2026','A pure estimate. It contributes ~$4bn of FY27 revenue but ~$49bn of FY31 revenue. FY2030 and FY2031 in this '
  'model are assumption, not schedule. FY2027 and FY2028 are largely the disclosed backlog.'),
 ('The legacy business perpetuity','Discounting a flat software annuity at the whole-group WACC values it at ~8x EBITDA against a peer group at '
  '14-19x. Both readings are shown on Valuation_RPO_NPV. This is the second-largest driver of the answer and it is a judgement, not a fact.'),
 ('THINGS THAT ARE DISCLOSED AND SHOULD NOT BE RE-ESTIMATED',''),
 ('RPO conversion schedule','12% / 34% / 34% / remainder. FY2026 10-K Note 1, verbatim. This is data.'),
 ('Intangible amortisation FY27-31','$731 / $694 / $620 / $582 / $377m. 10-K R53. This is data.'),
 ('Debt maturities FY27-31','$7,210 / $10,145 / $5,500 / $7,250 / $9,750m. 10-K R57. This is data.'),
 ('Mandatory convertible terms','Converts 1/15/2029 at 499.8126-624.7657 shares per preferred share. 10-K Note 10. This is data.'),
 ('ATM programme','$20bn authorised 2/2/2026, ZERO drawn at 5/31/2026. 10-K R70. This is data.'),
 ('Server life','6 years. 10-K R50. This is data.'),
 ('Construction in progress','$39,973m of $122,651m gross PP&E at 5/31/2026 — not yet depreciating. 10-K R49. This is data.'),
 ('SHEETS COMPATIBILITY',''),
 ('Functions used','SUM, SUMPRODUCT, MAX, MIN, AVERAGE, MATCH, CHOOSE, IFERROR, POWER via ^. All work identically in Google Sheets. '
  'No XLOOKUP, FILTER, SORT, UNIQUE, SEQUENCE, LET or LAMBDA. No array formulas requiring Ctrl-Shift-Enter. No Excel Data Tables — '
  'the two-way sensitivity grids are written as ordinary formulas, one per cell.'),
 ('Named ranges','None used. Every reference is an explicit cell address so that nothing breaks on import.')]
r=4
for a,b in items:
    if not b:
        c=ws.cell(row=r,column=1,value=a); c.font=SUB; c.fill=GFILL; ws.cell(row=r,column=2).fill=GFILL; r+=1; continue
    ws.cell(row=r,column=1,value=a).font=HDR
    c=ws.cell(row=r,column=2,value=b); c.font=BLACK; c.alignment=Alignment(wrap_text=True,vertical='top')
    ws.row_dimensions[r].height=max(28,14*(len(b)//110+1)); r+=1
order=['README','Inputs','Historicals','RPO_Schedule','Capex_Depreciation','Income_Statement','NonGAAP_Recon',
       'Cash_Flow','Debt_Shares','Valuation_RPO_NPV','Valuation_DCF','Sensitivity','ROIC_Breakeven',
       'Comps_Software','Comps_AI','Formula_Audit']
wb._sheets=[wb[n] for n in order if n in wb.sheetnames]+[s for s in wb._sheets if s.title not in order]
wb.save('ORCL_model.xlsx'); print('part8 saved. sheets:',wb.sheetnames)
