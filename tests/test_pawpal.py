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

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

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


# ---------------------------------------------------------------------------
# Duplicates: same pet twice, or the same task twice for one pet at one time
# ---------------------------------------------------------------------------


def test_pet_with_same_name_and_species_is_rejected(owner):
    owner.add_pet(Pet("Biscuit", "dog"))

    # Same name and species, even with different capitals and spacing -> duplicate.
    with pytest.raises(ValueError):
        owner.add_pet(Pet(" biscuit ", "DOG"))
    # Same name but a different species is a different pet, so it's allowed.
    owner.add_pet(Pet("Biscuit", "cat"))

    assert [p.label() for p in owner.pets] == ["Biscuit (dog)", "Biscuit (cat)"]


def test_same_task_name_at_the_same_time_is_rejected_but_other_times_are_allowed():
    pet = Pet("Luna", "cat")
    pet.add_task(Task("Feeding", 10, start_time=at(TODAY, 8)))
    pet.add_task(Task("Brushing", 10, due_date=at(TODAY, 18)))

    # Fixed task: same name, same start time -> duplicate.
    with pytest.raises(ValueError):
        pet.add_task(Task("feeding", 10, start_time=at(TODAY, 8)))
    # Flexible task: same name, due the same day (even at a different hour) -> duplicate.
    with pytest.raises(ValueError):
        pet.add_task(Task("Brushing", 10, due_date=at(TODAY, 9)))

    # Same name at another time, or on another day, is a separate task.
    pet.add_task(Task("Feeding", 10, start_time=at(TODAY, 18)))
    pet.add_task(Task("Brushing", 10, due_date=at(TOMORROW, 18)))

    assert len(pet.list_tasks()) == 4


def test_recurring_task_still_creates_next_day_copy(owner):
    # Tomorrow's copy has the same name, so it must not be mistaken for a duplicate.
    pet = Pet("Biscuit", "dog")
    owner.add_pet(pet)
    walk = Task("Walk", 30, start_time=at(TODAY, 7), frequency=Frequency.DAILY)
    pet.add_task(walk)
    walk.mark_complete()

    created = Scheduler(owner).handle_recurring_tasks(today=TODAY)

    assert [t.start_time for t in created] == [at(TOMORROW, 7)]
    assert len(pet.list_tasks()) == 2


def test_edit_that_would_create_a_duplicate_is_rejected_and_changes_nothing(owner):
    biscuit, rex = Pet("Biscuit", "dog"), Pet("Rex", "dog")
    owner.add_pet(biscuit)
    owner.add_pet(rex)
    morning = Task("Walk", 30, start_time=at(TODAY, 7))
    evening = Task("Walk", 30, start_time=at(TODAY, 18))
    biscuit.add_task(morning)
    biscuit.add_task(evening)

    # Renaming Rex to "Biscuit" would give the owner two dogs named Biscuit.
    with pytest.raises(ValueError):
        owner.edit_pet(rex.pet_id, name="Biscuit")
    # Moving the evening walk to 07:00 would duplicate the morning walk.
    with pytest.raises(ValueError):
        biscuit.edit_task(evening.task_id, start_time=at(TODAY, 7))

    assert rex.name == "Rex"
    assert evening.start_time == at(TODAY, 18)


# ---------------------------------------------------------------------------
# Ties: same priority AND same due-date bonus -> same score
#   -> earlier due date first -> then alphabetical
# ---------------------------------------------------------------------------


def test_tied_scores_are_sorted_alphabetically(owner):
    # All three are high priority and due at the same moment today: 30 + 10 = 40 each,
    # and the due dates are identical too, so the last tie-break (name A-Z) decides.
    pet = Pet("Kiwi", "parrot")
    owner.add_pet(pet)
    for name in ("Wing trim", "bath", "Feeding"):  # mixed capitals on purpose
        pet.add_task(Task(name, 15, Priority.HIGH, due_date=at(TODAY, 18)))
    scheduler = Scheduler(owner)

    ordered = scheduler.sort_by_weighted_priority(today=TODAY)

    assert {scheduler.weighted_priority(t, TODAY) for t in ordered} == {40}
    assert [t.name for t in ordered] == ["bath", "Feeding", "Wing trim"]


