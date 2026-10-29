"""Прямые ссылки на кинотеатры: адрес страницы ↔ название в базе, проверка по году на странице.
Адреса и куски страниц — настоящие, из карт сайта кинотеатров (октябрь 2026)."""
import os
import sys
import unittest

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
        self.assertEqual(c.page_year('<title>Фильм 13 жизней 2022 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), 2022)
        self.assertEqual(c.page_year('<title>Фильм 28 лет спустя 2025 — смотреть онлайн в HD | Flex</title>', c.SITES["flex"]["year"]), 2025)
        self.assertEqual(c.page_year('<meta property="og:title" content="Первая любовь (Первая любовь, 2022)"/>', c.SITES["ivi"]["year"]), 2022)
        self.assertEqual(c.page_year('{"name":"Мошенники","year":2026}', c.SITES["start"]["year"]), 2026)
        self.assertEqual(c.page_year('{"releaseYear":1998,"x":1}', c.SITES["kion"]["year"]), 1998)
        self.assertEqual(c.page_year('<title>Без года</title>', c.SITES["flex"]["year"]), 0)


class Assign(unittest.TestCase):
    def test_namesakes_are_told_apart_by_year(self):
        old, new = film("tt1", "Дюна", 1984), film("tt2", "Дюна", 2021)
        films = {"tt1": old, "tt2": new}
        cands = c.candidates(films, {"https://www.ivi.ru/watch/dyuna"}, "t")
        self.assertEqual(len(cands["https://www.ivi.ru/watch/dyuna"]), 2)
        self.assertEqual(c.assign(cands, {"https://www.ivi.ru/watch/dyuna": 2021}), {"tt2": "https://www.ivi.ru/watch/dyuna"})

    def test_year_off_by_one_is_ok_wrong_or_unknown_year_is_not(self):
        f = {"tt1": film("tt1", "Холоп 3", 2026)}
        cands = c.candidates(f, {"https://start.ru/watch/holop-3"}, "t")
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": 2025}), {"tt1": "https://start.ru/watch/holop-3"})
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": 2019}), {})
        self.assertEqual(c.assign(cands, {"https://start.ru/watch/holop-3": 0}), {})

    def test_short_titles_are_not_matched(self):
        self.assertEqual(c.candidates({"tt1": film("tt1", "Он", 2000)}, {"https://start.ru/watch/on"}, "t"), {})


if __name__ == "__main__":
    unittest.main()
