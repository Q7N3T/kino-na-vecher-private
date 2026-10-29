"""Прямые ссылки на кинотеатры: адрес страницы ↔ название в базе, проверка по году на странице.
Адреса и куски страниц — настоящие, из карт сайта кинотеатров (октябрь 2026)."""
import os
import sys
import io
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cinemas as c  # noqa: E402


def film(tid, t, y, o=None):
    return {"id": tid, "t": t, "o": o or t, "y": y}


class Keys(unittest.TestCase):
    def same(self, title, url):
        self.assertEqual(c.key_of(film("tt1", title, 2000), "t"), c.url_key(url, "t"), (title, url))

    def test_each_cinema_transliteration_matches_russian_title(self):
        self.same("Холоп 3", "https://start.ru/watch/holop-3")
        self.same("Твоё сердце будет разбито", "https://start.ru/watch/tvoe-serdce-budet-razbito")
        self.same("Я знаю твои секреты", "https://www.ivi.ru/watch/ya-znayu-tvoi-sekretyi")
        self.same("Воскресший Эртугрул", "https://www.ivi.ru/watch/voskresshij-ertugrul")
        self.same("Я тебя нашёл", "https://www.ivi.ru/watch/ya-tebya-nashyol")
        self.same("Близнецы", "https://www.ivi.ru/watch/bliznetsyi")
        self.same("В лесах и на горах", "https://www.ivi.ru/watch/v_lesah_i_na_gorah")
        self.same("Секс в большом городе", "https://kion.ru/serial/seks-v-bolshom-gorode")
        self.same("Главный бой Мухаммеда Али", "https://www.amediateka.ru/watch/glavnyy-boy-muhammeda-ali")

    def test_different_titles_do_not_match(self):
        self.assertNotEqual(c.key_of(film("tt1", "Холоп 2", 2000), "t"), c.url_key("https://start.ru/watch/holop-3", "t"))

    def test_flex_uses_original_title_exactly(self):
        self.assertEqual(c.key_of(film("tt1", "Клан Сопрано", 1999, "The Sopranos"), "o"), "thesopranos")
        self.assertEqual(c.url_key("https://kinoflex.ru/movie/thesopranos", "o"), "thesopranos")

    def test_title_without_cyrillic_gets_no_russian_key(self):
        self.assertEqual(c.key_of(film("tt1", "Up", 2009), "t"), "")


class Guess(unittest.TestCase):
    """Адрес страницы по названию — так, как его пишет сам кинотеатр (настоящие адреса из карт сайта)."""
    def test_ivi(self):
        for t, s in [("Я знаю твои секреты", "ya-znayu-tvoi-sekretyi"), ("Воскресший Эртугрул", "voskresshij-ertugrul"),
                     ("Я тебя нашёл", "ya-tebya-nashyol"), ("Крылышко или ножка", "kryilyishko-ili-nozhka"),
                     ("Дом ада 2. Отель «Абаддон»", "dom-ada-2-otel-abaddon"), ("Большой босс", "bolshoj-boss"),
                     ("Полицейская история 3: Суперполицейский", "politsejskaya-istoriya-3-superpolitsejskij")]:
            self.assertEqual(c.slug(t, c.IVI), s)

    def test_kion(self):
        for t, s in [("Кровный отец", "krovnyj-otets"), ("Очень плохие парни", "ochen-plohie-parni"), ("8 женщин", "8-zhenschin"),
                     ("Ещё вчера", "esche-vchera"), ("Человек-паук: Через вселенные", "chelovek-pauk-cherez-vselennye"),
                     ("После нашей эры", "posle-nashej-ery"), ("Пятьдесят оттенков свободы", "pyatdesyat-ottenkov-svobody")]:
            self.assertEqual(c.slug(t, c.KION), s)

    def test_start(self):
        for t, s in [("Твоё сердце будет разбито", "tvoe-serdce-budet-razbito"), ("Сирано де Бержерак", "sirano-de-berzherak"),
                     ("Папины дочки. Новые", "papiny-dochki-novye")]:
            self.assertEqual(c.slug(t, c.START), s)

    def test_flex_russian_addresses(self):
        g = lambda t, o: c.SITES["flex"]["guess"]({"t": t, "o": o})
        self.assertEqual(g("Приключения девы Мэриан", "Maid Marian"), ["https://kinoflex.ru/movie/maidmarian", "https://kinoflex.ru/movie/prikliucheniiadevymerian"])
        self.assertIn("https://kinoflex.ru/movie/vremiaprikliucheniifionnaikeik", g("Время приключений: Фионна и Кейк", "Adventure Time: Fionna & Cake"))
        self.assertIn("https://kinoflex.ru/movie/rikimorti", g("Рик и Морти", "Rick and Morty"))

    def test_guessed_address_knows_its_title(self):
        rm = {"id": "tt2861424", "t": "Рик и Морти", "o": "Rick and Morty", "y": 2013}
        got = dict((u, f["id"]) for u, f in c.guesses({"tt2861424": rm}, c.SITES["flex"]))
        self.assertEqual(got["https://kinoflex.ru/movie/rikimorti"], "tt2861424")

    def test_premier(self):
        for t, s in [("Двойная жизнь", "dvojnaya-zhizn"), ("Холоп", "holop"), ("Горький 53", "gorkij-53"), ("Физрук", "fizruk")]:
            self.assertEqual(c.slug(t, c.PREMIER), s)
        y = c.SITES["premier"]["year"]
        self.assertEqual(c.page_years("<title>Холоп (2019, фильм) смотреть в хорошем качестве онлайн на сайте PREMIER.ONE</title>", y), [2019])
        self.assertEqual(c.page_years('<title>«Физрук» сериал смотреть</title>…{"year":2014,"x":1}', y), [2014])
        self.assertEqual(c.page_years("<title>Нет такой страницы</title>", y), [])

    def test_kion_series_and_films_live_apart(self):
        self.assertEqual(c.SITES["kion"]["guess"]({"t": "Рим", "k": "s"}), ["https://kion.ru/serial/rim"])
        self.assertEqual(c.SITES["kion"]["guess"]({"t": "Сияние"}), ["https://kion.ru/film/siyanie"])
        self.assertEqual(c.SITES["ivi"]["guess"]({"t": "Up"}), [], "без русского названия адреса не угадать")


