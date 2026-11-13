"""
tests/test_scene3d_stops.py — the 3D preview's named moments and viewpoints
(V3.44, F261; src/scene3d_stops.py).

The V3.43 review found a window of unlabelled sliders that opened on a yard
*fully grown* in June at one in the afternoon. These hold the short lists that
replaced them to what the owner chose (D5: the fifth summer, July,
mid-afternoon, from the street), to one rule (a list never names a stop the
picture is not at), and the page's copy of the year words to this one. Pure:
no Qt, no database, no browser.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import scene3d_stops as S                            # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _views_js() -> str:
    with open(os.path.join(_ROOT, "html", "scene3d", "27-views.js"),
              encoding="utf-8") as fh:
        return fh.read()


class TheOpeningIsTheOwnersChoice(unittest.TestCase):

    def test_it_is_the_fifth_summer_in_july_in_the_afternoon(self):
        self.assertEqual(S.OPENING, {"year": 5, "month": 7, "hour": 15,
                                     "view": "street"})
        self.assertEqual(S.when_words(S.OPENING["year"]), "Fifth summer")
        self.assertEqual(S.month_words(S.OPENING["month"]), "Summer")
        self.assertEqual(S.hour_words(S.OPENING["hour"]), "Afternoon")

    def test_every_part_of_it_is_a_named_stop(self):
        """Or the window would open with a list showing an entry that is not
        one of its stops."""
        self.assertIn(S.OPENING["year"], [v for v, _w in S.WHEN_STOPS])
        self.assertIn(S.OPENING["month"], [v for v, _w in S.SEASON_STOPS])
        self.assertIn(S.OPENING["hour"], [v for v, _w in S.DAY_STOPS])
        self.assertIn(S.OPENING["view"], [k for k, _w, _t in S.VIEWS])


class TheStopsSayWhatTheyAre(unittest.TestCase):

    def test_when_runs_from_the_first_summer_to_fully_grown(self):
        years = [v for v, _w in S.WHEN_STOPS]
        self.assertEqual(years[0], 1)
        self.assertEqual(years[-1], 0, "fully grown is year 0 in the model, "
                                       "and comes last: where it is headed")
        self.assertEqual(years[:-1], sorted(years[:-1]))
        for value, words in S.WHEN_STOPS:
            self.assertEqual(S.when_words(value), words)

    def test_year_0_is_never_called_planting_day(self):
        """The V3.43 fault: year 0 is the design fully grown, and three
        surfaces called it the day it was planted."""
        self.assertEqual(S.when_words(0), "Fully grown")
        for value, words in S.WHEN_STOPS:
            self.assertNotRegex(words.lower(), r"plant|today|now|install")

    def test_every_year_of_the_timeline_has_words(self):
        from src.scene3d_toolbar import MAX_YEAR
        self.assertEqual(len(S.ordinals()), MAX_YEAR)
        seen = {S.when_words(y) for y in range(0, MAX_YEAR + 1)}
        self.assertEqual(len(seen), MAX_YEAR + 1)
        self.assertEqual(S.when_words(7), "Seventh summer")
        self.assertEqual(S.when_words(25), "Twenty-fifth summer")

    def test_a_cold_month_is_a_year_not_a_summer(self):
        self.assertEqual(S.when_words(5, 1), "Fifth year")
        self.assertEqual(S.when_words(5, 11), "Fifth year")
        self.assertEqual(S.when_words(5, 4), "Fifth summer")
        self.assertEqual(S.when_words(0, 1), "Fully grown")

    def test_the_seasons_and_the_day(self):
        self.assertEqual([w for _v, w in S.SEASON_STOPS],
                         ["Spring", "Summer", "Fall", "Winter"])
        self.assertEqual(S.month_words(8), "August")
        self.assertEqual([w for _v, w in S.DAY_STOPS],
                         ["Morning", "Midday", "Afternoon", "Evening",
                          "Night"])
        self.assertEqual(S.hour_words(17), "17:00")


class AListNeverNamesAStopThePictureIsNotAt(unittest.TestCase):

    def test_at_a_stop_the_list_is_the_stops(self):
        self.assertEqual(S.when_entries(5), list(S.WHEN_STOPS))
        self.assertEqual(S.season_entries(7), list(S.SEASON_STOPS))
        self.assertEqual(S.day_entries(15), list(S.DAY_STOPS))

    def test_between_stops_it_says_where_the_picture_is(self):
        rows = S.when_entries(7)
        self.assertEqual(rows[:-1], list(S.WHEN_STOPS))
        self.assertEqual(rows[-1], (7, "Seventh summer"))
        self.assertEqual(S.season_entries(8)[-1], (8, "August"))
        self.assertEqual(S.day_entries(17)[-1], (17, "17:00"))

    def test_every_word_a_list_can_say_is_known_for_sizing(self):
        for key, entries in (("year", S.when_entries),
                             ("month", S.season_entries),
                             ("hour", S.day_entries)):
            words = set(S.every_word(key))
            lo, hi = {"year": (0, 25), "month": (1, 12), "hour": (0, 23)}[key]
            for value in range(lo, hi + 1):
                for _v, said in entries(value):
                    self.assertIn(said, words, (key, value))


class ThePageSaysTheSameWords(unittest.TestCase):
    """``html/scene3d/27-views.js`` keeps a copy of the year words for the
    line over the picture. A page cannot import Python; a test can compare."""

    def test_the_year_words(self):
        m = re.search(r"const _YEAR_WORDS = \[(.*?)\];", _views_js(), re.S)
        self.assertIsNotNone(m)
        words = re.findall(r"'([^']+)'", m.group(1))
        self.assertEqual(tuple(words), S.ordinals())

    def test_the_cold_months(self):
        m = re.search(r"const _COLD_MONTHS = \[(.*?)\];", _views_js())
        self.assertEqual(tuple(int(x) for x in m.group(1).split(",")),
                         S._COLD_MONTHS)

    def test_fully_grown(self):
        self.assertIn(f"'{S.FULLY_GROWN}'", _views_js())

    def test_every_named_view_is_one_the_page_knows(self):
        js = _views_js()
        for key, _words, _tip in S.VIEWS:
            self.assertRegex(js, rf"name === '{key}'", key)


class TheFlyover(unittest.TestCase):

    def test_no_frame_is_year_0(self):
        """V3.43: it opened on the finished yard and then shrank it."""
        frames = S.flyover_storyboard()
        self.assertTrue(frames)
        self.assertNotIn(0, [f[0] for f in frames])
        self.assertEqual(frames[0][0], 1)

    def test_no_frame_says_green_over_snow(self):
        """V3.46: the scene draws the region's seasons. The tour said "spring
        green" on 21 March, which is under snow."""
        from datetime import datetime
        from src import scene_season
        for year, month, hour, _big, sub in S.flyover_storyboard():
            season = scene_season.apply_seasons(
                [], datetime(2025, month, 21, hour), {})
            if "green" in sub or "bloom" in sub or "summer" in sub:
                self.assertFalse(season["snow"], (month, sub))
            if "bare" in sub:
                self.assertEqual(season["leaves"], "bare", (month, sub))

    def test_every_frame_is_a_moment_and_two_captions(self):
        for year, month, hour, big, sub in S.flyover_storyboard():
            self.assertTrue(1 <= year <= 25 and 1 <= month <= 12
                            and 0 <= hour <= 23)
            self.assertTrue(big and sub)


if __name__ == "__main__":
    unittest.main()
