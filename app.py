"""PawPal+ Streamlit UI. Run with: streamlit run app.py

The UI only collects input and shows results; all the logic lives in pawpal_system.py
(see diagrams/uml_draft.mmd):
- Owner holds the pets (add / edit / remove / filter pets, save / load JSON).
- Each Pet holds its tasks (add / edit / remove tasks). One Task can belong to
  several pets, e.g. a walk for two dogs.
- Scheduler reads every task through the Owner, so it always works across all pets:
  sorting, filtering, conflicts, next free slot, recurring tasks, and the daily plan.

How Streamlit works (for beginners):
1. `streamlit run app.py` starts a local web server and opens the app in your browser.
2. Streamlit runs this file from top to bottom, and each `st.something(...)` call
   draws one thing on the page, in that order (a title, a text box, a table, ...).
3. Every time you interact (click a button, type in a box), Streamlit runs the
   WHOLE file again from the top. This is called a "rerun".
4. Input widgets return their current value on every run: `st.text_input(...)`
   returns the text in the box; `st.button(...)` returns True only on the one
   run right after it was clicked, and False otherwise.
5. Normal variables are reset on every rerun. Anything that must be remembered
   (here: the Owner, with all pets and tasks) is stored in `st.session_state`,
   a dictionary that survives reruns for as long as the browser tab is open.
6. `st.rerun()` starts a fresh run immediately, so the page redraws with the
   latest data (used after edits so the tables above show the change).
"""

import os
from dataclasses import replace
from datetime import date, datetime, time

import streamlit as st

from pawpal_system import Frequency, Owner, Pet, Priority, Scheduler, Task

# Saved next to app.py (not in whatever folder the terminal is in), so the same file is
# found no matter where `streamlit run` is started from.
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pawpal_data.json")
SPECIES = ["dog", "cat", "other", "parrot", "rabbit", "hamster", "fish"]

# Browser tab title and icon. Must be the first Streamlit call in the file.
st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to PawPal+.

Add your pets and their care tasks, then generate a daily schedule. The scheduler orders
tasks by priority and due date, fits them into your available hours, warns you about
overlapping tasks, and **explains why** it planned the day the way it did.

