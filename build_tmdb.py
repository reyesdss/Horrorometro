from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
BASE_CATALOG = DATA_DIR / "base_catalog.json"
MOVIES_OUT = DATA_DIR / "movies.json"
SERIES_OUT = DATA_DIR / "series.json"

TOKEN = os.environ.get("TMDB_READ_TOKEN", "").strip()
if not TOKEN:
    raise SystemExit("ERROR: Falta el secret TMDB_READ_TOKEN.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "accept": "application/json",
}
BASE_URL = "https://api.themoviedb.org/3"
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Alternate titles for entries where the Spanish/local title may not be the
# strongest TMDB search key. These are only fallbacks; exact title/year still wins.
ALIASES = {
    "Huye": ["Get Out"],
    "El Descenso": ["The Descent"],
    "Secretos Ocultos": ["Marrowbone"],
    "Despues del Apocalipcis": ["Arcadian"],
    "Despues del Apocalipsis": ["Arcadian"],
    "La Cabaña (The Cabin in the Woods)": ["The Cabin in the Woods"],
    "Así en la Tierra Como en el Infierno": ["As Above, So Below"],
    "La Cura Siniestra": ["A Cure for Wellness"],
    "Detras de las paredes": ["The Resident"],
    "Muerte en Silencio (Dead Silence)": ["Dead Silence"],
    "Actividad Paranormal": ["Paranormal Activity"],
    "Actividad Paranormal 2": ["Paranormal Activity 2"],
    "Actividad Paranormal 3": ["Paranormal Activity 3"],
    "Actividad Paranormal 4": ["Paranormal Activity 4"],
    "Paranormal Activity: The Marked Ones": ["Paranormal Activity: The Marked Ones"],
    "Paranormal Activity: The Ghost Dimension": ["Paranormal Activity: The Ghost Dimension"],
    "V/H/S 94": ["V/H/S/94"],
    "V/H/S 99": ["V/H/S/99"],
    "V/H/S 85": ["V/H/S/85"],
    "V/H/S Beyond": ["V/H/S/Beyond"],
    "V/H/S Halloween": ["V/H/S/Halloween"],
    "V/H/S 2": ["V/H/S/2"],
    "V/H/S": ["V/H/S"],
    "V/H/S Viral": ["V/H/S: Viral"],
    "Cuando Acecha la Maldad": ["Cuando Acecha la Maldad", "When Evil Lurks"],
    "El Páramo": ["The Wasteland"],
    "Siniestro": ["Sinister"],
    "Demoniaca": ["The Dark and the Wicked"],
    "El Wendigo": ["Wendigo"],
    "La Morgue": ["The Autopsy of Jane Doe"],
    "No One Will Save You": ["No One Will Save You"],
    "La sustancia": ["The Substance"],
    "Belcebud": ["Belzebuth"],
    "La Maldicion de Charlie": ["The Curse of Charlie"],
    "La Maldición de Charlie": ["The Curse of Charlie"],
    "Gonjiam: Haunted Asylum": ["Gonjiam: Haunted Asylum"],
    "The Tunel": ["The Tunnel"],
    "The Witch": ["The Witch"],
    "The Thing": ["The Thing"],
    "Color Out of Space": ["Color Out of Space"],
    "The Mist": ["The Mist"],
    "The Void": ["The Void"],
    "The Empty Man": ["The Empty Man"],
    "Annihilation": ["Annihilation"],
    "Pandorum": ["Pandorum"],
    "Coherence": ["Coherence"],
    "Ghostland": ["Incident in a Ghostland", "Ghostland"],
    "Nope": ["Nope"],
    "Alien Romulus": ["Alien: Romulus"],
    "La Ultima Casa": ["The Last House"],
    "La Última Casa": ["The Last House"],
    "BackRooms": ["Backrooms"],
    "1408": ["1408"],
    "Good Boy": ["Good Boy"],
    "Obsession": ["Obsession"],
    "Libralos del Mal": ["Bring Them Down"],
    "Maleficio": ["Incantation"],
    "Area 51": ["Area 51"],
    "The Medium": ["The Medium"],
    "The Endless": ["The Endless"],
    "Hell House LLC": ["Hell House LLC"],
    "The Visit": ["The Visit"],
    "Skinwalker: El Rancho Maldito": ["Skinwalker Ranch"],
    "The Taking of Deborah Logan": ["The Taking of Deborah Logan"],
    "Devil's Gate": ["Devil's Gate"],
    "The Blair Witch Project": ["The Blair Witch Project"],
    "Noroi": ["Noroi: The Curse"],
    "Last Shift": ["Last Shift"],
    "The Conjuring": ["The Conjuring"],
    "Shutter": ["Shutter"],
    "Nadie Sale Vivo": ["No One Gets Out Alive"],
    "REC": ["[REC]"],
    "The Wretched": ["The Wretched"],
    "Smile": ["Smile"],
    "Smile 2": ["Smile 2"],
    "Llaman a la Puerta": ["Knock at the Cabin"],
    "Phoenix Forgotten": ["Phoenix Forgotten"],
}

