# Problems

This folder is yours. Everything in it except this file is ignored by git, so nothing you put here gets pushed.

Every time the coding room writes a fresh problem, it saves it here, and you can run it again from **Use a saved problem**. You can also add your own: one folder per problem.

```
exercises/
  my-problem/
    exercise.json      title, module name, the parts, the answer key
    my_module.py       the starting code the candidate sees
    test_my_module.py  optional: starting test file (one is made for you if missing)
    hidden_tests.py    optional: the tests your interviewer runs
    reference.py       optional: a known-good solution, for your own checking
```

`exercise.json`:

```json
{
  "title": "Short name",
  "module": "my_module",
  "parts": [
    "### Part 1: ...\nWhat to build, with exact method signatures in backticks.",
    "### Part 2: ...\nA new requirement that builds on part 1.",
    "### Part 3: ...\nA harder requirement with something to discuss."
  ],
  "answer_key": "Edge cases the interviewer explains only when asked, one per line.",
  "skip": []
}
```

The parts are markdown. Only Part 1 is shown at the start; the interviewer reveals the next part after walking through your code.

`hidden_tests.py` is a normal `unittest` file that imports from your module and has one class per part: `TestPart1`, `TestPart2`, `TestPart3`. When the interviewer runs them for part N, every class up to N runs. Give each test method a one-line docstring, because that line is what the candidate sees when it fails:

```python
import unittest
from my_module import Thing


class TestPart1(unittest.TestCase):
    def test_empty(self):
        """A new Thing has nothing in it."""
        self.assertEqual(Thing().items(), [])
```

To leave a test out without deleting it, put its name (like `"part2.test_empty"`) in `skip`.

Without `hidden_tests.py` the problem still works; the interviewer reads your code instead of running tests.
