from __future__ import annotations
import json, os, re, time, unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any
import requests

ROOT=Path(__file__).resolve().parent
DATA=ROOT/"data"
BASE=DATA/"base_catalog.json"
MOVIES=DATA/"movies.json"
SERIES=DATA/"series.json"
POSTERS=ROOT/"posters"
TOKEN=os.environ.get("TMDB_READ_TOKEN","").strip()
if not TOKEN:
    raise SystemExit("Falta TMDB_READ_TOKEN.")
HEADERS={"Authorization":f"Bearer {TOKEN}","accept":"application/json"}
S=requests.Session(); S.headers.update(HEADERS)
BASE_URL="https://api.themoviedb.org/3"

ALIASES={
"Huye":["Get Out"],"El Descenso":["The Descent"],"Secretos Ocultos":["Marrowbone"],
"Despues del Apocalipcis":["Arcadian"],"Despues del Apocalipsis":["Arcadian"],
"La Cabaña (The Cabin in the Woods)":["The Cabin in the Woods"],
"Así en la Tierra Como en el Infierno":["As Above, So Below"],"La Cura Siniestra":["A Cure for Wellness"],
"Detras de las paredes":["The Resident"],"Muerte en Silencio (Dead Silence)":["Dead Silence"],
"Cuando Acecha la Maldad":["Cuando Acecha la Maldad","When Evil Lurks"],
"El Páramo":["The Wasteland"],"Siniestro":["Sinister"],"Demoniaca":["The Dark and the Wicked"],
"V/H/S 94":["V/H/S/94"],"V/H/S 99":["V/H/S/99"],"V/H/S 85":["V/H/S/85"],
"V/H/S Beyond":["V/H/S/Beyond"],"V/H/S Halloween":["V/H/S/Halloween"],
"V/H/S 2":["V/H/S/2"],"V/H/S":["V/H/S"],"V/H/S Viral":["V/H/S: Viral"],
"Alien Romulus":["Alien: Romulus"],"The Thing":["The Thing"],"The Witch":["The Witch"],
"Color Out of Space":["Color Out of Space"],"The Mist":["The Mist"],"The Void":["The Void"],
"No One Will Save You":["No One Will Save You"],"The Substance":["The Substance"],
"Obsession":["Obsession"],"Good Boy":["Good Boy"],"1408":["1408"],
}
def strip_year(t:str)->tuple[str,int|None]:
    t=t.strip()
    m=re.search(r"\s*\((19|20)\d{2}\)\s*$",t)
    if m:
        return t[:m.start()].strip(),int(re.search(r"(19|20)\d{2}",m.group(0)).group(0))
    m=re.search(r"\s+(19|20)\d{2}\s*$",t)
    if m:
        return t[:m.start()].strip(),int(re.search(r"(19|20)\d{2}",m.group(0)).group(0))
    return t,None
def norm(s:str)->str:
    s=unicodedata.normalize("NFKD",s);s="".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+"," ",s.casefold()).strip()
def sim(a,b): return SequenceMatcher(None,norm(a),norm(b)).ratio()
def get(path,params):
    r=S.get(BASE_URL+path,params=params,timeout=30)
    if r.status_code==401: raise SystemExit("TMDB 401: revisa TMDB_READ_TOKEN.")
    r.raise_for_status(); return r.json()
def pick_movie(results,title,year):
    if not results:return None
    for x in results:
        y=str(x.get("release_date",""))[:4]
        if year and y==str(year) and any(norm(t)==norm(title) for t in [x.get("title",""),x.get("original_title","")] if t): return x
    scored=[]
    for x in results:
        names=[x.get("title",""),x.get("original_title","")]
        s=max([sim(title,n) for n in names if n] or [0])*100
        if year and str(x.get("release_date",""))[:4]==str(year): s+=35
        scored.append((s,x))
    scored.sort(reverse=True,key=lambda z:z[0])
    return scored[0][1] if scored and scored[0][0]>=55 else None
def pick_tv(results,title,year):
    if not results:return None
    for x in results:
        y=str(x.get("first_air_date",""))[:4]
        if year and y==str(year) and any(norm(n)==norm(title) for n in [x.get("name",""),x.get("original_name","")] if n): return x
    scored=[]
    for x in results:
        names=[x.get("name",""),x.get("original_name","")]
        s=max([sim(title,n) for n in names if n] or [0])*100
        if year and str(x.get("first_air_date",""))[:4]==str(year): s+=35
        scored.append((s,x))
    scored.sort(reverse=True,key=lambda z:z[0])
    return scored[0][1] if scored and scored[0][0]>=55 else None
