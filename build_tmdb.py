import json, os, time, requests
from pathlib import Path

TOKEN = os.environ.get("TMDB_READ_TOKEN")
if not TOKEN:
    raise SystemExit("Falta el secret TMDB_READ_TOKEN en GitHub.")

HEADERS={"Authorization":f"Bearer {TOKEN}","accept":"application/json"}
BASE="https://api.themoviedb.org/3"
DATA=json.loads(Path("data/base_catalog.json").read_text(encoding="utf-8"))

def search_movie(title,year):
    p={"query":title,"language":"es-MX","include_adult":"false"}
    if year: p["year"]=year
    r=requests.get(BASE+"/search/movie",headers=HEADERS,params=p,timeout=30); r.raise_for_status()
    res=r.json().get("results",[])
    if not res: return None
    for x in res:
        if x.get("title","").casefold()==title.casefold():
            return x
    return res[0]

def search_tv(title,year):
    p={"query":title,"language":"es-MX","include_adult":"false"}
    r=requests.get(BASE+"/search/tv",headers=HEADERS,params=p,timeout=30); r.raise_for_status()
    res=r.json().get("results",[])
    if not res: return None
    for x in res:
        if x.get("name","").casefold()==title.casefold():
            return x
    return res[0]

movies=[]
for item in DATA.get("movies",[]):
    title=item.get("title") or item.get("name")
    tmdb=search_movie(title,item.get("year"))
    out=dict(item)
    out["poster"]=("https://image.tmdb.org/t/p/w500"+tmdb["poster_path"]) if tmdb and tmdb.get("poster_path") else None
    out["tmdb_id"]=tmdb.get("id") if tmdb else None
    movies.append(out)
    time.sleep(.1)

series=[]
for item in DATA.get("series",[]):
    title=item.get("title") or item.get("name")
    tmdb=search_tv(title,item.get("year"))
    out=dict(item)
    out["poster"]=("https://image.tmdb.org/t/p/w500"+tmdb["poster_path"]) if tmdb and tmdb.get("poster_path") else None
    out["tmdb_id"]=tmdb.get("id") if tmdb else None
    series.append(out)
    time.sleep(.1)

Path("data/movies.json").write_text(json.dumps(movies,ensure_ascii=False,indent=2),encoding="utf-8")
Path("data/series.json").write_text(json.dumps(series,ensure_ascii=False,indent=2),encoding="utf-8")
print("Peliculas:",len(movies),"Series:",len(series))
