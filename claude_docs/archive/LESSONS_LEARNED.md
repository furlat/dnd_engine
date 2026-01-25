# Lessons Learned

This document consolidates failure patterns and lessons from past Claude sessions working on this codebase. Read this before starting work to avoid repeating mistakes.

---

## Core Behavioral Rules

### What Killed Previous Sessions

These specific behaviors caused sessions to fail badly:

1. **Making 5+ speculative fixes without user validation** - Claude would make a change, see it didn't work, make another change, see that didn't work, and continue chaining changes without stopping to ask
2. **Not studying backend code before making changes** - Jumping into fixes without understanding how the Python code actually works
3. **Continuing to flail instead of asking for help** - Uncertainty should mean stopping and asking, not trying more things
4. **Not using the PvP test loop to validate changes immediately** - Making multiple changes without testing each one

### The Right Pattern

```
Claude: I made change X. Does this look right?
User: No, try Y instead.
Claude: Done. Here's the result. Should I continue?
User: Yes, now do Z.
```

### The Wrong Pattern

```
Claude: I'll fix this. [change 1] Hmm that didn't work. [change 2] Still broken. [change 3] [change 4] [change 5]
User: What are you doing? That's all wrong.
```

---

## Frontend Combat Viewer Failure (2025)

### Context
Attempted to build a TypeScript frontend to visualize D&D combat via WebSocket events. Stack: Vite + vanilla TypeScript + Axios + Valtio.

### The Problem
Attack events always showed "misses (rolled ?)" regardless of actual outcome.

### Root Cause
The backend event system fires multiple events at each phase:

```
DECLARATION → EXECUTION → EFFECT → COMPLETION
```

For attacks, `attack_consequences()` broadcasts MULTIPLE events at EXECUTION phase:
1. First `phase_to(EXECUTION)` - broadcasts event **without** `dice_roll`/`attack_outcome`
2. Then `post(dice_roll=..., attack_outcome=...)` - broadcasts event **with** data

Server logs showed:
```
[WS BROADCAST] attack execution: outcome=None, dice=None
[WS BROADCAST] attack execution: outcome=None, dice=None
[WS BROADCAST] attack execution: outcome=AttackOutcome.HIT, dice=...total=23...
```

But the frontend only received the first event (with nulls) - WebSocket messages were getting lost when fired in rapid succession via `queue.put_nowait()`.

### Key Mistakes Made

1. **Didn't study backend event flow first** - Should have traced through `attack_consequences()` before writing any frontend code

2. **Assumed WebSocket delivery was reliable** - Didn't consider that rapid-fire synchronous events might not all arrive

3. **Too many changes without user validation** - Made multiple "fixes" in sequence without confirming each one worked

4. **Vite HMR unreliability** - Wasted significant time on stale code being served; should have verified served code matches source earlier

5. **Debugging in TypeScript instead of Python** - User correctly called out: "study it from python first instead of chasing dragons in typescript"

### What Should Have Been Done

1. Add server-side event coalescing or delays to ensure WebSocket has time to deliver each message
2. Use a single completion event for attack results, not rely on catching the right execution event
3. Add message sequence numbers to detect when messages are dropped
4. Test WebSocket delivery independently before assuming frontend bug
5. **Ask user for guidance earlier** instead of making 5+ failed fix attempts

### General Lessons

1. When debugging cross-system issues, start from the source (backend) not the sink (frontend)
2. WebSocket message delivery is not guaranteed to be 1:1 with send calls
3. Vite HMR can silently fail - always verify with `curl` or hard refresh
4. Stop and ask when stuck instead of making repeated speculative fixes
5. The user knows their codebase better - listen to their suggestions

---

## Anti-Patterns to Avoid

### "Know-it-all" Behavior
Phrases like "I'll just fix this" or "This should work" followed by failed attempts are not acceptable. Uncertainty means stopping and asking.

### Late Imports for Circular Dependencies
Never use "late imports" or "import inside function" to avoid circular imports. If you need a late import, it means the design is wrong - the circular dependency still exists, you're just hiding it.

**The Rule**: Dependencies flow DOWN the hierarchy, never UP.

```
Entity (high-level)
   ↓ owns
Senses, Equipment, Health (blocks/components)
   ↓ uses
ModifiableValue, Modifiers (primitives)
   ↓ uses
BaseObject, BaseBlock (base classes)
```

### Guessing Method Names
Never assume method/attribute names exist. Always read the actual class definition first. Common pitfalls:
- `Entity.get_hp()` returns current HP, NOT `entity.health.current_hit_points` (doesn't exist)
- `AbilityScoresConfig` takes `AbilityConfig` objects, not raw integers
- Bestiary factories use keyword args: `create_goblin(name="Name", position=(0,0))`

---

## Adding to This Document

When a session fails due to behavioral issues or systematic mistakes, document:
1. What went wrong (specific behaviors)
2. What the correct approach would have been
3. General lessons that apply to future work

Keep entries concise and actionable.
