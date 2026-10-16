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

    def next_occurrence(self) -> Task | None:
        """The next instance of a repeating task: same details, not completed, new id.

        Its due_date and start_time move forward by one day, week, or month. A monthly
        task on the 31st lands on the last day of shorter months.
        Returns None if frequency is NONE. Does not add the copy to any pet.
        """
        if self.frequency == Frequency.NONE:
            return None

        def shift(dt: datetime | None) -> datetime | None:
            """Move a datetime forward by one repeat period (None stays None)."""
            if dt is None:
                return None
            if self.frequency == Frequency.DAILY:
                return dt + timedelta(days=1)
            if self.frequency == Frequency.WEEKLY:
                return dt + timedelta(weeks=1)
            return _add_months(dt, 1)

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
        """
        _check_type(task, Task, "task")
        if all(t.task_id != task.task_id for t in self.tasks):
            self.tasks.append(task)

    def list_tasks(self) -> list[Task]:
        """Return this pet's tasks."""
        return list(self.tasks)

    def get_task(self, task_id: str) -> Task | None:
        """Return this pet's task with this id, or None."""
        return next((t for t in self.tasks if t.task_id == task_id), None)

    def edit_task(self, task_id: str, **fields) -> None:
        """Update one of this pet's tasks by id."""
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(f"{self.name} has no task with id {task_id}")
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
        """Add a pet to this owner. Adding the same pet twice does nothing."""
        _check_type(pet, Pet, "pet")
        if self.get_pet(pet.pet_id) is None:
            self.pets.append(pet)

    def edit_pet(self, pet_id: str, **fields) -> None:
        """Update one of this owner's pets by id."""
        pet = self.get_pet(pet_id)
        if pet is None:
            raise KeyError(f"No pet with id {pet_id}")
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

        Uses all tasks if `tasks` is None. Returns a new list; the input is not changed.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks
        return sorted(
            tasks,
            key=lambda t: (
                -self.weighted_priority(t, today),
                t.due_date or datetime.max,
                t.name.lower(),
            ),
        )

    def sort_by_due_date(self, tasks: list[Task] | None = None) -> list[Task]:
        """Earliest due date first; tasks with no due date go last. Ties: higher priority first.

        Uses all tasks if `tasks` is None. Returns a new list; the input is not changed.
        """
        tasks = self.get_all_tasks() if tasks is None else tasks
        return sorted(
            tasks,
            key=lambda t: (
                t.due_date is None,
                t.due_date or datetime.max,
                -PRIORITY_WEIGHT[t.priority],
                t.name.lower(),
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
    ) -> list[Task]:
        """Find tasks matching ALL the criteria given; criteria left as None are ignored.

        name/description: partial, case-insensitive. is_completed/priority: exact.
        due_date: due on that calendar day. min_weighted_priority: score at least this.
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
        """Time-block tasks for a day. Returns (scheduled copies, [(skipped task, reason)])."""
        window_start, window_end = self._window(day)
        ordered = self.sort_by_weighted_priority(tasks, today=day)
        scheduled: list[Task] = []
        skipped: list[tuple[Task, str]] = []

        # Fixed-time tasks (e.g. a vet visit) go first, highest priority first.
        for task in (t for t in ordered if t.start_time is not None):
            clash = next((s for s in scheduled if task.overlaps(s)), None)
            if clash is not None:
                skipped.append((
                    task,
                    f"its {task.start_time:%H:%M}-{task.end_time():%H:%M} slot overlaps "
                    f"higher-priority '{clash.name}' ({clash.start_time:%H:%M}-{clash.end_time():%H:%M}) "
                    f"by {task.overlap_minutes(clash)} min",
                ))
            else:
                scheduled.append(task)

        # Flexible tasks fill the earliest free gap in the owner's available hours.
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

    def handle_recurring_tasks(self) -> list[Task]:
        """For each completed repeating task, add its next occurrence to the same pets.

        Example: completing today's daily walk creates tomorrow's walk for both dogs.
        Safe to call repeatedly: skips a task whose next occurrence (same name, same next
        due date/start time) already exists. Returns only the newly created tasks.
        """
        all_tasks = self.get_all_tasks()
        created: list[Task] = []
        for task in all_tasks:
            if not task.is_completed:
                continue
            upcoming = task.next_occurrence()
            if upcoming is None:
                continue
            already_exists = any(
                t.name == upcoming.name
                and t.due_date == upcoming.due_date
                and t.start_time == upcoming.start_time
                for t in all_tasks + created
            )
            if already_exists:
                continue
            for pet in self.owner.pets_for_task(task):
                pet.add_task(upcoming)
            created.append(upcoming)
        return created

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
