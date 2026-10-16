"""Manual end-to-end check for pawpal_system.py. Run with: python main.py. I made 4 Task objects but to expedite process asked Claude Pro to complete the file"""

import sys
from datetime import date, datetime, time, timedelta

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

# Windows terminals default to cp1252, which can't print the "—" used in the plan.
sys.stdout.reconfigure(encoding="utf-8")

today = date.today()


def at(hour: int, minute: int = 0, days_from_today: int = 0) -> datetime:
    """Return a datetime at hour:minute, `days_from_today` days from today."""
    return datetime.combine(today + timedelta(days=days_from_today), time(hour, minute))


# --- Owner and pets ---
owner = Owner("Bob", available_start=time(7, 0), available_end=time(21, 0))
biscuit = Pet("Biscuit", "dog", age=4, description="Golden Retriever")
rex = Pet("Rex", "dog", age=2, description="Beagle")
kiwi = Pet("Kiwi", "parrot", age=6, description="African Grey", ailments=["feather plucking"])
for pet in (biscuit, rex, kiwi):
    owner.add_pet(pet)

# --- Tasks ---
# Fixed time: a shared walk for both dogs.
morning_walk = Task(
    "Morning walk", 90, Priority.LOW,
    description="Walk the dogs around the neighborhood in the early morning",
    start_time=at(7), frequency=Frequency.DAILY,
)
# Flexible (no start time): the scheduler finds a slot.
fill_water = Task(
    "Fill bowl of pure water", 15, Priority.HIGH,
    description="Fill each pet's clean bowl with pure water",
    due_date=at(9), frequency=Frequency.DAILY,
)
buy_feed = Task(
    "Buy parrot feed", 60, Priority.MEDIUM,
    description="Buy parrot food of X brand from the Y store",
    due_date=at(18, days_from_today=7),
)
# Fixed time: a vet visit, plus a lower-priority task that overlaps it.
vet_visit = Task("Vet checkup", 45, Priority.HIGH, start_time=at(10))
wing_trim = Task("Wing trim", 30, Priority.LOW, start_time=at(10, 30))
# Not today: shows up in the task list but not in today's plan.
bath = Task(
    "Bath", 60, Priority.MEDIUM,
    description="Use pet-safe shampoo",
    start_time=at(9, days_from_today=2), frequency=Frequency.WEEKLY,
)

biscuit.add_task(morning_walk)
rex.add_task(morning_walk)
for pet in (biscuit, rex, kiwi):
    pet.add_task(fill_water)
kiwi.add_task(buy_feed)
kiwi.add_task(vet_visit)
kiwi.add_task(wing_trim)
biscuit.add_task(bath)

scheduler = Scheduler(owner)

# --- Today's schedule ---
print("=== Today's Schedule ===")
print(scheduler.generate_daily_plan(today).explain())

# --- Other scheduler features ---
print("\n=== All tasks by weighted priority (across all pets) ===")
for task in scheduler.sort_by_weighted_priority(today=today):
    pets = ", ".join(p.label() for p in owner.pets_for_task(task))
    print(f"  {scheduler.weighted_priority(task, today):>4.0f}  {task.name} — {pets}")

print("\n=== Conflicts ===")
conflicts = scheduler.detect_conflicts()
if not conflicts:
    print("  none")
for first, second in conflicts:
    # A conflict means the later task starts before the earlier one ends.
    print(f"  {first.name}: {first.start_time:%H:%M}-{first.end_time():%H:%M} ({first.duration_minutes} min)")
    print(f"  {second.name}: {second.start_time:%H:%M}-{second.end_time():%H:%M} ({second.duration_minutes} min)")
    print(
        f"  -> {second.name} starts at {second.start_time:%H:%M}, before {first.name} ends at "
        f"{first.end_time():%H:%M}: they overlap by {first.overlap_minutes(second)} min"
    )

print("\n=== Next available 30-minute slot after 08:00 ===")
slot = scheduler.next_available_slot(30, at(8))
print(f"  {slot:%H:%M}" if slot else "  none today")

print("\n=== Recurring tasks ===")
morning_walk.mark_complete()
for task in scheduler.handle_recurring_tasks():
    print(f"  Completed '{task.name}', next one created for {task.start_time or task.due_date:%Y-%m-%d %H:%M}")