def find_movie(title,year):
    clean,parsed=strip_year(title); year=year or parsed
    queries=[(clean,"es-MX"),(clean,"en-US")]+[(a,"en-US") for a in ALIASES.get(clean,[])]
    seen=set(); allr=[]
    for q,lang in queries:
        if (q,lang) in seen: continue
        seen.add((q,lang))
        d=get("/search/movie",{"query":q,"include_adult":"false","language":lang,**({"year":year} if year else {})})
        allr += d.get("results",[])
        m=pick_movie(d.get("results",[]),q,year)
        if m:return m
        time.sleep(.1)
    return pick_movie(allr,clean,year)
def find_tv(title,year):
    clean,parsed=strip_year(title); year=year or parsed
    queries=[(clean,"es-MX"),(clean,"en-US")]+[(a,"en-US") for a in ALIASES.get(clean,[])]
    seen=set(); allr=[]
    for q,lang in queries:
        if (q,lang) in seen:continue
        seen.add((q,lang))
        d=get("/search/tv",{"query":q,"include_adult":"false","language":lang})
        allr += d.get("results",[])
        m=pick_tv(d.get("results",[]),q,year)
        if m:return m
        time.sleep(.1)
    return pick_tv(allr,clean,year)

def download_poster(item,tmdb_id,path_stub):
    POSTERS.mkdir(exist_ok=True)
    poster_path=item.get("poster_path")
    if not poster_path:return None
    url="https://image.tmdb.org/t/p/w500"+poster_path
    local=POSTERS/f"{path_stub}.jpg"
    r=S.get(url,timeout=45)
    r.raise_for_status()
    local.write_bytes(r.content)
    return f"posters/{local.name}"

def main():
    if not BASE.exists(): raise SystemExit(f"No existe {BASE}")
    cat=json.loads(BASE.read_text(encoding="utf-8"))
    movies_out=[];series_out=[]
    for i,item in enumerate(cat.get("movies",[]),1):
        out=dict(item); out["poster"]=None;out["poster_local"]=None;out["tmdb_id"]=None
        title=str(item.get("title") or item.get("name") or ""); year=item.get("year")
        try:
            m=find_movie(title,year)
            if m:
                out["tmdb_id"]=m.get("id");out["poster"]=("https://image.tmdb.org/t/p/w500"+m["poster_path"]) if m.get("poster_path") else None
                if out["poster"]: out["poster_local"]=download_poster(m,"",str(item.get("id") or f"movie_{i}"))
                out["tmdb_title"]=m.get("title");out["tmdb_year"]=str(m.get("release_date",""))[:4] or None
        except Exception as e: out["tmdb_error"]=str(e)
        movies_out.append(out); print(f"[PELÍCULA {i}/{len(cat.get('movies',[]))}] {title} -> {'OK' if out['poster_local'] else 'SIN PORTADA'}"); time.sleep(.08)
    for i,item in enumerate(cat.get("series",[]),1):
        out=dict(item); out["poster"]=None;out["poster_local"]=None;out["tmdb_id"]=None
        title=str(item.get("title") or item.get("name") or ""); year=item.get("start")
        try:
            m=find_tv(title,year)
            if m:
                out["tmdb_id"]=m.get("id");out["poster"]=("https://image.tmdb.org/t/p/w500"+m["poster_path"]) if m.get("poster_path") else None
                if out["poster"]: out["poster_local"]=download_poster(m,"",str(item.get("id") or f"series_{i}"))
                out["tmdb_title"]=m.get("name")
        except Exception as e: out["tmdb_error"]=str(e)
        series_out.append(out); print(f"[SERIE {i}/{len(cat.get('series',[]))}] {title} -> {'OK' if out['poster_local'] else 'SIN PORTADA'}"); time.sleep(.08)
    MOVIES.write_text(json.dumps(movies_out,ensure_ascii=False,indent=2),encoding="utf-8")
    SERIES.write_text(json.dumps(series_out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("FIN.")
if __name__=="__main__": main()
