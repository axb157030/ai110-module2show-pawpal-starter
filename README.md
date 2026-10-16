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

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

> Fill in once you've implemented scheduling logic.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | | e.g., by priority, duration |
| Filtering | | e.g., skip tasks if time runs out |
| Conflict handling | | e.g., overlapping time slots |
| Recurring tasks | | e.g., daily vs. weekly |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
