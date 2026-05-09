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



## Open Issues

### Equipment API test sends stale equip/unequip payloads
- **Found**: 2026-05-08 during edge-aware spatial foundation validation
- **Test file**: `examples/server_tests/test_equipment_api.py`
- **Error**: Running against a temporary `uvicorn server.event_server:app --port 8000` reaches the equipment endpoints, but `POST /entity/{uuid}/equip` and `POST /entity/{uuid}/unequip` return HTTP 422 because the request body omits required `entity_uuid`. The later expected 400/404 error-case checks then fail as follow-on failures.
- **Hypothesis**: The server request models were updated to require `entity_uuid`, but this manual integration test still sends the older payload shape with only `session_id`, `item_uuid`/`slot`. The test likely needs to include `entity_uuid` in equip/unequip payloads or the endpoint model needs compatibility handling.
- **Status**: OPEN

### WebSocket ping test assumes pong is the next frame
- **Found**: 2026-05-03 during spell catalog endpoint validation
- **Test file**: `server/test_websocket.py`
- **Error**: Running `PYTHONPATH=. .venv/bin/python server/test_websocket.py` reaches `test_websocket_connection`, sends `{"type": "ping"}`, then `assert data["type"] == "pong"` fails because the next received frame can still be an `"event"` frame.
- **Hypothesis**: The WebSocket stream is asynchronous and may have queued spatial events when the ping is sent. The test should drain/filter frames until it sees `pong` or times out, instead of assuming request/response ordering on a mixed event/control channel.
- **Status**: OPEN

### `alt_skip_slot` getattr in BaseAction violates no-duck-typing principle
- **Found**: 2026-02-28
- **File**: `dnd/core/base_actions.py` line 274
- **Error**: `getattr(self, 'alt_skip_slot', False)` — parent class (`BaseAction.effective_costs()`) uses getattr to access a field (`alt_skip_slot`) that only exists on a subclass (`SpellAction`). This is duck-typing from parent to child, violating the codebase rule against getattr/hasattr.
- **Hypothesis**: `alt_skip_slot` should either be moved up to `BaseAction` (alongside the other `alt_*` override fields that are already there), or `effective_costs()` should be overridden in `SpellAction` to handle spell-slot-specific cost filtering. Moving the field up is the simpler fix since `alt_cost_type`, `alt_extra_costs`, `alt_target_type`, and `alt_target_count` are already on `BaseAction`.
- **Status**: FIXED — moved `alt_skip_slot` to `BaseAction` alongside other `alt_*` fields, removed duplicate from `SpellAction`



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