def strip_year(raw: str) -> tuple[str, int | None]:
    s = raw.strip()
    m = re.search(r"\s*\((19|20)\d{2}\)\s*$", s)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        s = s[:m.start()].strip()
        return s, y
    m = re.search(r"\s+(19|20)\d{2}\s*$", s)
    if m:
        y = int(re.search(r"(19|20)\d{2}", m.group(0)).group(0))
        s = s[:m.start()].strip()
        return s, y
    return s, None

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

def similarity(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()

def year_of_movie(item: dict[str, Any]) -> int | None:
    y = item.get("year")
    if isinstance(y, int):
        return y
    if isinstance(y, str) and y[:4].isdigit():
        return int(y[:4])
    t = str(item.get("title") or item.get("name") or "")
    _, parsed = strip_year(t)
    return parsed

def api_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    r = SESSION.get(BASE_URL + path, params=params, timeout=30)
    if r.status_code == 401:
        raise SystemExit(
            "ERROR 401: TMDB rechazó TMDB_READ_TOKEN. "
            "Comprueba que sea el API Read Access Token."
        )
    r.raise_for_status()
    return r.json()

def result_score(result: dict[str, Any], query_title: str, year: int | None) -> float:
    candidates = [
        result.get("title", ""),
        result.get("original_title", ""),
        *[str(x) for x in result.get("known_for_department", [])] if False else []
    ]
    title_score = max((similarity(query_title, c) for c in candidates if c), default=0.0)
    release = str(result.get("release_date", ""))[:4]
    year_bonus = 1.0 if year and release == str(year) else 0.0
    # Small popularity tie-breaker; title/year remain dominant.
    popularity = float(result.get("popularity") or 0.0)
    return title_score * 100 + year_bonus * 35 + min(popularity, 50) / 50

def choose_movie(results: list[dict[str, Any]], title: str, year: int | None) -> dict[str, Any] | None:
    if not results:
        return None
    # Hard exact match by title/year first.
    for x in results:
        titles = [x.get("title",""), x.get("original_title","")]
        y = str(x.get("release_date",""))[:4]
        if year and y == str(year) and any(norm(t) == norm(title) for t in titles if t):
            return x
    # Exact title without year as second priority.
    for x in results:
        titles = [x.get("title",""), x.get("original_title","")]
        if any(norm(t) == norm(title) for t in titles if t):
            if not year or not x.get("release_date") or str(x.get("release_date",""))[:4] == str(year):
                return x
    ranked = sorted(results, key=lambda x: result_score(x, title, year), reverse=True)
    best = ranked[0]
    # Reject clearly unrelated results.
    if result_score(best, title, year) < 55:
        return None
    return best

def choose_tv(results: list[dict[str, Any]], title: str, year: int | None) -> dict[str, Any] | None:
    if not results:
        return None
    for x in results:
        names = [x.get("name",""), x.get("original_name","")]
        y = str(x.get("first_air_date",""))[:4]
        if year and y == str(year) and any(norm(n) == norm(title) for n in names if n):
            return x
    for x in results:
        names = [x.get("name",""), x.get("original_name","")]
        if any(norm(n) == norm(title) for n in names if n):
            return x
    ranked = []
    for x in results:
        names = [x.get("name",""), x.get("original_name","")]
        title_score = max((similarity(title,n) for n in names if n), default=0.0)
        y = str(x.get("first_air_date",""))[:4]
        bonus = 1.0 if year and y == str(year) else 0
        ranked.append((title_score*100 + bonus*35, x))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] >= 55 else None

def query_movie(title: str, year: int | None) -> dict[str, Any] | None:
    queries = []
    clean, parsed = strip_year(title)
    if parsed and not year:
        year = parsed
    queries.append((clean, "es-MX"))
    queries.append((clean, "en-US"))
    for alias in ALIASES.get(clean, []):
        queries.append((alias, "en-US"))
    # Also try the raw title once if it differs.
    if title.strip() != clean:
        queries.append((title.strip(), "es-MX"))

    seen = set()
    all_results = []
    for q, lang in queries:
        key = (q.casefold(), lang)
        if key in seen:
            continue
        seen.add(key)
        params = {"query": q, "include_adult": "false", "language": lang}
        if year:
            params["year"] = year
        payload = api_get("/search/movie", params)
        all_results.extend(payload.get("results", []))
        match = choose_movie(payload.get("results", []), q, year)
        if match:
            return match
        time.sleep(0.15)
    # One final combined scoring pass over all results.
    unique = {x.get("id"): x for x in all_results if x.get("id")}
    return choose_movie(list(unique.values()), clean, year)

