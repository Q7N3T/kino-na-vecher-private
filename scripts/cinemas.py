"""Прямые ссылки на страницы фильмов в онлайн-кинотеатрах — из их открытых карт сайта (sitemap).

Кинотеатры не дают номеров IMDb, поэтому сопоставляем по названию: адрес страницы — это название
латиницей (start.ru/watch/holop-3, kinoflex.ru/movie/thesopranos). Одинаковых названий много
(ремейки, тёзки), поэтому кандидата проверяем по году на самой странице; проверенные страницы
запоминаются в data/cinema-cache.json, чтобы не открывать их заново каждую неделю.

Работает только оттуда, где сайты кинотеатров открываются (GitHub Actions). Okko, Wink и More.tv
из-за границы закрыты, у Premier в карте сайта только подборки, Амедиатека не пускает роботов.
"""
import concurrent.futures as cf, datetime, gzip, json, os, re, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "cinema-cache.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; kino-na-vecher/1.0; +https://github.com/Q7N3T/kino-na-vecher-private)"}
PER_RUN = 1500  # сколько страниц проверять за запуск на кинотеатр — остальное в следующие недели
RECHECK = 30  # через сколько дней проверять страницу снова: фильмы приходят и уходят, страница может стать 404
MINUTES = 8  # не дольше стольких минут на кинотеатр за запуск: остальное — в следующие запуски

# key: карта сайта (индекс или список), какие дочерние карты брать, какие адреса — страницы тайтлов,
# как найти год на странице. by: "o" — адрес из оригинального названия, "t" — из русского.
# guess — адреса, которые пробуем для каждого тайтла базы, даже если их нет в карте сайта (у FLEX
# в карте сайта не всё: kinoflex.ru/movie/wednesday открывается, а в карте его нет); страница
# должна открыться (не 404) и показать тот же год. strict — переадресация значит «страницы нет»
# (у FLEX так; Иви же переадресует настоящие страницы на основной адрес).
# Свой способ писать по-русски латиницей у каждого кинотеатра — по адресам из их карт сайта:
# Иви: ivi.ru/watch/ya-znayu-tvoi-sekretyi, voskresshij-ertugrul, ya-tebya-nashyol;
# KION: kion.ru/film/krovnyj-otets, 8-zhenschin, esche-vchera; Start: start.ru/watch/tvoe-serdce-budet-razbito.
IVI = {"й": "j", "ы": "yi", "ё": "yo", "ц": "ts", "щ": "sch"}
KION = {"й": "j", "ы": "y", "ё": "e", "ц": "ts", "щ": "sch"}
START = {"й": "y", "ы": "y", "ё": "e", "ц": "c", "щ": "sch"}
PREMIER = KION  # premier.one/show/dvojnaya-zhizn-mi, 16-let-i-9-mesyatsev, holop


def slug(title, scheme):
    """Название → адрес по способу кинотеатра: «Дом ада 2. Отель «Абаддон»» → dom-ada-2-otel-abaddon."""
    s = "".join(scheme.get(c, RU.get(c, c)) if c not in "ьъ" else "" for c in title.lower())
    return re.sub(r"[^a-z0-9]+", "-", s.replace("-", " ")).strip("-")


