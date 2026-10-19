#!/usr/bin/env python3
"""Собирает data/films.js — фильмы и сериалы из открытых датасетов IMDb (+ постеры и описания из TMDB).

Датасеты скачиваются с datasets.imdbws.com в data/.imdb/ (в git не попадают).

  python3 scripts/build_films.py              # база IMDb
  python3 scripts/build_films.py --wikidata   # дополнить свободными постерами из Wikidata / Wikimedia Commons
  python3 scripts/build_films.py --tmdb       # дополнить постерами и описаниями из TMDB
                                              # (нужна переменная TMDB_API_KEY)
Порог по числу оценок: --min-votes (по умолчанию 10000).
"""
import argparse, concurrent.futures as cf, gzip, html, json, os, re, sys, time, urllib.parse, urllib.request

BASE = "https://datasets.imdbws.com/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "films.js")
CACHE = os.path.join(ROOT, "data", "tmdb-cache.json")
DL = os.path.join(ROOT, "data", ".imdb")
# Wikimedia просит указывать в User-Agent, кто делает запросы
UA = {"User-Agent": "kino-na-vecher/1.0 (https://github.com/Q7N3T/kino-na-vecher-private)"}

KINDS = {"movie": None, "tvSeries": "s", "tvMiniSeries": "ms"}  # None — фильм
SKIP_GENRES = {"Talk-Show", "News"}


def skip(genres, ttype):
    """Не «кино на вечер»: ток-шоу и новости, реалити и игровые шоу (кроме сценарных, с драмой), рестлинг."""
    g = set(genres)
    if g & SKIP_GENRES:
        return True
    if g & {"Reality-TV", "Game-Show"} and "Drama" not in g:
        return True
    return ttype != "movie" and "Sport" in g and g <= {"Sport", "Action"}  # «WWE RAW» и подобные шоу

GENRES_RU = {
    "Action": "боевик", "Adventure": "приключения", "Animation": "мультфильм", "Biography": "биография",
    "Comedy": "комедия", "Crime": "криминал", "Documentary": "документальный", "Drama": "драма",
    "Family": "семейный", "Fantasy": "фэнтези", "Film-Noir": "нуар", "History": "история",
    "Horror": "ужасы", "Music": "музыка", "Musical": "мюзикл", "Mystery": "детектив",
    "Romance": "мелодрама", "Sci-Fi": "фантастика", "Sport": "спорт", "Thriller": "триллер",
    "War": "военный", "Western": "вестерн", "News": "новости", "Reality-TV": "реалити", "Talk-Show": "ток-шоу", "Game-Show": "игровое шоу",
}


def moods(g):
    """Настроения выводятся из жанров IMDb: грубо, но предсказуемо."""
    g = set(g); m = []
    if "Comedy" in g: m.append("laugh")
    if g & {"Thriller", "Horror", "Mystery", "Crime", "Action"}: m.append("nerve")
    if "War" in g or ("Drama" in g and g & {"Romance", "Family"} and "Comedy" not in g): m.append("sad")
    if g & {"Sci-Fi", "Documentary", "History", "Mystery"} or ("Drama" in g and not g & {"Comedy", "Action", "Romance"}): m.append("think")
    if g & {"Biography", "Sport", "Music", "Musical", "Adventure", "Animation"}: m.append("inspire")
    return m


def fetch(name):
    """Скачивает датасет в data/.imdb/ и проверяет целостность; свежий файл повторно не качает."""
    os.makedirs(DL, exist_ok=True)
    path = os.path.join(DL, name + ".tsv.gz")
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < 86400:
        return path
    part = path + ".part"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(BASE + name + ".tsv.gz", timeout=120) as r, open(part, "wb") as out:
                total = int(r.headers.get("Content-Length", 0))
                while chunk := r.read(1 << 20):
                    out.write(chunk)
            got = os.path.getsize(part)
            if got < total:  # прокси может молча оборвать соединение
                raise OSError(f"получено {got:,} из {total:,} байт")
            with gzip.open(part) as g:  # проверка, что архив читается до конца
                while g.read(1 << 24): pass
            os.replace(part, path)
            return path
        except (OSError, EOFError, urllib.error.URLError) as e:
            print(f"  {name}: {e}, качаю заново…", file=sys.stderr)
            time.sleep(2 ** attempt)
    sys.exit(f"Не удалось скачать {name}")