def query_tv(title: str, year: int | None) -> dict[str, Any] | None:
    clean, parsed = strip_year(title)
    if parsed and not year:
        year = parsed
    queries = [(clean, "es-MX"), (clean, "en-US")]
    queries += [(a, "en-US") for a in ALIASES.get(clean, [])]
    seen=set()
    all_results=[]
    for q,lang in queries:
        key=(q.casefold(),lang)
        if key in seen:
            continue
        seen.add(key)
        payload=api_get("/search/tv", {"query":q,"include_adult":"false","language":lang})
        all_results.extend(payload.get("results",[]))
        match=choose_tv(payload.get("results",[]),q,year)
        if match:
            return match
        time.sleep(0.15)
    unique={x.get("id"):x for x in all_results if x.get("id")}
    return choose_tv(list(unique.values()),clean,year)

def build_movie(item: dict[str, Any]) -> dict[str, Any]:
    raw = str(item.get("title") or item.get("name") or "").strip()
    clean, parsed_year = strip_year(raw)
    year = year_of_movie(item) or parsed_year
    out = dict(item)
    out["tmdb_query_title"] = clean
    out["poster"] = None
    out["tmdb_id"] = None
    try:
        match = query_movie(clean, year)
        if match:
            out["tmdb_id"] = match.get("id")
            out["poster"] = (
                "https://image.tmdb.org/t/p/w500" + match["poster_path"]
                if match.get("poster_path") else None
            )
            out["tmdb_title"] = match.get("title")
            out["tmdb_original_title"] = match.get("original_title")
            out["tmdb_year"] = str(match.get("release_date",""))[:4] or None
    except Exception as exc:
        out["tmdb_error"] = str(exc)
    return out

def build_series(item: dict[str, Any]) -> dict[str, Any]:
    raw = str(item.get("title") or item.get("name") or "").strip()
    clean, parsed_year = strip_year(raw)
    year = item.get("start") if isinstance(item.get("start"), int) else parsed_year
    out = dict(item)
    out["tmdb_query_title"] = clean
    out["poster"] = None
    out["tmdb_id"] = None
    try:
        match = query_tv(clean, year)
        if match:
            out["tmdb_id"] = match.get("id")
            out["poster"] = (
                "https://image.tmdb.org/t/p/w500" + match["poster_path"]
                if match.get("poster_path") else None
            )
            out["tmdb_title"] = match.get("name")
            out["tmdb_original_title"] = match.get("original_name")
    except Exception as exc:
        out["tmdb_error"] = str(exc)
    return out

def main() -> None:
    if not BASE_CATALOG.exists():
        raise SystemExit(f"ERROR: No existe {BASE_CATALOG}")

    catalog=json.loads(BASE_CATALOG.read_text(encoding="utf-8"))
    movies=catalog.get("movies",[])
    series=catalog.get("series",[])

    print(f"Películas: {len(movies)}")
    movie_results=[]
    for i,item in enumerate(movies,1):
        raw=str(item.get("title") or item.get("name") or "")
        result=build_movie(item)
        movie_results.append(result)
        status="OK" if result.get("poster") else "SIN PORTADA"
        print(f"[PELÍCULA {i}/{len(movies)}] {raw} -> {status} ({result.get('tmdb_title')})")
        time.sleep(0.12)

    print(f"Series: {len(series)}")
    series_results=[]
    for i,item in enumerate(series,1):
        raw=str(item.get("title") or item.get("name") or "")
        result=build_series(item)
        series_results.append(result)
        status="OK" if result.get("poster") else "SIN PORTADA"
        print(f"[SERIE {i}/{len(series)}] {raw} -> {status} ({result.get('tmdb_title')})")
        time.sleep(0.12)

    MOVIES_OUT.write_text(json.dumps(movie_results,ensure_ascii=False,indent=2),encoding="utf-8")
    SERIES_OUT.write_text(json.dumps(series_results,ensure_ascii=False,indent=2),encoding="utf-8")

    print(f"Portadas encontradas: películas {sum(1 for x in movie_results if x.get('poster'))}/{len(movie_results)}; series {sum(1 for x in series_results if x.get('poster'))}/{len(series_results)}")
    print("OK: archivos TMDB generados.")

if __name__=="__main__":
    main()
