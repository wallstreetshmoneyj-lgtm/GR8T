import re,json,warnings
from bs4 import BeautifulSoup
warnings.filterwarnings("ignore")
TK=["ORCL","MSFT","CRM","SAP","IBM","NOW","WDAY","AMZN","GOOGL","CRWV","NBIS"]
def num(s):
    if s is None: return None
    s=s.strip().replace(',','').replace('$','')
    if s in ('n/a','-','','Upgrade','Pro','*'): return None
    neg = s.startswith('(') or s.startswith('-')
    s=s.lstrip('-').strip('()')
    m=re.match(r'^([\d\.]+)\s*([BMTK%]?)$',s)
    if not m: return None
    v=float(m.group(1)); u=m.group(2)
    v*= {'T':1e6,'B':1e3,'M':1.0,'K':1e-3,'':1.0,'%':1.0}[u]
    return -v if neg else v
out={}
for t in TK:
    d={}
    soup=BeautifulSoup(open(f"comps/{t}_stats.html",encoding='utf-8',errors='replace').read(),'html.parser')
    for tr in soup.find_all('tr'):
        c=[td.get_text(" ",strip=True) for td in tr.find_all(['td','th'])]
        if len(c)==2 and c[0]: d[c[0]]=c[1]
    fc={}
    soup2=BeautifulSoup(open(f"comps/{t}_fc.html",encoding='utf-8',errors='replace').read(),'html.parser')
    for tbl in soup2.find_all('table'):
        rows=[[td.get_text(" ",strip=True) for td in tr.find_all(['td','th'])] for tr in tbl.find_all('tr')]
        rows=[r for r in rows if r]
        if rows and rows[0] and rows[0][0]=='Fiscal Year':
            hdr=rows[0]; per=None
            for r in rows:
                if r[0]=='Period Ending': per=r
            for r in rows[1:]:
                fc[r[0]]=dict(zip(hdr[1:],r[1:]))
            fc['_hdr']=hdr; fc['_per']=per
        if rows and rows[0] and rows[0][0]=='Target':
            for r in rows[1:]: fc['_pt_'+r[0]]=dict(zip(rows[0][1:],r[1:]))
    out[t]={'stats':d,'fc':fc}
json.dump(out,open('comps_raw.json','w'))
# summary
for t in TK:
    d=out[t]['stats']; fc=out[t]['fc']
    hdr=fc.get('_hdr',[]); per=fc.get('_per',[])
    print(f"\n===== {t} =====")
    print("  fiscal cols:", hdr[1:] if hdr else "?")
    print("  period end :", per[1:] if per else "?")
    for k in ['Market Cap','Enterprise Value','Shares Outstanding','PE Ratio','Forward PE','EV / EBITDA','EV / EBIT','EV / Sales','EV / FCF','PB Ratio','Debt / EBITDA','Total Debt','Net Cash','Equity (Book Value)','Revenue','Gross Profit','Gross Margin','EBITDA','EBIT','Operating Income','Net Income','Free Cash Flow','FCF Margin','Operating Cash Flow','Capital Expenditures','Return on Invested Capital (ROIC)','Return on Equity (ROE)','Beta (5Y)','Employee Count','Effective Tax Rate']:
        if k in d: print(f"    {k:36s} {d[k]}")
    for k in ['Revenue','Revenue Growth','Gross Margin','Operating Income','Net Income','EPS','EPS Growth','Free Cash Flow','No. Analysts']:
        if k in fc: print(f"    FC {k:33s} {fc[k]}")
