from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
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


def tmdb_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{BASE_URL}{path}"
    response = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if response.status_code == 401:
        raise SystemExit(
            "ERROR 401: TMDB rechazó el token. Revisa que TMDB_READ_TOKEN "
            "contenga el API Read Access Token completo."
        )
    response.raise_for_status()
    return response.json()


def pick_movie(results: list[dict[str, Any]], title: str, year: int | str | None) -> dict[str, Any] | None:
    if not results:
        return None

    wanted_title = title.strip().casefold()
    wanted_year = str(year)[:4] if year else ""

    exact = []
    for item in results:
        item_title = str(item.get("title", "")).strip().casefold()
        release = str(item.get("release_date", ""))
        item_year = release[:4]
        if item_title == wanted_title:
            exact.append((0 if wanted_year and item_year == wanted_year else 1, item))

    if exact:
        exact.sort(key=lambda pair: pair[0])
        return exact[0][1]

    if wanted_year:
        same_year = [
            item for item in results
            if str(item.get("release_date", ""))[:4] == wanted_year
        ]
        if same_year:
            return same_year[0]

    return results[0]


def pick_tv(results: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    if not results:
        return None

    wanted_title = title.strip().casefold()

    for item in results:
        if str(item.get("name", "")).strip().casefold() == wanted_title:
            return item

    return results[0]


def clean_movie_title(raw_title: str) -> str:
    """Remove a trailing release year like ' (2017)' or ' 2017' from the title."""
    title = raw_title.strip()
    title = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", title)
    title = re.sub(r"\s+(?:19|20)\d{2}\s*$", "", title)
    return title.strip()


def movie_record(item: dict[str, Any]) -> dict[str, Any]:
    raw_title = str(item.get("title") or item.get("name") or "").strip()
    title = clean_movie_title(raw_title)
    year = item.get("year")

    try:
        params = {
            "query": title,
            "include_adult": "false",
            "language": "es-MX",
        }
        if year:
            params["year"] = int(year)

        payload = tmdb_get("/search/movie", params)
        results = payload.get("results", [])
        match = pick_movie(results, title, year)

        # If the localized title search misses, retry with English/default language.
        if match is None:
            fallback_payload = tmdb_get(
                "/search/movie",
                {
                    "query": title,
                    "include_adult": "false",
                    "language": "en-US",
                },
            )
            match = pick_movie(fallback_payload.get("results", []), title, year)

        out = dict(item)
        out["tmdb_id"] = match.get("id") if match else None
        out["poster"] = (
            f"https://image.tmdb.org/t/p/w500{match['poster_path']}"
            if match and match.get("poster_path")
            else None
        )
        out["tmdb_title"] = match.get("title") if match else None
        out["tmdb_year"] = (
            str(match.get("release_date", ""))[:4]
            if match
            else None
        )
        return out

    except Exception as exc:
        # Keep the movie in the catalog even if a single TMDB lookup fails.
        out = dict(item)
        out["tmdb_id"] = None
        out["poster"] = None
        out["tmdb_error"] = str(exc)
        print(f"[AVISO] Película sin portada: {title}: {exc}")
        return out


def series_record(item: dict[str, Any]) -> dict[str, Any]:
    title = str(item.get("title") or item.get("name") or "").strip()

    try:
        payload = tmdb_get(
            "/search/tv",
            {
                "query": title,
                "include_adult": "false",
                "language": "es-MX",
            },
        )
        match = pick_tv(payload.get("results", []), title)

        out = dict(item)
        out["tmdb_id"] = match.get("id") if match else None
        out["poster"] = (
            f"https://image.tmdb.org/t/p/w500{match['poster_path']}"
            if match and match.get("poster_path")
            else None
        )
        out["tmdb_title"] = match.get("name") if match else None
        return out

    except Exception as exc:
        out = dict(item)
        out["tmdb_id"] = None
        out["poster"] = None
        out["tmdb_error"] = str(exc)
        print(f"[AVISO] Serie sin portada: {title}: {exc}")
        return out


def main() -> None:
    if not BASE_CATALOG.exists():
        raise SystemExit(
            f"ERROR: No existe {BASE_CATALOG}. "
            "La carpeta debe ser data/ y debe contener base_catalog.json."
        )

    catalog = json.loads(BASE_CATALOG.read_text(encoding="utf-8"))

    movies = catalog.get("movies", [])
    series = catalog.get("series", [])

    print(f"Películas a procesar: {len(movies)}")
    print(f"Series a procesar: {len(series)}")

    movie_results: list[dict[str, Any]] = []
    for index, item in enumerate(movies, start=1):
        movie_results.append(movie_record(item))
        poster = movie_results[-1].get("poster")
        print(
            f"[PELÍCULA {index}/{len(movies)}] "
            f"{item.get('title') or item.get('name')} -> "
            f"{'OK' if poster else 'SIN PORTADA'}"
        )
        time.sleep(0.12)

    series_results: list[dict[str, Any]] = []
    for index, item in enumerate(series, start=1):
        series_results.append(series_record(item))
        print(f"[SERIE {index}/{len(series)}] {item.get('title') or item.get('name')}")
        time.sleep(0.12)

    MOVIES_OUT.write_text(
        json.dumps(movie_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    SERIES_OUT.write_text(
        json.dumps(series_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    posters_movies = sum(1 for x in movie_results if x.get("poster"))
    posters_series = sum(1 for x in series_results if x.get("poster"))

    print(f"Portadas de películas encontradas: {posters_movies}/{len(movie_results)}")
    print(f"Portadas de series encontradas: {posters_series}/{len(series_results)}")
    print("OK: catálogo TMDB generado.")


if __name__ == "__main__":
    main()