def test_tied_fixed_tasks_that_clash_keep_the_alphabetically_first(owner):
    # Same score and same due date (high, due 18:00 today). Wing trim STARTS earlier, but
    # start time isn't a tie-break, so Bath wins by name.
    pet = Pet("Kiwi", "parrot")
    owner.add_pet(pet)
    wing_trim = Task("Wing trim", 30, Priority.HIGH, due_date=at(TODAY, 18), start_time=at(TODAY, 10, 15))
    bath = Task("Bath", 30, Priority.HIGH, due_date=at(TODAY, 18), start_time=at(TODAY, 10, 30))
    pet.add_task(wing_trim)
    pet.add_task(bath)

    plan = Scheduler(owner).generate_daily_plan(TODAY)

    assert plan.scheduled_tasks == [bath]
    assert plan.skipped_tasks == [wing_trim]
    assert any("Wing trim: skipped" in r and "'Bath'" in r and "ranks higher" in r for r in plan.reasoning)


def test_tied_flexible_tasks_go_to_the_earlier_due_date_before_the_alphabet():
    # Only 30 free minutes; two 30-minute medium tasks, both in the "+10" band (20 + 10 = 30):
    # Zoomies is OVERDUE (due yesterday), Brushing is due today. Same score, so the earlier
    # due date wins: Zoomies gets the slot even though "Brushing" comes first alphabetically.
    owner = Owner("Sam", available_start=time(8), available_end=time(8, 30))
    pet = Pet("Biscuit", "dog")
    owner.add_pet(pet)
    zoomies = Task("Zoomies", 30, Priority.MEDIUM, due_date=at(date(2026, 10, 14), 18))
    brushing = Task("Brushing", 30, Priority.MEDIUM, due_date=at(TODAY, 18))
    pet.add_task(zoomies)
    pet.add_task(brushing)
    scheduler = Scheduler(owner)

    plan = scheduler.generate_daily_plan(TODAY)

    assert scheduler.weighted_priority(zoomies, TODAY) == scheduler.weighted_priority(brushing, TODAY) == 30
    assert [t.name for t in plan.scheduled_tasks] == ["Zoomies"]
    assert plan.skipped_tasks == [brushing]


# ---------------------------------------------------------------------------
# Recurring tasks: marking a daily/weekly task done creates the next one
# ---------------------------------------------------------------------------


@pytest.fixture
def biscuit_with_owner(owner):
    """Owner with one dog, Biscuit, and no tasks yet."""
    biscuit = Pet("Biscuit", "dog")
    owner.add_pet(biscuit)
    return owner, biscuit


