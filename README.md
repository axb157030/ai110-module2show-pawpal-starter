# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Implementation Summary

I built **PawPal+**, an app where an owner adds care tasks to each of their pets (for example, a morning walk for Sally the poodle and feeding Stacy the parrot) and gets a daily plan that explains its choices.

**How the classes work together:**

- **Task**: one care activity: name, duration, priority, optional due date and fixed start time, completion status, and how often it repeats (daily, weekly, monthly).
- **Pet**: a pet's details (name, type, age, ailments) and its list of tasks. Two pets can share the same task, like one walk for two dogs; it is stored once and scheduled once.
- **Owner**: the owner's available hours and their pets. `get_all_tasks()` gathers every pet's tasks into one list, and the owner can save and load everything as JSON.
- **Scheduler**: the "brain." It reads tasks only through the Owner, so it always works across all pets. It scores each task by **weighted priority** (higher priority, closer due date, and not yet completed means a higher score). It can sort and filter tasks, detect overlapping tasks, find the next free time slot, and create the next copy of a completed repeating task.
- **DailyPlan**: the result of `Scheduler.generate_daily_plan()`. It lists scheduled tasks in time order, skipped tasks, which pets each task is for, and the reason for every decision.

**Flow:** Owner → pets → tasks → Scheduler → DailyPlan → printed in `main.py` or shown in the Streamlit app.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```

## 🧪 Testing PawPal+

Run the test suite from the project folder (with the virtual environment activated):

```bash
python -m pytest
```

Add `-v` to see the name of every test. All tests use fixed dates, so they give the same result on any day.

**What the tests cover** (`tests/test_pawpal.py`, 52 tests):

- **Basics:** marking a task complete changes its status; adding a task to a pet increases its task count.
- **Sorting:** tasks added out of order come back in time order by due date (a fixed task's start time counts as its deadline); weighted-priority ties go to the earlier due date, then alphabetically.
- **Filtering:** by completion status, by pet name (partial, ignores capitals), and both combined.
- **Conflicts:** overlapping tasks of different pets are detected with the overlap in minutes (cat bath 16:15–16:45 vs. parrot feeding 16:30); tasks with the same due date or back-to-back times are *not* conflicts; the daily plan keeps the higher-ranked task and explains why the other was skipped.
- **Shared tasks:** one task for two pets is listed, scheduled, and recurred once, and never conflicts with itself.
- **Recurring tasks:** completing a daily task creates the next one for today + 1 day (weekly: + 7 days), including late tasks and month ends (Oct 31 → Nov 1); unticking takes the copy back, and repeated ticking never piles up copies.
- **Duplicates:** the same pet (name + species) or the same task at the same time can't be added twice, and an edit that would create one changes nothing.
- **Empty data:** an owner with no pets or pets with no tasks give empty results, not errors.
- **Invalid input:** wrong types (a number as a name, text as a duration, `True` as a frequency) and bad values (blank names, 0-minute tasks, start time after end time) are rejected with a clear error.

Output of a successful run:

```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\amine\Documents\codepath-training\AI\projects\ai110-module2show-pawpal-starter
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collected 52 items

tests\test_pawpal.py ................................................... [ 98%]
.                                                                        [100%]

============================= 52 passed in 0.11s ==============================
```

**Confidence Level: (4/5)**

All 52 tests pass, covering the core scheduling behaviors, multi-pet cases, and invalid input. One star is held back. To expedite development AI was used and made much black code. Also the Streamlit UI was only tested manually. 



## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting |sort_by_weighted_priority | Sort by a value calculated from task  priority, duration and its completion status. |
| Task sorting |sort_by_due_date | Sort by task due date. If their is a tie, it will sorted by task weighted priority. |

| Filtering | filter_pets | Filters tasks by name, pet type, age, and ailments. |
| Filtering | filter_tasks| Filters tasks by Task name, description, completion status, priority, task due date, weighted priority task has to be at no less of, and pet name |
| Conflict handling | detect_conflict | for tasks that are not complete and have their start dates set, if a task that starts at X time and has a duration of X2 but if X time plus X2 duration is a time that is over a start date of another task, then those 2 tasks are added to a list, which is returned|
| Recurring tasks | handle_recurring_tasks | "every completed repeating task has its next occurrence created." From Claude Free version. |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:


1. Add a pet <img src="./assets/add_pet_1.png" alt="UI showing adding a white cat"/>
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
