"""Фото актёров из Wikidata: адрес картинки на Commons, разбор ответа, кому ставим фото, тёзки."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_films as b  # noqa: E402
import wiki_photos as w  # noqa: E402


class Thumb(unittest.TestCase):
    def test_commons_thumbnail_path_from_md5_of_file_name(self):
        # Example.jpg на Commons лежит в /a/a9/ — так устроены адреса всех файлов
        self.assertEqual(w.thumb("http://commons.wikimedia.org/wiki/Special:FilePath/Example.jpg"),
                         f"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Example.jpg/{w.WIDTH}px-Example.jpg")

    def test_spaces_and_unicode_in_name(self):
        url = w.thumb("http://commons.wikimedia.org/wiki/Special:FilePath/Masakazu%20Morita%202019.jpg")
        self.assertIn("/Masakazu_Morita_2019.jpg/", url)

    def test_only_photos(self):
        self.assertIsNone(w.thumb("http://commons.wikimedia.org/wiki/Special:FilePath/Signature.svg"))


class Apply(unittest.TestCase):
    def films(self):
        return {
            "tt1": {"cr": [["Masakazu Morita", "Ichigo", None], ["Noriaki Sugiyama", "Uryu", "/ns.jpg"]]},
            "tt2": {"cast": [{"n": "Masakazu Morita", "r": "Ichigo"}, {"n": "Fumiko Orikasa"}]},  # состав из IMDb
            "tt3": {"cr": [["Fumiko Orikasa", "Rukia", "/fo.jpg"]]},
        }

    def test_missing_is_who_has_no_photo_anywhere(self):
        self.assertEqual(w.missing(self.films()), {"Masakazu Morita"})

    def test_photo_goes_everywhere_the_actor_has_none(self):
        f = self.films()
        n = w.apply(f, {"Masakazu Morita": "https://upload.wikimedia.org/m.jpg"})
        self.assertEqual(n, 2)
        self.assertEqual(f["tt1"]["cr"][0][2], "https://upload.wikimedia.org/m.jpg")
        self.assertEqual(f["tt1"]["cr"][1][2], "/ns.jpg", "фото TMDB не трогаем")
        self.assertEqual(f["tt2"]["cr"], [["Masakazu Morita", "Ichigo", "https://upload.wikimedia.org/m.jpg"], ["Fumiko Orikasa", "", None]])

    def test_imdb_cast_without_found_photos_stays_as_is(self):
        f = self.films()
        self.assertEqual(w.apply(f, {}), 0)
        self.assertNotIn("cr", f["tt2"])

    def test_parses_sparql_answer(self):
        ans = {"results": {"bindings": [
            {"imdb": {"value": "nm0603342"}, "img": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Example.jpg"}},
            {"imdb": {"value": "nm1"}, "img": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Sign.svg"}},
        ]}}
        self.assertEqual(list(w.parse(ans)), ["nm0603342"])
        self.assertIn('"nm1" "nm2"', w.query(["nm1", "nm2"]))


class Namesakes(unittest.TestCase):
    row = lambda self, nid, name, prof="actor", known="": [nid, name, "\\N", "\\N", prof, known]

    def test_actor_from_our_titles_wins(self):
        c = {"John Smith": [self.row("nm1", "John Smith"), self.row("nm2", "John Smith")]}
        self.assertEqual(b.people_ids(c, {"nm2"}, set()), {"John Smith": "nm2"})
        c = {"John Smith": [self.row("nm1", "John Smith", known="tt9"), self.row("nm2", "John Smith", known="tt5,tt7")]}
        self.assertEqual(b.people_ids(c, set(), {"tt7"}), {"John Smith": "nm2"})

    def test_single_actor_among_namesakes(self):
        c = {"Jo Lee": [self.row("nm1", "Jo Lee", "composer"), self.row("nm2", "Jo Lee", "actress,producer")]}
        self.assertEqual(b.people_ids(c, set(), set()), {"Jo Lee": "nm2"})

    def test_cannot_tell_apart_no_photo(self):
        c = {"Jo Lee": [self.row("nm1", "Jo Lee"), self.row("nm2", "Jo Lee")]}
        self.assertEqual(b.people_ids(c, set(), set()), {"Jo Lee": None})


if __name__ == "__main__":
    unittest.main()