def rows(name):
    """Построчно читает скачанный .tsv.gz, отдаёт списки полей (без заголовка)."""
    t = time.time()
    with open(fetch(name), "rb") as r:
        with gzip.open(r, "rt", encoding="utf-8", newline="\n") as f:
            next(f)
            n = 0
            for line in f:
                n += 1
                yield line.rstrip("\n").split("\t")
    print(f"  {name}: {n:,} строк, {time.time()-t:.0f} с", file=sys.stderr)


def nn(v):
    return None if v == "\\N" else v


def build_imdb(min_votes):
    print("Рейтинги…", file=sys.stderr)
    rating = {r[0]: (float(r[1]), int(r[2])) for r in rows("title.ratings") if int(r[2]) >= min_votes}

    print("Названия и жанры…", file=sys.stderr)
    films = {}
    for r in rows("title.basics"):
        tid, ttype, primary, orig, adult, year, end, runtime, genres = r
        if tid not in rating or ttype not in KINDS or adult == "1" or nn(year) is None:
            continue
        if ttype == "movie" and nn(runtime) is None:
            continue
        g = nn(genres).split(",") if nn(genres) else []
        if skip(g, ttype):
            continue
        f = {"id": tid, "t": primary, "o": orig, "y": int(year), "g": g, "imdb": rating[tid][0], "v": rating[tid][1]}
        if nn(runtime): f["min"] = int(runtime)
        if KINDS[ttype]:
            f["k"] = KINDS[ttype]
            if nn(end): f["ye"] = int(end)
        films[tid] = f

    print("Серии…", file=sys.stderr)
    eps = {}
    for r in rows("title.episode"):
        eid, parent, season, _ = r
        if parent in films:
            eps[eid] = (parent, int(season) if nn(season) and season.isdigit() else None)
    # IMDb заранее заводит серии анонсированных сезонов — без даты и без оценок.
    # Вышедшей считаем серию, у которой есть оценки или год выхода раньше текущего.
    rated = {r[0] for r in rows("title.ratings") if r[0] in eps}
    year_now = time.gmtime().tm_year
    print("Даты и длительность серий…", file=sys.stderr)
    aired = {}
    for r in rows("title.basics"):
        if r[0] not in eps: continue
        parent, season = eps[r[0]]
        y = int(r[5]) if nn(r[5]) else None
        a = aired.setdefault(parent, {"ep": 0, "ep_any": 0, "ss": set(), "lens": [], "last": 0, "future": set(), "by": {}})
        if r[0] in rated or (y and y < year_now):
            a["ep_any"] += 1
            if season: a["ep"] += 1  # «серий вышло» = сумма по сезонам; серии без номера сезона (спецвыпуски) не считаем
            if season:
                a["ss"].add(season)
                b = a["by"].setdefault(season, [0, None, None])  # серий, первый и последний год
                b[0] += 1
                if y: b[1] = min(b[1] or y, y); b[2] = max(b[2] or y, y)
            if nn(r[7]): a["lens"].append(int(r[7]))
            if y: a["last"] = max(a["last"], y)
        elif season:
            a["future"].add(season)
    for tid, a in aired.items():
        f = films[tid]
        if a["ep"] or a["ep_any"]: f["ep"] = a["ep"] or a["ep_any"]  # у сериалов совсем без сезонов — все серии
        if a["ss"]: f["ss"] = len(a["ss"])
        if a["last"]: f["la"] = a["last"]  # год последней вышедшей серии
        if a["by"]: f["sx"] = [[n, *a["by"][n]] for n in sorted(a["by"])]  # по сезонам — для страницы сериала
        ann = {s for s in a["future"] if s > max(a["ss"], default=0)}
        if ann: f["ann"] = len(ann)  # анонсированные, но ещё не вышедшие сезоны
        # длительность серии в карточке сериала у IMDb бывает общей (у «Медведя» 1611 мин) —
        # надёжнее медиана по вышедшим сериям
        if len(a["lens"]) >= 3 or (a["lens"] and "min" not in f):
            l = sorted(a["lens"]); f["min"] = l[len(l) // 2]
    for tid in [t for t, f in films.items() if "min" not in f]:
        del films[tid]

    print("Русские названия…", file=sys.stderr)
    ru = {}
    for r in rows("title.akas"):
        tid, _, title, region, lang, types, _, _ = r
        if tid in films and (region == "RU" or (region == "SU" and tid not in ru)):
            # предпочитаем основное прокатное название
            if tid not in ru or types in ("imdbDisplay", "\\N"):
                ru[tid] = title
    for tid, title in ru.items():
        films[tid]["t"] = title

    print("Режиссёры…", file=sys.stderr)
    need = set()
    for r in rows("title.crew"):
        if r[0] in films and nn(r[1]) and "k" not in films[r[0]]:  # у сериалов это режиссёры отдельных серий
            films[r[0]]["d"] = r[1].split(",")[:3]
            need.update(films[r[0]]["d"])

    print("Актёры…", file=sys.stderr)
    for r in rows("title.principals"):
        tid, order, nid, cat, _, chars = r
        if tid in films and cat in ("actor", "actress", "self"):
            c = films[tid].setdefault("cast", [])
            if len(c) < 6:
                role = ""
                if nn(chars):
                    try: role = json.loads(chars)[0]
                    except Exception: pass
                c.append([nid, role])
                need.add(nid)

    print("Имена…", file=sys.stderr)
    names = {r[0]: r[1] for r in rows("name.basics") if r[0] in need}
    for f in films.values():
        f["d"] = [names[x] for x in f.get("d", []) if x in names]
        f["cast"] = [{"n": names[n], "r": role} if role else {"n": names[n]} for n, role in f.get("cast", []) if n in names]
    return films


def tmdb(films):
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        sys.exit("TMDB_API_KEY не задан")
    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding="utf-8"))
    auth = {"Authorization": "Bearer " + key} if len(key) > 40 else {}

    def api(url, q):
        if not auth: q = {**q, "api_key": key}
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url + "?" + urllib.parse.urlencode(q), headers=auth), timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504): time.sleep(2 ** attempt); continue
                return None
            except (urllib.error.URLError, OSError):
                time.sleep(2 ** attempt)
        return None

    def get(tid):
        q = {"external_source": "imdb_id", "language": "ru-RU"}
        if not auth: q["api_key"] = key
        url = f"https://api.themoviedb.org/3/find/{tid}?" + urllib.parse.urlencode(q)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=auth), timeout=30) as r:
                    j = json.load(r)
                res = j.get("movie_results") or j.get("tv_results") or []
                m = res[0] if res else {}
                v = {"p": m.get("poster_path"), "t": m.get("title") or m.get("name"), "ov": m.get("overview"), "pop": m.get("popularity")}
                if m.get("id"):
                    tv = bool(j.get("tv_results")) and not j.get("movie_results")
                    # подробности одним запросом: состав с фото, а у сериала ещё статус
                    det = api(f"https://api.themoviedb.org/3/{'tv' if tv else 'movie'}/{m['id']}",
                              {"language": "ru-RU", "append_to_response": "aggregate_credits" if tv else "credits"})
                    if det:
                        if tv:
                            v["ts"] = det.get("status")
                            nxt = det.get("next_episode_to_air") or {}
                            if nxt.get("air_date"): v["nx"] = nxt["air_date"]
                        cast = (det.get("aggregate_credits") if tv else det.get("credits") or {}) or {}
                        v["cr"] = [[c.get("name"), (c.get("roles") or [{}])[0].get("character") if tv else c.get("character"), c.get("profile_path")]
                                   for c in (cast.get("cast") or [])[:CAST]]
                    v["cv"] = CAST_VER
                return tid, v
            except urllib.error.HTTPError as e:
                if e.code == 401: sys.exit("TMDB отклонил ключ (401): проверьте TMDB_API_KEY")
                if e.code in (429, 500, 502, 503, 504): time.sleep(2 ** attempt); continue
                raise
            except (urllib.error.URLError, OSError):
                time.sleep(2 ** attempt)
        return tid, None

    # сериалы, закешированные до появления статуса, спрашиваем заново; статус меняется — раз в неделю обновляем
    # раз в неделю спрашиваем заново всё: популярность меняется каждый день, у сериалов — статус,
    # TMDB дополняет постеры и описания; в пределах недели повторный запуск берёт ответы из кеша
    week = time.strftime("%Y-%W")
    todo = [t for t in films if t not in cache or cache[t].get("cv") != CAST_VER or cache[t].get("tsd") != week]
    print(f"TMDB: {len(todo):,} запросов (в кеше {len(cache):,})", file=sys.stderr)
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (tid, v) in enumerate(ex.map(get, todo), 1):
            if v is not None:
                old = cache.get(tid) or {}
                for k in ("p", "t", "ov", "cr"):  # пустой ответ TMDB не стирает то, что было
                    if not v.get(k) and old.get(k): v[k] = old[k]
                v["tsd"] = week
                cache[tid] = v
            if i % 500 == 0:
                print(f"  {i:,}/{len(todo):,}", file=sys.stderr)
                json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    for tid, f in films.items():
        m = cache.get(tid) or {}
        if m.get("p"): f["p"] = m["p"]
        # без русского перевода TMDB отдаёт оригинальное название — тогда оставляем русское из IMDb
        if m.get("t") and (re.search("[а-яё]", m["t"], re.I) or not re.search("[а-яё]", f["t"], re.I)): f["t"] = m["t"]
        if m.get("ov"): f["syn"] = m["ov"]
        if m.get("pop"): f["pop"] = round(m["pop"], 1)  # популярность TMDB — порядок как на их сайте
        for k in ("ts", "nx", "cr"):
            f.pop(k, None)
            if m.get(k): f[k] = m[k]


