
# Summary

- A Streamlit app that helps a pet owner plan care tasks for their pet.

# Core requirements

- A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
Consider constraints (time available, priority, owner preferences)

- Produce a daily plan and explain why it chose that plan

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Example of Streamlit ouput

```bash
# e.g.:
# Daily plan for Biscuit (Golden Retriever):
#   08:00 — Morning walk (30 min) [priority: high]
#   09:00 — Feeding (10 min) [priority: high]
#   ...
```


## Core Classes

- Task class includes at least: description, due time or date, completion status, and one relevant method (e.g., mark_complete). It should also include the priority of the task and name of task. Some tasks may have to be done at specific times such as taking your pet parrot to the vet so it should another attribute saying start time. Users should be able to set the task and mark a task as complete. Methods to edit tasks.
    
- Pet class includes identifying info and a collection of tasks with methods to add/list/edit/manage them. Pet has a 0 to many relationship to Task class. Some attributes of Pet include, pet name, pet type (whether it is a cat, dog, hamster etc), pet description, age, ailments. Pet should have 0 to many relationship with tasks.

- Owner class includes identifying info and a list of pets with appropriate methods. Owner can add pets, edit them, and delete them. Through the Pet class they can also add tasks to those pets. They can filter list of pets by pet type (as if it is a cat or dog), pet name, age, and maybe ailment if it is not too complicated. When filtering in general for all the classes that have filter methods, users can filter by several attributes not just one. An owner has a 0 to many relationship with pets. Owen has pet(s).
    
- Scheduler class retrieves, organizes, or manages tasks across multiple pets (not just one pet's tasks, and not merely holding data). The scheduler class should have a method to sort tasks by weighted priority and another method to sort by their due dates. The weighted priority should take in task priority, and their completion status in consideration when calculating their weighted priority. Scheduler has a 0 to many  relationship to Pet class. Has method to retreive all tasks. Has method to filter tasks by name, description, completion status, priority, due date, weighted priority. Should be able to filter with all of them combined and some of them combined, like filtering by weighted priority and name. But for weighted priority, filterting by things it already considers such as task priority and due date maybe redundant and so weighted priority and name may both be fields to filter tasks instead of weighted priority and task priority or due date. Should have a method for detecting scheduling conflicts and one to handle recurring tasks. 
    
## Other Class Methods


- Time-blocking to prevent overlapping tasks. This time blocking maybe should be added to Pet class or their should be several variants of it with a time blocking method for Scheduler class and another for Pet class. Still a method that time blocks to prevent overlapping tasks should exist.

- Next available slot method. There should be a class method that makes it easy for a user to find next available slots. To get the times where they can add a task and not have it overlap.

- This is complicated and so is optional, but sometimes a task may involve several pets such as taking those pets to the park. Please account for those edge cases, but this is optional.

- JSON or CSV save/load functionality is implemented so that pets and tasks persist between application runs.

----

<cite>https://courses.codepath.org/courses/ai110/pages/grading</cite> A lot of text in this file was copied verbatim from that link.

<cite>https://github.com/codepath/ai110-module2show-pawpal-starter</cite> Text was also copied verbatim from that link as well.
