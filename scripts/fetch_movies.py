#!/usr/bin/env python3
"""Fetch 20 popular movies from TMDB and write to data/movies.yaml.

Requires TMDB_KEY environment variable.
"""

import sys
import os
import urllib.request
import json
import yaml

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "movies.yaml")


def main():
    api_key = os.environ.get("TMDB_KEY")
    if not api_key:
        print(
            "ERROR: TMDB_KEY environment variable is not set.\n"
            "Get a free API key at https://www.themoviedb.org/settings/api\n"
            "Then run: TMDB_KEY=your_key python3 scripts/fetch_movies.py",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"https://api.themoviedb.org/3/movie/popular?api_key={api_key}&language=en-US&page=1"
    print("Fetching popular movies from TMDB...")

    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    results = data.get("results", [])[:20]
    movies = []

    for m in results:
        release = m.get("release_date", "")
        year = release[:4] if release else ""
        movies.append({
            "title": m.get("title", ""),
            "year": year,
            "overview": m.get("overview", ""),
            "poster_path": m.get("poster_path", ""),
            "tmdb_id": m.get("id"),
            "vote_average": m.get("vote_average"),
        })

    out_path = os.path.normpath(DATA_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(movies, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"Wrote {len(movies)} movies to {out_path}")


if __name__ == "__main__":
    main()