def http_json(url, data=None):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers={**UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt * 3)
    sys.exit("Не удалось получить " + url[:80])


def wikidata(films):
    """Ищет по IMDb-номеру постер (P3383) или основное изображение (P18) и их лицензии на Commons."""
    ids, found = list(films), {}
    print(f"Wikidata: {len(ids):,} номеров IMDb…", file=sys.stderr)
    for i in range(0, len(ids), 400):
        values = " ".join(f'"{x}"' for x in ids[i:i + 400])
        q = f"""SELECT ?imdb ?poster ?image WHERE {{ VALUES ?imdb {{ {values} }} ?item wdt:P345 ?imdb.
                OPTIONAL {{ ?item wdt:P3383 ?poster }} OPTIONAL {{ ?item wdt:P18 ?image }} }}"""
        j = http_json("https://query.wikidata.org/sparql", urllib.parse.urlencode({"query": q, "format": "json"}).encode())
        for b in j["results"]["bindings"]:
            url, kind = (b["poster"]["value"], "poster") if "poster" in b else (b["image"]["value"], "image") if "image" in b else (None, None)
            if url and (b["imdb"]["value"] not in found or kind == "poster"):
                found[b["imdb"]["value"]] = (urllib.parse.unquote(url.rsplit("/", 1)[1]), kind)
        time.sleep(1)
    print(f"  найдено изображений: {len(found):,} (постеров: {sum(k == 'poster' for _, k in found.values()):,})", file=sys.stderr)

    # лицензия и автор каждого файла — для подписи на сайте
    files = sorted({f for f, _ in found.values()})
    meta = {}
    for i in range(0, len(files), 50):
        q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "extmetadata",
             "iiextmetadatafilter": "LicenseShortName|Artist|AttributionRequired",
             "titles": "|".join("File:" + f for f in files[i:i + 50])}
        j = http_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q))
        norm = {n["to"]: n["from"] for n in j["query"].get("normalized", [])}
        for page in j["query"]["pages"].values():
            if "imageinfo" not in page: continue
            m = page["imageinfo"][0].get("extmetadata", {})
            name = norm.get(page["title"], page["title"])[5:]
            artist = html.unescape(re.sub(r"<[^>]+>", "", m.get("Artist", {}).get("value", ""))).strip()
            meta[name.replace(" ", "_")] = meta[name] = {"l": m.get("LicenseShortName", {}).get("value", ""), "a": artist[:120]}
    for tid, (fname, kind) in found.items():
        f = films[tid]
        for k in ("w", "wk", "wl", "wa"): f.pop(k, None)
        m = meta.get(fname) or meta.get(fname.replace("_", " "))
        if not m: continue  # файл удалён с Commons
        f["w"] = fname
        if kind == "image": f["wk"] = 1  # не постер, а кадр или другое изображение
        if m["l"]: f["wl"] = m["l"]
        if m["a"]: f["wa"] = m["a"]
    print(f"  с лицензией: {sum('w' in f for f in films.values()):,}", file=sys.stderr)


