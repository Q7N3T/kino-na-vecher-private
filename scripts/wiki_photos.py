"""Фото актёров из Wikidata (P18 — изображение на Wikimedia Commons, свободные лицензии) — тем,
у кого фото нет в TMDB. Актёр ищется по номеру IMDb (P345), а не по имени: тёзок не путаем.

Номера IMDb актёров сохраняет сборка базы из IMDb (data/.imdb/people.json, в git не попадает);
без этого файла шаг пропускается.
"""
import hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEOPLE = os.path.join(ROOT, "data", ".imdb", "people.json")
UA = {"User-Agent": "kino-na-vecher/1.0 (https://github.com/Q7N3T/kino-na-vecher-private)"}
WIDTH = 400  # px по ширине: хватает на круг 200 px на экранах с двойной плотностью


def query(ids):
    values = " ".join(f'"{x}"' for x in ids)
    return f"SELECT ?imdb ?img WHERE {{ VALUES ?imdb {{ {values} }} ?item wdt:P345 ?imdb; wdt:P18 ?img. }}"


def thumb(file_url):
    """Commons отдаёт Special:FilePath/<имя>; уменьшенная копия лежит по адресу из md5 имени файла.
    Только снимки (jpg, png, webp): у svg и tif уменьшенные копии устроены иначе."""
    name = urllib.parse.unquote(file_url.rsplit("/", 1)[1]).replace(" ", "_")
    if not re.search(r"\.(jpe?g|png|webp)$", name, re.I): return None
    h = hashlib.md5(name.encode()).hexdigest()
    q = urllib.parse.quote(name)
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/{WIDTH}px-{q}"


def parse(ans):
    out = {}
    for row in ans.get("results", {}).get("bindings", []):
        url = thumb(row["img"]["value"])
        if url: out.setdefault(row["imdb"]["value"], url)
    return out


def missing(films):
    """Имена актёров, у которых фото нет ни в одном тайтле базы."""
    has, need = set(), set()
    for f in films.values():
        crew = f.get("cr") or [[c["n"], c.get("r"), None] for c in f.get("cast", [])]
        for n, _, p in crew:
            (has if p else need).add(n)
    return need - has


def apply(films, photos):
    """photos: имя → адрес фото. Ставит фото тем, у кого его нет; состав из IMDb (без cr) становится
    составом с фото — так он и показывается на странице."""
    n = 0
    for f in films.values():
        crew = f.get("cr") or [[c["n"], c.get("r") or "", None] for c in f.get("cast", [])]
        new = [[name, r, p or photos.get(name)] for name, r, p in crew]
        if new != crew:
            n += sum(1 for a, b in zip(crew, new) if a[2] != b[2])
            f["cr"] = new
    return n


def wiki_photos(films):
    try: people = json.load(open(PEOPLE, encoding="utf-8"))  # имя → номер IMDb (тёзки — null)
    except (OSError, ValueError):
        print("  Wikidata: нет data/.imdb/people.json — фото не добираем", file=sys.stderr)
        return
    names = [n for n in missing(films) if people.get(n)]
    by_id = {people[n]: n for n in names}
    ids, found = list(by_id), {}
    for i in range(0, len(ids), 250):
        body = urllib.parse.urlencode({"query": query(ids[i:i + 250]), "format": "json"}).encode()
        for attempt in range(4):
            try:
                req = urllib.request.Request("https://query.wikidata.org/sparql", data=body,
                                             headers={**UA, "Accept": "application/sparql-results+json"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    found.update(parse(json.load(r)))
                break
            except (urllib.error.URLError, OSError, ValueError) as e:
                if attempt == 3:
                    print(f"  Wikidata не ответила ({e}) — в этот раз без фото из Wikidata", file=sys.stderr)
                    return
                time.sleep(2 ** attempt * 3)
    n = apply(films, {by_id[i]: url for i, url in found.items()})
    print(f"Wikidata: без фото {len(names):,} актёров с номером IMDb, фото нашлось у {len(found):,} "
          f"(мест в составах: {n:,})", file=sys.stderr)
