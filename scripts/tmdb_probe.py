"""Разбор обложек: python3 scripts/tmdb_probe.py tt0084988 tt0088484 …
Для каждого тайтла: обложка в базе и открывается ли она (TMDB напрямую и через wsrv), что TMDB
отвечает на номер IMDb, а если это сезон шоу — обложки шоу и всех его сезонов. Нужен TMDB_API_KEY."""
import json, os, sys, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from build_films import load_existing  # noqa: E402

key = os.environ["TMDB_API_KEY"]
auth = {"Authorization": "Bearer " + key} if len(key) > 40 else {}


def api(path, **q):
    if not auth: q["api_key"] = key
    url = f"https://api.themoviedb.org/3/{path}?" + urllib.parse.urlencode({"language": "ru-RU", **q})
    with urllib.request.urlopen(urllib.request.Request(url, headers=auth), timeout=30) as r:
        return json.load(r)


def status(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "kino-na-vecher/1.0"}), timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return str(e)


def poster(p):
    tmdb = f"https://image.tmdb.org/t/p/w342{p}"
    return f"{p}: TMDB {status(tmdb)}, wsrv {status('https://wsrv.nl/?url=' + urllib.parse.quote(tmdb, safe='') + '&w=342&output=webp')}"


films = load_existing()
for tid in sys.argv[1:]:
    f = films.get(tid, {})
    print(f"\n== {tid} «{f.get('t')}» / {f.get('o')} {f.get('y')}")
    print("  в базе:", poster(f["p"]) if f.get("p") else "обложки нет")
    j = api(f"find/{tid}", external_source="imdb_id")
    print("  find:", {k: [(x.get("id"), x.get("name") or x.get("title"), x.get("poster_path"), x.get("season_number")) for x in v] for k, v in j.items() if v})
    show = next((x.get("show_id") or x.get("id") for x in j.get("tv_season_results", []) + j.get("tv_results", [])), None)
    if not show:
        for r in api("search/tv", query=f.get("o") or f.get("t") or tid).get("results", [])[:3]:
            print("  search/tv:", r["id"], r.get("name"), r.get("first_air_date"), r.get("poster_path"))
            show = show or r["id"]
    if show:
        d = api(f"tv/{show}")
        print(f"  шоу {show} «{d.get('name')}»:", poster(d["poster_path"]) if d.get("poster_path") else "без обложки")
        for s in d.get("seasons", []):
            print(f"    сезон {s.get('season_number')} {s.get('air_date')}:", poster(s["poster_path"]) if s.get("poster_path") else "без обложки")
