"""Прямые ссылки на страницы фильмов в онлайн-кинотеатрах — из их открытых карт сайта (sitemap).

Кинотеатры не дают номеров IMDb, поэтому сопоставляем по названию: адрес страницы — это название
латиницей (start.ru/watch/holop-3, kinoflex.ru/movie/thesopranos). Одинаковых названий много
(ремейки, тёзки), поэтому кандидата проверяем по году на самой странице; проверенные страницы
запоминаются в data/cinema-cache.json, чтобы не открывать их заново каждую неделю.

Работает только оттуда, где сайты кинотеатров открываются (GitHub Actions). Okko, Wink и More.tv
из-за границы закрыты, у Premier в карте сайта только подборки, Амедиатека не пускает роботов.
"""
import concurrent.futures as cf, datetime, gzip, json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cinema-cache.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; kino-na-vecher/1.0; +https://github.com/Q7N3T/kino-na-vecher-private)"}
PER_RUN = 1500  # сколько страниц проверять за запуск на кинотеатр — остальное в следующие недели
RECHECK = 30  # через сколько дней проверять страницу снова: фильмы приходят и уходят, страница может стать 404

# key: карта сайта (индекс или список), какие дочерние карты брать, какие адреса — страницы тайтлов,
# как найти год на странице. by: "o" — адрес из оригинального названия, "t" — из русского.
# guess — адрес, который пробуем для каждого тайтла базы, даже если его нет в карте сайта (у FLEX
# в карте сайта не всё: kinoflex.ru/movie/wednesday открывается, а в карте его нет).
SITES = {
    "flex": dict(maps=["https://kinoflex.ru/sitemap-film.xml", "https://kinoflex.ru/sitemap-serial.xml"],
                 page=r"^(https://kinoflex\.ru/movie/[^/?#]+)", by="o", guess="https://kinoflex.ru/movie/{}",
                 per_run=20000, read=60_000,
                 year=r"<title>[^<]*\b((?:19|20)\d\d)\s+—[^<]*</title>"),
    "ivi": dict(maps=["https://www.ivi.ru/sitemap.xml"], kids=r"sitemap-watch-", ver=2,
                page=r"^(https://www\.ivi\.ru/watch/(?!\d+(?:/|$))[^/?#]+)", by="t",
                year=r'og:title" content="[^"]*?((?:19|20)\d\d)\)'),
    "start": dict(maps=["https://start.ru/sitemap.xml"], kids=r"/(movies|series|animation)\.xml",
                  page=r"^(https://start\.ru/watch/[^/?#]+)", by="t", year=r'"year":((?:19|20)\d\d)'),
    "kion": dict(maps=["https://kion.ru/sitemapIndex.xml"], kids=r"sitemap\d+\.xml",
                 page=r"^(https://kion\.ru/(?:film|serial)/[^/?#]+)", by="t", year=r'"releaseYear":((?:19|20)\d\d)'),
}

RU = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
              "a b v g d e e zh z i y k l m n o p r s t u f h ts ch sh sch - y - e yu ya".split()))
# разные кинотеатры пишут латиницей по-разному (й → y/j/i, ц → ts/c/cz, ы → y/yi): сводим к одному
LOOSE = [("shch", "s"), ("sch", "s"), ("shh", "s"), ("sh", "s"), ("ch", "c"), ("zh", "z"), ("kh", "h"),
         ("ts", "c"), ("cz", "c"), ("yo", "e"), ("jo", "e"), ("yu", "u"), ("ju", "u"), ("iu", "u"),
         ("ya", "a"), ("ja", "a"), ("ia", "a"), ("yi", "i"), ("ij", "i"), ("iy", "i"), ("yy", "i"),
         ("y", "i"), ("j", "i"), ("x", "ks")]


def loose(latin):
    s = re.sub(r"[^a-z0-9]", "", latin.lower())
    for a, b in LOOSE: s = s.replace(a, b)
    return s


def translit(ru):
    return "".join(RU.get(c, c if c.isascii() else "") for c in ru.lower().replace("-", " ")).replace("-", "")


def key_of(f, by):
    if by == "o":  # FLEX: оригинальное название латиницей без пробелов и знаков — точно, без «примерно»
        return re.sub(r"[^a-z0-9]", "", (f.get("o") or f["t"]).lower())
    return loose(translit(f["t"])) if re.search(r"[а-яё]", f["t"], re.I) else ""


def url_key(url, by):
    tail = url.rstrip("/").rsplit("/", 1)[1]
    return tail.lower() if by == "o" else loose(tail)


def title_pages(urls, page_re):
    """Адреса страниц тайтлов из всех адресов карты (серии, трейлеры, актёры → страница тайтла)."""
    out = set()
    for u in urls:
        m = re.match(page_re, u)
        if m: out.add(m.group(1))
    return out


def page_year(html, year_re):
    m = re.search(year_re, html)
    return int(m.group(1)) if m else 0


