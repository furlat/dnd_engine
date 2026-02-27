# Known Issues

Bugs, failing tests, and hypotheses documented during implementation sessions. Updated by dispatching background sub-agents when issues are found during unrelated work.

## Format

```
### [SHORT TITLE]
- **Found**: [date or session context]
- **Test file**: `examples/test_xxx.py` (if applicable)
- **Error**: [brief error description]
- **Hypothesis**: [what might be causing it]
- **Status**: OPEN | INVESTIGATING | FIXED
```

## Fixed Issues

### Concentration 0-children bug (Concentrating persists with no effects)
- **Found**: 2026-02-27
- **Test file**: `examples/test_bless_bane.py`, `examples/test_concentration_spells.py`
- **Error**: When ALL targets of a concentration spell save (HoldPerson, Bane, Bless), `Concentrating` persisted with 0 linked children — a dead state that blocked future concentration spells.
- **Root cause**: `ensure_concentration()` spells create Concentrating BEFORE the save roll. If all targets save, no `add_linked_condition()` calls are made, but nothing cleaned up the empty Concentrating.
- **Fix**: Added `_cleanup_concentration` hook on `BaseAction`/`SpellAction` that calls `Concentrating.cleanup_if_no_effects()` after COMPLETION phase. If `linked_conditions` is empty, Concentrating is removed.
- **Status**: FIXED (2026-02-27)

### Infinite loop in Concentrating._apply() eviction loop
- **Found**: 2026-02-27 (during multi-slot concentration implementation)
- **Test file**: `examples/test_concentration.py` (test 7)
- **Error**: Infinite loop when casting a new concentration spell while at max slots. Process hung forever.
- **Root cause**: The eviction `while` loop checked `len(existing.concentration_slots) >= max_slots` and called `existing.drop_slot(oldest_name, ...)` each iteration. When the last slot was dropped, `drop_slot()` called `target.remove_condition("Concentrating")` and returned early WITHOUT deleting from the `concentration_slots` dict. The `existing` variable still held a reference to the now-removed condition object with its slots dict intact, so `len(existing.concentration_slots)` never decreased and the loop ran forever.
- **Fix**: Added re-check of `existing` inside the while loop after `drop_slot()`:
  ```python
  while len(existing.concentration_slots) >= max_slots:
      oldest_name = next(iter(existing.concentration_slots))
      existing.drop_slot(oldest_name, parent_event=declaration_event)
      # Re-check: drop_slot of last slot removes entire Concentrating
      existing = target.active_conditions.get("Concentrating")
      if not existing or not isinstance(existing, Concentrating):
          break
  ```
- **Lesson**: When a method has side effects that remove the object from a registry (like `remove_condition`), always re-validate the reference from the registry after calling it. Local references to removed objects are stale.
- **Status**: FIXED (2026-02-27)

## Open Issues

### API error messages need improvement
- **Found**: 2026-02-24
- **Test file**: N/A
- **Error**: HTTP 400 responses from the server return generic error messages with no structured detail, giving the AI agent no actionable information about what went wrong.
- **Hypothesis**: Error responses should include structured context: current action economy state (actions/bonus actions/reactions/movement remaining), the specific reason the request was rejected, and a list of valid alternatives or corrective steps. This would allow the AI agent to self-correct rather than retry blindly or stall.
- **Status**: OPEN



### Orchestrator drain timeout causes commands to execute against wrong entity
- **Found**: 2026-02-25, PvP session (Match 1, Round 2)
- **Test file**: N/A (orchestrator/CLI issue, not game engine)
- **Error**: After a 45-second drain timeout kills the Claude subprocess, buffered commands (e.g. `dodge`) execute against the *next* entity in turn order instead of the intended entity. In the observed case, a `dodge` command meant for Skeleton Warlock was applied to Skeleton Archer after the turn auto-advanced.
- **Root cause**: Two problems:
  1. **Why the subprocess got stuck for 45s**: Claude's reasoning/output exceeded the drain buffer capacity or the subprocess hung during output. The drain thread waits for the subprocess to complete writing, but if Claude is mid-generation when `end` fires, the remaining output can take arbitrarily long. The 45s timeout is a safety net, but it's also possibly too short for complex reasoning.
  2. **Why the wrong entity gets the command**: After `process.kill()`, the orchestrator advances to the next entity's turn and writes a new session file. But orphaned/buffered commands from the killed subprocess can still execute via the agent CLI. The agent CLI loads the *current* session file (now pointing to the next entity) and executes against it. There's no validation that the command originated from the correct entity's turn.
- **Impact**: Entity gets actions applied without spending action economy (Archer got Dodging for free). Turn log file for the affected entity is never created.
- **Potential fixes**:
  1. After `process.kill()`, discard any remaining buffered output instead of letting it execute
  2. Add a turn-sequence token to commands so stale commands from killed subprocesses are rejected
  3. Validate entity UUID at command execution time against the server's actual active entity
  4. Investigate why the subprocess takes 45+ seconds to drain — may need to interrupt Claude's generation more aggressively or increase the timeout
- **Status**: OPEN






