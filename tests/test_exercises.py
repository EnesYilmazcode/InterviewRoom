import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import exercises

REPLY = {
    "title": "Tally", "module": "Tally Board", "parts": ["### Part 1\n`add()`", "### Part 2\n`reset()`"],
    "starter": "class Tally:\n    pass\n", "answer_key": "Starts at zero.",
    "reference": "class Tally:\n    def __init__(self):\n        self.n = 0\n    def add(self):\n        self.n += 1\n        return self.n\n",
    "hidden_tests": "import unittest\nfrom tally_board import Tally\n\nclass TestPart1(unittest.TestCase):\n    def test_add(self):\n        \"\"\"add counts up\"\"\"\n        self.assertEqual(Tally().add(), 1)\n",
}


class TestExercises(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.old, exercises.ROOT = exercises.ROOT, self.root

    def tearDown(self):
        exercises.ROOT = self.old
        shutil.rmtree(self.root)

    def test_parse_accepts_fenced_json_and_cleans_module(self):
        d = exercises._parse("Here you go:\n```json\n" + json.dumps(REPLY) + "\n```")
        self.assertEqual(d["module"], "tally_board")

    def test_parse_rejects_missing_fields(self):
        with self.assertRaises(ValueError):
            exercises._parse(json.dumps({k: v for k, v in REPLY.items() if k != "hidden_tests"}))

    def test_save_then_load_round_trip(self):
        d = exercises._parse(json.dumps(REPLY))
        ex = exercises._save(d, [], 1)
        self.assertEqual(ex["title"], "Tally")
        self.assertIn("tally_board.py", ex["starter"])
        self.assertIn("from tally_board import *", ex["starter"]["test_tally_board.py"])
        self.assertIn("TestPart1", ex["hidden"])
        self.assertEqual([x["id"] for x in exercises.listing()], [ex["id"]])

    def test_hand_written_problem_without_hidden_tests(self):
        folder = os.path.join(self.root, "mine")
        os.makedirs(folder)
        with open(os.path.join(folder, "exercise.json"), "w") as f:
            json.dump({"title": "Mine", "module": "mine", "parts": ["one", "two"]}, f)
        ex = exercises.load("mine")
        self.assertIsNone(ex["hidden"])
        self.assertEqual(ex["starter"]["mine.py"], "")
        self.assertFalse(exercises.listing()[0]["hidden"])


if __name__ == "__main__":
    unittest.main()
