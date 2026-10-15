# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.

    - Owner owns pets, each pet owns its tasks, and the Scheduler reads everything through the Owner and produces a DailyPlan [[1]](#1).
    - A shared task like a park trip is the same Task added to several pets, rather than storing pet IDs on the task [[1]](#1).
    - Scheduling logic sits in one place, the Scheduler, instead of being spread across Pet and Owner [[1]](#1).
    - Scheduler has a 1 to 1 relationship with the Owner class which has a 1 to many relationship with the Pet class.
    - Has Pet and Task classes that have a many to many relationship with each other. A person can take 2 of their dogs for a walk at the same time. 

- What classes did you include, and what responsibilities did you assign to each?

    - There are essentially 4 core classes (Owner, Pet, Task, Scheduler), plus a DailyPlan result class and two enumerations (Priority and Frequency).
        - Scheduler class sorts, filters and schedules the tasks across 0 to several pets.  "DailyPlan is a small data class that holds the result of scheduling (tasks scheduled and skipped, which pets each task is for, and the reasoning) and can format itself as readable text." The Scheduler  class creates instances of DailyPlan class. It gets tasks, filters, sorts them, gets the respective pets of the tasks, and schedules the tasks essentially.
        
        - Owner class which adds, gets, edits,and removes pets. It also filters pets by name, type such as if cat or a dog, age, and ailments. It also persists the data.

        - Pet class does CRUD operations with Task class. Both of the classes have a name and description attribute. Some other attributes of the Task class is priority and frequency. The `frequency` attribute tells the application how often a task repeats (none, daily, weekly, or monthly), so that when a recurring task is completed, the scheduler can create its next occurrence. A task's pets are not stored on the task itself; instead, each pet keeps a list of its tasks, so a shared task (like a park trip) is just added to more than one pet.


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.
    - A method for time blocking existed for both Pet and Scheduler. I removed the time blocking method in the Pet class for simplicity as that method was not needed.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?


## 6. Citations and Extra Notes

<a id="1">[1]</a>: Anthropic. Claude Pro. https://claude.ai. 
    
