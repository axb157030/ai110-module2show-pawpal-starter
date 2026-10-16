"""PawPal+ core classes.

Implements the design in diagrams/uml_draft.mmd.
"""

from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta
from enum import Enum


def _new_id() -> str:
    """Return a new random unique id (32 hex characters)."""
    return uuid.uuid4().hex


def _add_months(dt: datetime, months: int) -> datetime:
    """Move a datetime forward by whole months, clamping the day (Jan 31 + 1 month -> Feb 28/29)."""
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _when(task) -> datetime:
    """When a task happens, for ordering: its start time, else its due date, else the earliest time."""
    return task.start_time or task.due_date or datetime.min


def _parse_datetime(value: str | None) -> datetime | None:
    """Turn an ISO datetime string from JSON back into a datetime (None stays None)."""
    return datetime.fromisoformat(value) if value else None


# --- Input validation ---------------------------------------------------------
# Wrong type -> TypeError (e.g. a number as a name, True as a frequency).
# Right type, bad value -> ValueError (e.g. a blank name, a 0-minute task).


def _check_text(value, field_name: str, required: bool = False) -> None:
    """Require a string; if `required`, it must also contain something besides spaces."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be text, got {type(value).__name__}: {value!r}")
    if required and not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _check_whole_number(value, field_name: str, minimum: int) -> None:
    """Require an int (not a bool or numeric string) that is at least `minimum`."""
    # bool is a subclass of int in Python, so True would otherwise pass as 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be a whole number, got {type(value).__name__}: {value!r}")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}, got {value}")


def _check_type(value, expected: type, field_name: str, optional: bool = False) -> None:
    """Require an instance of `expected` (or None when `optional`)."""
    if optional and value is None:
        return
    # bool is only accepted where a bool is expected (it is also an int).
    if not isinstance(value, expected) or (isinstance(value, bool) and expected is not bool):
        raise TypeError(f"{field_name} must be {expected.__name__}, got {type(value).__name__}: {value!r}")


def _check_list_of(values, item_type: type, field_name: str) -> None:
    """Require a list whose items are all `item_type`."""
    _check_type(values, list, field_name)
    for item in values:
        _check_type(item, item_type, f"each item in {field_name}")


class Priority(Enum):
    """How important a task is: LOW, MEDIUM, or HIGH."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Frequency(Enum):
    """How often a task repeats: NONE, DAILY, WEEKLY, or MONTHLY."""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class Task:
    """One pet care activity: what it is, how long it takes, when, how important, and whether it repeats."""

    name: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    description: str = ""
    due_date: datetime | None = None
    start_time: datetime | None = None
    is_completed: bool = False
    frequency: Frequency = Frequency.NONE
    task_id: str = field(default_factory=_new_id)

    def __post_init__(self) -> None:
        """Reject invalid values as soon as a Task is created (or edited, via edit())."""
        _check_text(self.name, "name", required=True)
        _check_whole_number(self.duration_minutes, "duration_minutes", minimum=1)
        _check_type(self.priority, Priority, "priority")
        _check_text(self.description, "description")
        _check_type(self.due_date, datetime, "due_date", optional=True)
        _check_type(self.start_time, datetime, "start_time", optional=True)
        _check_type(self.is_completed, bool, "is_completed")
        _check_type(self.frequency, Frequency, "frequency")
        _check_text(self.task_id, "task_id", required=True)

    def mark_complete(self) -> None:
        """Mark this task as done. Completed tasks score 0 priority and are left out of plans.

        If the task repeats, Scheduler.handle_recurring_tasks() creates its next occurrence.
        """
        self.is_completed = True

    def edit(self, **fields) -> None:
        """Update any of this task's attributes by name, with the same checks as creating one.

        All-or-nothing: if any value is invalid, nothing is changed.
        """
        for key in fields:
            if key == "task_id" or not hasattr(self, key):
                raise AttributeError(f"Task has no editable field '{key}'")
        validated = replace(self, **fields)  # runs __post_init__ on the new values
        for key in fields:
            setattr(self, key, getattr(validated, key))

    def end_time(self) -> datetime | None:
        """When the task finishes: start_time + duration_minutes.

        Returns None for flexible tasks (no start_time), since they have no fixed window.
        Assumes duration_minutes is the owner's realistic estimate; a vet visit that
        really takes 15 minutes should be entered as 15, not 45.
        """
        if self.start_time is None:
            return None
        return self.start_time + timedelta(minutes=self.duration_minutes)

    def overlaps(self, other: Task) -> bool:
        """Whether the owner would need to be doing both tasks at the same moment.

        Two windows overlap when each one starts before the other ends. Touching
        windows (one ends at 10:00, the next starts at 10:00) do NOT overlap.
        Returns False if either task is flexible (no start_time) or if both are the
        same task (e.g. a shared park trip).
        """
        return self.overlap_minutes(other) > 0

    def overlap_minutes(self, other: Task) -> int:
        """How many minutes the two tasks' time windows share (0 if they don't overlap).

        Example: 10:00-10:45 and 10:30-11:00 share 15 minutes.
        Same assumptions as overlaps().
        """
        if self.task_id == other.task_id:
            return 0
        if self.start_time is None or other.start_time is None:
            return 0
        shared = min(self.end_time(), other.end_time()) - max(self.start_time, other.start_time)
        return max(0, int(shared.total_seconds() // 60))

    def is_duplicate_of(self, other: Task) -> bool:
        """Whether `other` is a different task with the same name, at the same time.

        Names are compared ignoring capitals and extra spaces. "Same time" means the same
        start_time for fixed tasks, or the same due day for flexible ones. So "Feeding" at
        08:00 and at 18:00 are NOT duplicates, and neither is tomorrow's copy of a daily task.
        """
        if self.task_id == other.task_id:
            return False
        if self.name.strip().casefold() != other.name.strip().casefold():
            return False
        if self.start_time is not None or other.start_time is not None:
            return self.start_time == other.start_time
        own_day = self.due_date.date() if self.due_date else None
        other_day = other.due_date.date() if other.due_date else None
        return own_day == other_day

    def next_occurrence(self, today: date | None = None) -> Task | None:
        """The next instance of a repeating task: same details, not completed, new id.

        Counted from `today` (the day it was completed), keeping the same time of day:
        daily -> today + 1 day, weekly -> today + 7 days, monthly -> same day next month
        (the 31st lands on the last day of shorter months). So a daily task finished late
        comes back tomorrow, not on an already-past date.
        `today` defaults to the real date; pass a fixed date for repeatable tests.
        Returns None if frequency is NONE. Does not add the copy to any pet.
        """
        if self.frequency == Frequency.NONE:
            return None
        today = today or date.today()

        def shift(dt: datetime | None) -> datetime | None:
            """Return `today` at dt's time of day, moved forward one repeat period (None stays None)."""
            if dt is None:
                return None
            # datetime.combine joins a date and a time: e.g. today + 08:00 -> today at 08:00.
            base = datetime.combine(today, dt.time())
            if self.frequency == Frequency.DAILY:
                return base + timedelta(days=1)  # timedelta handles month/year ends (Oct 31 -> Nov 1)
            if self.frequency == Frequency.WEEKLY:
                return base + timedelta(weeks=1)
            return _add_months(base, 1)  # timedelta has no "months", since months differ in length

        return replace(
            self,
            due_date=shift(self.due_date),
            start_time=shift(self.start_time),
            is_completed=False,
            task_id=_new_id(),
        )

    def to_dict(self) -> dict:
        """Convert this task to a JSON-friendly dict."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "duration_minutes": self.duration_minutes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "is_completed": self.is_completed,
            "frequency": self.frequency.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Build a task from a dict produced by to_dict."""
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data.get("description", ""),
            priority=Priority(data.get("priority", Priority.MEDIUM.value)),
            duration_minutes=data["duration_minutes"],
            due_date=_parse_datetime(data.get("due_date")),
            start_time=_parse_datetime(data.get("start_time")),
            is_completed=data.get("is_completed", False),
            frequency=Frequency(data.get("frequency", Frequency.NONE.value)),
        )


@dataclass
class Pet:
    """A pet's details and the list of care tasks it needs."""

    name: str
    pet_type: str
    age: int = 0
    description: str = ""
    ailments: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    pet_id: str = field(default_factory=_new_id)

    def __post_init__(self) -> None:
        """Reject invalid values as soon as a Pet is created (or edited, via edit())."""
        _check_text(self.name, "name", required=True)
        _check_text(self.pet_type, "pet_type", required=True)
        _check_whole_number(self.age, "age", minimum=0)
        _check_text(self.description, "description")
        _check_list_of(self.ailments, str, "ailments")
        _check_list_of(self.tasks, Task, "tasks")
        _check_text(self.pet_id, "pet_id", required=True)

    def add_task(self, task: Task) -> None:
        """Add a task to this pet (the same Task can be added to several pets).

        Adding a task the pet already has does nothing, so it is never listed twice.
        Raises ValueError if the pet already has a duplicate (see Task.is_duplicate_of).
        """
        _check_type(task, Task, "task")
        if self.get_task(task.task_id) is not None:
            return
        duplicate = self.find_duplicate_task(task)
        if duplicate is not None:
            raise ValueError(f"{self.name} already has '{duplicate.name}' at that time")
        self.tasks.append(task)

    def find_duplicate_task(self, task: Task) -> Task | None:
        """Return this pet's task that duplicates `task` (same name, same time), or None."""
        return next((t for t in self.tasks if t.is_duplicate_of(task)), None)

    def list_tasks(self) -> list[Task]:
        """Return this pet's tasks."""
        return list(self.tasks)

    def get_task(self, task_id: str) -> Task | None:
        """Return this pet's task with this id, or None."""
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def edit_task(self, task_id: str, **fields) -> None:
        """Update one of this pet's tasks by id.

        Raises ValueError (and changes nothing) if the edit would make it a duplicate of
        another of this pet's tasks.
        """
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"{self.name} has no task with id {task_id}")
        preview = replace(task)  # a copy, so the duplicate check happens before anything changes
        preview.edit(**fields)
        duplicate = self.find_duplicate_task(preview)
        if duplicate is not None:
            raise ValueError(f"{self.name} already has '{duplicate.name}' at that time")
        task.edit(**fields)

    def remove_task(self, task_id: str) -> None:
        """Remove a task from this pet by id."""
        if self.get_task(task_id) is None:
            raise KeyError(f"{self.name} has no task with id {task_id}")
        self.tasks = [t for t in self.tasks if t.task_id != task_id]

    def edit(self, **fields) -> None:
        """Update any of this pet's attributes by name, with the same checks as creating one.

        All-or-nothing: if any value is invalid, nothing is changed.
        """
        for key in fields:
            if key in ("pet_id", "tasks") or not hasattr(self, key):
                raise AttributeError(f"Pet has no editable field '{key}'")
        validated = replace(self, **fields)  # runs __post_init__ on the new values
        for key in fields:
            setattr(self, key, getattr(validated, key))

    def is_duplicate_of(self, other: Pet) -> bool:
        """Whether `other` is a different pet with the same name and species (ignoring capitals)."""
        return (
            self.pet_id != other.pet_id
            and self.name.strip().casefold() == other.name.strip().casefold()
            and self.pet_type.strip().casefold() == other.pet_type.strip().casefold()
        )

    def to_dict(self) -> dict:
        """Convert this pet to a JSON-friendly dict. Tasks are stored by id so shared tasks stay shared."""
        return {
            "pet_id": self.pet_id,
            "name": self.name,
            "pet_type": self.pet_type,
            "age": self.age,
            "description": self.description,
            "ailments": list(self.ailments),
            "task_ids": [t.task_id for t in self.tasks],
        }

    
    # By Claude Pro after trying to do it myself using @classmethod and trying to making it return a custom object
    def label(self) -> str:
        """Return a display name like 'Biscuit (dog)'."""
        return f"{self.name} ({self.pet_type})"


    @classmethod
    def from_dict(cls, data: dict, tasks_by_id: dict[str, Task] | None = None) -> Pet:
        """Build a pet from a dict produced by to_dict, linking tasks from tasks_by_id."""
        tasks_by_id = tasks_by_id or {}
        return cls(
            pet_id=data["pet_id"],
            name=data["name"],
            pet_type=data["pet_type"],
            age=data.get("age", 0),
            description=data.get("description", ""),
            ailments=list(data.get("ailments", [])),
            tasks=[tasks_by_id[i] for i in data.get("task_ids", []) if i in tasks_by_id],
        )


