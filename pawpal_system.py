"""PawPal+ core classes.

Skeleton generated from diagrams/uml_draft.mmd: names, attributes, and empty method stubs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum


def _new_id() -> str:
    return uuid.uuid4().hex


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Frequency(Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class Task:
    name: str
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    description: str = ""
    due_date: datetime | None = None
    start_time: datetime | None = None
    is_completed: bool = False
    frequency: Frequency = Frequency.NONE
    task_id: str = field(default_factory=_new_id)

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        pass

    def edit(self, **fields) -> None:
        """Update any of this task's attributes by name."""
        pass

    def end_time(self) -> datetime | None:
        """Return start_time + duration, or None if the task has no fixed start time."""
        pass

    def overlaps(self, other: Task) -> bool:
        """Return True if this task's time window overlaps the other task's."""
        pass

    def next_occurrence(self) -> Task | None:
        """Return a new, incomplete copy of this task moved forward by its frequency (None if it doesn't repeat)."""
        pass

    def to_dict(self) -> dict:
        """Convert this task to a JSON-friendly dict."""
        pass

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Build a task from a dict produced by to_dict."""
        pass


@dataclass
class Pet:
    name: str
    pet_type: str
    age: int = 0
    description: str = ""
    ailments: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    pet_id: str = field(default_factory=_new_id)

    def add_task(self, task: Task) -> None:
        """Add a task to this pet (the same Task can be added to several pets)."""
        pass

    def list_tasks(self) -> list[Task]:
        """Return this pet's tasks."""
        pass

    def edit_task(self, task_id: str, **fields) -> None:
        """Update one of this pet's tasks by id."""
        pass

    def remove_task(self, task_id: str) -> None:
        """Remove a task from this pet by id."""
        pass

    def edit(self, **fields) -> None:
        """Update any of this pet's attributes by name."""
        pass

    def to_dict(self) -> dict:
        """Convert this pet to a JSON-friendly dict."""
        pass

    @classmethod
    def from_dict(cls, data: dict) -> Pet:
        """Build a pet from a dict produced by to_dict."""
        pass


@dataclass
class Owner:
    name: str
    available_start: time = time(8, 0)
    available_end: time = time(20, 0)
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass

    def edit_pet(self, pet_id: str, **fields) -> None:
        """Update one of this owner's pets by id."""
        pass

    def remove_pet(self, pet_id: str) -> None:
        """Remove a pet by id."""
        pass

    def get_pet(self, pet_id: str) -> Pet | None:
        """Return the pet with this id, or None."""
        pass

    def filter_pets(
        self,
        name: str | None = None,
        pet_type: str | None = None,
        age: int | None = None,
        ailment: str | None = None,
    ) -> list[Pet]:
        """Return pets matching every criterion given; criteria left as None are ignored."""
        pass

    def to_dict(self) -> dict:
        """Convert this owner, their pets, and tasks to a JSON-friendly dict."""
        pass

    @classmethod
    def from_dict(cls, data: dict) -> Owner:
        """Build an owner from a dict produced by to_dict."""
        pass

    def save_json(self, path: str) -> None:
        """Save this owner, their pets, and tasks to a JSON file."""
        pass

    @classmethod
    def load_json(cls, path: str) -> Owner:
        """Load an owner, their pets, and tasks from a JSON file."""
        pass


@dataclass
class DailyPlan:
    day: date
    scheduled_tasks: list[Task] = field(default_factory=list)
    skipped_tasks: list[Task] = field(default_factory=list)
    pet_names_by_task: dict[str, list[str]] = field(default_factory=dict)
    reasoning: list[str] = field(default_factory=list)

    def total_minutes(self) -> int:
        """Return the total duration of the scheduled tasks."""
        pass

    def explain(self) -> str:
        """Return the plan and its reasoning as readable text."""
        pass


class Scheduler:
    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of the owner's pets, with shared tasks listed once."""
        pass

    def pets_for_task(self, task: Task) -> list[Pet]:
        """Return the pets whose task list contains this task."""
        pass

    def weighted_priority(self, task: Task) -> float:
        """Score a task from its priority and completion status (higher = more urgent)."""
        pass

    def sort_by_weighted_priority(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted from highest to lowest weighted priority."""
        pass

    def sort_by_due_date(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted by due date, earliest first."""
        pass

    def filter_tasks(
        self,
        name: str | None = None,
        description: str | None = None,
        is_completed: bool | None = None,
        priority: Priority | None = None,
        due_date: date | None = None,
        min_weighted_priority: float | None = None,
    ) -> list[Task]:
        """Return tasks matching every criterion given; criteria left as None are ignored."""
        pass

    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        """Return pairs of tasks whose time windows overlap."""
        pass

    def time_block(self, tasks: list[Task]) -> list[Task]:
        """Assign start times so tasks fit the owner's available hours without overlapping."""
        pass

    def next_available_slot(self, duration_minutes: int, after: datetime) -> datetime | None:
        """Return the earliest start time after `after` with room for a task of this length."""
        pass

    def handle_recurring_tasks(self) -> list[Task]:
        """Create the next occurrence of each completed recurring task; return the new tasks."""
        pass

    def generate_daily_plan(self, day: date) -> DailyPlan:
        """Build the plan for a day: pick, order, and time-block tasks, recording the reasoning."""
        pass