def test_completing_daily_task_creates_one_for_today_plus_one_day(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    feeding = Task("Feeding", 10, start_time=at(TODAY, 8), frequency=Frequency.DAILY)
    biscuit.add_task(feeding)

    upcoming = Scheduler(owner).mark_task_complete(feeding, today=TODAY)

    assert feeding.is_completed is True
    assert upcoming.start_time == at(TOMORROW, 8)  # same time of day, today + 1 day
    assert upcoming.is_completed is False
    assert upcoming.task_id != feeding.task_id     # a new, separate task
    assert biscuit.list_tasks() == [feeding, upcoming]


def test_completing_weekly_task_creates_one_for_today_plus_seven_days(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    bath = Task("Bath", 30, due_date=at(TODAY, 18), frequency=Frequency.WEEKLY)
    biscuit.add_task(bath)

    upcoming = Scheduler(owner).mark_task_complete(bath, today=TODAY)

    assert upcoming.due_date == at(date(2026, 10, 22), 18)


def test_late_daily_task_comes_back_tomorrow_not_on_a_past_date(biscuit_with_owner):
    # Due Oct 10 but only done on Oct 15: the next one is Oct 16 (today + 1), not Oct 11.
    owner, biscuit = biscuit_with_owner
    meds = Task("Meds", 5, due_date=at(date(2026, 10, 10), 9), frequency=Frequency.DAILY)
    biscuit.add_task(meds)

    upcoming = Scheduler(owner).mark_task_complete(meds, today=TODAY)

    assert upcoming.due_date == at(TOMORROW, 9)


def test_daily_task_rolls_over_the_end_of_the_month(biscuit_with_owner):
    # timedelta(days=1) handles month ends: Oct 31 + 1 day = Nov 1.
    owner, biscuit = biscuit_with_owner
    walk = Task("Walk", 30, start_time=at(date(2026, 10, 31), 7), frequency=Frequency.DAILY)
    biscuit.add_task(walk)

    upcoming = Scheduler(owner).mark_task_complete(walk, today=date(2026, 10, 31))

    assert upcoming.start_time == at(date(2026, 11, 1), 7)


def test_non_repeating_task_creates_nothing(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    vet = Task("Vet visit", 45, start_time=at(TODAY, 10))  # frequency defaults to NONE
    biscuit.add_task(vet)

    assert Scheduler(owner).mark_task_complete(vet, today=TODAY) is None
    assert biscuit.list_tasks() == [vet]


def test_shared_daily_task_gets_one_next_copy_for_both_pets(owner):
    biscuit, rex = Pet("Biscuit", "dog"), Pet("Rex", "dog")
    owner.add_pet(biscuit)
    owner.add_pet(rex)
    walk = Task("Walk", 30, start_time=at(TODAY, 7), frequency=Frequency.DAILY)
    biscuit.add_task(walk)
    rex.add_task(walk)

    upcoming = Scheduler(owner).mark_task_complete(walk, today=TODAY)

    assert owner.pets_for_task(upcoming) == [biscuit, rex]
    assert len(owner.get_all_tasks()) == 2  # today's walk + one shared walk tomorrow


def test_recurring_never_leaves_two_open_copies(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    scheduler = Scheduler(owner)
    feeding = Task("Feeding", 10, start_time=at(TODAY, 8), frequency=Frequency.DAILY)
    biscuit.add_task(feeding)
    scheduler.mark_task_complete(feeding, today=TODAY)

    # Catch-up runs on later days, while tomorrow's copy is still not done: nothing new.
    assert scheduler.handle_recurring_tasks(today=TODAY) == []
    assert scheduler.handle_recurring_tasks(today=date(2026, 10, 20)) == []
    assert [t.is_completed for t in biscuit.list_tasks()] == [True, False]


# ---------------------------------------------------------------------------
# Tick / untick like a calendar: unticking takes back the copy ticking created
# ---------------------------------------------------------------------------


def test_untick_reopens_task_and_removes_the_next_copy(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    scheduler = Scheduler(owner)
    feeding = Task("Feeding", 10, start_time=at(TODAY, 8), frequency=Frequency.DAILY)
    biscuit.add_task(feeding)
    upcoming = scheduler.mark_task_complete(feeding, today=TODAY)

    removed = scheduler.mark_task_incomplete(feeding)

    assert removed is upcoming
    assert feeding.is_completed is False
    assert biscuit.list_tasks() == [feeding]  # back to exactly how it started


def test_tick_untick_tick_never_piles_up_copies(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    scheduler = Scheduler(owner)
    feeding = Task("Feeding", 10, start_time=at(TODAY, 8), frequency=Frequency.DAILY)
    biscuit.add_task(feeding)

    for _ in range(3):  # click the checkbox on and off three times
        scheduler.mark_task_complete(feeding, today=TODAY)
        scheduler.mark_task_incomplete(feeding)
    scheduler.mark_task_complete(feeding, today=TODAY)

    # Same result as a single tick: today's done, one copy for tomorrow.
    assert [(t.start_time, t.is_completed) for t in biscuit.list_tasks()] == [
        (at(TODAY, 8), True),
        (at(TOMORROW, 8), False),
    ]


def test_untick_only_takes_back_the_copy_this_task_created(biscuit_with_owner):
    # Monday done -> Tuesday created; Tuesday done -> Wednesday created.
    owner, biscuit = biscuit_with_owner
    scheduler = Scheduler(owner)
    monday = Task("Walk", 30, start_time=at(TODAY, 7), frequency=Frequency.DAILY)
    biscuit.add_task(monday)
    tuesday = scheduler.mark_task_complete(monday, today=TODAY)
    wednesday = scheduler.mark_task_complete(tuesday, today=TOMORROW)

    removed = scheduler.mark_task_incomplete(monday)

    # Wednesday was created by ticking Tuesday, not Monday, so unticking Monday only
    # reopens Monday: Tuesday stays done and Wednesday stays.
    assert removed is None
    assert monday.is_completed is False
    assert tuesday.is_completed is True
    assert biscuit.list_tasks() == [monday, tuesday, wednesday]

    # Unticking Tuesday (the latest done copy) does take Wednesday back.
    assert scheduler.mark_task_incomplete(tuesday) is wednesday
    assert biscuit.list_tasks() == [monday, tuesday]


def test_untick_non_repeating_task_just_reopens_it(biscuit_with_owner):
    owner, biscuit = biscuit_with_owner
    scheduler = Scheduler(owner)
    vet = Task("Vet visit", 45, start_time=at(TODAY, 10))
    biscuit.add_task(vet)
    scheduler.mark_task_complete(vet, today=TODAY)

    assert scheduler.mark_task_incomplete(vet) is None
    assert vet.is_completed is False
    assert biscuit.list_tasks() == [vet]


# ---------------------------------------------------------------------------
# Filtering by pet name / completion, and sorting tasks added out of order
# ---------------------------------------------------------------------------


@pytest.fixture
def two_pets_with_tasks(owner):
    """Biscuit (dog) and Kiwi (parrot) with tasks added out of time order; one is done."""
    biscuit, kiwi = Pet("Biscuit", "dog"), Pet("Kiwi", "parrot")
    owner.add_pet(biscuit)
    owner.add_pet(kiwi)
    tasks = {
        "bath": Task("Bath", 30, due_date=at(TOMORROW, 9)),
        "trim": Task("Wing trim", 30, start_time=at(TODAY, 10, 30)),   # fixed, no due date
        "water": Task("Water", 5, due_date=at(TODAY, 9)),              # shared by both pets
        "walk": Task("Walk", 30, start_time=at(TODAY, 7), is_completed=True),
    }
    biscuit.add_task(tasks["bath"])
    kiwi.add_task(tasks["trim"])
    biscuit.add_task(tasks["water"])
    kiwi.add_task(tasks["water"])
    biscuit.add_task(tasks["walk"])
    return Scheduler(owner), tasks


def test_filter_by_pet_name_is_partial_and_case_insensitive(two_pets_with_tasks):
    scheduler, t = two_pets_with_tasks

    # "KI" matches Kiwi; the shared water task matches because Kiwi is one of its pets.
    # Results keep get_all_tasks() order (pet by pet: Biscuit first, so water comes before trim).
    assert scheduler.filter_tasks(pet_name="KI") == [t["water"], t["trim"]]
    assert scheduler.filter_tasks(pet_name="nobody") == []


def test_filter_by_completion_status(two_pets_with_tasks):
    scheduler, t = two_pets_with_tasks

    assert scheduler.filter_tasks(is_completed=True) == [t["walk"]]
    assert set(map(id, scheduler.filter_tasks(is_completed=False))) == {id(t["bath"]), id(t["trim"]), id(t["water"])}


def test_filter_by_pet_name_and_completion_combined(two_pets_with_tasks):
    scheduler, t = two_pets_with_tasks

    # Biscuit has bath, water, and the completed walk; only the first two are still to do.
    assert scheduler.filter_tasks(pet_name="biscuit", is_completed=False) == [t["bath"], t["water"]]


def test_sort_by_due_date_orders_tasks_added_out_of_order(two_pets_with_tasks):
    scheduler, t = two_pets_with_tasks

    # The fixed wing trim has no due date, so its start time (10:30) counts as its deadline.
    assert scheduler.sort_by_due_date() == [t["walk"], t["water"], t["trim"], t["bath"]]