@dataclass
class Owner:
    """The pet owner: their available hours, preferences, and pets."""

    name: str
    available_start: time = time(8, 0)
    available_end: time = time(20, 0)
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Reject invalid values as soon as an Owner is created."""
        _check_text(self.name, "name", required=True)
        _check_type(self.available_start, time, "available_start")
        _check_type(self.available_end, time, "available_end")
        if self.available_start >= self.available_end:
            raise ValueError("available_start must be earlier than available_end")
        _check_type(self.preferences, dict, "preferences")
        _check_list_of(self.pets, Pet, "pets")

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner. Adding the same pet twice does nothing.

        Raises ValueError if the owner already has a pet with the same name and species.
        """
        _check_type(pet, Pet, "pet")
        if self.get_pet(pet.pet_id) is not None:
            return
        duplicate = self.find_duplicate_pet(pet)
        if duplicate is not None:
            raise ValueError(f"you already have a {duplicate.pet_type} named {duplicate.name}")
        self.pets.append(pet)

    def find_duplicate_pet(self, pet: Pet) -> Pet | None:
        """Return the owner's pet with the same name and species as `pet`, or None."""
        return next((p for p in self.pets if p.is_duplicate_of(pet)), None)

    def edit_pet(self, pet_id: str, **fields) -> None:
        """Update one of this owner's pets by id.

        Raises ValueError (and changes nothing) if the edit would duplicate another pet.
        """
        pet = self.get_pet(pet_id)
        if pet is None:
            raise KeyError(f"No pet with id {pet_id}")
        preview = replace(pet)  # a copy, so the duplicate check happens before anything changes
        preview.edit(**fields)
        duplicate = self.find_duplicate_pet(preview)
        if duplicate is not None:
            raise ValueError(f"you already have a {duplicate.pet_type} named {duplicate.name}")
        pet.edit(**fields)

    def remove_pet(self, pet_id: str) -> None:
        """Remove a pet by id."""
        if self.get_pet(pet_id) is None:
            raise KeyError(f"No pet with id {pet_id}")
        self.pets = [p for p in self.pets if p.pet_id != pet_id]

    def get_pet(self, pet_id: str) -> Pet | None:
        """Return the pet with this id, or None."""
        return next((p for p in self.pets if p.pet_id == pet_id), None)

    def filter_pets(
        self,
        name: str | None = None,
        pet_type: str | None = None,
        age: int | None = None,
        ailment: str | None = None,
    ) -> list[Pet]:
        """Find pets matching ALL the criteria given; criteria left as None are ignored.

        name: partial, case-insensitive ("bis" matches "Biscuit").
        pet_type: exact, case-insensitive ("DOG" matches "dog").
        age: exact. ailment: the pet has an ailment with this name (case-insensitive).
        Returns a new list; an empty list if nothing matches.
        """
        results = []
        for pet in self.pets:
            if name is not None and name.lower() not in pet.name.lower():
                continue
            if pet_type is not None and pet_type.lower() != pet.pet_type.lower():
                continue
            if age is not None and age != pet.age:
                continue
            if ailment is not None and ailment.lower() not in (a.lower() for a in pet.ailments):
                continue
            results.append(pet)
        return results

    def get_all_tasks(self) -> list[Task]:
        """Every task for every pet, as one list. This is the Scheduler's only source of tasks.

        A task shared by several pets (e.g. a park trip) appears once, not once per pet.
        Includes completed tasks; callers filter those out if needed.
        """
        tasks: list[Task] = []
        seen_ids: set[str] = set()
        for pet in self.pets:
            for task in pet.tasks:
                if task.task_id not in seen_ids:
                    seen_ids.add(task.task_id)
                    tasks.append(task)
        return tasks

    def pets_for_task(self, task: Task) -> list[Pet]:
        """Which pets a task is for. A shared task returns several pets; returns [] if none."""
        return [p for p in self.pets if p.get_task(task.task_id) is not None]

    def to_dict(self) -> dict:
        """Convert this owner, their pets, and tasks to a JSON-friendly dict."""
        return {
            "name": self.name,
            "available_start": self.available_start.isoformat(),
            "available_end": self.available_end.isoformat(),
            "preferences": self.preferences,
            "tasks": [t.to_dict() for t in self.get_all_tasks()],
            "pets": [p.to_dict() for p in self.pets],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Owner:
        """Build an owner from a dict produced by to_dict."""
        tasks_by_id = {d["task_id"]: Task.from_dict(d) for d in data.get("tasks", [])}
        return cls(
            name=data["name"],
            available_start=time.fromisoformat(data.get("available_start", "08:00")),
            available_end=time.fromisoformat(data.get("available_end", "20:00")),
            preferences=data.get("preferences", {}),
            pets=[Pet.from_dict(p, tasks_by_id) for p in data.get("pets", [])],
        )

    def save_json(self, path: str) -> None:
        """Save this owner, their pets, and tasks to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: str) -> Owner:
        """Load an owner, their pets, and tasks from a JSON file."""
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class DailyPlan:
    """The result of scheduling one day: tasks scheduled and skipped, which pets they're for, and why."""

    day: date
    scheduled_tasks: list[Task] = field(default_factory=list)
    skipped_tasks: list[Task] = field(default_factory=list)
    pet_labels_by_task: dict[str, list[str]] = field(default_factory=dict)      
    reasoning: list[str] = field(default_factory=list)

    def total_minutes(self) -> int:
        """Total minutes of scheduled work (skipped tasks not counted)."""
        return sum(t.duration_minutes for t in self.scheduled_tasks)

    def _pets_label(self, task: Task) -> str:
        """Return the comma-separated pet labels for a task, or "no pet" if it has none."""
        labels = self.pet_labels_by_task.get(task.task_id, [])
        return ", ".join(labels) if labels else "no pet" 
        # From Claude pro after trying to make it build a custom object with pet name and type values


    def explain(self) -> str:
        """The plan as readable text: scheduled tasks in time order, skipped tasks, and why.

        Used by both the CLI (main.py) and the Streamlit app, so they always match.
        """
        lines = [f"Daily plan for {self.day.isoformat()} ({self.total_minutes()} min scheduled):"]
        if not self.scheduled_tasks:
            lines.append("  (nothing scheduled)")
        for task in self.scheduled_tasks:
            start = task.start_time.strftime("%H:%M") if task.start_time else "--:--"
            lines.append(
                f"  {start} — {task.name} ({task.duration_minutes} min) "
                f"[priority: {task.priority.value}] — {self._pets_label(task)}"
            )
        if self.skipped_tasks:
            lines.append("Skipped:")
            for task in self.skipped_tasks:
                lines.append(f"  {task.name} ({task.duration_minutes} min) — {self._pets_label(task)}")
        if self.reasoning:
            lines.append("Why:")
            lines.extend(f"  - {reason}" for reason in self.reasoning)
        return "\n".join(lines)


PRIORITY_WEIGHT = {Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3}


class Scheduler:
    """Plans, sorts, filters, and checks conflicts for tasks across all of an owner's pets."""

    def __init__(self, owner: Owner) -> None:
        """Create a scheduler for this owner; raises TypeError if `owner` isn't an Owner."""
        _check_type(owner, Owner, "owner")
        self.owner = owner

    def get_all_tasks(self) -> list[Task]:
        """Every task across all of the owner's pets (delegates to Owner.get_all_tasks)."""
        return self.owner.get_all_tasks()

    def weighted_priority(self, task: Task, today: date | None = None) -> float:
        """One urgency number per task, used to decide what gets scheduled first.

        Score = 10 x priority (low 10, medium 20, high 30)
                + 10 if due today or overdue, or + 5 if due within 3 days.
        Completed tasks always score 0. Tasks with no due date get no bonus.
        `today` defaults to the real date; pass a fixed date to get repeatable results in tests.

        Ties are common: there are only a few possible scores, so two tasks with the same
        priority and the same due-date bonus score the same. The bonus is a band, not an
        exact countdown: due in 1 day and due in 3 days both get +5, and every task with no
        due date gets +0. sort_by_weighted_priority() breaks these ties by the earlier due
        date first, then alphabetically.
        """
        if task.is_completed:
            return 0.0
        score = PRIORITY_WEIGHT[task.priority] * 10.0
        if task.due_date is not None:
            today = today or date.today()
            days_until_due = (task.due_date.date() - today).days
            if days_until_due <= 0:
                score += 10
            elif days_until_due <= 3:
                score += 5
        return score

    def sort_by_weighted_priority(
        self, tasks: list[Task] | None = None, today: date | None = None
    ) -> list[Task]:
        """Most urgent first, by weighted_priority(). Ties: earlier due date, then name A-Z.

        A tie means the same priority AND the same due-date bonus (see weighted_priority).
        Because the bonus is a band, tied tasks can still have different due dates, so the
        tie goes to the one due EARLIER: an overdue task beats one due today, and a task due
        tomorrow beats one due in 3 days. Tasks with no due date come after dated ones.
        Only if the due dates are also identical is the order alphabetical (ignoring capitals),
        e.g. "Bath" before "Wing trim" when both are high priority and due at 18:00 today.

        In the daily plan, ranking first decides who wins a clash between fixed tasks and
        who gets the earlier free slot among flexible ones. The order is always the same
        for the same tasks (deterministic).

        Uses all tasks if `tasks` is None. Returns a new list; the input is not changed.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks
        return sorted(
            tasks,
            key=lambda t: (
                -self.weighted_priority(t, today),  # highest score first
                t.due_date or datetime.max,           # same score: earlier due date first (undated last)
                t.name.casefold(),                    # same due date too: alphabetical
            ),
        )
    # The sort_by_time() method
    def sort_by_due_date(self, tasks: list[Task] | None = None) -> list[Task]:
        """Earliest deadline first; tasks with no date at all go last. Ties: higher priority first.

        A task's deadline is its due_date; a fixed task with only a start_time is due when it
        starts (a 10:00 vet visit is "due" at 10:00). So tasks added in any order come out
        in time order. Uses all tasks if `tasks` is None. Returns a new list; the input is
        not changed.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks

        def deadline(t: Task) -> datetime | None:
            return t.due_date or t.start_time

        return sorted(
            tasks,
            key=lambda t: (
                deadline(t) is None,           # undated tasks last
                deadline(t) or datetime.max,   # earliest first
                -PRIORITY_WEIGHT[t.priority],  # same deadline: higher priority first
                t.name.casefold(),             # then alphabetical
            ),
        )

    def filter_tasks(
        self,
        name: str | None = None,
        description: str | None = None,
        is_completed: bool | None = None,
        priority: Priority | None = None,
        due_date: date | None = None,
        min_weighted_priority: float | None = None,
        tasks: list[Task] | None = None,
        pet_name: str | None = None,
    ) -> list[Task]:
        """Find tasks matching ALL the criteria given; criteria left as None are ignored.

        name/description: partial, case-insensitive. is_completed/priority: exact.
        due_date: due on that calendar day. min_weighted_priority: score at least this.
        pet_name: the task belongs to a pet whose name contains this (partial,
        case-insensitive); a shared task matches if ANY of its pets matches.
        Combine freely, e.g. filter_tasks(pet_name="kiwi", is_completed=False) is
        "Kiwi's tasks that are still to do".
        Searches all tasks if `tasks` is None. Returns [] if nothing matches.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks
        results = []
        for task in tasks:
            if name is not None and name.lower() not in task.name.lower():
                continue
            if description is not None and description.lower() not in task.description.lower():
                continue
            if is_completed is not None and task.is_completed != is_completed:
                continue
            if priority is not None and task.priority != priority:
                continue
            if due_date is not None and (task.due_date is None or task.due_date.date() != due_date):
                continue
            if min_weighted_priority is not None and self.weighted_priority(task) < min_weighted_priority:
                continue
            if pet_name is not None and not any(
                pet_name.casefold() in p.name.casefold() for p in self.owner.pets_for_task(task)
            ):
                continue
            results.append(task)
        return results

    def detect_conflicts(self, tasks: list[Task] | None = None) -> list[tuple[Task, Task]]:
        """Find double-bookings: pairs of tasks the owner can't do at the same time.

        Only checks incomplete tasks with a fixed start_time; flexible tasks can't
        conflict because the scheduler places them in free time. Overlap is based on
        each task's window, start_time to start_time + duration_minutes (see Task.overlaps).
        Returns (earlier task, later task) pairs; [] if there are no conflicts.
        Use Task.overlap_minutes() on a pair to see how long they clash.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks
        timed = sorted(
            (t for t in tasks if t.start_time is not None and not t.is_completed),
            key=lambda t: t.start_time,
        )
        conflicts = []
        for i, first in enumerate(timed):
            for second in timed[i + 1:]:
                if second.start_time >= first.end_time():
                    break  # sorted by start, so nothing later can overlap `first`
                conflicts.append((first, second))
        return conflicts

    def _window(self, day: date) -> tuple[datetime, datetime]:
        """Return the owner's available start and end times on `day` as datetimes."""
        return (
            datetime.combine(day, self.owner.available_start),
            datetime.combine(day, self.owner.available_end),
        )

    @staticmethod
    def _first_fit(
        busy: list[tuple[datetime, datetime]], start: datetime, end: datetime, duration_minutes: int
    ) -> datetime | None:
        """Return the earliest time in [start, end] with `duration_minutes` free, given busy intervals."""
        needed = timedelta(minutes=duration_minutes)
        candidate = start
        for busy_start, busy_end in sorted(busy):
            if busy_end <= candidate:
                continue
            if busy_start - candidate >= needed:
                break
            candidate = max(candidate, busy_end)
        return candidate if candidate + needed <= end else None

    def _plan_slots(self, tasks: list[Task], day: date) -> tuple[list[Task], list[tuple[Task, str]]]:
        """Time-block tasks for a day. Returns (scheduled copies, [(skipped task, reason)]).

        How priority decides what gets skipped:
        - Every task is ranked by weighted_priority() (priority + due-date urgency, 0 if done).
          Ties (same score) go to the earlier due date, then the name A-Z
          (see sort_by_weighted_priority).
        - Fixed-time tasks are placed BEFORE any flexible task, whatever their priority, because
          their time can't move. A low-priority fixed task still beats a high-priority flexible
          one for that time slot; the flexible one is simply placed around it.
        - Two fixed tasks that overlap: the higher-ranked one is kept, the other is SKIPPED
          (not moved to a new time, since a fixed time is usually an appointment).
        - Flexible tasks never conflict, but they're placed most-urgent first, so when the day
          runs out of room it's the lowest-ranked flexible tasks that get skipped.
        """
        window_start, window_end = self._window(day)
        # Rank once, highest score first; both passes below walk this same order.
        ordered = self.sort_by_weighted_priority(tasks, today=day)
        scheduled: list[Task] = []
        skipped: list[tuple[Task, str]] = []

        # Pass 1: fixed-time tasks (e.g. a vet visit), highest-ranked first.
        # Because higher-ranked tasks are placed first, any task already in `scheduled`
        # outranks the current one; so on a clash, the current (lower-ranked) task loses.
        for task in (t for t in ordered if t.start_time is not None):
            clash = next((s for s in scheduled if task.overlaps(s)), None)
            if clash is not None:
                # Skipped, not rescheduled: the owner decides whether to move or shorten it.
                skipped.append((
                    task,
                    f"its {task.start_time:%H:%M}-{task.end_time():%H:%M} slot overlaps "
                    f"'{clash.name}' ({clash.start_time:%H:%M}-{clash.end_time():%H:%M}), which ranks higher, "
                    f"by {task.overlap_minutes(clash)} min",
                ))
            else:
                scheduled.append(task)

        # Pass 2: flexible tasks, highest-ranked first, each into the earliest free gap within
        # the owner's available hours (fixed tasks from pass 1 count as busy time). A flexible
        # task can't clash with anything, so it is only skipped if no gap is long enough.
        # The plan gets a copy with start_time filled in; the saved task stays flexible.
        for task in (t for t in ordered if t.start_time is None):
            busy = [(s.start_time, s.end_time()) for s in scheduled]
            slot = self._first_fit(busy, window_start, window_end, task.duration_minutes)
            if slot is None:
                skipped.append((task, "no free slot left in the owner's available hours"))
            else:
                scheduled.append(replace(task, start_time=slot))

        scheduled.sort(key=lambda t: t.start_time)
        return scheduled, skipped

    def time_block(self, tasks: list[Task], day: date) -> list[Task]:
        """Fit tasks into one day without any two overlapping.

        1. Fixed-time tasks keep their time. If two clash, the higher-scoring one wins.
        2. Flexible tasks, most urgent first, go into the earliest free gap within the
           owner's available hours.
        Returns copies with start times filled in, in time order; your saved tasks are
        not changed. Tasks that don't fit are left out (generate_daily_plan reports why).
        """
        scheduled, _ = self._plan_slots(tasks, day)
        return scheduled

    def next_available_slot(self, duration_minutes: int, after: datetime) -> datetime | None:
        """Earliest time at or after `after` when the owner is free for `duration_minutes`.

        Stays within the owner's available hours on that same day and avoids incomplete
        fixed-time tasks. Flexible tasks aren't counted as busy since they have no set time.
        Returns None if no gap is long enough before the end of the day.
        """
        window_start, window_end = self._window(after.date())
        busy = [
            (t.start_time, t.end_time())
            for t in self.get_all_tasks()
            if t.start_time is not None and not t.is_completed and t.start_time.date() == after.date()
        ]
        return self._first_fit(busy, max(after, window_start), window_end, duration_minutes)

    def mark_task_complete(self, task: Task, today: date | None = None) -> Task | None:
        """Mark a task done and, if it repeats, automatically create its next occurrence.

        The next copy is due one period after `today` (see Task.next_occurrence) and is
        added to the same pets. Returns the new task, or None if the task doesn't repeat
        (or its next copy already exists). This is the method the app and main.py call
        when the owner clicks "Done".
        """
        task.mark_complete()
        return self._create_next_occurrence(task, today)

    def mark_task_incomplete(self, task: Task) -> Task | None:
        """Undo mark_task_complete(): the task is open again, and its next copy is removed.

        Works like ticking/unticking a repeating task in a calendar app: ticking creates the
        next occurrence, unticking takes it back, so tick -> untick leaves things as they were.
        The next copy is only removed if this task is the LATEST completed copy in its series
        (so the open copy really is the one it created) and that copy is still open. Unticking
        an older copy, e.g. Monday when Tuesday is also done, just reopens it and removes
        nothing. Returns the removed copy, or None.
        """
        if not task.is_completed:
            return None
        task.edit(is_completed=False)
        if task.frequency == Frequency.NONE:
            return None
        series = self._series(task)
        # A later copy was also completed, so the open copy was created by that one, not this.
        if any(t.is_completed and _when(t) > _when(task) for t in series):
            return None
        # The open copy AFTER this task is the one that completing it created. (Only look
        # later: an earlier copy may be open too, e.g. one that was unticked before.)
        upcoming = next((t for t in series if not t.is_completed and _when(t) > _when(task)), None)
        if upcoming is None:
            return None
        for pet in self.owner.pets_for_task(upcoming):
            pet.remove_task(upcoming.task_id)
        return upcoming

    def handle_recurring_tasks(self, today: date | None = None) -> list[Task]:
        """Catch-up for completed repeating tasks that don't have a next occurrence yet.

        mark_task_complete() already does this for one task; this method checks them all,
        e.g. for tasks marked done with Task.mark_complete() directly.
        Safe to call repeatedly. Returns only the newly created tasks.
        """
        created = []
        for task in self.get_all_tasks():
            if task.is_completed:
                upcoming = self._create_next_occurrence(task, today)
                if upcoming is not None:
                    created.append(upcoming)
        return created

    def _create_next_occurrence(self, task: Task, today: date | None) -> Task | None:
        """Add `task`'s next occurrence to its pets, unless that would leave two open copies.

        Rule: a repeating task has at most ONE open (not completed) copy at a time. So no
        new copy is made while an open task with the same name, frequency, and pets exists;
        that open copy IS the next occurrence. This keeps repeated calls, or old completed
        copies, from piling up extra tasks.
        """
        upcoming = task.next_occurrence(today)
        if upcoming is None:
            return None
        if self._open_copy_in_series(task) is not None:
            return None
        if any(other.is_duplicate_of(upcoming) for other in self.get_all_tasks()):
            return None
        for pet in self.owner.pets_for_task(task):
            pet.add_task(upcoming)
        return upcoming

    def _series(self, task: Task) -> list[Task]:
        """The other copies of `task`'s repeating series (not including `task` itself).

        Copies of one series share the name (ignoring capitals), the frequency, and the pets.
        """
        pet_ids = {p.pet_id for p in self.owner.pets_for_task(task)}
        return [
            other for other in self.get_all_tasks()
            if other.task_id != task.task_id
            and other.name.strip().casefold() == task.name.strip().casefold()
            and other.frequency == task.frequency
            and {p.pet_id for p in self.owner.pets_for_task(other)} == pet_ids
        ]

    def _open_copy_in_series(self, task: Task) -> Task | None:
        """The open (not completed) copy of `task`'s repeating series, or None."""
        return next((t for t in self._series(task) if not t.is_completed), None)

    @staticmethod
    def _is_for_day(task: Task, day: date) -> bool:
        """A task belongs in a day's plan if it's fixed to that day, due by that day, or undated."""
        if task.start_time is not None:
            return task.start_time.date() == day
        if task.due_date is not None:
            return task.due_date.date() <= day
        return True

    def generate_daily_plan(self, day: date) -> DailyPlan:
        """The app's main output: what to do on `day`, when, for which pets, and why.

        Picks incomplete tasks that belong to that day (fixed to that day, due on or
        before it, or undated), time-blocks them (see time_block), and records a reason
        for every task scheduled or skipped.
        Returns a DailyPlan; call .explain() on it for readable text.
        """
        candidates = [t for t in self.get_all_tasks() if not t.is_completed and self._is_for_day(t, day)]
        scheduled, skipped = self._plan_slots(candidates, day)

        reasoning = [
            f"Available {self.owner.available_start.strftime('%H:%M')}–"
            f"{self.owner.available_end.strftime('%H:%M')}; "
            f"{len(candidates)} task(s) to do, ordered by weighted priority."
        ]
        for task in scheduled:
            score = self.weighted_priority(task, today=day)
            if any(t.task_id == task.task_id and t.start_time is not None for t in candidates):
                reasoning.append(f"{task.name}: fixed time, kept at {task.start_time:%H:%M} (score {score:.0f}).")
            else:
                reasoning.append(f"{task.name}: placed in the earliest free slot (score {score:.0f}).")
        for task, reason in skipped:
            reasoning.append(f"{task.name}: skipped — {reason}.")

        plan_tasks = scheduled + [t for t, _ in skipped]
        return DailyPlan(
            day=day,
            scheduled_tasks=scheduled,
            skipped_tasks=[t for t, _ in skipped],
            pet_labels_by_task={
                t.task_id: [p.label() for p in self.owner.pets_for_task(t)] for t in plan_tasks
            },
            reasoning=reasoning,
        )
