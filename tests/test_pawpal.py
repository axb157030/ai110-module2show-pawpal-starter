"""Tests for the PawPal+ core classes in pawpal_system.py.

Run with: pytest

Conventions used here:
- Every test uses fixed dates (TODAY / TOMORROW below), never date.today(), so
  results are the same no matter when the suite runs.
- Each test follows Arrange / Act / Assert and checks one behavior.
- Wrong types are expected to raise TypeError; right type but bad value
  (blank name, 0-minute task, ...) is expected to raise ValueError.
"""

from datetime import date, datetime, time

import pytest

from pawpal_system import Owner, Pet, Priority, Scheduler, Task

# Fixed reference dates so every test is deterministic.
TODAY = date(2026, 10, 15)
TOMORROW = date(2026, 10, 16)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    """Build a datetime on `day` at hour:minute (keeps test setup short and readable)."""
    return datetime.combine(day, time(hour, minute))


@pytest.fixture
def owner() -> Owner:
    """An owner available 08:00-20:00 with no pets yet."""
    return Owner("Sam", available_start=time(8), available_end=time(20))


# ---------------------------------------------------------------------------
# Basic behavior
# ---------------------------------------------------------------------------


def test_mark_complete_changes_status():
    task = Task("Morning walk", 30, Priority.HIGH)
    assert task.is_completed is False

    task.mark_complete()

    assert task.is_completed is True


def test_add_task_increases_pet_task_count():
    pet = Pet("Biscuit", "dog")
    assert len(pet.list_tasks()) == 0

    pet.add_task(Task("Feeding", 10, Priority.HIGH))

    assert len(pet.list_tasks()) == 1


# ---------------------------------------------------------------------------
# Edge case 1: two pets sharing the same task (e.g. one walk for both dogs)
# ---------------------------------------------------------------------------


def test_shared_task_belongs_to_both_pets_but_is_listed_once(owner):
    # Arrange: one Task object added to two pets, and added to Biscuit twice.
    biscuit, rex = Pet("Biscuit", "dog"), Pet("Rex", "dog")
    owner.add_pet(biscuit)
    owner.add_pet(rex)
    walk = Task("Park walk", 60, start_time=at(TODAY, 9))

    # Act
    biscuit.add_task(walk)
    rex.add_task(walk)
    biscuit.add_task(walk)  # duplicate add should be ignored

    # Assert: each pet has it exactly once, and the owner sees one task, not two.
    assert biscuit.list_tasks() == [walk]
    assert rex.list_tasks() == [walk]
    assert owner.get_all_tasks() == [walk]
    assert owner.pets_for_task(walk) == [biscuit, rex]


def test_shared_task_is_not_a_conflict_and_is_scheduled_once(owner):
    # Arrange: the same 09:00 walk on two pets.
    biscuit, rex = Pet("Biscuit", "dog"), Pet("Rex", "dog")
    owner.add_pet(biscuit)
    owner.add_pet(rex)
    walk = Task("Park walk", 60, start_time=at(TODAY, 9))
    biscuit.add_task(walk)
    rex.add_task(walk)
    scheduler = Scheduler(owner)

    # Act
    conflicts = scheduler.detect_conflicts()
    plan = scheduler.generate_daily_plan(TODAY)

    # Assert: a task never clashes with itself; the plan lists it once, for both dogs.
    assert conflicts == []
    assert [t.name for t in plan.scheduled_tasks] == ["Park walk"]
    assert plan.pet_labels_by_task[walk.task_id] == ["Biscuit (dog)", "Rex (dog)"]


# ---------------------------------------------------------------------------
# Edge case 2: tasks of DIFFERENT pets that overlap in time
# Scenario: tomorrow, cat bath 16:15-16:45 (30 min) and parrot feeding
# 16:30-16:45 (15 min). The owner can't do both, so this is a conflict.
# ---------------------------------------------------------------------------