SYN = os.path.join(ROOT, "data", "syn")
SYN_PARTS = 64  # описания и состав с фото лежат отдельно и грузятся только на странице фильма
CAST, CAST_VER = 10, 1  # сколько актёров брать из TMDB; версия — чтобы перезапросить кеш при изменениях
INDEX = os.path.join(ROOT, "index.html")


def syn_part(tid):
    return int(tid[2:]) % SYN_PARTS


def write(films):
    out, parts = [], [{} for _ in range(SYN_PARTS)]
    for f in sorted(films.values(), key=lambda f: (-f["v"])):
        f["m"] = moods(f["g"])
        f["genres"] = [GENRES_RU.get(x, x.lower()) for x in f.pop("g")]
        if f["o"] == f["t"]: f.pop("o")
        f.pop("hs", None)
        extra = {k: v for k, v in (("s", f.pop("syn", None)), ("c", f.pop("cr", None)), ("x", f.pop("sx", None))) if v}
        if extra:
            parts[syn_part(f["id"])][f["id"]] = extra
            f["hs"] = 1
        out.append(f)
    os.makedirs(SYN, exist_ok=True)
    for n, part in enumerate(parts):
        with open(os.path.join(SYN, f"{n:02d}.json"), "w", encoding="utf-8") as fh:
            json.dump(part, fh, ensure_ascii=False, separators=(",", ":"))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("// Сгенерировано scripts/build_films.py. Information courtesy of IMDb (https://www.imdb.com). Used with permission.\n")
        fh.write("window.FILMS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    # новая версия в адресе, чтобы браузеры не показывали старую базу из кеша
    ver = time.strftime("%Y%m%d%H%M", time.gmtime())
    if not os.path.exists(INDEX):  # старый одностраничный сайт; новый на Astro собирается из data/ сам
        return print(f"Готово: {len(out):,} фильмов, {os.path.getsize(OUT)/1e6:.1f} МБ, описаний {sum(map(len, parts)):,} → {OUT}", file=sys.stderr)
    html = open(INDEX, encoding="utf-8").read()
    html = re.sub(r'data/films\.js(\?v=\w+)?"', f'data/films.js?v={ver}"', html, count=1)
    html = re.sub(r'const DATA_VER = "\w*"', f'const DATA_VER = "{ver}"', html, count=1)
    open(INDEX, "w", encoding="utf-8").write(html)
    print(f"Готово: {len(out):,} фильмов, {os.path.getsize(OUT)/1e6:.1f} МБ, описаний {sum(map(len, parts)):,} → {OUT}", file=sys.stderr)


def load_existing():
    s = open(OUT, encoding="utf-8").read()
    arr = json.loads(s[s.index("["):s.rindex("]") + 1])
    rev = {v: k for k, v in GENRES_RU.items()}
    syn = {}
    for n in range(SYN_PARTS):
        path = os.path.join(SYN, f"{n:02d}.json")
        if os.path.exists(path): syn.update(json.load(open(path, encoding="utf-8")))
    films = {}
    for f in arr:
        f["g"] = [rev.get(x, x) for x in f.pop("genres")]
        f.pop("m", None)
        f.setdefault("o", f["t"])
        x = syn.get(f["id"]) if f.pop("hs", None) else None
        if isinstance(x, str): x = {"s": x}  # старый формат: только описание
        if x and x.get("s"): f["syn"] = x["s"]
        if x and x.get("c"): f["cr"] = x["c"]
        if x and x.get("x"): f["sx"] = x["x"]
        films[f["id"]] = f
    return films


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-votes", type=int, default=10000)
    ap.add_argument("--tmdb", action="store_true", help="дополнить уже собранную базу данными TMDB")
    ap.add_argument("--wikidata", action="store_true", help="дополнить уже собранную базу изображениями из Wikidata")
    a = ap.parse_args()
    if a.tmdb or a.wikidata:
        films = load_existing()
        if a.wikidata: wikidata(films)
        if a.tmdb: tmdb(films)
    else:
        films = build_imdb(a.min_votes)
    write(films)
