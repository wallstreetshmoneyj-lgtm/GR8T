import re,json,time,warnings,subprocess,os
from bs4 import BeautifulSoup
warnings.filterwarnings("ignore")
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
TK=["ORCL","MSFT","CRM","SAP","IBM","NOW","WDAY","AMZN","GOOGL","CRWV","NBIS"]
os.makedirs("comps",exist_ok=True)
def get(url,out):
    if os.path.exists(out) and os.path.getsize(out)>5000: return
    subprocess.run(["curl","-sS","-A",UA,"--max-time","40",url,"-o",out],check=False)
    time.sleep(1.0)
for t in TK:
    get(f"https://stockanalysis.com/stocks/{t.lower()}/statistics/", f"comps/{t}_stats.html")
    get(f"https://stockanalysis.com/stocks/{t.lower()}/forecast/",  f"comps/{t}_fc.html")
    print(t, os.path.getsize(f"comps/{t}_stats.html"), os.path.getsize(f"comps/{t}_fc.html"))