@pytest.fixture
def cat_bath_and_parrot_feeding(owner):
    """Owner with a cat and a parrot whose tasks overlap by 15 minutes tomorrow."""
    luna, kiwi = Pet("Luna", "cat"), Pet("Kiwi", "parrot")
    owner.add_pet(luna)
    owner.add_pet(kiwi)
    bath = Task("Bath", 30, Priority.MEDIUM, start_time=at(TOMORROW, 16, 15))
    feeding = Task("Feeding", 15, Priority.HIGH, start_time=at(TOMORROW, 16, 30))
    luna.add_task(bath)
    kiwi.add_task(feeding)
    return owner, bath, feeding


def test_overlapping_tasks_of_different_pets_are_detected(cat_bath_and_parrot_feeding):
    owner, bath, feeding = cat_bath_and_parrot_feeding

    conflicts = Scheduler(owner).detect_conflicts()

    # Feeding starts at 16:30, before the bath ends at 16:45 -> 15 min overlap.
    # Pairs are reported earliest-start first.
    assert conflicts == [(bath, feeding)]
    assert bath.overlap_minutes(feeding) == 15


def test_daily_plan_keeps_higher_priority_task_when_pets_tasks_clash(cat_bath_and_parrot_feeding):
    owner, bath, feeding = cat_bath_and_parrot_feeding

    plan = Scheduler(owner).generate_daily_plan(TOMORROW)

    # HIGH-priority feeding wins; the MEDIUM bath is skipped with a clear reason.
    assert plan.scheduled_tasks == [feeding]
    assert plan.skipped_tasks == [bath]
    assert any("Bath: skipped" in r and "by 15 min" in r for r in plan.reasoning)


# ---------------------------------------------------------------------------
# Edge case 3: same due date, but the time windows don't overlap
# Conflicts are about when the owner is busy (start_time + duration), not
# about due dates, so sharing a due date alone must not count as a conflict.
# ---------------------------------------------------------------------------


def test_same_due_date_with_separate_or_back_to_back_windows_is_not_a_conflict(owner):
    # Arrange: three tasks all due at the same moment.
    #   Brushing   09:00-09:30
    #   Feeding    09:30-09:40  (starts exactly when brushing ends: touching, not overlapping)
    #   Grooming   14:00-14:30  (hours later)
    pet = Pet("Biscuit", "dog")
    owner.add_pet(pet)
    same_due = at(TODAY, 18)
    brushing = Task("Brushing", 30, due_date=same_due, start_time=at(TODAY, 9))
    feeding = Task("Feeding", 10, due_date=same_due, start_time=at(TODAY, 9, 30))
    grooming = Task("Grooming", 30, due_date=same_due, start_time=at(TODAY, 14))
    for task in (brushing, feeding, grooming):
        pet.add_task(task)
    scheduler = Scheduler(owner)

    # Act
    conflicts = scheduler.detect_conflicts()
    plan = scheduler.generate_daily_plan(TODAY)

    # Assert: no conflicts, and all three fit in the plan in time order.
    assert conflicts == []
    assert brushing.overlaps(feeding) is False
    assert plan.scheduled_tasks == [brushing, feeding, grooming]
    assert plan.skipped_tasks == []


# ---------------------------------------------------------------------------
# Edge case 4: empty data (owner with no pets, pets with no tasks)
# ---------------------------------------------------------------------------


def test_owner_with_no_pets_gives_empty_results_not_errors(owner):
    scheduler = Scheduler(owner)

    plan = scheduler.generate_daily_plan(TODAY)

    assert owner.get_all_tasks() == []
    assert owner.filter_pets(pet_type="dog") == []
    assert scheduler.detect_conflicts() == []
    assert scheduler.sort_by_weighted_priority(today=TODAY) == []
    assert plan.scheduled_tasks == [] and plan.skipped_tasks == []
    assert plan.total_minutes() == 0
    assert "(nothing scheduled)" in plan.explain()


