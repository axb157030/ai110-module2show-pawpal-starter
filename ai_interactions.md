# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agent Workflow (SF7)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

<!-- Describe the goal you asked the agent to accomplish -->
- I asked Claude to make test cases to test pawpal_system.py. Here are the prompts I used to generate tests for edge cases

```bash
Also add 4 complex edge case tests. Test when users have 2 pets with the same task. Test whether there is a conflict on that or not and whether a user can add 2 pets with the same task. Test when one pet has a task that overlaps with another task that belongs to a different pet.  A person feeds their parrot at 4:30 pm   tomorrow which takes 15 minutes,and also bathes their cat at 4:15 pm which takes 30 minutes. Also test tasks that have overlaaping due dates but the duration since their respective start dates do not overlap. Test scheduler, owner, when there are no tasks and pets respectively. Handle invalid input like not giving any values to the tasks except for the name. Assigning numbers to task and pet names. Handle non numeric strings, assigning values to attributes of the core classes such as Owner and Scheduler. Assigning booleans in places that except the task frequency, the task start date. etc. Tests should be specific. The test file should be well documented and have comments as defined by common best practices. The tests should be deterministic
```

```bash
Can add more test case such 12 test cases
```

**What did the agent do?**

<!-- List the steps the agent took (files edited, commands run, etc.) -->

1. **Read the existing code and test setup.** `tests/test_pawpal.py` was empty, and pytest was already listed in `requirements.txt`.
2. **Wrote the first two tests** (`mark_complete` and `add_task`) and ran them. They passed with `python -m pytest`, but plain `pytest`, the command in the README, failed with `ModuleNotFoundError: No module named 'pawpal_system'`. The agent added a three-line `pytest.ini` that tells pytest to look in the project root and collect tests from `tests/`.
3. **Checked how the classes handled bad input before writing the edge-case tests.** A short script created objects with invalid values. Only "task with just a name" raised an error. Numbers as names, `"thirty"` as a duration, `True` as a frequency or start time, `Scheduler("Bob")` and a start time after the end time were all accepted without any error.
4. **Added validation to `pawpal_system.py`** so those tests would have something to check:
   - four small check functions, raising `TypeError` for a wrong type and `ValueError` for a bad value;
   - checks that run when a Task, Pet or Owner is created;
   - all-or-nothing `edit()` methods;
   - type checks in `Scheduler()`, `add_pet` and `add_task`.
5. **Confirmed nothing broke** by rerunning `main.py` and an earlier test script, both of which still worked.
6. **Wrote the 12 new tests**, adjusting the plan when I asked for 12 partway through:
   - fixed dates throughout so results are deterministic;
   - shared setup helpers (fixtures) for repeated scenarios, such as the cat-and-parrot clash;
   - one list-driven test for each class's invalid values.
7. **Ran the suite:** 30 out of 30 passed.
8. **Cleaned up:**
   - removed an unused import the editor flagged;
   - renamed the list-driven cases so a failure reads `[number as a task name]` instead of `[kwargs0]`;
   - reran the suite, and it passed again.

**What the agent didn't do:** it didn't change any scheduling logic, and every test passed on its first run apart from the import problem in step 2. The main changes beyond the tests were the validation in step 4, which goes beyond "write tests", and the new `pytest.ini`.

-

**Edge cases tested and why**

| Edge case | Rationale |
|-----------|-----------|
| Two pets share the same task | A shared task like a park walk is one Task object on two pets. If it were counted twice, the plan would schedule it twice and conflict detection would report it as clashing with itself. |
| Tasks of different pets overlap (cat bath 16:15, 30 min, and parrot feeding 16:30, 15 min) | The owner is the one doing the tasks, so a clash between two different pets' tasks is still a real conflict. The higher-priority task should be kept and the reason for skipping the other should be clear. |
| Same due date, but the time windows don't overlap | A conflict depends on when the owner is busy (start time + duration), not on the deadline. Tasks that end and start at the same minute (09:30) should not count as a conflict. |
| Owner with no pets / pets with no tasks | A new user starts with no data. The app should show an empty plan and a free day instead of crashing. |
| Invalid input (missing fields, numbers as names, text or booleans where a number, time, or frequency is expected) | Without validation, bad values were accepted silently and only failed later in scheduling with confusing errors. Rejecting them right away with a clear `TypeError`/`ValueError` keeps bad data out of the plan and the saved JSON. |
| Invalid edit | If an edit with one bad value were partly applied, the task would be left half-changed. An edit is either applied in full or not at all. |

**What did you have to verify or fix manually?**

<!-- Describe anything the agent got wrong or that required human review -->

---

## Prompt Comparison (SF11)

> Compare two different prompts (or two different models) on the same task.

| | Option A | Option B |
|-|----------|----------|
| **Model / tool used** | | |
| **Prompt** | | |
| **Response summary** | | |
| **What was useful** | | |
| **Problems noticed** | | |
| **Decision** | | |

**Which approach did you use in your final implementation and why?**

<!-- Your conclusion -->