Your pets and tasks are kept while this tab is open; use **Save to file** at the bottom to keep them between runs.
"""
)

# st.expander draws a collapsible section; everything indented under "with" goes inside it.
with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

The scheduling logic lives in `pawpal_system.py` and is connected to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

# --- App state -----------------------------------------------------------------
# Streamlit reruns this whole script on every click, so the Owner (and through it,
# every pet and task) lives in session_state to survive between reruns.
# The "if ... not in" check means the Owner is created only on the very first run;
# later runs reuse the same one instead of starting over with an empty owner.
if "owner" not in st.session_state:
    # First run after starting the app: load the saved pets and tasks, if there are any.
    st.session_state.owner = Owner("Jordan")
    st.session_state.autosave = True
    if os.path.exists(DATA_FILE):
        try:
            st.session_state.owner = Owner.load_json(DATA_FILE)
            st.session_state.messages = [("success", "Loaded your saved pets and tasks.")]
        except (OSError, ValueError, TypeError, KeyError) as e:
            # Don't overwrite a file we couldn't read; the owner can fix or delete it first.
            st.session_state.autosave = False
            st.session_state.messages = [("error", f"Couldn't load {DATA_FILE}: {e}. Auto-save is off.")]
elif not isinstance(st.session_state.owner, Owner):
    # When pawpal_system.py is edited while the app runs, Streamlit reloads it and creates a
    # NEW Owner class; the owner saved in session_state still belongs to the OLD class, so
    # checks like isinstance(owner, Owner) fail ("owner must be Owner, got Owner").
    # Rebuilding it through to_dict/from_dict converts it to the new class, keeping all data.
    st.session_state.owner = Owner.from_dict(st.session_state.owner.to_dict())
if "messages" not in st.session_state:
    st.session_state.messages = []
# Starting values for the owner inputs (kept in session_state so "Load from file" can update them).
# A widget created with key="owner_name" reads and writes st.session_state["owner_name"].
st.session_state.setdefault("owner_name", st.session_state.owner.name)
st.session_state.setdefault("available_start", st.session_state.owner.available_start)
st.session_state.setdefault("available_end", st.session_state.owner.available_end)

# After "Load from file", copy the loaded owner's details into the owner inputs.
# This must happen before those inputs are drawn, so it's done here on the rerun.
if st.session_state.pop("just_loaded", False):
    loaded = st.session_state.owner
    st.session_state.owner_name = loaded.name
    st.session_state.available_start = loaded.available_start
    st.session_state.available_end = loaded.available_end

owner: Owner = st.session_state.owner
scheduler = Scheduler(owner)


def notify(kind: str, text: str) -> None:
    """Queue a message ("success", "error", "info") to show after st.rerun()."""
    st.session_state.messages.append((kind, text))


# Messages queued by actions that needed a rerun (edit, remove, mark done, load...).
# A message drawn just before st.rerun() would vanish with the old page, so actions
# save it in session_state and it is drawn here, at the top of the next run.
for kind, text in st.session_state.messages:
    getattr(st, kind)(text)
st.session_state.messages = []


def pet_names(task: Task) -> str:
    """Comma-separated labels of the pets a task belongs to, e.g. 'Biscuit (dog), Rex (dog)'."""
    return ", ".join(p.label() for p in owner.pets_for_task(task)) or "no pet"


def when_text(task: Task) -> str:
    """Short description of when a task happens: fixed time, deadline, or anytime."""
    if task.start_time:
        return f"{task.start_time:%a %b %d, %H:%M}"
    if task.due_date:
        return f"by {task.due_date:%a %b %d}"
    return "anytime"


def schedule_fields(prefix: str, task: Task | None = None) -> dict:
    """Draw the scheduling inputs (repeats, day, fixed start time, notes) and return them as Task kwargs.

    Filled from `task` when editing. `prefix` keeps widget keys unique between forms.
    """
    when = (task.start_time or task.due_date) if task else None
    col1, col2 = st.columns(2)
    frequency = col1.selectbox(
        "Repeats", list(Frequency), format_func=lambda f: f.value,
        index=list(Frequency).index(task.frequency) if task else 0, key=f"{prefix}_frequency",
    )
    day = col2.date_input("Day", value=when.date() if when else date.today(), key=f"{prefix}_day")
    col1, col2 = st.columns(2)
    # Fixed-time tasks (a vet visit) keep their time; flexible ones are placed by the scheduler.
    is_fixed = col1.checkbox("Fixed start time", value=bool(task and task.start_time), key=f"{prefix}_fixed")
    # Greyed out unless "Fixed start time" is ticked, since flexible tasks get their time from the scheduler.
    # (Ticking the box reruns the script, so the time box turns on right away.)
    start_at = col2.time_input(
        "Start time (if fixed)", value=task.start_time.time() if task and task.start_time else time(9, 0),
        key=f"{prefix}_start", disabled=not is_fixed,
    )
    notes = st.text_input("Notes (optional)", value=task.description if task else "", key=f"{prefix}_notes")
    return {
        "frequency": frequency,
        "description": notes,
        "due_date": datetime.combine(day, time(23, 59)),  # due by the end of the chosen day
        "start_time": datetime.combine(day, start_at) if is_fixed else None,
    }


st.subheader("Owner and Pets")
owner_name = st.text_input("Owner name", key="owner_name")  # starts as "Jordan" (set above)
# The owner's available hours: flexible tasks are only scheduled inside this window.
# st.columns(2) splits the row into two side-by-side columns; col1.x(...) draws x in the left one.
col1, col2 = st.columns(2)
available_start = col1.time_input("Available from", key="available_start")
available_end = col2.time_input("Available until", key="available_end")
try:
    # Building an Owner runs its validation (non-blank name, start before end).
    Owner(owner_name, available_start=available_start, available_end=available_end)
    owner.name, owner.available_start, owner.available_end = owner_name, available_start, available_end
except (TypeError, ValueError) as e:
    st.error(f"Owner not updated: {e}")

pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", SPECIES)
col1, col2 = st.columns(2)
age = col1.number_input("Age (years)", min_value=0, max_value=50, value=1, step=1)
description = col2.text_input("Breed / description", placeholder="Golden Retriever")
ailments_text = st.text_input("Ailments (comma-separated)", placeholder="arthritis, allergies")

# st.button is True only on the run right after the click, so this block runs once per click.
if st.button("Add pet"):
    try:
        ailments = [a.strip() for a in ailments_text.split(",") if a.strip()]
        owner.add_pet(Pet(pet_name, species, age=int(age), description=description, ailments=ailments))
        st.success(f"Added {pet_name}.")
    except (TypeError, ValueError) as e:
        # e.g. a blank name: Pet rejects it, and we show why instead of crashing.
        st.error(f"Couldn't add pet: {e}")

# --- Pets: list, filter, edit, remove ------------------------------------------
if owner.pets:
    # Filter pets by any combination of name, species, age, and ailment (Owner.filter_pets).
    with st.expander("🔎 Filter pets"):
        col1, col2 = st.columns(2)
        f_name = col1.text_input("Name contains", key="fp_name")
        f_type = col2.selectbox("Species", ["any"] + SPECIES, key="fp_type")
        col1, col2 = st.columns(2)
        f_age = col1.number_input("Age (0 = any)", min_value=0, max_value=50, value=0, step=1, key="fp_age")
        f_ailment = col2.text_input("Has ailment", key="fp_ailment")
    shown_pets = owner.filter_pets(
        name=f_name or None,
        pet_type=None if f_type == "any" else f_type,
        age=int(f_age) or None,
        ailment=f_ailment or None,
    )
    st.write("Your pets:")
    if shown_pets:
        # st.table draws a list of dicts as a table: each dict is a row, its keys are the columns.
        st.table([
            {"Name": p.name, "Species": p.pet_type, "Age": p.age, "Description": p.description,
             "Ailments": ", ".join(p.ailments), "Tasks": len(p.list_tasks())}
            for p in shown_pets
        ])
    else:
        st.info("No pets match these filters.")

    with st.expander("✏️ Edit or remove a pet"):
        pets_by_id = {p.pet_id: p for p in owner.pets}
        pet_id = st.selectbox("Pet", list(pets_by_id), format_func=lambda pid: pets_by_id[pid].label())
        pet = pets_by_id[pet_id]
        # Keys include the pet id so the fields refill when a different pet is picked.
        col1, col2 = st.columns(2)
        e_name = col1.text_input("Name", value=pet.name, key=f"ep_name_{pet_id}")
        e_type = col2.selectbox(
            "Species", SPECIES, index=SPECIES.index(pet.pet_type) if pet.pet_type in SPECIES else SPECIES.index("other"),
            key=f"ep_type_{pet_id}",
        )
        col1, col2 = st.columns(2)
        e_age = col1.number_input("Age", min_value=0, max_value=50, value=pet.age, step=1, key=f"ep_age_{pet_id}")
        e_desc = col2.text_input("Breed / description", value=pet.description, key=f"ep_desc_{pet_id}")
        e_ail = st.text_input("Ailments", value=", ".join(pet.ailments), key=f"ep_ail_{pet_id}")
        col1, col2 = st.columns(2)
        if col1.button("Save pet", width="stretch"):
            try:
                owner.edit_pet(
                    pet_id, name=e_name, pet_type=e_type, age=int(e_age), description=e_desc,
                    ailments=[a.strip() for a in e_ail.split(",") if a.strip()],
                )
                notify("success", f"Saved {e_name}.")
            except (TypeError, ValueError) as e:
                notify("error", f"Couldn't save pet: {e}")
            # The pet table was already drawn above this point; rerun so it shows the change.
            st.rerun()
        if col2.button("Remove pet", width="stretch"):
            owner.remove_pet(pet_id)
            notify("success", f"Removed {pet.name}.")
            st.rerun()
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")
st.caption("Add care tasks for your pets. They feed straight into the scheduler below.")

# Tasks now live on the pets (through the Owner), not in a separate session list.
col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

pets_by_id = {p.pet_id: p for p in owner.pets}
# Picking several pets creates ONE shared task (e.g. one walk for two dogs).
# Defaults to the most recently added pet.
task_pet_ids = st.multiselect(
    "For which pet(s)?", list(pets_by_id), format_func=lambda pid: pets_by_id[pid].label(),
    default=[owner.pets[-1].pet_id] if owner.pets else [],
)
new_task_fields = schedule_fields("add")

if st.button("Add task"):
    try:
        if not task_pet_ids:
            raise ValueError("add a pet first, then pick at least one pet for the task")
        task = Task(task_title, int(duration), Priority(priority), **new_task_fields)  # Task validates its values
        # Check every chosen pet before adding to any, so a shared task is added to all or none.
        for pid in task_pet_ids:
            duplicate = pets_by_id[pid].find_duplicate_task(task)
            if duplicate is not None:
                raise ValueError(f"{pets_by_id[pid].name} already has '{duplicate.name}' at that time")
        for pid in task_pet_ids:
            pets_by_id[pid].add_task(task)
        st.success(f"Added '{task.name}' for {', '.join(pets_by_id[p].name for p in task_pet_ids)}.")
    except (TypeError, ValueError) as e:
        st.error(f"Couldn't add task: {e}")

if owner.get_all_tasks():
    # Sort and filter by any combination of criteria (Scheduler.filter_tasks + sort methods).
    with st.expander("🔎 Sort and filter tasks"):
        sort_by = st.radio("Sort by", ["Weighted priority", "Due date"], horizontal=True)
        col1, col2 = st.columns(2)
        f_name = col1.text_input("Name contains", key="ft_name")
        f_desc = col2.text_input("Notes contain", key="ft_desc")
        f_pet = st.text_input("For pet (name contains)", key="ft_pet")
        col1, col2, col3 = st.columns(3)
        f_status = col1.selectbox("Status", ["any", "to do", "done"], key="ft_status")
        f_priority = col2.selectbox("Priority", ["any"] + [p.value for p in Priority], key="ft_priority")
        f_score = col3.number_input("Min score", min_value=0, max_value=40, value=0, step=5, key="ft_score")
        use_due = st.checkbox("Only tasks due on a specific day", key="ft_use_due")
        f_due = st.date_input("Due on", value=date.today(), key="ft_due", disabled=not use_due)

    matches = scheduler.filter_tasks(
        name=f_name or None,
        description=f_desc or None,
        pet_name=f_pet or None,
        is_completed={"to do": False, "done": True, "any": None}[f_status],
        priority=None if f_priority == "any" else Priority(f_priority),
        due_date=f_due if use_due else None,
        min_weighted_priority=f_score or None,
    )
    ordered = (scheduler.sort_by_weighted_priority(matches) if sort_by == "Weighted priority"
               else scheduler.sort_by_due_date(matches))

    st.write("Current tasks:")
    if ordered:
        # st.data_editor is a table the user can edit. Only the "Done" column is editable,
        # so each row works like a calendar checkbox: tick = complete, untick = not complete.
        # The key changes after every applied click so the editor starts fresh on the rerun
        # (otherwise it would re-apply the old click to the updated table).
        st.session_state.setdefault("tasks_table_version", 0)
        edited = st.data_editor(
            [
                {
                    "Done": t.is_completed,
                    "Score": f"{scheduler.weighted_priority(t):.0f}",
                    "Task": t.name,
                    "Pets": pet_names(t),
                    "When": when_text(t),
                    "Duration": f"{t.duration_minutes} min",
                    "Priority": t.priority.value,
                    "Repeats": t.frequency.value,
                    "Notes": t.description,
                }
                for t in ordered
            ],
            disabled=["Score", "Task", "Pets", "When", "Duration", "Priority", "Repeats", "Notes"],
            hide_index=True,
            width="stretch",
            key=f"tasks_table_{st.session_state.tasks_table_version}",
        )
        # Rows come back in the same order as `ordered`, so row i is task ordered[i].
        for task, row in zip(ordered, edited):
            if row["Done"] and not task.is_completed:
                # Tick: done, and a repeating task gets its next copy (today + 1 day/week/month).
                upcoming = scheduler.mark_task_complete(task)
                notify("success", f"Marked '{task.name}' done.")
                if upcoming:
                    notify("info", f"'{upcoming.name}' repeats: next one added for {when_text(upcoming)}.")
            elif not row["Done"] and task.is_completed:
                # Untick: open again, and the next copy that ticking created is taken back.
                removed = scheduler.mark_task_incomplete(task)
                notify("success", f"Marked '{task.name}' not done.")
                if removed:
                    notify("info", f"Removed the next '{removed.name}' ({when_text(removed)}) that ticking had added.")
            else:
                continue
            st.session_state.tasks_table_version += 1
            st.rerun()
        st.caption("Tick **Done** to complete a task (repeating tasks get their next copy); untick to undo. "
                   "Score = 10 × priority (low 10, medium 20, high 30), +10 if due today or overdue, "
                   "+5 if due within 3 days. Completed tasks score 0.")
    else:
        st.info("No tasks match these filters.")

    with st.expander("✏️ Edit or remove a task"):
        tasks_by_id = {t.task_id: t for t in owner.get_all_tasks()}
        task_id = st.selectbox(
            "Task", list(tasks_by_id),
            format_func=lambda tid: f"{tasks_by_id[tid].name} ({when_text(tasks_by_id[tid])}) — {pet_names(tasks_by_id[tid])}",
        )
        task = tasks_by_id[task_id]
        # Keys include the task id so the fields refill when a different task is picked.
        col1, col2, col3 = st.columns(3)
        e_title = col1.text_input("Task title", value=task.name, key=f"et_title_{task_id}")
        e_duration = col2.number_input(
            "Duration (minutes)", min_value=1, max_value=720, value=task.duration_minutes, key=f"et_dur_{task_id}"
        )
        e_priority = col3.selectbox(
            "Priority", [p.value for p in Priority], index=list(Priority).index(task.priority),
            key=f"et_pri_{task_id}",
        )
        edit_fields = schedule_fields(f"edit_{task_id}", task)
        # Same as the Done checkbox in the table above.
        e_done = st.checkbox("Completed", value=task.is_completed, key=f"et_done_{task_id}")
        col1, col2 = st.columns(2)
        if col1.button("Save task", width="stretch"):
            try:
                changes = dict(
                    name=e_title, duration_minutes=int(e_duration), priority=Priority(e_priority), **edit_fields,
                )
                task_pets = owner.pets_for_task(task)
                was_done = task.is_completed
                # A shared task is one object, so editing it through one pet updates it for all;
                # first make sure the edit doesn't duplicate a task on any of its other pets.
                preview = replace(task, **changes)  # an edited copy (validated); the real task is untouched
                for p in task_pets:
                    duplicate = p.find_duplicate_task(preview)
                    if duplicate is not None:
                        raise ValueError(f"{p.name} already has '{duplicate.name}' at that time")
                task_pets[0].edit_task(task_id, **changes)
                notify("success", f"Saved '{e_title}'.")
                # "Completed" works exactly like the Done checkbox in the table:
                # ticking creates a repeating task's next copy, unticking takes it back.
                if e_done and not was_done:
                    upcoming = scheduler.mark_task_complete(task)
                    if upcoming:
                        notify("info", f"'{upcoming.name}' repeats: next one added for {when_text(upcoming)}.")
                elif was_done and not e_done:
                    removed = scheduler.mark_task_incomplete(task)
                    if removed:
                        notify("info", f"Removed the next '{removed.name}' ({when_text(removed)}) that ticking had added.")
            except (TypeError, ValueError) as e:
                notify("error", f"Couldn't save task: {e}")
            st.rerun()
        if col2.button("Remove task", width="stretch"):
            for p in owner.pets_for_task(task):
                p.remove_task(task_id)
            notify("success", f"Removed '{task.name}'.")
            st.rerun()

    # Conflicts: fixed-time tasks whose time windows overlap, with both windows shown.
    for first, second in scheduler.detect_conflicts():
        st.warning(
            f"⚠️ **Conflict:** {second.name} ({second.start_time:%B %d %a %H:%M}–{second.end_time():%H:%M}) "
            f"starts before {first.name} ({first.start_time:%B %d %H:%M}–{first.end_time():%H:%M}) ends — "
            f"they overlap by {first.overlap_minutes(second)} min."
        )
else:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("Builds the day's plan from your tasks, their priorities, and your available hours.")

plan_day = st.date_input("Plan for", value=date.today(), key="plan_day")

if st.button("Generate schedule"):
    # Scheduler.generate_daily_plan picks the day's tasks, time-blocks them into the
    # owner's available hours, and records a reason for every decision.
    plan = scheduler.generate_daily_plan(plan_day)

    if plan.scheduled_tasks:
        st.success(f"{len(plan.scheduled_tasks)} task(s) scheduled, {plan.total_minutes()} min total.")
        st.table([
            {
                "Time": f"{t.start_time:%H:%M}–{t.end_time():%H:%M}",
                "Task": t.name,
                "Pets": ", ".join(plan.pet_labels_by_task.get(t.task_id, [])),
                "Duration": f"{t.duration_minutes} min",
                "Priority": t.priority.value,
                "Notes": t.description,
            }
            for t in plan.scheduled_tasks
        ])
    else:
        st.info("Nothing to schedule for this day.")

    if plan.skipped_tasks:
        st.warning("Skipped: " + ", ".join(t.name for t in plan.skipped_tasks) + " (see why below)")

    with st.expander("Why this plan?", expanded=True):
        for reason in plan.reasoning:
            st.markdown(f"- {reason}")
    with st.expander("Plain-text version"):
        st.code(plan.explain(), language=None)

# --- Find a free slot (Scheduler.next_available_slot) --------------------------
st.markdown("### Find a free slot")
col1, col2, col3 = st.columns(3)
slot_minutes = col1.number_input("Length (minutes)", min_value=1, max_value=720, value=30, step=5)
slot_day = col2.date_input("Day", value=date.today(), key="slot_day")
slot_after = col3.time_input("After", value=time(8, 0), key="slot_after")
slot = scheduler.next_available_slot(int(slot_minutes), datetime.combine(slot_day, slot_after))
if slot:
    st.success(f"Next free {slot_minutes}-minute slot: **{slot:%a %b %d, %H:%M}**")
else:
    st.warning("No free slot that long before the end of your available hours that day.")
st.caption("Checks your available hours and fixed-time tasks.")

# --- Save / load: pets and tasks persist between runs (Owner.save_json / load_json) ---
st.divider()
col1, col2 = st.columns(2)
if col1.button("💾 Save to file", width="stretch"):
    owner.save_json(DATA_FILE)
    st.session_state.autosave = True  # a manual save also turns auto-save back on
    notify("success", f"Saved to {os.path.basename(DATA_FILE)}.")
    st.rerun()
if col2.button("📂 Load from file", width="stretch", disabled=not os.path.exists(DATA_FILE)):
    st.session_state.owner = Owner.load_json(DATA_FILE)
    st.session_state.just_loaded = True
    notify("success", f"Loaded from {os.path.basename(DATA_FILE)}.")
    st.rerun()

# Auto-save: this line is reached at the end of every run (every click), so any change made
# above is written to the file. Only writes when something actually changed.
if st.session_state.autosave:
    current = owner.to_dict()
    if current != st.session_state.get("last_saved"):
        owner.save_json(DATA_FILE)
        st.session_state.last_saved = current
    st.caption(f"✅ Changes are saved automatically to {os.path.basename(DATA_FILE)} and loaded when the app starts.")
else:
    st.caption("⚠️ Auto-save is off because the saved file couldn't be loaded. Click Save to file to overwrite it.")