def candidates(films, pages, by):
    """{адрес страницы: [фильмы с тем же названием]} — без проверки года."""
    idx = {}
    for f in films.values():
        k = key_of(f, by)
        if len(k) >= 3: idx.setdefault(k, []).append(f)
    out = {}
    for u in pages:
        fs = idx.get(url_key(u, by))
        if fs: out[u] = fs
    return out


def assign(cands, years):
    """Привязать страницу к фильму, чей год совпал с годом на странице (±1: у кинотеатров бывает год
    премьеры в России). Несколько подходят — берём точный год; год не нашёлся — страницу пропускаем."""
    links = {}
    for u in sorted(cands):
        y = years.get(u)
        if not y: continue
        hit = [f for f in cands[u] if abs(f["y"] - y) <= 1]
        if len(hit) > 1: hit = [f for f in hit if f["y"] == y]
        if len(hit) == 1: links.setdefault(hit[0]["id"], u)
    return links


def get(url, limit=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read(limit) if limit else r.read()
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    return b.decode("utf-8", "replace")


def check_page(url, site):
    """Год со страницы; 0 — страницы нет (404, переадресация на другую страницу, нет года — пустая
    заглушка); None — сайт не ответил, проверим в следующий раз."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            # угаданный адрес, переадресованный в другое место, — страницы нет; адрес из карты сайта
            # кинотеатр вправе переадресовать на свой основной (Иви так и делает)
            if site.get("guess") and r.url.rstrip("/") != url.rstrip("/"): return 0
            b = r.read(site.get("read", 400_000))
    except urllib.error.HTTPError as e:
        return 0 if e.code in (404, 410) else None
    except Exception:
        return None
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    return page_year(b.decode("utf-8", "replace"), site["year"])


def sitemap(site):
    locs = lambda t: re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", t)
    out = []
    for m in site["maps"]:
        t = get(m)
        if "<sitemapindex" in t:
            for k in locs(t):
                if re.search(site.get("kids", "."), k): out += locs(get(k))
        else:
            out += locs(t)
    return out


def cinema_links(films):
    """Пишет f["ln"] = {кинотеатр: адрес страницы}. Кинотеатр не ответил — в этот раз без его ссылок."""
    try: cache = json.load(open(CACHE, encoding="utf-8"))
    except (OSError, ValueError): cache = {}
    today = datetime.date.today().toordinal()
    cache = {u: v if isinstance(v, list) else [v, today] for u, v in cache.items()}  # старый формат: только год
    for name, site in SITES.items():
        try:
            pages = title_pages(sitemap(site), site["page"])
        except Exception as e:
            print(f"  {name}: карта сайта не открылась ({e}) — в этот раз без его ссылок", file=sys.stderr)
            continue
        listed = len(pages)
        if site.get("guess"):
            pages |= {site["guess"].format(k) for f in films.values() if len(k := key_of(f, site["by"])) >= 3}
        cands = candidates(films, pages, site["by"])
        # кеш: адрес → [год или 0, когда проверено, версия]; сначала непроверенные, потом самые давние
        # ver — версия проверки у кинотеатра: поменялась — проверяем его страницы заново
        ver = site.get("ver", 1)
        age = lambda u: today - cache[u][1] if u in cache and (cache[u][2:] or [1])[0] == ver else 10**6
        todo = sorted((u for u in cands if age(u) >= RECHECK), key=age, reverse=True)[:site.get("per_run", PER_RUN)]
        with cf.ThreadPoolExecutor(8) as ex:
            for u, y in zip(todo, ex.map(lambda u: check_page(u, site), todo)):
                if y is not None: cache[u] = [y, today, ver]
        links = assign(cands, {u: cache[u][0] for u in cands if age(u) < 10**6})
        for f in films.values():
            ln = f.setdefault("ln", {})
            ln.pop(name, None)
            if f["id"] in links: ln[name] = links[f["id"]]
        print(f"  {name}: в карте сайта {listed:,}, адресов к проверке {len(cands):,}, "
              f"проверено сейчас {len(todo):,}, ссылок {len(links):,}", file=sys.stderr)
    for f in films.values():
        if not f.get("ln"): f.pop("ln", None)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    # пробный запуск на нынешней базе: сколько ссылок нашлось и примеры — базу не меняет
    import random
    from build_films import load_existing
    films = load_existing()
    cinema_links(films)
    random.seed(1)
    for name in SITES:
        got = [(f["t"], f["y"], f["ln"][name]) for f in films.values() if name in f.get("ln", {})]
        print(f"{name}: {len(got)}")
        for row in random.sample(got, min(15, len(got))): print("   ", *row)
    for t in ("Уэнсдэй", "Сопрано", "Друзья", "Пчеловод", "Крёстный отец"):
        print(t, [(f["y"], f.get("ln")) for f in films.values() if f["t"] == t])