def test_pets_with_no_tasks_leave_the_whole_day_free(owner):
    owner.add_pet(Pet("Biscuit", "dog"))
    owner.add_pet(Pet("Kiwi", "parrot"))
    scheduler = Scheduler(owner)

    # Asking at 07:00 (before the owner's 08:00 start) should return 08:00.
    assert scheduler.next_available_slot(30, at(TODAY, 7)) == at(TODAY, 8)
    assert scheduler.generate_daily_plan(TODAY).scheduled_tasks == []


# ---------------------------------------------------------------------------
# Invalid input: wrong types and bad values are rejected with a clear error
# ---------------------------------------------------------------------------


def test_task_with_only_a_name_is_rejected():
    # duration_minutes is required: a task must say how long it takes.
    with pytest.raises(TypeError):
        Task("Walk")


@pytest.mark.parametrize(
    "kwargs, error",
    [
        pytest.param({"name": 123}, TypeError, id="number as a task name"),
        pytest.param({"name": "   "}, ValueError, id="blank name"),
        pytest.param({"duration_minutes": "thirty"}, TypeError, id="non-numeric string"),
        pytest.param({"duration_minutes": "30"}, TypeError, id="numeric string is still text"),
        pytest.param({"duration_minutes": 0}, ValueError, id="a task must take some time"),
        pytest.param({"duration_minutes": True}, TypeError, id="bool is not a duration"),
        pytest.param({"priority": "high"}, TypeError, id="must be Priority.HIGH"),
        pytest.param({"frequency": True}, TypeError, id="bool instead of a Frequency"),
        pytest.param({"start_time": True}, TypeError, id="bool instead of a datetime"),
        pytest.param({"start_time": "2026-10-15 09:00"}, TypeError, id="text instead of a datetime"),
        pytest.param({"due_date": TODAY}, TypeError, id="date without a time of day"),
        pytest.param({"is_completed": "yes"}, TypeError, id="text instead of True/False"),
    ],
)
def test_invalid_task_values_are_rejected(kwargs, error):
    valid = {"name": "Walk", "duration_minutes": 30}

    with pytest.raises(error):
        Task(**{**valid, **kwargs})


@pytest.mark.parametrize(
    "kwargs, error",
    [
        pytest.param({"name": 42}, TypeError, id="number as a pet name"),
        pytest.param({"name": ""}, ValueError, id="empty name"),
        pytest.param({"pet_type": 7}, TypeError, id="number as a pet type"),
        pytest.param({"age": "three"}, TypeError, id="non-numeric string"),
        pytest.param({"age": -1}, ValueError, id="negative age"),
        pytest.param({"ailments": "arthritis"}, TypeError, id="a single string, not a list"),
    ],
)
def test_invalid_pet_values_are_rejected(kwargs, error):
    valid = {"name": "Biscuit", "pet_type": "dog"}

    with pytest.raises(error):
        Pet(**{**valid, **kwargs})


def test_invalid_owner_and_scheduler_values_are_rejected(owner):
    with pytest.raises(TypeError):
        Owner(5)  # number as an owner name
    with pytest.raises(TypeError):
        Owner("Sam", available_start="8am")  # text instead of a time
    with pytest.raises(ValueError):
        Owner("Sam", available_start=time(20), available_end=time(8))  # start after end
    with pytest.raises(TypeError):
        Scheduler("Sam")  # a name instead of an Owner object
    with pytest.raises(TypeError):
        owner.add_pet("Biscuit")  # a name instead of a Pet object
    with pytest.raises(TypeError):
        Pet("Biscuit", "dog").add_task("Walk")  # a name instead of a Task object


def test_invalid_edit_is_rejected_and_leaves_task_unchanged():
    task = Task("Walk", 30, Priority.HIGH)

    # One bad value in the edit means nothing is applied, not even the valid name change.
    with pytest.raises(TypeError):
        task.edit(name="Long walk", duration_minutes="forty")

    assert task.name == "Walk"
    assert task.duration_minutes == 30
