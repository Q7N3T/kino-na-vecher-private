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
# адреса, которых не угадать и нет в карте сайта (kinoflex.ru/movie/rickandmortysndk): {номер IMDb: {кинотеатр: адрес}};
# страница всё равно проверяется — открылась ли и какие на ней сезоны, — а год не сверяется: адрес дан вручную
MANUAL = os.path.join(ROOT, "data", "cinema-links.json")
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
# у части тайтлов FLEX адрес — русское название паспортной транслитерацией, слитно:
# prikliucheniiadevymerian («Приключения девы Мэриан»), vremiaprikliucheniifionnaikeik
FLEX_RU = {"й": "i", "ы": "y", "ё": "e", "ц": "ts", "щ": "shch", "х": "kh", "ю": "iu", "я": "ia", "ъ": "ie"}


def slug(title, scheme):
    """Название → адрес по способу кинотеатра: «Дом ада 2. Отель «Абаддон»» → dom-ada-2-otel-abaddon."""
    s = "".join(scheme.get(c, RU.get(c, c)) if c not in "ьъ" else "" for c in title.lower())
    return re.sub(r"[^a-z0-9]+", "-", s.replace("-", " ")).strip("-")


ru = lambda f: bool(re.search(r"[а-яё]", f["t"], re.I))
SITES = {
    # у FLEX, кроме фильмов и сериалов, — раздел сезонов: часть сериалов есть только там
    "flex": dict(maps=["https://kinoflex.ru/sitemap.xml"], kids=r"sitemap-(film|serial|season)",
                 page=r"^(https://kinoflex\.ru/movie/[^/?#]+)", by="o", strict=True,
                 guess=lambda f: [f"https://kinoflex.ru/movie/{key_of(f, 'o')}"]
                 + ([f"https://kinoflex.ru/movie/{slug(f['t'], FLEX_RU).replace('-', '')}"] if ru(f) else []),
                 per_run=20000, read=300_000, ver=2, seasons=r'href="{path}/season-(\d+)"',
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


def guesses(films, site):
    """(адрес, тайтл) для каждого угаданного адреса."""
    return [(u, f) for f in films.values() for u in (site.get("guess") or (lambda f: []))(f) if len(url_key(u, site["by"])) >= 3]


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


def fetch_page(url, site):
    """(годы со страницы, сезоны на ней); годы [] — страницы нет (404, переадресация на другую
    страницу, нет года — пустая заглушка); None — сайт не ответил, проверим в следующий раз.
    Сезоны — номера сезонов, на которые ссылается страница сериала (у FLEX: /movie/<адрес>/season-8)."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            # угаданный адрес, переадресованный в другое место, — страницы нет; адрес из карты сайта
            # кинотеатр вправе переадресовать на свой основной (Иви так и делает)
            if site.get("strict") and r.url.rstrip("/") != url.rstrip("/"): return [], []
            b = r.read(site.get("read", 400_000))
    except urllib.error.HTTPError as e:
        return ([] if e.code in (404, 410) else None), []
    except Exception:
        return None, []
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    html = b.decode("utf-8", "replace")
    return page_years(html, site["year"]), page_seasons(html, url, site)


def page_seasons(html, url, site):
    if not site.get("seasons"): return []
    path = re.escape(re.sub(r"^https?://[^/]+", "", url.rstrip("/")))
    return sorted({int(n) for n in re.findall(site["seasons"].format(path=path), html)})


def check_page(url, site):
    return fetch_page(url, site)[0]


def sitemap(site):
    locs = lambda t: re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", t)
    out = []
    for m in site["maps"]:
        t = get(m)
        if "<sitemapindex" in t:
            for k in locs(t):
                if not re.search(site.get("kids", "."), k): continue
                try: out += locs(get(k))
                except Exception as e: print(f"  {k}: не открылась ({e}) — без неё", file=sys.stderr)
        else:
            out += locs(t)
    return out


def manual_links():
    try: return json.load(open(MANUAL, encoding="utf-8"))
    except (OSError, ValueError): return {}


MANUAL_LINKS = manual_links()


def cinema_links(films):
    """Пишет f["ln"] = {кинотеатр: адрес страницы} и f["lns"] = {кинотеатр: [сезоны]}, если там не все.
    Кинотеатр не ответил — в этот раз без его ссылок."""
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
        cands = candidates(films, pages, site["by"]) if pages else {}
        # угаданный адрес сразу знает, для какого тайтла угадан (русский адрес FLEX с английским
        # названием не сопоставить); тёзки, угадавшие тот же адрес, разойдутся по году
        for u, f in guesses(films, site):
            if f not in cands.setdefault(u, []): cands[u].append(f)
        manual = {tid: m[name] for tid, m in MANUAL_LINKS.items() if name in m and tid in films}
        for tid, u in manual.items():
            if films[tid] not in cands.setdefault(u, []): cands[u].append(films[tid])
        # кеш: адрес → [годы со страницы, когда проверено, версия]; сначала непроверенные, потом самые давние
        # ver — версия проверки у кинотеатра: поменялась — проверяем его страницы заново
        ver = site.get("ver", 1)
        age = lambda u: today - cache[u][1] if u in cache and (cache[u][2:] or [1])[0] == ver else 10**6
        # среди одинаково давних — сначала популярное: за первые запуски проверяется то, что смотрят
        pop = lambda u: max(f.get("pop", 0) for f in cands[u])
        # у страницы сериала ещё не смотрели, какие на ней сезоны, — тоже проверить
        no_seasons = lambda u: site.get("seasons") and u in cache and cache[u][0] and len(cache[u]) < 4 and any(f.get("k") for f in cands[u])
        todo = sorted((u for u in cands if age(u) >= RECHECK or no_seasons(u)), key=lambda u: (age(u), pop(u)), reverse=True)[:site.get("per_run", PER_RUN)]
        stop, done = time.monotonic() + MINUTES * 60, 0
        ex = cf.ThreadPoolExecutor(8)
        try:
            for u, (y, ss) in zip(todo, ex.map(lambda u: fetch_page(u, site), todo)):
                if y is not None: cache[u] = [y, today, ver, ss]
                done += 1
                if time.monotonic() > stop: break  # время вышло — остальное в следующий раз
        finally:
            ex.shutdown(wait=True, cancel_futures=True)
        save(cache)  # после каждого кинотеатра: оборвётся запуск — проверенное не пропадёт
        links = assign(cands, {u: cache[u][0] for u in cands if age(u) < 10**6})
        for tid, u in manual.items():  # ручной адрес — если страница не пропала (ещё не проверена — верим)
            if u not in cache or cache[u][0]: links[tid] = u
        for f in films.values():
            ln = f.setdefault("ln", {})
            ln.pop(name, None)
            (f.get("lns") or {}).pop(name, None)
            if f["id"] in links:
                u = ln[name] = links[f["id"]]
                part = part_seasons(f, (cache.get(u) or [])[3:4])
                if part: f.setdefault("lns", {})[name] = part
        print(f"  {name}: в карте сайта {listed:,}, адресов к проверке {len(cands):,}, "
              f"проверено сейчас {done:,} из {len(todo):,}, ссылок {len(links):,}", file=sys.stderr)
    for f in films.values():
        if not f.get("ln"): f.pop("ln", None)
        if not f.get("lns"): f.pop("lns", None)
    save(cache)


def part_seasons(f, seasons):
    """Сезоны на странице кинотеатра, если там не все: «Рик и Морти» на FLEX — только 8 и 9."""
    ss = (seasons or [[]])[0]
    return ss if f.get("k") and ss and f.get("ss") and len(ss) < f["ss"] else None


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
            if u == "maps":  # какие разделы в картах сайта
                for name, site in SITES.items():
                    for m in site["maps"]:
                        try: print(name, m, "→", *re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", get(m))[:40])
                        except Exception as e: print(name, m, "не открылась:", e)
            elif u.startswith("find:"):
                for name, site in SITES.items():
                    try: hits = sorted({p for p in sitemap(site) if u[5:].lower() in p.lower()})  # сырые адреса карты — и не похожие на страницу тайтла
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
