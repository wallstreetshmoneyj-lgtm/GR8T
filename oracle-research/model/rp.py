import sys,re
from bs4 import BeautifulSoup
def parse(fn, only_first=True, maxw=150, maxrows=200):
    soup=BeautifulSoup(open(fn,encoding='utf-8',errors='replace').read(),'lxml')
    tbls=soup.find_all('table')
    if only_first: tbls=tbls[:1]
    out=[]
    for tbl in tbls:
        rows=[]
        for tr in tbl.find_all('tr'):
            cells=[]
            for td in tr.find_all(['td','th']):
                t=re.sub(r'\s+',' ',td.get_text(" ",strip=True).replace('\xa0',' '))
                if t in ('$','%',')','(',''): continue
                cells.append(t)
            if cells: rows.append(cells)
        if not rows: continue
        n=max(len(r) for r in rows)
        w=[0]*n
        for r in rows:
            for i,c in enumerate(r): w[i]=max(w[i],min(len(c),55))
        for r in rows[:maxrows]:
            out.append(" | ".join(c[:55].ljust(w[i]) for i,c in enumerate(r))[:maxw])
        out.append("")
    return "\n".join(out)
if __name__=="__main__":
    for f in sys.argv[1:]:
        print("#"*90); print("FILE:",f); print(parse(f))