class Pages(unittest.TestCase):
    def test_subpages_lead_to_title_page(self):
        urls = ["https://start.ru/watch/holop-3/trailers/140199", "https://start.ru/watch/holop-3",
                "https://start.ru/movies", "https://start.ru/watch/holop-3/person"]
        self.assertEqual(c.title_pages(urls, c.SITES["start"]["page"]), {"https://start.ru/watch/holop-3"})

    def test_ivi_episodes_and_bare_numbers_are_not_title_pages(self):
        urls = ["https://www.ivi.ru/watch/493358", "https://www.ivi.ru/watch/415821/reviews",
                "https://www.ivi.ru/watch/sled/178652", "https://www.ivi.ru/watch/ezel/669694"]
        self.assertEqual(c.title_pages(urls, c.SITES["ivi"]["page"]),
                         {"https://www.ivi.ru/watch/sled", "https://www.ivi.ru/watch/ezel"})

    def test_year_from_each_page(self):
        self.assertEqual(c.page_years('<title>Фильм 13 жизней 2022 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), [2022])
        self.assertEqual(c.page_years('<title>Фильм 28 лет спустя 2025 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), [2025])
        self.assertEqual(c.page_years('<meta property="og:title" content="Первая любовь (Первая любовь, 2022)"/>', c.SITES["ivi"]["year"]), [2022])
        self.assertEqual(c.page_years('{"name":"Мошенники","year":2026}', c.SITES["start"]["year"]), [2026])
        self.assertEqual(c.page_years('{"releaseYear":1998,"x":1}', c.SITES["kion"]["year"]), [1998])
        self.assertEqual(c.page_years('<title>Без года</title>', c.SITES["flex"]["year"]), [])
        # сериал — диапазон лет; год в названии («1883») тоже попадёт, но и год выхода рядом
        self.assertEqual(c.page_years('<title>Сериал Уэнсдэй 2022–2025 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), [2022, 2025])
        self.assertEqual(c.page_years('<title>Сериал 1883 2021 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), [2021])  # «1883» — часть названия, до годов
        self.assertEqual(c.page_years('<title>Flex — онлайн-кинотеатр</title>', c.SITES["flex"]["year"]), [])


class Assign(unittest.TestCase):
    def test_namesakes_are_told_apart_by_year(self):
        old, new = film("tt1", "Дюна", 1984), film("tt2", "Дюна", 2021)
        films = {"tt1": old, "tt2": new}
        cands = c.candidates(films, {"https://www.ivi.ru/watch/dyuna"}, "t")
        self.assertEqual(len(cands["https://www.ivi.ru/watch/dyuna"]), 2)
        self.assertEqual(c.assign(cands, {"https://www.ivi.ru/watch/dyuna": [2021]}), {"tt2": "https://www.ivi.ru/watch/dyuna"})

    def test_year_off_by_one_is_ok_wrong_or_unknown_year_is_not(self):
        f = {"tt1": film("tt1", "Холоп 3", 2026)}
        cands = c.candidates(f, {"https://start.ru/watch/holop-3"}, "t")
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": [2025]}), {"tt1": "https://start.ru/watch/holop-3"})
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": [2019]}), {})
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": []}), {})

    def test_short_titles_are_not_matched(self):
        self.assertEqual(c.candidates({"tt1": film("tt1", "Он", 2000)}, {"https://start.ru/watch/on"}, "t"), {})


class FakePage(io.BytesIO):
    def __init__(self, body, url):
        super().__init__(body.encode())
        self.url = url
    def __enter__(self): return self
    def __exit__(self, *a): pass


class CheckPage(unittest.TestCase):
    flex = c.SITES["flex"]
    url = "https://kinoflex.ru/movie/wednesday"

    def check(self, answer):
        with mock.patch.object(c.urllib.request, "urlopen", side_effect=[answer]):
            return c.check_page(self.url, self.flex)

    def test_open_page_gives_its_year(self):
        self.assertEqual(self.check(FakePage("<title>Сериал Уэнсдэй 2022 — смотреть онлайн в HD | Flex</title>", self.url)), [2022])

    def test_404_and_redirect_mean_no_page(self):
        self.assertEqual(self.check(urllib.error.HTTPError(self.url, 404, "Not Found", {}, None)), [])
        self.assertEqual(self.check(FakePage("<title>Flex 2026 — главная</title>", "https://kinoflex.ru/")), [])

    def test_sitemap_page_may_redirect_to_main_address(self):
        ivi, url = c.SITES["ivi"], "https://www.ivi.ru/watch/pchelovod"
        page = FakePage('<meta property="og:title" content="Пчеловод (The Beekeeper, 2024)"/>', "https://www.ivi.ru/watch/511457")
        with mock.patch.object(c.urllib.request, "urlopen", side_effect=[page]):
            self.assertEqual(c.check_page(url, ivi), [2024])

    def test_site_down_means_try_later(self):
        self.assertIsNone(self.check(urllib.error.HTTPError(self.url, 503, "Unavailable", {}, None)))
        self.assertIsNone(self.check(TimeoutError()))


if __name__ == "__main__":
    unittest.main()


class EndToEnd(unittest.TestCase):
    def test_rick_and_morty_gets_flex_page_by_russian_address(self):
        import tempfile
        rm = {"id": "tt2861424", "t": "Рик и Морти", "o": "Rick and Morty", "y": 2013, "k": "s"}
        films = {"tt2861424": rm}
        live = {"https://kinoflex.ru/movie/rikimorti": [2013]}
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(c, "CACHE", os.path.join(d, "cache.json")), \
                mock.patch.object(c, "SITES", {"flex": c.SITES["flex"]}), \
                mock.patch.object(c, "MANUAL_LINKS", {}), \
                mock.patch.object(c, "sitemap", return_value=[]), \
                mock.patch.object(c, "fetch_page", side_effect=lambda u, s: (live.get(u, []), [])):
            c.cinema_links(films)
        self.assertEqual(rm.get("ln"), {"flex": "https://kinoflex.ru/movie/rikimorti"})

    def run_flex(self, films, live, manual):
        import tempfile
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(c, "CACHE", os.path.join(d, "cache.json")), \
                mock.patch.object(c, "SITES", {"flex": c.SITES["flex"]}), \
                mock.patch.object(c, "MANUAL_LINKS", manual), \
                mock.patch.object(c, "sitemap", return_value=[]), \
                mock.patch.object(c, "fetch_page", side_effect=lambda u, s: live.get(u, ([], []))):
            c.cinema_links(films)

    def test_manual_address_without_year_check_and_partial_seasons_noted(self):
        # kinoflex.ru/movie/rickandmortysndk — не угадать; на FLEX только 8 и 9 сезоны из 9, год на странице — 2025
        rm = {"id": "tt2861424", "t": "Рик и Морти", "o": "Rick and Morty", "y": 2013, "k": "s", "ss": 9}
        u = "https://kinoflex.ru/movie/rickandmortysndk"
        self.run_flex({"tt2861424": rm}, {u: ([2025], [8, 9])}, {"tt2861424": {"flex": u}})
        self.assertEqual(rm["ln"], {"flex": u})
        self.assertEqual(rm["lns"], {"flex": [8, 9]})

    def test_all_seasons_no_note_and_manual_404_dropped(self):
        w = {"id": "tt1", "t": "Уэнздей", "o": "Wednesday", "y": 2022, "k": "s", "ss": 2}
        u = "https://kinoflex.ru/movie/wednesday"
        self.run_flex({"tt1": w}, {u: ([2022], [1, 2])}, {})
        self.assertEqual(w["ln"], {"flex": u})
        self.assertNotIn("lns", w)
        gone = {"id": "tt2", "t": "Тест", "o": "Test", "y": 2000, "k": "s", "ss": 3}
        self.run_flex({"tt2": gone}, {}, {"tt2": {"flex": "https://kinoflex.ru/movie/gone"}})
        self.assertNotIn("ln", gone, "ручной адрес, который стал 404, — без ссылки")


class Seasons(unittest.TestCase):
    def test_seasons_from_flex_page(self):
        html = '<a href="/movie/rickandmortysndk/season-8">8</a><a href="/movie/rickandmortysndk/season-9">9</a><a href="/movie/other/season-1">'
        self.assertEqual(c.page_seasons(html, "https://kinoflex.ru/movie/rickandmortysndk", c.SITES["flex"]), [8, 9])
        self.assertEqual(c.page_seasons(html, "https://kion.ru/serial/x", c.SITES["kion"]), [], "у KION сезоны не читаем")
