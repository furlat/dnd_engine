# Frontend Combat Viewer - Post Mortem

## Project Summary

**Goal**: Build a simple TypeScript frontend to visualize the D&D combat simulation via WebSocket events.

**Stack chosen**: Vite + vanilla TypeScript + Axios (REST) + Valtio (state management)

**Location**: `ui/` folder

## What Was Built

```
ui/
├── src/
│   ├── types/          # TypeScript interfaces matching backend API
│   │   ├── api.ts      # APIEntitySummary, APIGrid, APIEncounter, etc.
│   │   └── events.ts   # BaseEvent, MovementEvent, AttackEvent types
│   ├── store/
│   │   ├── api.ts      # Axios REST client
│   │   └── gameStore.ts # Valtio store + WebSocket connection
│   ├── components/
│   │   ├── Grid.ts     # ASCII/emoji grid renderer
│   │   ├── EntityPanel.ts # HP bars, conditions, turn indicator
│   │   ├── Controls.ts # Reset/Step/Play/Pause buttons
│   │   └── EventLog.ts # Scrollable combat log
│   ├── main.ts         # Entry point
│   └── style.css       # Dark theme styling
```

## What Worked

1. **Grid visualization** - Entities render correctly with emojis, grid updates reactively
2. **WebSocket connection** - Connects, receives events, handles reconnection
3. **REST API integration** - Initial state loads correctly from `/state` endpoint
4. **Movement logging** - "Goblin moved to (7, 7)" logs correctly
5. **Turn/Round tracking** - Round headers and turn announcements work
6. **Death detection** - "Entity has been defeated" logs correctly

## What Failed: Attack Event Logging

### The Problem
Attack events always showed "misses (rolled ?)" regardless of actual outcome.

### Root Cause Analysis

The backend event system fires events at multiple phases:
```
DECLARATION → EXECUTION → EFFECT → COMPLETION
```

For attacks specifically, `attack_consequences()` in `dnd/actions.py` broadcasts MULTIPLE events at the EXECUTION phase:

1. First `phase_to(EXECUTION)` - broadcasts event **without** `dice_roll`/`attack_outcome`
2. Then `post(dice_roll=..., attack_outcome=...)` - broadcasts event **with** data
3. Additional `post()` calls for effect/completion phases

**Server log showing this:**
```
[WS BROADCAST] attack execution: outcome=None, dice=None
[WS BROADCAST] attack execution: outcome=None, dice=None
[WS BROADCAST] attack execution: outcome=AttackOutcome.HIT, dice=...total=23...
[WS BROADCAST] attack completion: outcome=AttackOutcome.HIT, dice=...
```

**But frontend only received ONE execution event** (the first one with nulls).

### Why WebSocket Messages Were Lost

The backend sends events synchronously via `queue.put_nowait()`. When multiple events fire in rapid succession during `attack_consequences()`, the WebSocket appears to drop or coalesce messages. The frontend consistently received:
- 3 declaration events (correct)
- 1 execution event (should be 3)
- 0 completion events initially visible

### Attempted Fixes (All Failed)

1. **Filter for execution phase with data** - Added check `if (!e.attack_outcome) return;`
   - Result: No attack events logged at all (first event has null, subsequent events lost)

2. **Changed attack_outcome comparison to title case** ("Hit" not "HIT")
   - Correct fix for enum values, but didn't solve the missing data problem

3. **Process at completion phase instead**
   - Server logs showed completion events DO have data
   - But frontend still wasn't receiving them reliably

### Time Wasted

Approximately 2+ hours debugging, including:
- Multiple Vite HMR failures requiring full restarts
- Chasing TypeScript type issues
- Adding/removing console.log debug statements
- Back-and-forth between frontend and backend investigation

## Key Mistakes Made

1. **Didn't study backend event flow first** - Should have traced through `attack_consequences()` before writing any frontend code

2. **Assumed WebSocket delivery was reliable** - Didn't consider that rapid-fire synchronous events might not all arrive

3. **Too many changes without user validation** - Made multiple "fixes" in sequence without confirming each one worked

4. **Vite HMR unreliability** - Wasted significant time on stale code being served, should have verified served code matches source earlier

5. **Debugging in TypeScript instead of Python** - User correctly called out: "study it from python first instead of chasing dragons in typescript"

## What Should Have Been Done

1. **Add server-side event coalescing or delays** - Ensure WebSocket has time to deliver each message

2. **Use a single completion event for attack results** - Don't rely on catching the right execution event

3. **Add message sequence numbers** - Detect when messages are dropped

4. **Test WebSocket delivery independently** - Before assuming frontend bug, verify all messages arrive

5. **Ask user for guidance earlier** - Instead of making 5+ failed fix attempts

## Remaining State

- Frontend runs but attack outcomes show incorrectly
- Grid, movement, turns, deaths all work
- Server has debug logging added (should be removed)
- Code is functional but event log is incomplete

## Files Modified During Debugging

- `ui/src/store/gameStore.ts` - Multiple changes to event handling logic
- `server/event_server.py` - Added debug logging in `_on_event()`

## Lessons Learned

1. When debugging cross-system issues, start from the source (backend) not the sink (frontend)
2. WebSocket message delivery is not guaranteed to be 1:1 with send calls
3. Vite HMR can silently fail - always verify with `curl` or hard refresh
4. Stop and ask when stuck instead of making repeated speculative fixes
5. The user knows their codebase better - listen to their suggestions
