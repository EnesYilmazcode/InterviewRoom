import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import candidate
import prompts_call
import prompts_coding

PROFILE = {"name": "Sam", "role": "Backend Intern", "company": "", "company_notes": "",
           "background": "Built a {weird} parser with braces.", "interviewer": "", "saved": True}
EXERCISE = {"parts": ["### Part 1\nReturn `{\"hits\": int}`.", "### Part 2\nMore."], "answer_key": "Hits start at 0."}


class TestPrompts(unittest.TestCase):
    def test_every_call_mode_renders(self):
        for m in prompts_call.MODES:
            text = prompts_call.interviewer(m["id"], PROFILE) + prompts_call.grader(m["id"], PROFILE)
            self.assertIn("Sam", text)
            self.assertIn("[[END]]", text)
            self.assertNotRegex(text, r"\{(kind|candidate|parts|answer_key)\}")

    def test_unknown_mode_falls_back(self):
        self.assertEqual(prompts_call.mode("nope")["id"], prompts_call.MODES[0]["id"])

    def test_coding_prompts_keep_braces_from_the_problem(self):
        text = prompts_coding.interviewer(EXERCISE, PROFILE)
        self.assertIn('{"hits": int}', text)
        self.assertIn("Hits start at 0.", text)
        self.assertIn("{weird}", prompts_coding.grader(EXERCISE, PROFILE))

    def test_placeholder_background_is_not_treated_as_a_resume(self):
        p = dict(PROFILE, background="Paste your resume here as plain text")
        self.assertIn("No background was given", candidate.describe(p))

    def test_no_em_dashes_in_what_the_models_are_told(self):
        for mod in (prompts_call, prompts_coding):
            src = open(mod.__file__, encoding="utf-8").read()
            self.assertIsNone(re.search("[–—]", src))


if __name__ == "__main__":
    unittest.main()
