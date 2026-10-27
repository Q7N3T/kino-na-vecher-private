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


class WatchProviders(unittest.TestCase):
    def det(self, ru):
        return {"watch/providers": {"results": {"RU": ru}}}

    def test_groups_by_kind_in_display_order_without_yandex(self):
        out = b.watch_providers(self.det({
            "link": "https://www.themoviedb.org/movie/1/watch?locale=RU",
            "flatrate": [
                {"provider_id": 2, "provider_name": "Иви", "logo_path": "/i.png", "display_priority": 5},
                {"provider_id": 1, "provider_name": "Okko", "logo_path": "/o.png", "display_priority": 1},
                {"provider_id": 3, "provider_name": "Кинопоиск", "logo_path": "/k.png", "display_priority": 0},
            ],
            "buy": [{"provider_id": 4, "provider_name": "Apple TV Store", "logo_path": "/a.png"}],
        }))
        self.assertEqual(out["s"], [[1, "Okko", "/o.png"], [2, "Иви", "/i.png"]])
        self.assertEqual(out["b"], [[4, "Apple TV Store", "/a.png"]])
        self.assertEqual(out["l"], "https://www.themoviedb.org/movie/1/watch?locale=RU")

    def test_nothing_in_russia_is_none(self):
        self.assertIsNone(b.watch_providers({}))
        self.assertIsNone(b.watch_providers(self.det({"link": "x", "flatrate": [{"provider_name": "Yandex"}]})))


if __name__ == "__main__":
    unittest.main()
