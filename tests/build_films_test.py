"""Фильтры и разбор данных сборщика базы: что попадает в базу и как."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_films as b  # noqa: E402


class Skip(unittest.TestCase):
    def test_talk_shows_and_news_are_skipped(self):
        self.assertTrue(b.skip(["Talk-Show", "Comedy"], "tvSeries"))
        self.assertTrue(b.skip(["News"], "movie"))

    def test_reality_skipped_unless_scripted_drama(self):
        self.assertTrue(b.skip(["Reality-TV"], "tvSeries"))
        self.assertTrue(b.skip(["Game-Show", "Family"], "tvSeries"))
        self.assertFalse(b.skip(["Reality-TV", "Drama"], "tvSeries"))

    def test_wrestling_shows_skipped_sport_movies_kept(self):
        self.assertTrue(b.skip(["Sport", "Action"], "tvSeries"))
        self.assertFalse(b.skip(["Sport", "Action"], "movie"))
        self.assertFalse(b.skip(["Sport", "Drama"], "tvSeries"))


class Moods(unittest.TestCase):
    def test_moods_from_genres(self):
        self.assertEqual(b.moods(["Comedy"]), ["laugh"])
        self.assertEqual(b.moods(["Drama", "Romance"]), ["sad"])
        self.assertEqual(b.moods(["Thriller", "Sci-Fi"]), ["nerve", "think"])
        self.assertEqual(b.moods([]), [])


class Laugh(unittest.TestCase):
    """«Посмеяться» — когда комедия главное в тайтле, а не одна из трёх меток IMDb."""

    def laugh(self, g, tg=None):
        return "laugh" in b.moods(g, tg)

    def test_plain_comedy_romcom_and_light_family(self):
        self.assertTrue(self.laugh(["Comedy"]))
        self.assertTrue(self.laugh(["Comedy", "Romance"]))  # «Друзья»
        self.assertTrue(self.laugh(["Comedy", "Family"]))  # «Один дома»
        self.assertTrue(self.laugh(["Comedy", "Crime"]))  # «Большой куш»

    def test_comedy_tag_next_to_heavy_genre_is_not_enough(self):
        self.assertFalse(self.laugh(["Comedy", "Drama", "Romance"]))  # «Перед рассветом»
        self.assertFalse(self.laugh(["Comedy", "Drama"]))  # «Медведь»
        self.assertFalse(self.laugh(["Action", "Comedy", "Crime"]))  # «Семьянин» (2019)
        self.assertFalse(self.laugh(["Comedy", "Horror"]))

    def test_not_funny_comedy_tag_moves_to_other_moods(self):
        self.assertEqual(b.moods(["Comedy", "Drama", "Romance"]), ["sad"])  # «Перед рассветом» — погрустить
        self.assertEqual(b.moods(["Comedy", "Drama"]), ["think"])  # «Медведь» — подумать

    def test_tmdb_must_agree_when_it_knows_the_genres(self):
        self.assertFalse(self.laugh(["Adventure", "Animation", "Comedy"], [16, 10759, 18, 10765]))  # «Фрирен»: у TMDB не комедия
        self.assertTrue(self.laugh(["Adventure", "Animation", "Comedy"], [16, 35, 10751]))
        self.assertTrue(self.laugh(["Comedy"], None))  # TMDB молчит — решает IMDb


class WatchProviders(unittest.TestCase):
    def det(self, ru):
        return {"watch/providers": {"results": {"RU": ru}}}

    def test_groups_by_kind_in_display_order(self):
        out = b.watch_providers(self.det({
            "link": "https://www.themoviedb.org/movie/1/watch?locale=RU",
            "flatrate": [
                {"provider_id": 2, "provider_name": "Иви", "logo_path": "/i.png", "display_priority": 5},
                {"provider_id": 1, "provider_name": "Okko", "logo_path": "/o.png", "display_priority": 1},
                {"provider_id": 3, "provider_name": "Кинопоиск", "logo_path": "/k.png", "display_priority": 0},
            ],
            "buy": [{"provider_id": 4, "provider_name": "Apple TV Store", "logo_path": "/a.png"}],
        }))
        self.assertEqual(out["s"], [[3, "Кинопоиск", "/k.png"], [1, "Okko", "/o.png"], [2, "Иви", "/i.png"]])
        self.assertEqual(out["b"], [[4, "Apple TV Store", "/a.png"]])
        self.assertEqual(out["l"], "https://www.themoviedb.org/movie/1/watch?locale=RU")

    def test_nothing_in_russia_is_none(self):
        self.assertIsNone(b.watch_providers({}))
        self.assertIsNone(b.watch_providers(self.det({"link": "x"})))


class RoundTrip(unittest.TestCase):
    def test_reading_and_writing_the_base_changes_nothing(self):
        """Запись повторяема: прочитанная и снова записанная база — байт в байт та же."""
        import filecmp, glob, tempfile
        films = b.load_existing()
        with tempfile.TemporaryDirectory() as tmp:
            out, syn = b.OUT, b.SYN
            b.OUT, b.SYN = os.path.join(tmp, "films.js"), os.path.join(tmp, "syn")
            try:
                b.write(films)
            finally:
                b.OUT, b.SYN = out, syn
            orig, new = open(b.OUT, encoding="utf-8").read(), open(os.path.join(tmp, "films.js"), encoding="utf-8").read()
            self.assertEqual(orig, new)
            for f in sorted(glob.glob(os.path.join(b.SYN, "*.json"))):
                self.assertTrue(filecmp.cmp(f, os.path.join(tmp, "syn", os.path.basename(f)), shallow=False), f)


if __name__ == "__main__":
    unittest.main()
