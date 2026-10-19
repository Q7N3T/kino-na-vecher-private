#!/usr/bin/env python3
"""Собирает data/films.js — фильмы и сериалы из открытых датасетов IMDb (+ постеры и описания из TMDB).

Датасеты скачиваются с datasets.imdbws.com в data/.imdb/ (в git не попадают).

  python3 scripts/build_films.py              # база IMDb
  python3 scripts/build_films.py --tmdb       # дополнить постерами и описаниями из TMDB
                                              # (нужна переменная TMDB_API_KEY)
Порог по числу оценок: --min-votes (по умолчанию 10000).
"""
import argparse, concurrent.futures as cf, gzip, json, os, sys, time, urllib.parse, urllib.request

BASE = "https://datasets.imdbws.com/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "films.js")
CACHE = os.path.join(ROOT, "data", "tmdb-cache.json")
DL = os.path.join(ROOT, "data", ".imdb")

KINDS = {"movie": None, "tvSeries": "s", "tvMiniSeries": "ms"}  # None — фильм

GENRES_RU = {
    "Action": "боевик", "Adventure": "приключения", "Animation": "мультфильм", "Biography": "биография",
    "Comedy": "комедия", "Crime": "криминал", "Documentary": "документальный", "Drama": "драма",
    "Family": "семейный", "Fantasy": "фэнтези", "Film-Noir": "нуар", "History": "история",
    "Horror": "ужасы", "Music": "музыка", "Musical": "мюзикл", "Mystery": "детектив",
    "Romance": "мелодрама", "Sci-Fi": "фантастика", "Sport": "спорт", "Thriller": "триллер",
    "War": "военный", "Western": "вестерн", "News": "новости", "Reality-TV": "реалити", "Talk-Show": "ток-шоу",
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
        f = {"id": tid, "t": primary, "o": orig, "y": int(year), "g": g, "imdb": rating[tid][0], "v": rating[tid][1]}
        if nn(runtime): f["min"] = int(runtime)
        if KINDS[ttype]:
            f["k"] = KINDS[ttype]
            if nn(end): f["ye"] = int(end)
        films[tid] = f

    print("Серии…", file=sys.stderr)
    seasons, eps = {}, {}
    for r in rows("title.episode"):
        eid, parent, season, _ = r
        if parent in films:
            films[parent]["ep"] = films[parent].get("ep", 0) + 1
            if nn(season): seasons.setdefault(parent, set()).add(season)
            if "min" not in films[parent]: eps[eid] = parent
    for tid, ss in seasons.items():
        films[tid]["ss"] = len(ss)
    if eps:
        # у части сериалов длительность не указана — берём медиану по их сериям
        print("Длительность серий…", file=sys.stderr)
        lens = {}
        for r in rows("title.basics"):
            if r[0] in eps and nn(r[7]):
                lens.setdefault(eps[r[0]], []).append(int(r[7]))
        for tid, l in lens.items():
            films[tid]["min"] = sorted(l)[len(l) // 2]
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
                return tid, {"p": m.get("poster_path"), "t": m.get("title") or m.get("name"), "ov": m.get("overview")}
            except urllib.error.HTTPError as e:
                if e.code == 429: time.sleep(2 ** attempt); continue
                raise
        return tid, None

    todo = [t for t in films if t not in cache]
    print(f"TMDB: {len(todo):,} запросов (в кеше {len(cache):,})", file=sys.stderr)
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (tid, v) in enumerate(ex.map(get, todo), 1):
            if v is not None: cache[tid] = v
            if i % 500 == 0:
                print(f"  {i:,}/{len(todo):,}", file=sys.stderr)
                json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    for tid, f in films.items():
        m = cache.get(tid) or {}
        if m.get("p"): f["p"] = m["p"]
        if m.get("t"): f["t"] = m["t"]
        if m.get("ov"): f["syn"] = m["ov"]


def write(films):
    out = []
    for f in sorted(films.values(), key=lambda f: (-f["v"])):
        f["m"] = moods(f["g"])
        f["genres"] = [GENRES_RU.get(x, x.lower()) for x in f.pop("g")]
        if f["o"] == f["t"]: f.pop("o")
        out.append(f)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("// Сгенерировано scripts/build_films.py. Information courtesy of IMDb (https://www.imdb.com). Used with permission.\n")
        fh.write("window.FILMS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"Готово: {len(out):,} фильмов, {os.path.getsize(OUT)/1e6:.1f} МБ → {OUT}", file=sys.stderr)


def load_existing():
    s = open(OUT, encoding="utf-8").read()
    arr = json.loads(s[s.index("["):s.rindex("]") + 1])
    rev = {v: k for k, v in GENRES_RU.items()}
    films = {}
    for f in arr:
        f["g"] = [rev.get(x, x) for x in f.pop("genres")]
        f.pop("m", None)
        f.setdefault("o", f["t"])
        films[f["id"]] = f
    return films


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-votes", type=int, default=10000)
    ap.add_argument("--tmdb", action="store_true", help="дополнить уже собранную базу данными TMDB")
    a = ap.parse_args()
    if a.tmdb:
        films = load_existing(); tmdb(films)
    else:
        films = build_imdb(a.min_votes)
    write(films)
