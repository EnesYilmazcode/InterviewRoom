import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runner

CODE = "class Counter:\n    def __init__(self):\n        self.n = 0\n    def add(self):\n        self.n += 1\n        return self.n\n"
MINE = "import unittest\nfrom counter import Counter\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(Counter().add(), 1)\n"
HIDDEN = '''import unittest
from counter import Counter

class TestPart1(unittest.TestCase):
    def test_first(self):
        """First add returns 1"""
        self.assertEqual(Counter().add(), 1)

class TestPart2(unittest.TestCase):
    def test_reset(self):
        """reset() goes back to zero"""
        c = Counter(); c.add(); c.reset(); self.assertEqual(c.n, 0)
'''


class TestRunner(unittest.TestCase):
    def test_own_tests_pass(self):
        r = runner.run_tests({"counter.py": CODE, "test_counter.py": MINE})
        self.assertTrue(r["ok"], r["output"])

    def test_no_tests_is_not_ok(self):
        r = runner.run_tests({"counter.py": CODE})
        self.assertFalse(r["ok"])

    def test_hidden_only_up_to_part(self):
        res = runner.run_hidden({"counter.py": CODE}, HIDDEN, 1)
        self.assertEqual([(x["name"], x["ok"]) for x in res], [("part1.test_first", True)])

    def test_hidden_part_two_fails_and_explains(self):
        res = {x["name"]: x for x in runner.run_hidden({"counter.py": CODE}, HIDDEN, 2)}
        self.assertFalse(res["part2.test_reset"]["ok"])
        self.assertIn("reset", res["part2.test_reset"]["detail"])
        self.assertEqual(res["part2.test_reset"]["doc"], "reset() goes back to zero")

    def test_skip_list(self):
        res = runner.run_hidden({"counter.py": CODE}, HIDDEN, 2, skip=["part2.test_reset"])
        self.assertEqual(len(res), 1)

    def test_candidate_cannot_shadow_hidden_tests(self):
        res = runner.run_hidden({"counter.py": CODE, "hidden_tests.py": "raise SystemExit"}, HIDDEN, 1)
        self.assertTrue(res[0]["ok"])


if __name__ == "__main__":
    unittest.main()