ru = lambda f: bool(re.search(r"[а-яё]", f["t"], re.I))
SITES = {
    "flex": dict(maps=["https://kinoflex.ru/sitemap-film.xml", "https://kinoflex.ru/sitemap-serial.xml"],
                 page=r"^(https://kinoflex\.ru/movie/[^/?#]+)", by="o", strict=True,
                 guess=lambda f: [f"https://kinoflex.ru/movie/{key_of(f, 'o')}"],
                 per_run=20000, read=60_000, ver=2,
                 # «Сериал Уэнсдэй 2022–2025 — смотреть…»: годы — все в заголовке, кроме названия
                 year=r"<title>[^<]*?((?:(?:19|20)\d\d\D{0,3})+)—[^<]*</title>"),
    "ivi": dict(maps=["https://www.ivi.ru/sitemap.xml"], kids=r"sitemap-watch-", ver=2,
                page=r"^(https://www\.ivi\.ru/watch/(?!\d+(?:/|$))[^/?#]+)", by="t", per_run=6000,
                guess=lambda f: [f"https://www.ivi.ru/watch/{slug(f['t'], IVI)}"] if ru(f) else [],
                year=r'og:title" content="[^"]*?((?:19|20)\d\d)\)'),
    "start": dict(maps=["https://start.ru/sitemap.xml"], kids=r"/(movies|series|animation)\.xml",
                  page=r"^(https://start\.ru/watch/[^/?#]+)", by="t", per_run=6000,
                  guess=lambda f: [f"https://start.ru/watch/{slug(f['t'], START)}"] if ru(f) else [],
                  year=r'"year":((?:19|20)\d\d)'),
    "kion": dict(maps=["https://kion.ru/sitemapIndex.xml"], kids=r"sitemap\d+\.xml",
                 page=r"^(https://kion\.ru/(?:film|serial)/[^/?#]+)", by="t", per_run=6000,
                 guess=lambda f: [f"https://kion.ru/{'serial' if f.get('k') else 'film'}/{slug(f['t'], KION)}"] if ru(f) else [],
                 year=r'"releaseYear":((?:19|20)\d\d)'),
    # в карте сайта Premier — только подборки; страницы тайтлов (и фильмов) — premier.one/show/<название>,
    # несуществующая — 404; год — в заголовке «Холоп (2019, фильм)», у сериалов — в данных страницы
    "premier": dict(maps=[], page=r"^(https://premier\.one/show/[^/?#]+)", by="t", per_run=6000,
                    guess=lambda f: [f"https://premier.one/show/{slug(f['t'], PREMIER)}"] if ru(f) else [],
                    year=r'<title>[^<]*?\(((?:19|20)\d\d)|"(?:year|releaseYear|productionYear)"\s*:\s*"?((?:19|20)\d\d)'),
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


def page_years(html, year_re):
    """Годы со страницы: один или диапазон, как у сериалов («2022–2025»); [] — года нет."""
    m = re.search(year_re, html)  # у regex может быть несколько вариантов — берём сработавший
    return sorted({int(y) for y in re.findall(r"(?:19|20)\d\d", next(g for g in m.groups() if g))}) if m else []


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
    """Привязать страницу к фильму, чей год есть на странице (±1: у кинотеатров бывает год премьеры
    в России). Несколько подходят — берём точный год; года на странице нет — страницу пропускаем."""
    links = {}
    for u in sorted(cands):
        ys = years.get(u) or []
        hit = [f for f in cands[u] if any(abs(f["y"] - y) <= 1 for y in ys)]
        if len(hit) > 1: hit = [f for f in hit if f["y"] in ys]
        if len(hit) == 1: links.setdefault(hit[0]["id"], u)
    return links


def get(url, limit=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read(limit) if limit else r.read()
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    return b.decode("utf-8", "replace")


def check_page(url, site):
    """Годы со страницы; [] — страницы нет (404, переадресация на другую страницу, нет года — пустая
    заглушка); None — сайт не ответил, проверим в следующий раз."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            # угаданный адрес, переадресованный в другое место, — страницы нет; адрес из карты сайта
            # кинотеатр вправе переадресовать на свой основной (Иви так и делает)
            if site.get("strict") and r.url.rstrip("/") != url.rstrip("/"): return []
            b = r.read(site.get("read", 400_000))
    except urllib.error.HTTPError as e:
        return [] if e.code in (404, 410) else None
    except Exception:
        return None
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    return page_years(b.decode("utf-8", "replace"), site["year"])


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
    # старые форматы: только год; год числом, а не списком лет
    cache = {u: v if isinstance(v, list) else [v, today] for u, v in cache.items()}
    for v in cache.values():
        if isinstance(v[0], int): v[0] = [v[0]] if v[0] else []
    for name, site in SITES.items():
        try:
            pages = title_pages(sitemap(site), site["page"])
        except Exception as e:
            print(f"  {name}: карта сайта не открылась ({e}) — в этот раз без его ссылок", file=sys.stderr)
            continue
        listed = len(pages)
        if site.get("guess"):
            pages |= {u for f in films.values() for u in site["guess"](f) if len(url_key(u, site["by"])) >= 3}
        cands = candidates(films, pages, site["by"])
        # кеш: адрес → [годы со страницы, когда проверено, версия]; сначала непроверенные, потом самые давние
        # ver — версия проверки у кинотеатра: поменялась — проверяем его страницы заново
        ver = site.get("ver", 1)
        age = lambda u: today - cache[u][1] if u in cache and (cache[u][2:] or [1])[0] == ver else 10**6
        # среди одинаково давних — сначала популярное: за первые запуски проверяется то, что смотрят
        pop = lambda u: max(f.get("pop", 0) for f in cands[u])
        todo = sorted((u for u in cands if age(u) >= RECHECK), key=lambda u: (age(u), pop(u)), reverse=True)[:site.get("per_run", PER_RUN)]
        stop, done = time.monotonic() + MINUTES * 60, 0
        ex = cf.ThreadPoolExecutor(8)
        try:
            for u, y in zip(todo, ex.map(lambda u: check_page(u, site), todo)):
                if y is not None: cache[u] = [y, today, ver]
                done += 1
                if time.monotonic() > stop: break  # время вышло — остальное в следующий раз
        finally:
            ex.shutdown(wait=True, cancel_futures=True)
        save(cache)  # после каждого кинотеатра: оборвётся запуск — проверенное не пропадёт
        links = assign(cands, {u: cache[u][0] for u in cands if age(u) < 10**6})
        for f in films.values():
            ln = f.setdefault("ln", {})
            ln.pop(name, None)
            if f["id"] in links: ln[name] = links[f["id"]]
        print(f"  {name}: в карте сайта {listed:,}, адресов к проверке {len(cands):,}, "
              f"проверено сейчас {done:,} из {len(todo):,}, ссылок {len(links):,}", file=sys.stderr)
    for f in films.values():
        if not f.get("ln"): f.pop("ln", None)
    save(cache)


def save(cache):
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, separators=(",", ":"))


def explain(url):
    """Почему адрес прошёл или не прошёл проверку: ответ сайта, конечный адрес, заголовок, годы."""
    name = next((n for n, s in SITES.items() if re.match(s["page"], url)), None)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            code, final, html = r.status, r.url, r.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, final, html = e.code, url, ""
    except Exception as e:
        return print(url, "не открылся:", e)
    title = (re.search(r"<title>[^<]*</title>", html) or [""])[0]
    print(url, f"→ {code} {final if final != url else ''}", title, "| годы:", page_years(html, SITES[name]["year"]) if name else "—",
          "| проверка:", check_page(url, SITES[name]) if name else "—")


if __name__ == "__main__":
    if sys.argv[1:]:  # python3 scripts/cinemas.py <адрес>… — разобрать отдельные адреса, базу не трогать;
        # find:<слово> — найти адреса со словом в картах сайта кинотеатров
        for u in sys.argv[1:]:
            if u.startswith("find:"):
                for name, site in SITES.items():
                    try: hits = sorted(p for p in title_pages(sitemap(site), site["page"]) if u[5:].lower() in p.lower())
                    except Exception as e: hits = [f"карта сайта не открылась: {e}"]
                    print(name, u[5:], "→", *hits[:15])
            else: explain(u)
        sys.exit()
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
    for name, u in (("premier", "https://premier.one/show/fizruk"), ("premier", "https://premier.one/show/holop"),
                    ("kion", "https://kion.ru/serial/rim"), ("ivi", "https://www.ivi.ru/watch/pchelovod")):
        print(u, check_page(u, SITES[name]))
    for t in ("Уэнздей", "Сопрано", "Друзья", "Пчеловод", "Крёстный отец", "Физрук", "Слово пацана. Кровь на асфальте"):
        print(t, [(f["y"], f.get("ln")) for f in films.values() if f["t"] == t])
