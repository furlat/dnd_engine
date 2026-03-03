# D&D 5e PixiJS Browser Client — Single-Document, End-to-End Implementation Guide
**Events Cursor Edition (COMPLETION-only, exactly-once)**
**Stack:** Vite + TypeScript + PixiJS (raw) + Zustand (vanilla) + Axios + Zod
**UI scope (for now):** Minimal DOM debug overlay only (event queue + playback queue + cursor + speed + performance metrics) — everything else is Pixi.

---

## Preface: What this document is

This is a **single, holistic, implementation-oriented** guide for building a browser client that:

- Renders an isometric battle map and entities (8-direction animations, many actions).
- Is **observer-first** when not in control: consumes server events and plays them back.
- Is **controller-ready** when it is your turn: fetches available actions, sends requests, supports optimistic visual starts, and reconciles with server truth.
- Solves the key problem: **server state changes are instant; visuals take time**.
- Uses the cursor endpoint:

```
GET /events?since=<cursor>&limit=200&phase=completion
=> { "events": [...], "count": N, "total": NEXT_CURSOR }
```

### Two-Phase Development Philosophy

This guide is structured around two phases:

- **Phase 1 — Correctness + Measurement.** Sync everything aggressively. After every event batch: refresh visibility, overwrite AW from ActionResult snapshots, measure every REST call cost. The goal is a client that is *always correct* and generates performance data to inform Phase 2.

- **Phase 2 — Optimize From Data.** Once correctness is proven and the Performance Monitor has accumulated real metrics, selectively reduce sync frequency. Skip `/visibility` calls when `SensesUpdateHint` proves nothing changed. Trust the reducer instead of overwriting from ActionResult. Every optimization is justified by measured data, not guesswork.

**Do not skip to Phase 2.** Premature optimization causes silent correctness bugs that are nearly impossible to diagnose. Build Phase 1 first, let the Performance Monitor tell you what's expensive, then optimize surgically.

---

## Core Principles (non-negotiable)

### 1) Two Worlds + One Bridge
You **must** separate:

- **Authoritative World (AW):** what the server says is true *now* (positions, HP, conditions, turn owner, encounter state).
- **Presentation World (PW):** what the player currently sees (animated, time-based, possibly behind).
- **EventDirector:** consumes events, updates AW immediately, and schedules PW animations ("clips").

If you try to render AW directly, you will desync horribly during AI bursts.

### 2) "COMPLETION only" for truth
The backend event system has phases (declaration/execution/effect/completion/cancel). Only COMPLETION is final; earlier phases can be modified/cancelled by handlers.
Therefore:

- **AW updates only from COMPLETION events.**
- PW can optionally animate "intent" earlier later, but that's polish; ignore for now.

### 3) Events drive causal state; REST drives computed state — with phased sync

Events are enough to track:
- positions, HP changes, conditions, deaths, turn transitions, light/perceivability changes.

Events do **not** replace:
- **available actions** (range/LOS/targets/paths/hazards computed on server)
- **FOV / fog-of-war sets** (server senses)
- **movement paths** (computed by server, surfaced via available-actions)

So the client uses REST for these. **How aggressively** depends on the phase:

| Need | Phase 1 (Correctness) | Phase 2 (Optimized) |
|------|----------------------|---------------------|
| `/state` | Bootstrap + resync + ActionResult comparison | Bootstrap + resync only |
| `/visibility` | After EVERY non-empty event batch | Only when `SensesUpdateHint` signals changes |
| `/available-actions` | Turn start only (ActionResult covers mid-turn) | Same |

### 4) Measure Before You Optimize
The debug overlay is a **correctness tool**, not polish. It ships in Milestone 4.5. It includes:
- Per-poll latency, event counts, response sizes
- Per-sync cycle cost (visibility, state fetches)
- AW drift detection (reducer vs ActionResult.state comparison)
- Rolling counters for REST calls/min and sync triggers/min

These metrics are the **only valid input** for Phase 2 optimization decisions.

---

## Part A — Project Setup (Vite + TS + Pixi + Zustand + Axios + Zod)

### A1) Create project
```bash
npm create vite@latest dnd-pixi-client -- --template vanilla-ts
cd dnd-pixi-client
npm install
```

### A2) Install dependencies

```bash
npm i pixi.js pixi-viewport zustand axios zod
npm i -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**PixiJS v8 note:** `Application.init()` is async in v8. You MUST await it before accessing `app.canvas` or `app.renderer`:

```ts
const app = new Application();
await app.init({
  resizeTo: document.getElementById("pixi-root")!,
  background: 0x111111,
  antialias: true,
});
document.getElementById("pixi-root")!.appendChild(app.canvas); // v8: .canvas not .view
```

See Appendix S for all v7→v8 breaking changes.

**Why Tailwind if UI is minimal?**
Because a tiny debug overlay is still useful and Tailwind makes it easy. You can drop Tailwind later without changing architecture.

### A3) Tailwind config

`tailwind.config.js`

```js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

`src/styles.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root { color-scheme: dark; }
```

### A4) Index layout (canvas + minimal overlay)

`index.html` body content:

```html
<div id="app" class="w-screen h-screen relative overflow-hidden">
  <div id="pixi-root" class="absolute inset-0"></div>
  <div id="ui-root" class="absolute inset-0 pointer-events-none"></div>
</div>
```

* Pixi canvas will be appended to `#pixi-root`.
* Debug overlay DOM nodes go in `#ui-root`.
* `pointer-events-none` ensures Pixi receives mouse input unless you explicitly enable pointer events on a UI element.

---

## Part B — Mental Model of Runtime

### B1) From "state 0" to live game

At browser start:

1. Create session, join game.
2. Fetch `/state` snapshot (world baseline).
3. Initialize event cursor (`/events?since=0&limit=0&phase=completion` → `total`).
4. Fetch `/visibility` for fog-of-war baseline (observer selection).
5. Create Pixi scene objects based on snapshot.
6. Start polling:
   * ping (turn ownership)
   * events (cursor stream)
7. As events arrive:
   * patch AW immediately (truth)
   * enqueue PW clips for animation
   * **Phase 1**: refresh `/visibility` after every non-empty batch
8. If it becomes your turn:
   * fetch available actions
   * accept input; optionally run optimistic windup
   * send `/action/execute`

### B2) Why the cursor endpoint changes everything

Previously `/events` was "recent events"; you needed overlap polling + dedupe.
Now you have a cursor. That means:

* Exactly-once delivery (from client POV) with a single integer `cursor`.
* No dedupe sets.
* Recovery after disconnect is just "continue from cursor".
* WS overflow recovery becomes "resume via /events since cursor".

### B2b) Observer UUID vs camera follow target (separate concerns)

Two things move independently:

| Concept | What it controls | When it changes |
|---------|------------------|-----------------|
| **Observer UUID** (`visionStore.observer_uuid`) | Which entity's perception drives fog-of-war (`/visibility` calls) | Set once at bootstrap (primary controlled entity). **Stable for the entire session.** |
| **Camera follow target** (`followTargetUuid`) | Which entity the camera centers on / follows | Changes every turn start (active entity) |

**Rule:** Observer UUID = primary controlled entity (stable). Camera follow target = active entity (changes every turn). These are **never** the same variable.

**Why this matters:** If you accidentally switch `observer_uuid` to the active entity every turn, fog-of-war will flicker wildly (you'd see from the enemy's perspective during their turn, then snap back to yours). The player's fog should always reflect *their* hero's perception — the camera just pans to show whose turn it is.

### B3) ActionResult is a free resync

`POST /action/execute` returns `ActionResult` which includes:

```ts
{
  success: boolean;
  message: string;
  state: APIGameState | null;           // Full world snapshot AFTER the action
  available_actions: AvailableActions;  // Re-computed actions AFTER the action
  combat_log_entries: CombatLogEntry[]; // All logs generated by this action
  deaths: string[];                     // Names of entities that died
  encounter_ended: boolean;
  turn_continues: boolean;
  // ... plus event_type, event_data, entity_hp, target_hp, triggered_reactions
}
```

**This means during your turn, you never need separate `/state` or `/available-actions` calls between actions.** The execute response gives you everything. The only time you call `GET /available-actions` is at **turn start** (before your first action). After that, every `ActionResult` includes the updated available actions inline.

In **Phase 1**, always overwrite AW from `ActionResult.state` — this is a continuous correctness check. In **Phase 2**, trust the reducer and use `ActionResult.state` only for drift detection.

**ActionResult vs /events — no deduplication needed.** The two streams serve different purposes and the client does NOT attempt to dedupe between them:
- **ActionResult** → AW overwrite (Phase 1) or drift detection (Phase 2) + inline available actions update + combat log display.
- **/events** → AW reducer updates + animation clip generation. Events drive the visual playback.

Both may describe the same state change (e.g., an HP reduction). That's fine — the reducer is idempotent (setting HP to X twice is harmless), and Phase 1's overwrite from ActionResult makes the reducer's update redundant anyway. Do not invent an "ignore events that came from my own action" rule — it adds complexity for zero benefit and risks dropping events that trigger visual clips.

### B4) Client runtime state machine

The client has exactly 7 states. Every state transition is deterministic and triggered by a specific event.

**State diagram:**
```
BOOTSTRAPPING ──→ OBSERVING ←──→ MY_TURN_READY ──→ MY_TURN_INPUT ←──→ MY_TURN_INFLIGHT
                      ↑                                                       │
                  RESYNCING ← ─ ─ ─ ─ ─ (any error) ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘
                                                                              ↓
                                                                           ENDED
```

**State definitions:**

| State | Description | Active pollers |
|---|---|---|
| BOOTSTRAPPING | Creating session, fetching /state, initializing cursor | None |
| OBSERVING | Not my turn. Watching events, polling ping. | ping + events |
| MY_TURN_READY | Ping returned `is_my_turn=true`. Need to fetch available actions. | ping + events |
| MY_TURN_INPUT | Actions fetched. Player selecting target. | ping + events |
| MY_TURN_INFLIGHT | Action request sent, awaiting ActionResult. | ping + events |
| RESYNCING | Error recovery. Re-fetching /state + cursor. | None (paused) |
| ENDED | Encounter ended. | None |

**Transition table:**

| From | To | Trigger | API calls |
|---|---|---|---|
| BOOTSTRAPPING | OBSERVING | Bootstrap done, `is_my_turn=false` | POST /session/create, GET /state, GET /visibility, cursor init, start pollers |
| BOOTSTRAPPING | MY_TURN_READY | Bootstrap done, `is_my_turn=true` | Same as above |
| OBSERVING | MY_TURN_READY | `ping.is_my_turn=true` | None |
| MY_TURN_READY | MY_TURN_INPUT | GET /available-actions succeeds | GET /entity/{uuid}/available-actions |
| MY_TURN_READY | OBSERVING | `ping.is_my_turn=false` (turn ended before fetch) | None |
| MY_TURN_INPUT | MY_TURN_INFLIGHT | Player clicks execute | POST /action/execute |
| MY_TURN_INFLIGHT | MY_TURN_INPUT | `ActionResult.turn_continues=true` | Process ActionResult, update AW + available actions |
| MY_TURN_INFLIGHT | OBSERVING | `ActionResult.turn_continues=false` | Process ActionResult, clear targeting mode |
| MY_TURN_INFLIGHT | ENDED | `ActionResult.encounter_ended=true` | Stop pollers, show result |
| MY_TURN_INPUT | OBSERVING | `ping.is_my_turn=false` (died from reaction during opponent's turn) | Clear targeting mode |
| Any | RESYNCING | Error (see G4) | Pause pollers |
| RESYNCING | OBSERVING | Resync complete | GET /state, cursor reinit, GET /visibility, flush clip queue, snap PW to AW, resume pollers |
| Any | ENDED | `encounter_ended` (from event or ping) | Stop pollers |

**TypeScript implementation:**

```ts
type ClientState =
  | "bootstrapping"
  | "observing"
  | "my_turn_ready"
  | "my_turn_input"
  | "my_turn_inflight"
  | "resyncing"
  | "ended";

const VALID_TRANSITIONS: Record<ClientState, ClientState[]> = {
  bootstrapping:   ["observing", "my_turn_ready"],
  observing:       ["my_turn_ready", "resyncing", "ended"],
  my_turn_ready:   ["my_turn_input", "observing", "resyncing", "ended"],
  my_turn_input:   ["my_turn_inflight", "observing", "resyncing", "ended"],
  my_turn_inflight:["my_turn_input", "observing", "ended", "resyncing"],
  resyncing:       ["observing"],
  ended:           [],
};

function transition(current: ClientState, next: ClientState): ClientState {
  if (!VALID_TRANSITIONS[current].includes(next)) {
    console.error(`Invalid transition: ${current} → ${next}`);
    return current;  // Stay in current state
  }
  onStateEnter(next);
  return next;
}

function onStateEnter(state: ClientState) {
  switch (state) {
    case "observing":       clearTargetingMode(); break;
    case "my_turn_ready":   fetchAvailableActions(); break;
    case "resyncing":       pausePollers(); performResync(); break;
    case "ended":           stopPollers(); showEndScreen(); break;
  }
}
```

**Key invariants:**
- Player input is accepted **only** in MY_TURN_INPUT
- Only one inflight request at a time (MY_TURN_INFLIGHT blocks further input)
- Events poller processes events in ALL active states (AW is always current, even during targeting)
- Pollers run in OBSERVING, MY_TURN_READY, MY_TURN_INPUT, MY_TURN_INFLIGHT — paused in BOOTSTRAPPING, RESYNCING, ENDED
- RESYNCING always resolves to OBSERVING (turn ownership re-evaluated from fresh state)

---

## Part C — Data Architecture (Single Store, Four Slices)

Implement a **single Zustand store** with four logical slices. The render loop needs cross-slice reads constantly (e.g., "is this entity visible?" reads AW position + Vision visibility + PW animation state), and separate stores turn this into subscription management hell. One store with slices gives you:

- Selectors across all slices without `useSyncExternalStore` hacks
- A single `subscribe` for the ticker/render loop
- No cross-store race conditions on batch updates

```ts
import { create } from "zustand";

export const useGameStore = create<AuthState & VisionState & PresentationState & UIState>()((set, get) => ({
  // Auth slice (C2)
  session_id: null,
  entitiesById: {},
  // ...

  // Vision slice (C3)
  observer_uuid: null,
  seenCells: new Set(),
  // ...

  // Presentation slice (C4)
  globalAnimSpeed: 1.0,
  entityVisualsById: {},
  // ...

  // UI slice (C5)
  selectedEntity: null,
  // ...
}));
```

**Slice naming convention:** Prefix mutations with their domain: `awUpdateEntity()`, `visionRefresh()`, `pwSnapToAW()`, `uiSelectEntity()`. This keeps the flat namespace navigable.

**Code example convention:** Throughout this document, code examples use `authStore`, `visionStore`, `presentationStore`, `uiStore` as shorthand for accessing the corresponding slice fields via `useGameStore.getState()`. They are NOT separate stores:

```ts
// These are all the same store — shorthand for readability
const store = useGameStore.getState();
const entity = store.entitiesById[uuid];         // Auth slice field
const visible = store.visibleCells.has(key);     // Vision slice field
const visual = store.entityVisualsById[uuid];    // Presentation slice field
```

The four logical slices:

### C1) Common types

Use these types throughout (keep them in one file, e.g. `src/engine/types.ts`):

```ts
export type Uuid = string;
export type Pos = [number, number];
export type TileKey = `${number},${number}`;

export const tileKey = (x: number, y: number): TileKey => `${x},${y}`;
```

### C2) Auth slice — Authoritative World (AW)

**Purpose:** hold server truth, updated from `/state` (bootstrap/resync) and `/events` (COMPLETION).

**Key properties to store:**

* session_id, controlled_entity_uuids
* active_entity_uuid, is_my_turn
* entities (by uuid)
* encounter state
* grid tiles + objects
* computed affordances cache (available actions)
* event cursor (integer)
* performance metrics

**Canonical structure:**

```ts
export type EntityAuth = {
  uuid: Uuid;
  name: string;
  position: Pos;
  faction: string | null;
  hp: number;
  max_hp: number;
  ac: number;
  is_dead: boolean;
  conditions: string[];
  condition_details: { name: string; category: string }[];
};

export type EncounterAuth = {
  uuid: Uuid;
  name: string;
  state: string;
  round_number: number;
  current_turn_index: number;
  current_entity_uuid: Uuid | null;
  initiative_order: { uuid: Uuid; name: string; initiative: number; is_dead: boolean }[];
};

export type TileAuth = {
  x: number; y: number;
  name: string;
  walkable: boolean;
  walking_cost: number;
  is_hazardous: boolean;
  conditions: string[];
  light_level: number;
};

export type FloorObjectAuth = {
  uuid: Uuid;
  name: string;
  position: Pos;
  map_char: string;
};

export type PerfMetrics = {
  // Per-poll metrics (ring buffer, last N entries)
  pollLatenciesMs: number[];
  pollEventCounts: number[];
  pollResponseSizes: number[];

  // Per-sync metrics
  visibilityFetchMs: number[];
  stateFetchMs: number[];

  // Rolling counters
  restCallsThisMinute: number;
  syncTriggersThisMinute: number;
  lastMinuteResetAtMs: number;

  // Drift detection
  awDriftCount: number;              // How many times reducer AW != ActionResult.state
  awDriftFields: string[];           // Which fields drifted (last occurrence)
  lastDriftAtMs: number | null;
};

export type AuthState = {
  // Session / control
  session_id: string | null;
  controlled_entity_uuids: Uuid[];
  active_entity_uuid: Uuid | null;
  is_my_turn: boolean;

  // Truth state
  entitiesById: Record<Uuid, EntityAuth>;
  encounter: EncounterAuth | null;

  gridBounds: { min_x: number; min_y: number; max_x: number; max_y: number };
  tilesByKey: Record<TileKey, TileAuth>;
  floorObjectsById: Record<Uuid, FloorObjectAuth>;

  // Computed affordances
  availableActions: any | null;
  availableActionsFor: Uuid | null;
  lastActionsFetchAtMs: number | null;

  // Event cursor (the most important field)
  eventCursor: number;

  // Health / connectivity
  lastStateSyncAtMs: number | null;
  lastPingAtMs: number | null;
  lastEventsPollAtMs: number | null;
  connectionStatus: "connected" | "degraded" | "disconnected";

  // Performance monitoring
  perfMetrics: PerfMetrics;

  revision: number;
};
```

**Notes on `revision`:**

* Increment on any meaningful mutation so render systems can cheaply detect "something changed" without deep comparisons.

### C3) Vision slice — Fog-of-war / observer perception

**Purpose:** represent **never-seen vs seen vs visible** for one observer.

From `/visibility`, you get for each entity:

* visible_cells
* seen_cells
* visible_entities
* sense_modes

Store only what you need for the current observer (to avoid huge memory).

```ts
export type VisionState = {
  observer_uuid: Uuid | null;
  seenCells: Set<TileKey>;
  visibleCells: Set<TileKey>;
  visibleEntities: Set<Uuid>;
  senseModes: { name: string; range: number }[];
  lastVisibilityFetchAtMs: number | null;
  revision: number;
};
```

### C4) Presentation slice — what Pixi actually renders

**Purpose:** PW is time-based and can lag AW; it also contains camera controls.

Key fields:

* globalAnimSpeed (scalar multiplier)
* camera center + zoom + drag state
* per-entity visual state: position (float), anim name, facing, hpDisplayed, visibility flag
* clip queue metrics for debug overlay
* optimistic state flag

```ts
export type Facing8 = "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW";

export type EntityVisual = {
  uuid: Uuid;
  worldX: number; // grid-space float
  worldY: number; // grid-space float
  facing: Facing8;
  anim: string;
  animTime: number;
  hpDisplayed: number;
  visibleToObserver: boolean;
};

export type CameraState = {
  centerWorldX: number;
  centerWorldY: number;
  zoom: number;
  isDragging: boolean;
  dragStartScreenX: number;
  dragStartScreenY: number;
  dragStartCenterX: number;
  dragStartCenterY: number;
};

export type PresentationState = {
  globalAnimSpeed: number;
  camera: CameraState;
  entityVisualsById: Record<Uuid, EntityVisual>;
  queuedClipCount: number;
  queuedClipMsEstimate: number;
  optimistic: { active: boolean; requestId: string | null; startedAtMs: number | null; };
  revision: number;
};
```

### C5) UI slice — minimal

Keep it tiny:

* selected entity UUID
* debug toggles (show fog overlay, show tile coords, show perf overlay, etc.)

---

## Part D — API Client Design (Axios + Zod)

### D1) Axios instance

Create an axios client with a base URL and timeouts.

* Base URL: `http://localhost:8000` (or your configurable env var)
* Timeout: ~5000ms
* Prefer an abortable request pattern for polling.

### D2) Zod validation strategy

Don't try to validate every nested type on day 1; validate top-level shape and critical fields first:

* `/events` response: `{ events: array, count: number, total: number }`
* `Event`: must include `uuid`, `event_type`, `phase`, `timestamp`, `source_entity_uuid`, optional target fields.

Later you can expand.

### D3) Required endpoints and exactly when to call them

**Bootstrap / resync**

* `GET /state` → `APIGameState`
* `GET /events?since=0&limit=0&phase=completion` (cursor init)
* `GET /visibility` (fog baseline)

**Live polling**

* `GET /events?since=<cursor>&limit=200&phase=completion`
* `POST /session/{id}/ping` → `SessionPingResponse`

**On your turn (first action)**

* `GET /entity/{uuid}/available-actions` — only needed **once** at turn start

**On your turn (each action)**

* `POST /action/execute` → `ActionResult` — includes `state`, `available_actions`, `combat_log_entries`, `deaths`, `encounter_ended`, `turn_continues` inline. **No need for separate `/state` or `/available-actions` calls between actions.**

**End of turn**

* `POST /action/end-turn`

**Simulation setup (dev)**

* `POST /simulation/start-human?character_class=fighter` — creates encounter + hero, returns `hero_uuid`

**SessionPingResponse fields:**

```ts
{
  status: string;
  session_id: string;
  connection_status: string;
  is_my_turn: boolean;
  active_entity_uuid: string | null;
  active_entity_name: string | null;
  controlled_entities: string[];   // Authoritative list of controlled entity UUIDs
}
```

---

## Part E — Bootstrap Flow (No Gaps, Cursor-Safe)

This section is extremely specific and is the "state 0" answer.

### E1) Step-by-step bootstrap (recommended)

Assume you have a single entry `bootstrap()` that runs once at startup.

1. `POST /session/create`

   * store `session_id`

2. Start encounter (dev) and join:

   * `POST /simulation/start-human?character_class=fighter` — returns `hero_uuid`
   * `POST /game/join { session_id, entity_uuids: [hero_uuid] }`
   * store `controlled_entity_uuids`

3. `GET /state`

   * parse and populate AuthStore:

     * tilesByKey
     * entitiesById
     * floorObjectsById
     * encounter
   * set `lastStateSyncAtMs=now`, `connectionStatus=connected`

4. `POST /session/{id}/ping`

   * set `active_entity_uuid`, `is_my_turn`
   * set `controlled_entity_uuids` from response (authoritative)
   * set `lastPingAtMs=now`

5. Initialize event cursor without pulling history:

   * `GET /events?since=0&limit=0&phase=completion`
   * set `eventCursor = response.total`

6. Choose observer UUID:

   * if `active_entity_uuid` is in controlled list → observer=active
   * else observer = first controlled entity (or null if spectator)
   * set VisionStore.observer_uuid

7. `GET /visibility`

   * extract observer's `seen_cells`, `visible_cells`, `visible_entities`, `sense_modes`
   * populate VisionStore sets

8. Initialize Presentation from Authoritative:

   * For each entity in AW:

     * create EntityView (Pixi object)
     * set PW entity visual:

       * worldX/Y = AW position
       * hpDisplayed = AW hp
       * visibleToObserver = VisionStore.visibleEntities has uuid (if observer exists)
   * Render fog overlay based on seen/visible sets.
   * Focus camera on observer entity (optional but recommended).

9. If it's your turn and active entity is controlled:

   * `GET /entity/{active}/available-actions`
   * store `availableActions` and `availableActionsFor=active`

10. Start pollers:

* ping poller
* events poller

### E2) Why step 5 happens after `/state`

You want your snapshot to define the baseline world.
Then you start listening only for events *after* that baseline via the cursor init call.

This avoids:

* replaying all events from encounter start
* and avoids a "gap" where events happened after snapshot but before your cursor started.

If you need full catch-up (replay from earlier cursor), you can do it, but default is: snapshot then cursor-init then live.

### E3) ActionResult as inline resync during your turn

During your turn, the data flow is:

1. **Turn start** → `GET /entity/{uuid}/available-actions` (the only explicit fetch)
2. **Each action** → `POST /action/execute` returns `ActionResult` with:
   - `state: APIGameState` — full world snapshot post-action
   - `available_actions` — re-computed options post-action
   - `combat_log_entries` — all logs from this action
   - `deaths`, `encounter_ended`, `turn_continues` — control flow signals
3. **No separate calls needed** between actions — `ActionResult` is a free resync.

The events poller may also pick up these same events (they're in the cursor stream too). That's fine — the reducer is idempotent. In Phase 1, ActionResult.state overwrites AW anyway. In Phase 2, the reducer handles them and ActionResult is used only for drift detection.

---

## Part F — Polling Loops (Ping + Events Cursor)

### F1) Ping poller (turn ownership)

* Interval: start at 1000ms. Performance Monitor will tell you if this is too frequent.
* This is lightweight and ensures your client knows when it can act.

On each ping:

* update `is_my_turn`
* update `active_entity_uuid`
* update `controlled_entity_uuids` (authoritative from response)
* if `is_my_turn` flipped from false → true:

  * trigger "turn-start routine":

    * fetch available actions
    * **Phase 1**: refresh visibility
    * optionally snap PW closer to AW to avoid aiming on stale visuals

### F2) Events poller (the backbone)

* Interval: start at 400ms. Performance Monitor will tell you whether to adjust.

Call:

```
GET /events?since=<eventCursor>&limit=200&phase=completion
```

Process:

1. if count == 0 → return quickly (still record poll latency in perfMetrics)
2. for each event **in response order** (do NOT sort by timestamp — see F3):

   * apply to AW reducer immediately
   * build 0..N animation clips and enqueue into EventDirector
3. set cursor to `response.total`
4. update `lastEventsPollAtMs`
5. **Phase 1**: if any events were processed, refresh `/visibility` for observer
6. record metrics: poll latency, event count, response size, whether sync was triggered

Because cursor is exact:

* no dedupe
* no overlap
* no risk of duplicate processing (unless you crash before persisting cursor)

### F3) Cursor ordering is causal — DO NOT sort by timestamp

The `/events?since=N` endpoint returns events in **storage order = causal order**. This is the correct processing order. Sorting by timestamp could reorder events incorrectly (e.g., two events at the same millisecond but with causal dependency). Trust the cursor order.

### F4) Persisting cursor (recommended)

Persist `eventCursor` to localStorage (and session_id optionally) so that refreshing the page can resume.

Caveat: if you rejoin a different encounter/session, discard persisted cursor.

Simple rule:

* Use `encounter.uuid` from the `/state` bootstrap response as the storage key: `localStorage.setItem(encounter_uuid, cursor)`.
* On bootstrap, compare the encounter UUID from `/state` against the stored key. If they differ (new encounter, server restart), discard the persisted cursor and initialize fresh.
* If the backend ever exposes a stable `game_id`, prefer that as the key instead.

### F5) Performance Monitor instrumentation on polls

Every poll should record:

```ts
perfMetrics.pollLatenciesMs.push(endTime - startTime);
perfMetrics.pollEventCounts.push(response.count);
perfMetrics.pollResponseSizes.push(JSON.stringify(response).length);
perfMetrics.restCallsThisMinute++;
if (syncTriggered) perfMetrics.syncTriggersThisMinute++;
```

Keep ring buffers at ~100 entries. Reset minute counters every 60s.

### F6) Future: WebSocket upgrade path

The polling-only approach (400ms events, 1s ping) is correct for turn-based combat and ships first. If you later want sub-100ms event delivery for smoother observer animations during AI burst turns, add WebSocket as a **supplement** to polling, not a replacement:

* WS pushes events as they happen (low latency)
* On WS disconnect or overflow → resume via `/events?since=cursor` (cursor recovery)
* Polling becomes a heartbeat fallback (every 2-5s instead of 400ms)
* The cursor integer makes this seamless — WS and polling use the same cursor

This is a Phase 2+ concern. Do not implement WS until polling is proven correct and the Performance Monitor shows that 400ms latency is actually a problem.

---

## Part G — Resync Strategy (Now Much Simpler)

Even with cursor, resync is still needed for:

* network failures
* backend restarts
* rare logic drift

### G1) Resync triggers (practical)

Resync when any of these happens:

1. Events poll fails repeatedly (e.g. 3 consecutive failures)
2. Cursor appears invalid (server returns `total < since`, or returns 400 for cursor)
3. You receive events referencing unknown entity UUIDs (means your snapshot baseline doesn't match reality)
4. User presses "Resync" in debug overlay

### G2) Resync procedure (deterministic)

1. `GET /state` → replace AW truth
2. `GET /events?since=0&limit=0&phase=completion` → set cursor = total
3. refresh `/visibility` for observer
4. snap PW entity visuals to AW positions/HP (simple)
5. clear clip queue (recommended in early development)
6. resume pollers

Resync is your "restore correctness" button.

### G3) ActionResult.state as opportunistic resync

Every `POST /action/execute` returns `ActionResult.state` (an `APIGameState` snapshot). Use it:

**Phase 1**: Always overwrite AW from `ActionResult.state`. This guarantees correctness during your turn — the server snapshot is truth.

**Phase 2**: Compare reducer-maintained AW against `ActionResult.state`. If they match → reducer is correct, no overwrite needed. If they drift → increment `perfMetrics.awDriftCount`, record which fields drifted, and overwrite AW from the snapshot. When `awDriftCount` stays at 0 over sustained play, you can stop overwriting.

```ts
function handleActionResult(result: ActionResult) {
  if (result.state) {
    if (PHASE === 1) {
      overwriteAW(result.state);
    } else {
      const drifted = detectDrift(authStore, result.state);
      if (drifted.length > 0) {
        perfMetrics.awDriftCount++;
        perfMetrics.awDriftFields = drifted;
        perfMetrics.lastDriftAtMs = Date.now();
        overwriteAW(result.state);  // Fix drift
      }
    }
  }
  if (result.available_actions) {
    authStore.availableActions = result.available_actions;
  }
}
```

### G4) Error handling rules (deterministic)

Every error scenario has a single, deterministic response. No ambiguity.

**Error scenario table:**

| Error | Detection | Response | Max retries | Backoff |
|---|---|---|---|---|
| Transient network on GET /events | Fetch throws or times out | Retry next poll cycle. After 5 consecutive failures → RESYNCING | 5 | Normal poll interval |
| Transient network on ping | Fetch throws or times out | Retry next poll cycle. After 5 → `connectionStatus="degraded"`. After 10 → RESYNCING | 10 | Normal poll interval |
| Cursor invalid (stale/server restart) | `server.total < local cursor` OR HTTP 400 on /events | Immediate RESYNCING (cursor is stale, server likely restarted) | 0 | Immediate |
| 401/403 any endpoint | HTTP 401 or 403 | Session expired → full re-bootstrap (BOOTSTRAPPING) | 0 | Immediate |
| 404 entity endpoint | HTTP 404 | Entity removed. Log warning. Don't resync. | 0 | N/A |
| /action/execute 4xx | HTTP 400 or 422 | Stop optimistic clip. Show error toast. Refetch available actions. Stay MY_TURN_INPUT | 0 | N/A |
| /action/execute 5xx or network | HTTP 5xx or timeout | Show error toast. Do NOT retry (risk double-execute). Refetch available actions. | 0 | N/A |
| /visibility failure | Any error | Log warning. Set `visionDirty = true`. Retry next poll cycle. | 0 | Next poll |
| /available-actions failure | Any error | Retry 1× after 500ms. On 2nd failure show error toast. Stay MY_TURN_READY | 1 | 500ms |
| Server unreachable (5+ failures) | 5+ consecutive failures across any endpoint | `connectionStatus="disconnected"`. Exponential backoff to 16s. On first success → RESYNCING | ∞ | 2s → 4s → 8s → 16s cap |
| Unknown entity UUID in event | `entity_uuid` not in AW entities map | Entity created after last snapshot → RESYNCING | 0 | Immediate |

**ConnectionStatus type:**

```ts
type ConnectionStatus = "connected" | "degraded" | "disconnected";
// connected:    last successful response < 5s ago
// degraded:     3+ consecutive ping failures OR 2+ consecutive event poll failures
// disconnected: 5+ consecutive failures on any endpoint
```

**Consecutive failure counter pattern:**

```ts
interface FailureTracker {
  consecutiveFailures: number;
  lastFailureAtMs: number;
}

function recordSuccess(tracker: FailureTracker) {
  tracker.consecutiveFailures = 0;
}

function recordFailure(tracker: FailureTracker): number {
  tracker.consecutiveFailures++;
  tracker.lastFailureAtMs = Date.now();
  return tracker.consecutiveFailures;
}

function getBackoffMs(tracker: FailureTracker, baseMs: number = 1000, capMs: number = 16000): number {
  const expo = Math.min(baseMs * Math.pow(2, tracker.consecutiveFailures - 1), capMs);
  return expo;
}
```

**Key invariants:**
- Never retry `/action/execute` — risk of double-execution (e.g., double attack, double spell slot consumption)
- Cursor invalidity always triggers RESYNCING — partial state is worse than a full refetch
- 401/403 always triggers full re-bootstrap — session is gone, no point resyncing
- Unknown entity UUIDs trigger RESYNCING rather than ignoring — the entity may be relevant to future events

---

## Part H — Event Processing (Reducer) — Complete Event Catalog

### H1) Event normalization

All events share base fields:

* `uuid` — unique event ID
* `lineage_uuid` — shared across phase transitions of the same logical event
* `timestamp` — ISO datetime string
* `event_type` — string enum (see H2)
* `phase` — always COMPLETION (filtered by endpoint)
* `source_entity_uuid` / `source_entity_name`
* `target_entity_uuid` / `target_entity_name`
* `canceled` — boolean (should be false for COMPLETION events)
* `parent_event` — UUID of parent event (for hierarchical events)
* `lineage_children_events` / `children_events` — UUID lists

Because your backend event schema is rich and varied, implement reducers by `event_type` string.

**Golden rule:** ignore events not in COMPLETION (but your endpoint filter already enforces that).

#### Event field normalization helpers

Different event types use different field names for actor and target. Define two canonical helpers and use them everywhere (reducers, clip builders, logging):

```ts
function getActorUuid(event: ServerEvent): Uuid | null {
  return event.entity_uuid ?? event.source_entity_uuid ?? null;
}

function getTargetUuid(event: ServerEvent): Uuid | null {
  return event.target_entity_uuid ?? event.target_uuid ?? null;
}
```

**Why:** `turn_start` uses `entity_uuid`, `attack` uses `source_entity_uuid`, `take_damage` uses `target_entity_uuid`. Rather than remembering which events use which field, normalize once and use `getActorUuid()`/`getTargetUuid()` everywhere. The reducer and clip builder should never access `event.entity_uuid` or `event.source_entity_uuid` directly.

**Usage in `buildClips()`:**

```ts
function buildClips(event: ServerEvent): ClipGroup[] {
  const actor = getActorUuid(event);
  const target = getTargetUuid(event);

  switch (event.event_type) {
    case "movement":
      if (!actor) return [];
      return [{ clips: [new MoveClip(actor, event.path ?? [event.start_position, event.end_position])] }];
    case "take_damage":
      if (!target) return [];
      return [{ clips: [new HitFlashClip(target), new DamageNumberClip(target, event.final_damage ?? event.total_damage)] }];
    case "heal":
      if (!target) return [];
      return [{ clips: [new DamageNumberClip(target, event.actual_healing, "heal")] }];
    case "death":
      if (!actor) return [];
      return [{ clips: [new DeathClip(actor)] }];
    case "attack":
      if (!actor || !target) return [];
      return [{ clips: [new AttackWindupClip(actor, target)] }];
    case "cast_spell":
      if (!actor) return [];
      return [{ clips: [new CastClip(actor, event.name)] }];
    // ... other types
    default:
      return [];
  }
}
```

### H1b) Event tree structure and COMPLETION ordering

Every action produces a **tree** of events. A melee attack creates: AttackEvent → (child) TakeDamageEvent → (grandchild) DeathEvent. An AoE spell creates: SpellEvent → N × (per-target child) → each with TakeDamageEvent children.

**The key insight:** In the `/events?phase=completion` stream, **children complete BEFORE parents**. This is because `phase_to(COMPLETION)` is called bottom-up — a child must finish (reach COMPLETION) before its parent can collect its combat log and complete.

#### Linking fields on every event

| Field | Type | Meaning |
|-------|------|---------|
| `parent_event` | `UUID \| null` | Points to the **specific phase UUID** of the parent event that spawned this child. For AoE per-target children, this points to the parent's EXECUTION phase UUID. **Warning:** this is NOT a lineage UUID — it's a specific phase instance UUID that may not appear in the COMPLETION stream. |
| `lineage_uuid` | `UUID` | Shared across all phase transitions of the same logical event. For single-target actions, children share the parent's lineage. **For AoE per-target children, each gets a NEW lineage_uuid** (isolated save/damage tracking). |
| `children_events` | `UUID[]` | Children spawned during the current phase only (reset on each `phase_to()`). |
| `lineage_children_events` | `UUID[]` | ALL children spawned across the event's entire lifetime. Accumulates: on `phase_to()`, `lineage_children_events = old_lineage_children + old_children`, then `children_events = []`. |

#### Backend mechanics (why children come first)

From `dnd/core/events.py` line 285, `phase_to()`:
1. Each `phase_to()` call creates a **new UUID** but preserves `lineage_uuid`
2. The new event is registered in `EventQueue._all_events` (sorted by timestamp)
3. At COMPLETION, `_collect_child_combat_logs()` walks `lineage_children_events` to gather child combat logs into `sub_entries`

From `dnd/core/base_actions.py` line 672, AoE convolution:
1. For each target in `all_target_uuids`, a **child event** is created with:
   - `uuid = uuid4()` — brand new UUID
   - `lineage_uuid = uuid4()` — brand new lineage (NOT shared with parent)
   - `parent_event = execution_event.uuid` — points to parent's EXECUTION phase UUID
2. Each child calls `_apply()` which creates TakeDamage → COMPLETION (child completes)
3. After ALL children complete, the parent calls `phase_to(EFFECT)` then `phase_to(COMPLETION)` — parent completes last

#### Concrete stream examples

**Single-target melee attack** — cursor order from `/events?phase=completion`:
```
Event 1: TakeDamageEvent   COMPLETION  target_entity_uuid=<skeleton>
                                        parent_event=<attack_effect_phase_uuid>
                                        total_damage=12
                                        damage_type="slashing"

Event 2: AttackEvent        COMPLETION  source_entity_uuid=<hero>
                                        target_entity_uuid=<skeleton>
                                        attack_outcome="hit"
                                        total_damage=12
                                        lineage_children_events=[<take_damage_uuid>, ...]
```

If the attack kills the target, a DeathEvent COMPLETION appears between events 1 and 2 (Death completes before Attack because Death is a child of TakeDamage which is a child of Attack).

**AoE spell (Fireball, 3 targets)** — cursor order:
```
Event 1: SavingThrowEvent  COMPLETION  target=Skel1  lineage_uuid=L1
                                        parent_event=<per_target_1_exec_uuid>
Event 2: TakeDamageEvent   COMPLETION  target=Skel1  lineage_uuid=L1
                                        parent_event=<saving_throw_1_effect_uuid>
                                        total_damage=28

Event 3: SavingThrowEvent  COMPLETION  target=Skel2  lineage_uuid=L2
                                        parent_event=<per_target_2_exec_uuid>
Event 4: TakeDamageEvent   COMPLETION  target=Skel2  lineage_uuid=L2
                                        parent_event=<saving_throw_2_effect_uuid>
                                        total_damage=14  (saved, half)

Event 5: SavingThrowEvent  COMPLETION  target=Skel3  lineage_uuid=L3
                                        parent_event=<per_target_3_exec_uuid>
Event 6: TakeDamageEvent   COMPLETION  target=Skel3  lineage_uuid=L3
                                        parent_event=<saving_throw_3_effect_uuid>
                                        total_damage=28

Event 7: SpellEvent        COMPLETION  source=Wizard
                                        total_targets=3
                                        total_damage=70
                                        lineage_children_events=[...]
```

Key observations:
- Per-target children (events 1-6) each have a **unique lineage_uuid** (L1, L2, L3)
- The parent SpellEvent (event 7) arrives **last** with `total_targets` and `total_damage` summary
- `parent_event` on children points to intermediate phase UUIDs that are NOT in the COMPLETION stream (they're EXECUTION or EFFECT phase UUIDs) — **do NOT try to look up parent_event in your event store, it won't be there**

#### Practical impact on the reducer

**Process events in cursor order. Each event is independent for AW state updates.** You don't need to reconstruct the tree for the reducer:

- `TakeDamageEvent COMPLETION` → update target HP (use `event.target_entity_uuid`, `event.total_damage`)
- `DeathEvent COMPLETION` → mark entity as dead
- `AttackEvent/SpellEvent COMPLETION` → no AW update needed (children already applied damage)
- `ConditionApplicationEvent COMPLETION` → add condition to entity
- `MovementEvent COMPLETION` → update entity position

The parent event's `total_damage` / `total_targets` fields are summaries — the actual HP changes already happened via the child TakeDamage events.

#### Practical impact on animation (AoE grouping)

Use the **parent-last pattern** to detect AoE and group child clips for parallel playback.

**Why this needs care:** In the COMPLETION stream, an AoE spell like Fireball produces per-target event groups (saving throw → damage → per-target spell completion) interleaved across targets, with the parent spell completing last. Naively flushing accumulated damage clips when you see a non-damage event (like a saving throw or per-target spell completion) breaks the grouping. Instead, **keep accumulating until you see the AoE parent marker or the batch ends:**

```ts
function processEventBatch(events: ServerEvent[]): ClipGroup[] {
  const allGroups: ClipGroup[] = [];
  const pendingDamageClips: AnimationClip[] = [];

  for (const event of events) {
    const clips = buildClips(event);

    if (event.event_type === "take_damage") {
      // Accumulate damage clips — they might be part of an AoE batch.
      // Do NOT flush on intervening non-damage events (saving throws,
      // per-target spell completions, condition apps all appear between
      // damage events in AoE sequences).
      for (const group of clips) {
        pendingDamageClips.push(...group.clips);
      }
    } else if (
      (event.event_type === "cast_spell" || event.event_type === "attack") &&
      (event.total_targets ?? 0) > 1 &&
      pendingDamageClips.length > 1
    ) {
      // AoE parent arrived with multiple pending damage clips.
      // Parent clips (CastClip windup) play FIRST, then impacts in parallel.
      allGroups.push(...clips); // CastClip windup
      allGroups.push({ clips: [...pendingDamageClips] }); // Parallel damage hits
      pendingDamageClips.length = 0;
    } else {
      // Any other event (saving throws, conditions, single-target parents,
      // per-target spell completions): just add its clips, do NOT flush
      // pending damage. The pending buffer is only resolved by an AoE
      // parent marker or end-of-batch.
      allGroups.push(...clips);
    }
  }

  // End of batch: flush remaining damage clips sequentially
  // (either single-target hits, or an AoE whose parent wasn't in this batch)
  for (const clip of pendingDamageClips) {
    allGroups.push({ clips: [clip] });
  }

  return allGroups;
}
```

**Why this works:** The only two places that drain `pendingDamageClips` are (1) seeing an AoE parent with `total_targets > 1` (parallel) and (2) end-of-batch (sequential fallback). Intervening saving throws, condition applications, and per-target spell completions pass through without disturbing the buffer. Since the backend processes targets sequentially and the parent always completes last within a batch, the AoE parent marker reliably arrives after all per-target damage events.

**Known limitation — cross-batch AoE split:** If an AoE's child events land in poll batch N but the parent arrives in batch N+1 (due to network jitter or server load), the children flush sequentially at end-of-batch-N instead of being grouped as parallel. This is unlikely at 400ms polling with `limit=200` (a single AoE is typically < 20 events), but the visual result is minor — damage numbers appear one-by-one instead of simultaneously. Not worth added complexity to fix.

**Future extension — mass condition grouping:** The buffer currently only accumulates `take_damage` clips for parallel playback. If a future spell applies conditions to multiple targets simultaneously (mass Slow, mass Hold Person), the `condition_application` clips won't be grouped — they'll play sequentially. This is fine for now since condition badge animations are small visual accents. If you later add flashier condition VFX, extend the buffer pattern to also accumulate `condition_application` clips alongside damage clips.

#### Combat log vs raw events

**The `combat_log` field on Event has `exclude=True`** (line 246 of `dnd/core/events.py`) — it is NEVER present in `/events` API output (`model_dump()` excludes it).

For display-ready combat log text, use `ActionResult.combat_log_entries` which is already assembled with hierarchical `sub_entries` (the tree is already built server-side by `_collect_child_combat_logs()`).

Raw events from `/events` are for **AW state updates + animation clip generation** only. Combat log display is a separate concern served by `ActionResult.combat_log_entries`.

### H1c) Event type quick-reference table

Single lookup: event type → what the client does with it.

**Tier 1 — State-changing (client MUST handle):**

| event_type | Key fields read | AW mutation | Ph2 vis trigger? | Actions refresh? | Clip(s) |
|---|---|---|---|---|---|
| `turn_start` | entity_uuid, round_number, turn_index, actions/bonus/movement/reaction_available | encounter.current_entity_uuid, .current_turn_index, .round_number | Yes (force if is_my_turn) | Yes (if is_my_turn) | TurnBannerClip |
| `turn_end` | entity_uuid, actions/bonus/movement_used | None (informational) | No | No | None |
| `round_start` | round_number | encounter.round_number | No | No | None |
| `round_end` | round_number | None | No | No | None |
| `encounter_start` | encounter_uuid, initiative_order | encounter.state="active", initiative_order | No | No | None |
| `encounter_end` | encounter_uuid, reason | encounter.state="ended" → ENDED | No | No | None |
| `movement` | source_entity_uuid, start_position, end_position, path | entity.position = end_position | If mover is observer | No | MoveClip(path) |
| `forced_movement` | target_entity_uuid, start_position, end_position, cause | entity.position = end_position | If target is observer | No | ForcedMoveClip |
| `take_damage` | target_entity_uuid, total_damage, final_damage, damages | entity.hp -= (final_damage ?? total_damage) | No | No | HitFlashClip + DamageNumberClip |
| `heal` | target_entity_uuid, actual_healing | entity.hp = min(max_hp, hp + actual_healing) | No | No | DamageNumberClip("heal") |
| `death` | entity_uuid, entity_name, killer_name | entity.is_dead=true, hp=0 | Yes | No | DeathClip |
| `condition_application` | target_entity_uuid, condition.name, condition.condition_category | Add to entity.conditions | No | No | ConditionBadgeClip("apply") |
| `condition_removal` | target_entity_uuid, condition.name | Remove from entity.conditions | No | No | ConditionBadgeClip("remove") |

**Tier 2 — Parent/summary events (no AW mutation — children already applied):**

| event_type | Key fields read | AW mutation | Ph2 vis trigger? | Actions refresh? | Clip(s) |
|---|---|---|---|---|---|
| `attack` | source_entity_uuid, target_entity_uuid, attack_outcome, weapon_name | None (HP via child take_damage) | No | No | AttackWindupClip |
| `cast_spell` | source_entity_uuid, name, spell_school, aoe_position, total_targets | None (HP via child take_damage) | No | No | CastClip |

**Tier 3 — Spatial (visibility hints, Phase 2 optimization signals):**

| event_type | Key fields read | AW mutation | Ph2 vis trigger? | Actions refresh? | Clip(s) |
|---|---|---|---|---|---|
| `spatial_entity_entered` | position, entity_uuid, senses_hint | entity.position fallback | Yes | No | None |
| `spatial_entity_left` | position, entity_uuid, senses_hint | None | Yes | No | None |
| `spatial_tile_changed` | position, tile_walkable, senses_hint | tilesByKey update | Yes | No | None |
| `spatial_light_changed` | position, senses_hint | None | Yes | No | None |
| `spatial_perceivability_changed` | entity_uuid, senses_hint | None | Yes | No | None |
| `spatial_object_placed` | position, object_uuid, senses_hint | Add floorObject | Yes (if senses_hint.requires_fov) | No | None |
| `spatial_object_removed` | position, object_uuid, senses_hint | Remove floorObject | Yes (if senses_hint.requires_fov) | No | None |
| `spatial_object_changed` | position, object_uuid, senses_hint | None | Yes (if senses_hint.requires_fov) | No | None |

**Tier 4 — Skip (no AW mutation, no animation):**
- `step_movement` — parent `movement` covers the full path and final position
- `saving_throw`, `skill_check`, `base_action` — internal mechanics, parent events carry the outcome
- `inflict_damage` — source-side; `take_damage` on the target is what matters
- All `*_d20_roll*` and `*_roll_result` events — dice internals, not state-changing
- All equipment events: `weapon_equip`/`unequip`, `armor_equip`/`unequip`, `shield_equip`/`unequip` — state refresh handles these
- `movement_collision` — informational, no state change
- `trigger_event` — internal handler plumbing
- `ability_check` — covered by parent `skill_check`
- `enemy_spotted`, `enemy_killed`, `enemy_engaged` — combat log events, no AW mutation
- `dice_roll`, `dice_roll_result`, `damage_rolled` (deprecated) — internal

**Notes:**
1. **"Ph2 vis trigger?" column** is for Phase 2 optimization only — it tells you which events are worth checking `senses_hint` on. In Phase 1, visibility is refreshed after every non-empty event batch via K4b coalescing regardless of this column. The column becomes actionable only when you transition to Phase 2.
2. **`turn_start` visibility**: force-refresh (`maybeRefreshVisibility(force=true)`) only when `is_my_turn` flips true (your own turn start). For observed turn starts (not your entity), the normal batch-level coalescing in K4b is sufficient.
3. "Actions?" is almost always No — `ActionResult.available_actions` covers action updates inline during your turn. Only `turn_start` when `is_my_turn=true` triggers `GET /available-actions`.
4. `step_movement` reaches COMPLETION but the client ignores it — parent `movement` has the full path and final position.
5. For `take_damage`, prefer `final_damage` (post-resistance/vulnerability). Fallback to `total_damage` if `final_damage` is absent.
6. `attack`/`cast_spell` parent events carry `total_damage`/`total_targets` summaries. Don't apply damage from these — child `take_damage` events already did it.
7. `heal` events carry `actual_healing` (clamped to not exceed max HP). Apply as `entity.hp = min(max_hp, hp + actual_healing)`.

### H2) Complete event reducer catalog

Implement reducers for all event types that carry state changes. Organized by category:

#### H2a) Turn & Encounter Lifecycle

**TURN_START** (`TurnStartEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `entity_uuid` | string | Entity whose turn it is |
| `encounter_uuid` | string | |
| `round_number` | number | |
| `turn_index` | number | 0-indexed initiative position |
| `actions_available` | number | Action budget for this turn |
| `bonus_actions_available` | number | |
| `movement_available` | number | In feet |
| `reaction_available` | number | |

Reducer: update `encounter.current_entity_uuid`, `encounter.current_turn_index`, `encounter.round_number`. Useful for turn banner animation.

**TURN_END** (`TurnEndEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `entity_uuid` | string | |
| `encounter_uuid` | string | |
| `round_number` | number | |
| `turn_index` | number | |
| `actions_used` | number | How many actions were consumed |
| `bonus_actions_used` | number | |
| `movement_used` | number | Feet moved |

Reducer: optional — primarily useful for debug/stats display.

**ROUND_START / ROUND_END** (`RoundStartEvent` / `RoundEndEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `encounter_uuid` | string | |
| `round_number` | number | |

Reducer: update `encounter.round_number`.

**ENCOUNTER_START** (`EncounterStartEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `encounter_uuid` | string | |
| `combatant_uuids` | string[] | All combatant UUIDs |
| `initiative_order` | string[] | UUIDs in initiative order |

Reducer: update encounter state to "active", populate initiative order.

**ENCOUNTER_END** (`EncounterEndEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `encounter_uuid` | string | |
| `combatant_uuids` | string[] | |
| `reason` | string \| null | Why it ended |

Reducer: update encounter state to "ended".

#### H2b) Movement

**MOVEMENT** (`MovementEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `start_position` | [x, y] | Where entity was |
| `end_position` | [x, y] | Where entity ended up |
| `path` | [x, y][] \| null | Full waypoint path for animation |

Reducer: update entity position to `end_position`. Use `path` for MoveClip animation.

**FORCED_MOVEMENT** (`ForcedMovementEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `start_position` | [x, y] | |
| `end_position` | [x, y] | |
| `direction` | [dx, dy] | Push/pull direction vector |
| `intended_distance` | number | Feet intended |
| `actual_distance` | number | Feet actually moved (may be less if blocked) |
| `blocked_by_obstacle` | boolean | Hit a wall/entity |
| `blocked_by` | string \| null | What blocked movement |
| `cause` | string | e.g. "shove", "thunderwave" |

Reducer: update entity position to `end_position`. Use `direction` + `cause` for push/knockback animation clips.

**STEP_MOVEMENT** (`StepMovementEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `from_position` | [x, y] | |
| `to_position` | [x, y] | |
| `path_index` | number | Which step in the path |
| `total_path_length` | number | |
| `movement_cost` | number | Feet for this step |

Reducer: generally skip — `MOVEMENT` completion covers the final position. Useful for step-by-step animation if you want sub-move granularity.

#### H2c) Damage, Healing & Death

**TAKE_DAMAGE** (`TakeDamageEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `total_damage` | number | Pre-resistance damage |
| `final_damage` | number \| null | Post-resistance damage (if modified by handler) |
| `damages` | Damage[] | Per-type breakdown |
| `damage_rolls` | DiceRoll[] | Roll results |

Reducer: `effective = final_damage ?? total_damage`. Apply: `hp = max(0, hp - effective)`. **No `target_hp_after` field** — always use delta.

**HEAL** (`HealEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `total_healing` | number | Raw healing amount |
| `actual_healing` | number | After HP cap |
| `source_description` | string | e.g. "Cure Wounds" |
| `was_blocked` | boolean | If healing was prevented |
| `spell_level` | number | Level of healing spell |

Reducer: `hp = min(max_hp, hp + actual_healing)`.

**DEATH** (`DeathEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `entity_uuid` | string | Who died |
| `entity_name` | string | |
| `killer_uuid` | string \| null | |
| `killer_name` | string | |
| `final_hp` | number | HP at death (usually 0) |
| `encounter_uuid` | string \| null | |

Reducer: set `entity.is_dead = true`, `entity.hp = 0`. Mark dead in initiative order.

#### H2d) Conditions

**CONDITION_APPLICATION** (`ConditionApplicationEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `condition` | object | Full condition object (has `name`, `category`, etc.) |

Reducer: add condition name to `entity.conditions` and `entity.condition_details`. Key condition fields: `name`, `description`, `condition_category` (tag enum), `duration`, `source_entity_uuid`, `target_entity_uuid`.

**CONDITION_REMOVAL** (`ConditionRemovalEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `condition` | object | Full condition object |
| `expired` | boolean | Whether it expired naturally vs was dispelled |

Reducer: remove condition name from `entity.conditions` / `condition_details`.

In early MVP: store only names + categories. Show icons/badges in Pixi later.

#### H2e) Attack

**ATTACK** (`AttackEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `weapon_slot` | string | MELEE_MAIN, MELEE_OFF, RANGED_MAIN, RANGED_OFF |
| `weapon_name` | string \| null | Display name of weapon |
| `is_long_range` | boolean | Attacking at long range (disadvantage) |
| `is_threatened` | boolean | Attacker is in melee threat |
| `dice_roll` | DiceRoll \| null | The d20 roll |
| `attack_outcome` | string \| null | "HIT", "MISS", "CRIT", "CRIT_MISS" |
| `damages` | Damage[] \| null | Damage type list |
| `damage_rolls` | DiceRoll[] \| null | Damage dice results |
| `total_damage` | number | From ActionEvent parent |
| `total_targets` | number | From ActionEvent parent (>0 for multi-target) |

Reducer: attack events are informational for animation. The actual HP change comes from `TAKE_DAMAGE` (child event). Use `attack_outcome` for hit/miss/crit animation choice.

#### H2f) Spells

**CAST_SPELL** (`SpellEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `spell_level` | number | Base spell level |
| `cast_at_level` | number | Actual cast level (may be upcast) |
| `spell_school` | string | "evocation", "abjuration", etc. — use for VFX color |
| `verbal` | boolean | Has verbal component |
| `save_ability` | string \| null | Ability for save ("dexterity", etc.) |
| `save_dc` | number \| null | Save DC |
| `save_success` | boolean \| null | Whether target saved |
| `save_roll` | DiceRoll \| null | Save roll result |
| `save_bonus` | number \| null | Target's save bonus |
| `attack_outcome` | string \| null | For spell attacks |
| `dice_roll` | DiceRoll \| null | For spell attack rolls |
| `damages` | Damage[] \| null | |
| `damage_rolls` | DiceRoll[] \| null | |
| `total_damage` | number | From ActionEvent parent |
| `total_targets` | number | From ActionEvent parent |
| `aoe_position` | [x, y] \| null | Center of AoE (from ActionEvent parent) |

Reducer: like attacks, informational for animation. HP changes via `TAKE_DAMAGE`. Use `spell_school` for VFX color theming, `aoe_position` for AoE origin.

#### H2g) Spatial Events

All spatial events use `SpatialChangeEvent`:

| Field | Type | Notes |
|-------|------|-------|
| `change_type` | string | ENTITY_ENTERED, ENTITY_LEFT, TILE_CHANGED, etc. |
| `position` | [x, y] | Grid position |
| `entity_uuid` | string \| null | Entity involved (or tile UUID for LIGHT_CHANGED) |
| `object_uuid` | string \| null | Object involved |
| `old_position` | [x, y] \| null | Previous position |
| `tile_walkable` | boolean \| null | New walkable state |
| `tile_visible` | boolean \| null | New visible state |
| `senses_hint` | SensesUpdateHint \| null | Optimization hints (see H8) |

**Event types and their meanings:**

| event_type | change_type | Reducer action |
|------------|-------------|---------------|
| `SPATIAL_ENTITY_ENTERED` | ENTITY_ENTERED | Update entity position (entity_uuid at position) |
| `SPATIAL_ENTITY_LEFT` | ENTITY_LEFT | Old position info (old_position = new position) |
| `SPATIAL_TILE_CHANGED` | TILE_CHANGED | Update tile walkable/visible in tilesByKey |
| `SPATIAL_OBJECT_PLACED` | OBJECT_PLACED | Add floor object at position |
| `SPATIAL_OBJECT_REMOVED` | OBJECT_REMOVED | Remove floor object |
| `SPATIAL_LIGHT_CHANGED` | LIGHT_CHANGED | Phase 1: triggers visibility refresh |
| `SPATIAL_PERCEIVABILITY_CHANGED` | PERCEIVABILITY_CHANGED | Phase 1: triggers visibility refresh |
| `SPATIAL_OBJECT_CHANGED` | OBJECT_CHANGED | Phase 1: triggers visibility refresh if blocking changed |
| `MOVEMENT_COLLISION` | MOVEMENT_COLLISION | Informational (entity hit something) |

#### H2h) Other Event Types

**SAVING_THROW** (`SavingThrowEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `ability_name` | string | "strength", "dexterity", etc. |
| `dc` | number \| null | Difficulty class |
| `dice_roll` | DiceRoll \| null | Roll result |
| `result` | boolean \| null | Pass/fail |

Reducer: informational — use for combat log display.

**SKILL_CHECK** (`SkillCheckEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `skill_name` | string | "athletics", "stealth", etc. |
| `dc` | number \| null | |
| `dice_roll` | DiceRoll \| null | |
| `result` | boolean \| null | |

Reducer: informational.

**BASE_ACTION** (`ActionEvent`)

| Field | Type | Notes |
|-------|------|-------|
| `costs` | Cost[] | Action economy costs |
| `description` | string | |
| `total_targets` | number | |
| `total_damage` | number | |
| `aoe_position` | [x, y] \| null | |

Reducer: catch-all for non-attack, non-spell actions (Dash, Dodge, Disengage, etc.). Informational.

**Equipment events**: `WEAPON_EQUIP`, `WEAPON_UNEQUIP`, `ARMOR_EQUIP`, `ARMOR_UNEQUIP`, `SHIELD_EQUIP`, `SHIELD_UNEQUIP` — all carry `slot` and the equipped/unequipped item object. Reducer: update entity display if you show equipment visually.

**Dice events**: `D20_ROLL_RESULT`, `ATTACK_D20_ROLL_RESULT`, `SAVE_D20_ROLL_RESULT`, `CHECK_D20_ROLL_RESULT`, `DAMAGE_ROLL_RESULT`, `HEAL_ROLL_RESULT` — roll detail events. Reducer: skip for AW purposes; useful for detailed combat log display.

### H3) Position updates: pick a precedence rule

You may receive:

* MovementEvent completion with end_position
* Spatial entered/left events for each step

**Choose a precedence and stick to it**, otherwise you'll oscillate.

Recommended:

1. If `MOVEMENT` event with `end_position` → update entity position.
2. If `FORCED_MOVEMENT` event with `end_position` → update entity position.
3. If `SPATIAL_ENTITY_ENTERED` → update entity position (fine-grained fallback).
4. Otherwise do nothing.

### H4) HP updates: effective damage

TakeDamageEvent has:

* total_damage (pre-resistance)
* final_damage (post-resistance, may be null)

Use:
* `effective = final_damage ?? total_damage`
* `hp = max(0, hp - effective)`

HealEvent has:

* actual_healing (already capped at max_hp on server)

Apply:
* `hp = min(max_hp, hp + actual_healing)`

DeathEvent:

* set `is_dead=true`
* set `hp=0`

### H5) Condition updates

ConditionApplicationEvent:

* add condition name + category to entity

ConditionRemovalEvent:

* remove condition name from entity

In early MVP:

* store only names + categories
* show icons/badges in Pixi later
* fetch full details only when you build character sheets

### H6) Turn/encounter updates

On TurnStart completion:

* update encounter current entity UUID / turn index / round number if present
* DO NOT use this to decide "is my turn" for the session. Use ping.
* But you can use it to animate a turn banner or focus camera.

When ping flips to your turn:

* fetch available actions
* **Phase 1**: refresh visibility

### H7) Visibility refresh triggers (phased approach)

**Phase 1 — Aggressive sync (correct by default):**

Refresh `/visibility` after **every non-empty event batch**. This is the simplest, most correct approach. Track the cost in `perfMetrics.visibilityFetchMs`.

```ts
// In events poller, after processing batch:
if (events.length > 0) {
  const t0 = performance.now();
  await refreshVisibility(observer_uuid);
  perfMetrics.visibilityFetchMs.push(performance.now() - t0);
  perfMetrics.syncTriggersThisMinute++;
}
```

**Phase 2 — Measured optimization:**

Once `perfMetrics` shows actual visibility fetch cost, use event types + `SensesUpdateHint` to decide when to skip. The optimization signals are documented in H8.

Start Phase 2 optimization when:
- `visibilityFetchMs` average > 50ms
- OR visibility fetches > 10/min
- AND `awDriftCount` has been 0 for 5+ minutes

### H8) SensesUpdateHint field reference (Phase 2 optimization signals)

`SensesUpdateHint` is carried on `SpatialChangeEvent.senses_hint`. It tells you exactly what changed:

```ts
type SensesUpdateHint = {
  requires_fov: boolean;        // Vision geometry changed (walls, magical darkness, doors)
  requires_paths: boolean;      // Path topology changed (entity moved, walkability changed)

  entity_entered: [Uuid, Pos] | null;    // O(1) entity appeared at position
  entity_left: [Uuid, Pos] | null;       // O(1) entity left position
  entity_died: [Uuid, Pos] | null;       // Entity removed from position

  light_changed_positions: Pos[] | null; // Positions where light level changed
  perceivability_entity: Uuid | null;    // One entity's perceivability changed

  object_placed: [Uuid, Pos] | null;     // Floor object appeared
  object_removed: [Uuid, Pos] | null;    // Floor object removed
};
```

**Phase 2 optimization rules (apply only after Phase 1 data justifies it):**

| Hint field | Visibility impact | Can skip `/visibility`? |
|-----------|-------------------|------------------------|
| `requires_fov = true` | Vision geometry changed | **No** — must refresh |
| `light_changed_positions` non-null | Light changed, may reveal/hide tiles | **No** — must refresh |
| `perceivability_entity` non-null | Hidden/invisible toggle | **No** — must refresh |
| `entity_entered` / `entity_left` only | Entity moved, no vision change | **Yes** — update position only |
| `object_placed` / `object_removed` only | Floor item change | **Yes** — update objects only |
| `requires_paths = true` only | Movement routes changed | **Yes** — no visibility impact |
| All fields null/false | Nothing interesting | **Yes** — skip entirely |

---

## Part I — Animation System (Events → Clips → Presentation)

### I1) Why clips exist

Events are instantaneous facts. Animations are time-based.

So each relevant event produces 0..N **AnimationClips**.

A clip:

* knows which entity(ies) it affects
* starts at time t0
* advances with dt
* ends deterministically

### I2) Minimal clip interface

```ts
interface AnimationClip {
  readonly name: string;
  readonly estimatedMs: number;
  start(): void;
  update(dtMs: number): void;
  isDone(): boolean;
}
```

### I3) EventDirector: FIFO playback with clip groups

EventDirector holds:

* `clipQueue: ClipGroup[]` — groups play sequentially
* `activeGroup: ClipGroup | null` — clips within a group play in parallel

```ts
type ClipGroup = {
  clips: AnimationClip[];        // All clips in this group run simultaneously
  allStarted: boolean;
};

class EventDirector {
  private queue: ClipGroup[] = [];
  private active: ClipGroup | null = null;

  enqueue(group: ClipGroup) {
    this.queue.push(group);
  }

  update(dtMs: number) {
    const dt = dtMs * globalAnimSpeed;

    if (!this.active && this.queue.length > 0) {
      this.active = this.queue.shift()!;
      this.active.clips.forEach(c => c.start());
    }

    if (this.active) {
      this.active.clips.forEach(c => c.update(dt));
      if (this.active.clips.every(c => c.isDone())) {
        this.active = null;
        // Immediately try next group this frame
      }
    }
  }

  get queuedCount(): number {
    return this.queue.length + (this.active ? 1 : 0);
  }

  flush() {
    this.queue = [];
    this.active = null;
  }
}
```

**Sequential between groups, parallel within a group.** This handles AoE naturally: a Fireball produces one group with 3 DamageNumberClips that play simultaneously.

**Event burst handling:** During AI turns, the poller may deliver 10-20 events in one batch. Each produces clip groups that enqueue. The queue grows; PW falls behind AW. This is expected — global speed is the only knob. Optionally add auto-speed:

```ts
// Optional: auto-speed when queue is large
const queueLen = director.queuedCount;
const effectiveSpeed = queueLen > 20 ? 4.0
                     : queueLen > 10 ? 2.0
                     : globalAnimSpeed;
```

### I3b) Event → Clip mapping

The `buildClips(event)` function maps each event type to clip groups:

```ts
function buildClips(event: ServerEvent): ClipGroup[] {
  switch (event.event_type) {
    case "movement":
      return [{ clips: [new MoveClip(event.source_entity_uuid, event.path ?? [event.start_position, event.end_position])] }];

    case "forced_movement":
      return [{ clips: [new ForcedMoveClip(event.target_entity_uuid, event.start_position, event.end_position, event.cause)] }];

    case "attack":
      const attackClips: ClipGroup[] = [];
      // Windup clip for attacker
      attackClips.push({ clips: [new AttackWindupClip(event.source_entity_uuid, event.target_entity_uuid, event.attack_outcome)] });
      // Damage/miss reaction handled by child TAKE_DAMAGE event
      return attackClips;

    case "cast_spell":
      return [{ clips: [new CastClip(event.source_entity_uuid, event.name, event.spell_school, event.aoe_position)] }];

    case "take_damage": {
      const effective = event.final_damage ?? event.total_damage;
      if (effective > 0) {
        return [{ clips: [
          new HitFlashClip(event.target_entity_uuid),
          new DamageNumberClip(event.target_entity_uuid, effective, "damage"),
        ] }];
      }
      return [];
    }

    case "heal":
      if (event.actual_healing > 0) {
        return [{ clips: [new DamageNumberClip(event.target_entity_uuid, event.actual_healing, "heal")] }];
      }
      return [];

    case "death":
      return [{ clips: [new DeathClip(event.entity_uuid)] }];

    case "condition_application":
      return [{ clips: [new ConditionBadgeClip(event.target_entity_uuid, event.condition.name, "apply")] }];

    case "condition_removal":
      return [{ clips: [new ConditionBadgeClip(event.target_entity_uuid, event.condition.name, "remove")] }];

    case "turn_start":
      return [{ clips: [new TurnBannerClip(event.source_entity_name ?? "Unknown", event.round_number)] }];

    // No visual clips for these:
    // saving_throw, skill_check, base_action, spatial_*, equipment_*,
    // dice_roll_*, turn_end, round_*, encounter_*
    default:
      return [];
  }
}
```

**AoE multi-target grouping**: In the COMPLETION stream, children arrive BEFORE parents (see H1b). Multiple TAKE_DAMAGE events from an AoE spell appear consecutively, followed by the parent CAST_SPELL event with `total_targets > 1`. Use `processEventBatch()` (defined in H1b) to detect this pattern and group damage clips for parallel playback.

Replace the old per-event enqueue pattern:
```ts
// OLD (wrong — doesn't group AoE):
// events.forEach(e => director.enqueue(...buildClips(e)));

// NEW — use processEventBatch for correct AoE grouping:
const groups = processEventBatch(events);
groups.forEach(g => director.enqueue(g));
```

### I4) Global speed multiplier

* `globalAnimSpeed` float (default 1.0)
* scale dt by it in EventDirector.update()
* Debug overlay shows current speed and queue depth

Add dev controls later to modify it live (buttons in debug overlay).

### I5) Movement clips

**MoveClip:**

```ts
class MoveClip implements AnimationClip {
  name = "move";
  estimatedMs: number;
  private entityUuid: Uuid;
  private path: Pos[];
  private msPerStep = 120;
  private elapsed = 0;
  private done = false;

  constructor(entityUuid: Uuid, path: Pos[]) {
    this.entityUuid = entityUuid;
    this.path = path;
    this.estimatedMs = (path.length - 1) * this.msPerStep;
  }

  start() { /* set entity anim to "walk" */ }

  update(dtMs: number) {
    this.elapsed += dtMs;
    const totalMs = this.estimatedMs;
    const t = Math.min(this.elapsed / totalMs, 1.0);

    // Find current segment
    const segFloat = t * (this.path.length - 1);
    const segIdx = Math.min(Math.floor(segFloat), this.path.length - 2);
    const segT = segFloat - segIdx;

    // Interpolate position
    const from = this.path[segIdx];
    const to = this.path[segIdx + 1];
    const visual = presentationStore.entityVisualsById[this.entityUuid];
    if (visual) {
      visual.worldX = from[0] + (to[0] - from[0]) * segT;
      visual.worldY = from[1] + (to[1] - from[1]) * segT;
      visual.facing = computeFacing(from, to);
    }

    if (t >= 1.0) {
      this.done = true;
      if (visual) visual.anim = "idle";
    }
  }

  isDone() { return this.done; }
}
```

**ForcedMoveClip:**

* Same interpolation logic but faster (80ms per cell)
* No "walk" anim — use "knockback" or "slide" if available
* `cause` can drive different visual effects (shove vs thunderwave vs gust)

### I6) Attack / spell clips (MVP)

**AttackWindupClip:**

* Duration: 300ms
* Set attacker anim to "attack", facing toward target
* At completion, set anim back to "idle"

**CastClip:**

* Duration: 400ms
* Set caster anim to "cast"
* Use `spell_school` for VFX color theming:
  * evocation = orange/red
  * necromancy = green/purple
  * abjuration = blue
  * enchantment = pink
  * conjuration = yellow
  * illusion = silver
  * transmutation = amber
  * divination = white
* If `aoe_position` present → spawn colored circle at position during cast

**HitFlashClip:**

* Duration: 150ms
* Tint entity sprite red briefly, then reset
* Runs in parallel with DamageNumberClip

**DamageNumberClip:**

* Duration: 800ms
* Spawn a `Text` in vfxLayer at entity position (v8 constructor):
  ```ts
  const text = new Text({
    text: `${amount}`,
    style: { fontSize: 18, fill: type === "damage" ? 0xff4444 : 0x44ff44, fontFamily: "monospace" },
  });
  ```
* Animate: float upward (y -= 30px over duration), fade alpha 1.0→0.0
* Destroy text on completion

### I7) Parallel clips and AoE

When an AoE spell (e.g., Fireball) hits 3 targets, the COMPLETION stream delivers children **before** the parent (see H1b):

1. `SAVING_THROW` target A COMPLETION → (no visual clip)
2. `TAKE_DAMAGE` target A COMPLETION → HitFlashClip + DamageNumberClip
3. `SAVING_THROW` target B COMPLETION → (no visual clip)
4. `TAKE_DAMAGE` target B COMPLETION → HitFlashClip + DamageNumberClip
5. `SAVING_THROW` target C COMPLETION → (no visual clip)
6. `TAKE_DAMAGE` target C COMPLETION → HitFlashClip + DamageNumberClip
7. `CAST_SPELL` COMPLETION (total_targets=3) → CastClip (parent arrives **last**)

The `processEventBatch()` function (H1b) accumulates damage clips from events 2/4/6. When it encounters the parent CAST_SPELL at event 7 with `total_targets > 1`, it groups all pending damage clips into **one parallel ClipGroup** so all three damage animations play simultaneously. The CastClip plays sequentially before the grouped damage.

### I8) Clip cancellation and queue flush

**On resync** (Part G): `director.flush()` clears the entire queue, then snap all PW entity visuals to AW positions/HP. This is the "hard reset" — visual correctness is restored instantly at the cost of losing in-progress animations.

**Auto-flush threshold**: If `director.queuedCount > 50`, the PW is hopelessly behind. Auto-flush and snap. This prevents runaway queue growth during long AI turns or reconnection replays.

```ts
if (director.queuedCount > 50) {
  director.flush();
  snapPWtoAW();
  console.warn("Animation queue overflow — snapped PW to AW");
}
```

### I9) Condition, death, and turn clips

**ConditionBadgeClip:**

* Duration: 600ms
* Spawn a small text label above entity (v8 constructor):
  ```ts
  const badge = new Text({
    text: `${mode === "apply" ? "+" : "-"}${condName}`,
    style: { fontSize: 12, fill: mode === "apply" ? 0xffcc00 : 0x999999, fontFamily: "monospace" },
  });
  ```
* Float upward and fade, similar to DamageNumberClip but smaller

**DeathClip:**

* Duration: 1000ms
* Tint entity sprite to gray over 500ms
* Scale y to 0.3 (collapse) over remaining 500ms
* At completion, set `visibleToObserver = false`

**TurnBannerClip:**

* Duration: 1200ms
* Show text banner at top-center of screen (v8 constructor):
  ```ts
  const banner = new Text({
    text: `Round ${roundNum} — ${entityName}'s Turn`,
    style: { fontSize: 24, fill: 0xffffff, fontFamily: "monospace" },
  });
  banner.anchor.set(0.5, 0.5);
  ```
* Fade in 200ms, hold 800ms, fade out 200ms
* This is a screen-space element (added to app.stage, not viewport)

---

## Part J — Isometric Rendering (Pixi) — Concrete Choices

### J1) Coordinate system: grid-world

Represent entity visual positions in grid coordinates (float):

* `worldX`, `worldY` (float)

**Forward transform** — grid → iso screen pixels:

```ts
const TILE_W = 64; // iso tile width in pixels
const TILE_H = 32; // iso tile height in pixels

function toIso(worldX: number, worldY: number): { sx: number; sy: number } {
  return {
    sx: (worldX - worldY) * (TILE_W / 2),
    sy: (worldX + worldY) * (TILE_H / 2),
  };
}
```

**Reverse transform** — iso screen pixels → grid (for mouse picking):

```ts
function fromIso(sx: number, sy: number): { worldX: number; worldY: number } {
  return {
    worldX: (sx / (TILE_W / 2) + sy / (TILE_H / 2)) / 2,
    worldY: (sy / (TILE_H / 2) - sx / (TILE_W / 2)) / 2,
  };
}

// For tile selection, round to nearest integer:
function screenToTile(sx: number, sy: number): Pos {
  const { worldX, worldY } = fromIso(sx, sy);
  return [Math.round(worldX), Math.round(worldY)];
}
```

**Canonical pointer→tile helper** — use this everywhere (J7 mouse picking, M5 movement, M7 AoE, M6 entity targeting). Never call `viewport.toLocal()` + `screenToTile()` separately in application code:

```ts
function pointerEventToTile(e: FederatedPointerEvent, viewport: Viewport): Pos {
  const local = viewport.toLocal(e.global);
  return screenToTile(local.x, local.y);
}
```

### J2) Layers

Use a `Viewport` (from pixi-viewport) as the root world container. See Part L for full setup.

```ts
import { Viewport } from "pixi-viewport";

// Viewport replaces the old plain Container — provides drag, zoom, follow, etc.
// Full configuration in Part L. Minimal creation shown here:
const viewport = new Viewport({
  screenWidth: app.screen.width,
  screenHeight: app.screen.height,
  worldWidth: 4000,
  worldHeight: 4000,
  events: app.renderer.events,  // REQUIRED for PixiJS v8
});
app.stage.addChild(viewport);

const tilesLayer = new Container();      // Tile sprites (floor, walls, water)
const fogLayer = new Container();        // Fog-of-war overlay
const highlightLayer = new Container();  // Targeting highlights (movement, AoE)
const entitiesLayer = new Container();   // Entity sprites + HP bars
const vfxLayer = new Container();        // Floating damage numbers, spell effects
const debugLayer = new Container();      // Debug info (tile coords, grid lines)

viewport.addChild(tilesLayer, fogLayer, highlightLayer, entitiesLayer, vfxLayer, debugLayer);
```

Layer order matters: tiles → fog → highlights → entities → vfx → debug. Each layer renders on top of the previous.

### J3) Z-sorting

For iso, entities at higher `(x+y)` values are "closer" to the camera and should render on top:

```ts
entitiesLayer.sortableChildren = true;

// Each frame (or when entity positions change):
for (const [uuid, visual] of Object.entries(entityVisualsById)) {
  const container = entityContainers.get(uuid);
  if (container) {
    container.zIndex = visual.worldX + visual.worldY;
  }
}
```

Tiles don't need z-sorting if you add them in row-major order (top-left to bottom-right in iso space).

### J4) Tile rendering

**MVP approach** — procedural `Graphics` diamonds:

```ts
function createTileDiamond(tileAuth: TileAuth): Graphics {
  const g = new Graphics();
  const color = tileAuth.name === "Wall" ? 0x8B4513
              : tileAuth.name === "Water" ? 0x1E90FF
              : 0x3a3a3a; // Floor

  g.poly([
    { x: 0, y: -TILE_H / 2 },       // top
    { x: TILE_W / 2, y: 0 },         // right
    { x: 0, y: TILE_H / 2 },         // bottom
    { x: -TILE_W / 2, y: 0 },        // left
  ]);
  g.fill(color);
  g.stroke({ width: 1, color: 0x555555 });

  const { sx, sy } = toIso(tileAuth.x, tileAuth.y);
  g.position.set(sx, sy);
  return g;
}
```

Store tiles in a `Map<TileKey, Graphics>` for O(1) lookup when updating fog, conditions, or highlights.

**Later**: swap `Graphics` for `Sprite` from a tileset spritesheet. The position logic stays identical.

### J5) Entity sprites

**MVP approach** — colored circle with name label:

```ts
function createEntityContainer(entity: EntityAuth): Container {
  const container = new Container();

  // Body circle
  const body = new Graphics();
  const color = entity.is_dead ? 0x666666
              : entity.faction === "heroes" ? 0x22cc22
              : 0xcc2222;
  body.circle(0, 0, 12);
  body.fill(color);
  container.addChild(body);

  // Name label
  const label = new Text({ text: entity.name, style: {
    fontSize: 10, fill: 0xffffff, fontFamily: "monospace",
  }});
  label.anchor.set(0.5, 0);
  label.position.set(0, -20);
  container.addChild(label);

  // Position in iso space
  const { sx, sy } = toIso(entity.position[0], entity.position[1]);
  container.position.set(sx, sy);

  return container;
}
```

**Later**: replace the circle with `AnimatedSprite`. Spritesheet structure per entity type: 8 directions × N animations (idle, walk, attack, cast, hit, death). Create `AnimatedSprite` from texture array, switch textures based on `EntityVisual.facing` + `EntityVisual.anim`.

**Entity lifecycle management:**

| Event | Container action |
|-------|-----------------|
| Entity appears in `/state` bootstrap | `createEntityContainer()`, add to `entityContainers` map and `entityLayer` |
| Unknown UUID in event (reducer sees new entity) | Trigger RESYNCING (will create container during resync) |
| `death` event | Play DeathClip (fade out). After clip finishes: `container.visible = false`. Do NOT destroy — the entity stays in initiative order and may be referenced by future events. |
| Resync | Diff `entitiesById` against `entityContainers`. Create missing, hide dead, reposition mismatched. Never destroy during encounter. |
| Encounter ends | Safe to `container.destroy()` all and clear the map |

**Rule:** Never `destroy()` entity containers mid-encounter. Dead entities keep their container (invisible) for potential future references (raise dead, combat log lookups, initiative display). Memory cost is negligible for encounter-sized entity counts (< 50).

### J6) Entity info overlay

Each entity Container holds child elements for gameplay info:

```ts
function addInfoOverlay(container: Container, entity: EntityAuth): void {
  // HP bar background
  const hpBg = new Graphics();
  hpBg.rect(-16, -28, 32, 4);
  hpBg.fill(0x333333);
  container.addChild(hpBg);

  // HP bar fill (width proportional to hp/max_hp)
  const hpFill = new Graphics();
  const hpRatio = entity.hp / entity.max_hp;
  const hpColor = hpRatio > 0.5 ? 0x22cc22 : hpRatio > 0.25 ? 0xcccc22 : 0xcc2222;
  hpFill.rect(-16, -28, 32 * hpRatio, 4);
  hpFill.fill(hpColor);
  container.addChild(hpFill);

  // Condition dots (small colored circles above HP bar)
  entity.conditions.forEach((cond, i) => {
    const dot = new Graphics();
    dot.circle(-14 + i * 8, -34, 3);
    dot.fill(conditionColor(cond)); // Map condition names to colors
    container.addChild(dot);
  });
}
```

Update HP bar and condition dots whenever `EntityAuth` changes in the reducer. Cheapest approach: rebuild the overlay children on each AW update for that entity.

### J7) Mouse picking

Convert screen pointer position to world tile and find entities:

```ts
app.stage.eventMode = "static";
app.stage.hitArea = app.screen;

app.stage.on("pointerdown", (e: FederatedPointerEvent) => {
  // 1. Convert pointer to grid tile (canonical helper from J1)
  const [tileX, tileY] = pointerEventToTile(e, viewport);

  // 2. Check for entity at this tile
  const entity = Object.values(authStore.entitiesById)
    .find(e => e.position[0] === tileX && e.position[1] === tileY && !e.is_dead);

  if (entity) {
    uiStore.selectedEntity = entity.uuid;
  } else {
    uiStore.selectedTile = tileKey(tileX, tileY);
  }
});
```

For multiple entities on the same tile: sort by z-index (highest first) and pick the topmost.

### J8) Asset loading strategy

**MVP (Milestone 1-5):** Procedural `Graphics` only — no external assets. This eliminates all asset pipeline complexity during core architecture work.

**Production:** Define a spritesheet JSON manifest per entity type:

```ts
// Later: load spritesheets
const sheet = await Assets.load("assets/skeleton.json");
const walkFrames = [
  sheet.textures["skeleton_walk_SE_0"],
  sheet.textures["skeleton_walk_SE_1"],
  sheet.textures["skeleton_walk_SE_2"],
];
const animSprite = new AnimatedSprite(walkFrames);
animSprite.animationSpeed = 0.15;
animSprite.play();
```

Structure: `{entity_type}_{anim}_{facing}_{frame}`. 8 facings × 4-6 animations × 4-8 frames each. Use `TexturePacker` or similar to generate the JSON+PNG atlas.

---

## Part K — Fog-of-war Rendering (Never-seen vs Seen vs Visible)

### K1) Definitions

For the observer:

* never-seen: tile not in `seenCells`
* seen-not-visible: in `seenCells` but not in `visibleCells`
* visible: in `visibleCells`

### K2) Source of truth

Use `/visibility`. Do not compute FOV client-side.

### K3) Implementation approach — Mesh-based fogLayer

Use a **single `Mesh`** with per-vertex alpha for the entire fog layer. This renders all tiles in one draw call regardless of grid size (vs 2500 separate `Graphics` objects for a 50×50 grid).

**Geometry construction** — built once at bootstrap, alpha buffer updated on visibility changes:

```ts
// Index mapping: TileKey → offset into the alpha buffer (4 vertices per tile)
const fogTileOffsets = new Map<TileKey, number>();
let fogAlphaBuffer: Float32Array;
let fogMesh: Mesh;

function buildFogMesh(tilesByKey: Record<TileKey, TileAuth>, visionState: VisionState): Mesh {
  const numTiles = Object.keys(tilesByKey).length;

  // 4 vertices per tile (diamond corners), 2 coords each
  const positions = new Float32Array(numTiles * 4 * 2);
  // UVs required by MeshGeometry but unused (solid color)
  const uvs = new Float32Array(numTiles * 4 * 2);
  // 2 triangles per tile, 3 indices each
  const indices = new Uint32Array(numTiles * 6);
  // Per-vertex alpha: 4 floats per tile (all 4 corners share the same alpha)
  fogAlphaBuffer = new Float32Array(numTiles * 4);

  let pi = 0, ui = 0, ii = 0, ai = 0, tileIdx = 0;

  for (const [key, tile] of Object.entries(tilesByKey)) {
    const { sx, sy } = toIso(tile.x, tile.y);
    const base = tileIdx * 4;

    // Diamond vertices: top, right, bottom, left
    positions[pi++] = sx;              positions[pi++] = sy - TILE_H / 2;
    positions[pi++] = sx + TILE_W / 2; positions[pi++] = sy;
    positions[pi++] = sx;              positions[pi++] = sy + TILE_H / 2;
    positions[pi++] = sx - TILE_W / 2; positions[pi++] = sy;

    // UVs (unused, fill with 0)
    uvs[ui++] = 0; uvs[ui++] = 0;
    uvs[ui++] = 1; uvs[ui++] = 0;
    uvs[ui++] = 1; uvs[ui++] = 1;
    uvs[ui++] = 0; uvs[ui++] = 1;

    // Two triangles: top-right-bottom, top-bottom-left
    indices[ii++] = base;     indices[ii++] = base + 1; indices[ii++] = base + 2;
    indices[ii++] = base;     indices[ii++] = base + 2; indices[ii++] = base + 3;

    // Initial alpha from vision state
    const tk = key as TileKey;
    const alpha = visionState.visibleCells.has(tk) ? 0.0
                : visionState.seenCells.has(tk)    ? 0.6
                : 1.0;
    fogAlphaBuffer[ai++] = alpha;
    fogAlphaBuffer[ai++] = alpha;
    fogAlphaBuffer[ai++] = alpha;
    fogAlphaBuffer[ai++] = alpha;

    fogTileOffsets.set(tk, tileIdx * 4);
    tileIdx++;
  }

  const geometry = new MeshGeometry({ positions, uvs, indices });
  // Attach alpha as a custom attribute — shader reads this
  geometry.addAttribute("aAlpha", { buffer: fogAlphaBuffer, size: 1 });

  fogMesh = new Mesh({ geometry, shader: fogShader });
  fogLayer.addChild(fogMesh);
  return fogMesh;
}
```

**Fog shader** — renders black with per-vertex alpha:

```ts
const fogShader = Shader.from({
  vertex: `
    in vec2 aPosition;
    in float aAlpha;
    out float vAlpha;

    uniform mat3 uProjectionMatrix;
    uniform mat3 uWorldTransformMatrix;

    void main() {
      gl_Position = vec4((uProjectionMatrix * uWorldTransformMatrix * vec3(aPosition, 1.0)).xy, 0.0, 1.0);
      vAlpha = aAlpha;
    }
  `,
  fragment: `
    in float vAlpha;

    void main() {
      gl_FragColor = vec4(0.0, 0.0, 0.0, vAlpha);
    }
  `,
});
```

**Shader compatibility caveat:** The GLSL above uses `gl_FragColor` (GLSL ES 1.0). PixiJS v8 defaults to WebGPU (WGSL) with WebGL2 fallback, and its shader system may not accept raw GLSL via `Shader.from()`. Test this early in Milestone 6. If it doesn't work, options in order of preference: (1) use `GlProgram` explicitly for the WebGL2 path, (2) use `MeshMaterial` with a custom fragment via Pixi's shader abstraction, (3) fall back to per-tile `Graphics` behind a `RenderTexture` (one draw call via caching). The buffer-based alpha update architecture (K5) is correct regardless of which shader path works.

**Why mesh:** A 50×50 grid is 2500 tiles = 10000 vertices in one draw call. With separate `Graphics` objects, that's 2500 draw calls. The mesh approach is O(1) GPU cost regardless of grid size, and visibility updates are O(changed tiles) buffer writes (see K5).

**Entity visibility filtering:**

```ts
function updateEntityVisibility(visionState: VisionState) {
  for (const [uuid, container] of entityContainers) {
    container.visible = visionState.visibleEntities.has(uuid);
    // Later: show "last known" silhouette at remembered position for seen-but-not-visible
  }
}
```

### K4) When to refresh (phased approach)

**Phase 1 — Always correct:**

* Bootstrap
* After every non-empty event batch (see F2 step 5)
* After your own movement completion
* After every ActionResult

This is aggressive but guarantees correctness. Track cost via `perfMetrics.visibilityFetchMs`.

#### K4b) Visibility coalescing (even in Phase 1)

Even in Phase 1, "after every non-empty batch" can cause redundant calls during AI burst turns (multiple batches within milliseconds). Apply coalescing:

**Rules:**
1. Max 1 `/visibility` call per 200ms
2. If an event batch arrives within 200ms of the last visibility fetch → set `visionDirty = true` instead of fetching
3. At the start of each events poll cycle: if `visionDirty` → fetch and clear
4. **Immediate exceptions (bypass coalescing):** own movement completion, turn start (`is_my_turn` flips), resync
5. Timer fallback: if no poll within 500ms of `visionDirty` being set → `setTimeout` forces fetch

**Implementation:**
```ts
let visionDirty = false;
let lastVisibilityFetchAtMs = 0;
const VISIBILITY_COALESCE_MS = 200;

async function maybeRefreshVisibility(force: boolean = false) {
  const now = Date.now();
  if (force || (now - lastVisibilityFetchAtMs >= VISIBILITY_COALESCE_MS)) {
    await refreshVisibility(visionStore.observer_uuid);
    lastVisibilityFetchAtMs = Date.now();
    visionDirty = false;
  } else {
    visionDirty = true;
    // Fallback: force fetch if no poll clears the flag within 500ms
    setTimeout(() => {
      if (visionDirty) maybeRefreshVisibility(true);
    }, 500);
  }
}
```

**Usage points:**
- In events poller: drain `visionDirty` at the top of each poll cycle, then call `maybeRefreshVisibility()` after processing a non-empty batch
- Immediate (`force: true`) after own movement ActionResult
- Immediate (`force: true`) after turn start detection (`is_my_turn` flips to true)
- Immediate (`force: true`) during resync

**Rationale:** At 400ms poll interval, cuts `/visibility` calls ~50% during AI burst turns. Max 200ms stale fog is imperceptible when observing another entity's turn.

**Phase 2 — Measured optimization:**

* Bootstrap
* When `SensesUpdateHint` signals vision changes (see H8)
* After your turn starts
* After your own movement completion

Only transition to Phase 2 when Performance Monitor data shows visibility fetches are a measurable cost.

### K5) Efficient fog update (diff-based buffer writes)

When `/visibility` returns new data, diff the old and new sets and write only changed alphas into the mesh buffer:

```ts
function updateFog(oldVision: VisionState, newVision: VisionState) {
  let dirty = false;

  // Helper: set alpha for all 4 vertices of a tile
  function setTileAlpha(tk: TileKey, alpha: number) {
    const offset = fogTileOffsets.get(tk);
    if (offset === undefined) return;
    fogAlphaBuffer[offset]     = alpha;
    fogAlphaBuffer[offset + 1] = alpha;
    fogAlphaBuffer[offset + 2] = alpha;
    fogAlphaBuffer[offset + 3] = alpha;
    dirty = true;
  }

  // Tiles that became visible (fog clears)
  for (const tk of newVision.visibleCells) {
    if (!oldVision.visibleCells.has(tk)) {
      setTileAlpha(tk, 0.0);
    }
  }

  // Tiles that lost visibility (fog returns)
  for (const tk of oldVision.visibleCells) {
    if (!newVision.visibleCells.has(tk)) {
      setTileAlpha(tk, newVision.seenCells.has(tk) ? 0.6 : 1.0);
    }
  }

  // Tiles seen for the first time (1.0 → 0.6)
  for (const tk of newVision.seenCells) {
    if (!oldVision.seenCells.has(tk) && !newVision.visibleCells.has(tk)) {
      setTileAlpha(tk, 0.6);
    }
  }

  // Upload changed buffer to GPU (single call, only if anything changed)
  if (dirty) {
    fogMesh.geometry.getBuffer("aAlpha").update();
  }

  // Update entity visibility
  updateEntityVisibility(newVision);
}
```

This touches only changed tiles — O(changed) buffer writes + one GPU buffer upload. No scene graph manipulation, no object creation/destruction.

---

## Part L — Camera Controls (pixi-viewport + BG3-style)

### L1) Dependencies

```bash
npm i pixi-viewport  # v6 — compatible with PixiJS v8
```

pixi-viewport v6 provides: drag, pinch, wheel zoom, decelerate, edge scroll (mouseEdges), follow, clamp, clampZoom — all as composable plugins. No manual transform math needed.

### L2) Viewport setup

Replace the manual `worldContainer` from Part J with a `Viewport`:

```ts
import { Viewport } from "pixi-viewport";

// Create viewport INSTEAD of plain Container for worldContainer
const viewport = new Viewport({
  screenWidth: app.screen.width,
  screenHeight: app.screen.height,
  worldWidth: 4000,   // Will be updated from gridBounds
  worldHeight: 4000,
  events: app.renderer.events,  // REQUIRED for PixiJS v8 — passes the EventSystem
});

app.stage.addChild(viewport);

// Add all world layers to viewport (replaces worldContainer.addChild)
viewport.addChild(tilesLayer, fogLayer, highlightLayer, entitiesLayer, vfxLayer, debugLayer);

// Configure plugins
viewport
  .drag({ mouseButtons: "middle" })        // Middle-mouse drag to pan
  .wheel({ smooth: 3, percent: 0.1 })      // Scroll wheel zoom-to-cursor
  .decelerate({ friction: 0.93 })           // Momentum after drag release
  .clampZoom({ minScale: 0.3, maxScale: 3.0 })  // Zoom limits
  .clamp({ direction: "all" });             // Don't scroll past world edges

// Handle window resize
window.addEventListener("resize", () => {
  viewport.resize(app.screen.width, app.screen.height);
});
```

**CRITICAL: `events: app.renderer.events`** — pixi-viewport v6 requires the PixiJS v8 EventSystem instance. Without this, no mouse/touch input works. This replaces the old v7 `interaction` manager.

**Update worldWidth/worldHeight** when grid bounds change (bootstrap or resync):
```ts
function updateViewportBounds(gridBounds: { min_x: number; min_y: number; max_x: number; max_y: number }) {
  const margin = 5; // tiles of padding
  const topLeft = toIso(gridBounds.min_x - margin, gridBounds.min_y - margin);
  const bottomRight = toIso(gridBounds.max_x + margin, gridBounds.max_y + margin);
  viewport.worldWidth = bottomRight.sx - topLeft.sx;
  viewport.worldHeight = bottomRight.sy - topLeft.sy;
  viewport.clamp({ direction: "all" }); // Re-apply with new bounds
}
```

### L3) WASD panning

WASD is NOT a viewport plugin — implement it in the app ticker with lerp smoothing:

```ts
const keysDown = new Set<string>();
window.addEventListener("keydown", (e) => keysDown.add(e.key.toLowerCase()));
window.addEventListener("keyup", (e) => keysDown.delete(e.key.toLowerCase()));

const PAN_SPEED = 8; // pixels per frame at 60fps

app.ticker.add((ticker) => {
  let dx = 0, dy = 0;
  if (keysDown.has("w") || keysDown.has("arrowup"))    dy -= PAN_SPEED;
  if (keysDown.has("s") || keysDown.has("arrowdown"))  dy += PAN_SPEED;
  if (keysDown.has("a") || keysDown.has("arrowleft"))  dx -= PAN_SPEED;
  if (keysDown.has("d") || keysDown.has("arrowright")) dx += PAN_SPEED;

  if (dx !== 0 || dy !== 0) {
    // Scale by deltaTime for frame-rate independence
    const dt = ticker.deltaTime;
    viewport.moveCenter(
      viewport.center.x + dx * dt,
      viewport.center.y + dy * dt,
    );
    // Manual input breaks follow mode
    if (cameraMode === "follow") {
      setCameraMode("free");
    }
  }
});
```

### L4) Edge scrolling

BG3-style: when the mouse cursor is near the edge of the screen, pan the camera in that direction. Use the viewport's `mouseEdges` plugin:

```ts
// Enable edge scrolling
viewport.mouseEdges({
  distance: 20,    // Pixels from edge to trigger scrolling
  speed: 8,        // Pan speed (pixels per frame)
  allowButtons: true,  // Allow during button press
});
```

**Note:** `mouseEdges` only fires when the pointer is over the canvas. If the browser window is not focused or the pointer leaves the canvas, scrolling stops automatically.

**Alternative manual implementation** (if mouseEdges doesn't behave well with isometric view):

```ts
let mouseScreenX = 0, mouseScreenY = 0;
app.stage.eventMode = "static";
app.stage.hitArea = app.screen;
app.stage.on("globalpointermove", (e: FederatedPointerEvent) => {
  mouseScreenX = e.globalX;
  mouseScreenY = e.globalY;
});

const EDGE_THRESHOLD = 20;
const EDGE_SPEED = 6;

app.ticker.add((ticker) => {
  let dx = 0, dy = 0;
  const w = app.screen.width, h = app.screen.height;

  if (mouseScreenX < EDGE_THRESHOLD) dx = -EDGE_SPEED;
  else if (mouseScreenX > w - EDGE_THRESHOLD) dx = EDGE_SPEED;
  if (mouseScreenY < EDGE_THRESHOLD) dy = -EDGE_SPEED;
  else if (mouseScreenY > h - EDGE_THRESHOLD) dy = EDGE_SPEED;

  if (dx !== 0 || dy !== 0) {
    viewport.moveCenter(
      viewport.center.x + dx * ticker.deltaTime,
      viewport.center.y + dy * ticker.deltaTime,
    );
    if (cameraMode === "follow") setCameraMode("free");
  }
});
```

### L5) Zoom to cursor

Handled automatically by `viewport.wheel({ smooth: 3 })`. The wheel plugin zooms toward the cursor position by default (not toward screen center). This is the BG3/RTS standard behavior.

To zoom to screen center instead (for keyboard zoom): `viewport.zoomPercent(0.1, true)` (zooms in) or `viewport.zoomPercent(-0.1, true)` (zooms out). Wire to `+`/`-` keys if desired.

### L6) Camera modes — BG3-style follow system

Three camera modes forming a state machine:

```ts
type CameraMode = "free" | "follow" | "snap";

let cameraMode: CameraMode = "free";
let followTargetUuid: Uuid | null = null;

function setCameraMode(mode: CameraMode, targetUuid?: Uuid) {
  cameraMode = mode;

  switch (mode) {
    case "free":
      // Remove follow plugin if active
      viewport.plugins.remove("follow");
      followTargetUuid = null;
      break;

    case "snap":
      // Instant center on target (turn start)
      viewport.plugins.remove("follow");
      if (targetUuid) {
        const entity = authStore.entitiesById[targetUuid];
        if (entity) {
          const { sx, sy } = toIso(entity.position[0], entity.position[1]);
          viewport.moveCenter(sx, sy);
        }
        followTargetUuid = targetUuid;
        // Transition to follow mode after snap
        cameraMode = "follow";
        // viewport.follow needs a display object — use entity's Container
        const container = entityContainers.get(targetUuid);
        if (container) {
          viewport.follow(container, {
            radius: 100,      // Dead zone radius in pixels — camera doesn't move
                               // until entity is this far from center
            speed: 5,          // Follow speed (pixels per frame)
            acceleration: null, // No acceleration limit
          });
        }
      }
      break;

    case "follow":
      // Smooth follow with dead zone (during controlled entity's turn)
      if (targetUuid) {
        followTargetUuid = targetUuid;
        const container = entityContainers.get(targetUuid);
        if (container) {
          viewport.follow(container, { radius: 100, speed: 5 });
        }
      }
      break;
  }
}
```

**When to trigger each mode:**

| Trigger | Mode | Behavior |
|---------|------|----------|
| Turn start (TurnStartEvent for controlled entity) | `snap` → `follow` | Instant center, then follow with dead zone |
| Turn start (enemy entity, observing) | `snap` → `follow` | Same — center on active entity |
| WASD / edge scroll / middle-drag during follow | `free` | Break follow, manual control |
| Home key press | `snap` → `follow` | Re-lock to active entity |
| No active encounter | `free` | Free camera |

```ts
// In the event reducer, on TURN_START:
function onTurnStart(event: ServerEvent) {
  const entityUuid = event.source_entity_uuid ?? event.entity_uuid;
  if (entityUuid) {
    setCameraMode("snap", entityUuid);
  }
}

// Home key re-locks
window.addEventListener("keydown", (e) => {
  if (e.key === "Home") {
    const activeUuid = authStore.activeEntityUuid;
    if (activeUuid) setCameraMode("snap", activeUuid);
  }
});

// Manual input breaks follow (already shown in L3/L4 — any WASD/edge scroll sets mode to "free")
// Middle-drag: pixi-viewport drag plugin fires "moved" event
viewport.on("moved", (data: any) => {
  if (data.type === "drag" && cameraMode === "follow") {
    setCameraMode("free");
  }
});
```

### L7) Camera bounds

Already configured in L2 via `viewport.clamp({ direction: "all" })` and `viewport.clampZoom({ minScale: 0.3, maxScale: 3.0 })`.

On bootstrap, center camera on observer entity:
```ts
function focusCameraOnObserver() {
  const obs = authStore.entitiesById[visionStore.observer_uuid];
  if (obs) {
    const { sx, sy } = toIso(obs.position[0], obs.position[1]);
    viewport.moveCenter(sx, sy);
  }
}
```

Do not send camera state to server.

---

## Part M — Turn Control (Your Turn) — Actions + Execute + Optimistic Start

### M1) Determining your turn

Use `POST /session/{id}/ping`.
When it flips:

* is_my_turn = true
* active_entity_uuid set

If active entity is controlled:

* fetch `/entity/{active}/available-actions`
* enable input mode

### M2) Executing actions and handling ActionResult

Use the primary execute endpoint:

```
POST /action/execute
{
  session_id: string,
  entity_uuid: string,
  template_name: string,
  target_index: number,
  prefer_safe?: boolean,            // Default true (hazard-avoiding path)
  extra_target_uuids?: string[]     // For MULTI_ENTITY actions (e.g. Magic Missile)
}
```

**ActionResult handling pattern:**

```ts
const result = await api.post('/action/execute', request);

// 1. Overwrite AW from snapshot (Phase 1) or detect drift (Phase 2)
if (result.state) {
  overwriteOrDriftCheck(result.state);
}

// 2. Update available actions for next action
if (result.available_actions) {
  authStore.availableActions = result.available_actions;
  authStore.availableActionsFor = request.entity_uuid;
}

// 3. Handle deaths
for (const deathName of result.deaths) {
  // Mark dead in AW, schedule death animation
}

// 4. Check control flow
if (result.encounter_ended) {
  // Encounter over — disable input, show result
} else if (!result.turn_continues) {
  // Turn ended (entity died, etc.) — disable input, wait for next turn via ping
} else {
  // Turn continues — input stays enabled, availableActions already updated
}

// 5. Process inline combat log entries
for (const entry of result.combat_log_entries) {
  appendToCombatLog(entry);
}
```

### M3) Optimistic animation (starter approach)

Because targets are server-provided indices, failures are rare.

Minimal optimistic:

* when user clicks "attack target X":

  * immediately start attacker windup animation (e.g. 200ms)
  * send execute request
* the actual result (hit/damage) will arrive as completion events (attack completion + take_damage completion)
* if request fails, snap visuals back and show debug message

This hides latency without complex rollback.

### M4) Action selection UI flow

When it's your turn, parse `availableActions` into a DOM action panel:

```ts
// availableActions structure from server:
// { entity_actions, position_actions, self_actions, object_actions,
//   remaining_movement, actions_remaining, bonus_actions_remaining, ... }

function buildActionPanel(actions: AvailableActions) {
  const panel = document.getElementById("action-panel")!;
  panel.innerHTML = "";
  panel.style.pointerEvents = "auto"; // Enable clicks on this DOM panel

  // Group by category
  const groups = {
    "Movement": actions.position_actions,
    "Attacks": actions.entity_actions.filter(a => a.action_category === "attack"),
    "Spells": actions.entity_actions.filter(a => a.action_category === "spell"),
    "Actions": actions.self_actions,
    "Items": actions.object_actions,
  };

  for (const [label, items] of Object.entries(groups)) {
    if (items.length === 0) continue;
    const header = document.createElement("div");
    header.textContent = label;
    header.className = "text-xs text-gray-400 mt-2";
    panel.appendChild(header);

    for (const action of items) {
      const btn = document.createElement("button");
      btn.textContent = `${action.display_name} (${action.cost_type}: ${action.cost_amount})`;
      btn.className = action.can_afford
        ? "block w-full text-left text-sm text-white hover:bg-gray-700 px-2 py-1"
        : "block w-full text-left text-sm text-gray-600 px-2 py-1";
      btn.disabled = !action.can_afford;
      btn.onclick = () => enterTargetingMode(action);
      panel.appendChild(btn);
    }
  }
}
```

Resource display at the top: `Actions: {N} | Bonus: {N} | Movement: {N}ft | Reaction: {N}`.

### M5) Movement targeting

When the player selects "Move":

1. **Highlight reachable tiles** — iterate `action.valid_targets`, tint each position green in `highlightLayer`:

```ts
function showMovementTargets(action: AvailableActionInfo) {
  clearHighlights();
  for (const target of action.valid_targets) {
    const highlight = createTileHighlight(target.position, 0x22cc22, 0.3);
    // Show hazard warning: orange for hazardous paths
    if (target.is_path_hazardous) {
      highlight.tint = 0xcc8822;
    }
    highlightLayer.addChild(highlight);
    highlightMap.set(tileKey(target.position[0], target.position[1]), { target, highlight });
  }
}
```

2. **Hover path preview** — on `pointermove`, find which highlighted tile the mouse is over, draw a line along the path (if the target includes path data, or just draw source→destination):

```ts
app.stage.on("pointermove", (e: FederatedPointerEvent) => {
  if (currentTargetingMode !== "movement") return;
  const tile = pointerEventToTile(e, viewport);
  const key = tileKey(tile[0], tile[1]);
  const entry = highlightMap.get(key);
  if (entry) {
    drawPathLine(entry.target); // Draw a line from entity to target position
  }
});
```

3. **Click to execute** — on click, find the matching `target_index` and send execute:

```ts
app.stage.on("pointerdown", (e: FederatedPointerEvent) => {
  if (currentTargetingMode !== "movement" || e.button !== 0) return;
  const tile = pointerEventToTile(e, viewport);
  const key = tileKey(tile[0], tile[1]);
  const entry = highlightMap.get(key);
  if (entry) {
    // Default to safe paths. Shift+click overrides to force shortest path through hazards.
    const preferSafe = !e.shiftKey;
    executeAction("Move", entry.target.index, { prefer_safe: preferSafe });
    exitTargetingMode();
  }
});
```

### M6) Entity targeting (attacks, single-target spells)

When the player selects an attack or single-target spell:

1. **Highlight valid targets** — add a red outline/glow to each entity in `action.valid_targets`:

```ts
function showEntityTargets(action: AvailableActionInfo) {
  clearHighlights();
  for (const target of action.valid_targets) {
    const container = entityContainers.get(target.target_uuid);
    if (container) {
      // Add a red circle highlight around the entity
      const ring = new Graphics();
      ring.circle(0, 0, 16);
      ring.stroke({ width: 2, color: 0xff3333 });
      container.addChild(ring);
      targetHighlights.push({ uuid: target.target_uuid, ring, target });
    }
  }
}
```

2. **Click to execute** — on clicking a highlighted entity, send execute with the matching `target_index`.

3. **Multi-entity targeting** (e.g., Magic Missile with `num_projectiles > 1`, `allow_same_target=true`): allow clicking multiple targets. Track `extra_target_uuids` list. Show a counter of remaining projectiles. Send all with `extra_target_uuids` in the execute request.

### M7) AoE targeting (position-based spells)

When the player selects a position-AoE spell (Fireball, Thunderwave, etc.):

1. **Hover preview** — on `pointermove`, call `POST /action/position/preview` with the hovered position to get affected tiles and entities:

```ts
const previewCache = new Map<TileKey, AoEPreviewResult>();

app.stage.on("pointermove", async (e: FederatedPointerEvent) => {
  if (currentTargetingMode !== "aoe") return;
  const tile = pointerEventToTile(e, viewport);
  const key = tileKey(tile[0], tile[1]);

  // Cache to avoid redundant calls
  if (!previewCache.has(key)) {
    const preview = await api.post("/action/position/preview", {
      session_id, entity_uuid, action_name: currentAction.template_name,
      position: tile,
    });
    previewCache.set(key, preview);
  }

  const preview = previewCache.get(key)!;
  clearHighlights();

  // Highlight affected positions in orange
  for (const pos of preview.affected_positions) {
    highlightLayer.addChild(createTileHighlight(pos, 0xff8800, 0.4));
  }

  // Show affected entity count
  showTooltip(`${preview.affected_count} targets`);
});
```

2. **Click to execute** — find the matching `target_index` from `valid_targets` where `position` matches, send execute.

3. **Preview caching** — clear cache when mouse leaves targeting mode. Cache is small (only tiles the mouse has visited).

### M8) Complete action target-type flow specification

For each of the 7 active `TargetType` values (`POSITION` is deprecated), the exact UI flow from click to execute.

**Request body reference** (`ExecuteByIndexRequest`):
```ts
{
  session_id: string;
  entity_uuid: string;
  template_name: string;
  target_index: number;
  extra_target_uuids?: string[];  // MULTI_ENTITY only
  prefer_safe?: boolean;          // POSITION_PATH only (default true)
}
```

#### SELF — Immediate execution, no targeting mode

| Step | Detail |
|------|--------|
| 1. Click action button | `Dash`, `Dodge`, `Disengage`, `StandUp`, `DropConcentration` |
| 2. Execute immediately | `target_index: 0` (always index 0 — the only valid target is self) |
| 3. No targeting overlay | No highlights, no cancel needed |

Request: `{ session_id, entity_uuid, template_name: "Dash", target_index: 0 }`

#### ENTITY — Click action → highlight targets → click target → execute

| Step | Detail |
|------|--------|
| 1. Click action button | Melee/ranged attacks, single-target spells (Hold Person, Guiding Bolt) |
| 2. Enter targeting mode | `targetingMode.type = "entity"` |
| 3. Highlight valid targets | Iterate `valid_targets`, draw red targeting ring on each `target.target_uuid` entity |
| 4. Click highlighted entity | Find matching `target.index` from `valid_targets` |
| 5. Execute | `{ ..., template_name, target_index: target.index }` |
| Cancel | Right-click or Escape → clear highlights, exit targeting mode |

#### POSITION_PATH (Move) — Click action → highlight tiles → hover shows path → click tile → execute

| Step | Detail |
|------|--------|
| 1. Click Move action | Enter targeting mode `"position_path"` |
| 2. Highlight reachable tiles | Iterate `valid_targets`, tint each `target.position` tile green (orange if `target.hazardous`) |
| 3. Hover tile | Draw path line from entity to hovered tile using `target.path`. Show movement cost badge. |
| 4. Click tile | Find matching `target.index` where `target.position` matches clicked tile |
| 5. Execute | `{ ..., template_name: "Move", target_index: target.index, prefer_safe: true }` |
| Shift+click | Override `prefer_safe: false` to force shortest path through hazards |
| Cancel | Right-click or Escape |

#### POSITION_LOS (Jump/Teleport) — Click action → highlight tiles → click tile → execute

| Step | Detail |
|------|--------|
| 1. Click action | Jump, Misty Step, Dimension Door. Enter `"position_los"` targeting |
| 2. Highlight valid tiles | Blue tint (distinct from Move's green) on each `target.position` |
| 3. Click tile | No path line (direct LOS, not contiguous). Find matching `target.index` |
| 4. Execute | `{ ..., template_name, target_index: target.index }` |
| Cancel | Right-click or Escape |

#### POSITION_AOE — Click action → highlight castable positions → hover shows AoE shape → click → execute

| Step | Detail |
|------|--------|
| 1. Click spell | Fireball, Thunderwave, Burning Hands. Enter `"position_aoe"` targeting |
| 2. Highlight castable positions | Subtle tint on each `target.position` from `valid_targets` |
| 3. Hover castable position | Show AoE shape overlay. Use `target.affected_positions` if present, else POST `/action/position/preview` to get affected tiles + entity count |
| 4. AoE preview display | Orange tint on affected positions, show entity count tooltip |
| 5. Click position | Find matching `target.index`, execute |
| Preview caching | Cache by TileKey. Invalidate when `authStore.revision` changes (see C2). Call `previewCache.clear()` on revision change while in `position_aoe` targeting mode. **Note:** `revision` increments on any AW mutation (HP, conditions), not just position changes. This over-invalidates — most mutations don't affect targeting geometry. If Performance Monitor shows excessive preview calls during AoE targeting, add a separate `positionRevision` counter that only increments on position changes and deaths, and key cache invalidation off that instead. |
| Cancel | Right-click or Escape |

#### MULTI_ENTITY — Click spell → highlight targets → accumulate clicks → execute on full count or Enter

| Step | Detail |
|------|--------|
| 1. Click spell | Magic Missile (3 projectiles). Enter `"multi_entity"` targeting |
| 2. Read `num_projectiles` | From action info (e.g., 3 for Magic Missile) |
| 3. Highlight valid entities | Red targeting rings on all `valid_targets` entities |
| 4. Click entities to accumulate | Each click adds to `selectedTargets[]`. Same target allowed multiple times. |
| 5. Visual feedback | Show projectile count badge on selected entities ("×2" if targeted twice) |
| 6. Auto-execute on full count | When `selectedTargets.length === num_projectiles`, auto-send |
| 7. Early confirm | Press Enter to execute with fewer projectiles (if spell allows partial) |
| Undo last | Right-click pops last selection from `selectedTargets[]` |
| Cancel | Escape clears all selections and exits targeting mode |
| Request format | First target → `target_index`. Remaining → `extra_target_uuids: [uuid, uuid, ...]` |

#### OBJECT — Click action → highlight objects → click object → execute

| Step | Detail |
|------|--------|
| 1. Click action type | Pick Up, Open Door, Pull Lever, Open Chest. Enter `"object"` targeting |
| 2. Highlight interactable objects | Ring/glow on objects from `valid_targets` |
| 3. Click object | `target_uuid` is the object UUID (not entity UUID) |
| 4. Execute | `{ ..., template_name, target_index: target.index }` |
| Cancel | Right-click or Escape |

#### TargetingMode state type

```ts
type TargetingMode = {
  type: "none" | "entity" | "position_path" | "position_los" | "position_aoe" | "multi_entity" | "object";
  action: AvailableActionInfo | null;
  selectedTargets: Uuid[];  // For MULTI_ENTITY accumulation
};

// Initial state
const TARGETING_NONE: TargetingMode = { type: "none", action: null, selectedTargets: [] };
```

#### Global input handler wiring

| Input | Context | Action |
|-------|---------|--------|
| Escape | Any targeting mode | Cancel targeting → `TARGETING_NONE` |
| Right-click | `multi_entity` with selections | Undo last selection |
| Right-click | Any other targeting mode | Cancel targeting |
| Left-click on valid target | Any targeting mode | Select target (accumulate for multi_entity) |
| Left-click elsewhere | Any targeting mode | No-op (don't cancel — prevents accidental misclicks) |
| Shift+left-click | `position_path` | Execute with `prefer_safe: false` |
| Enter | `multi_entity` with 1+ selections | Early confirm and execute |

---

## Part N — Debug Overlay (Performance-Aware)

The debug overlay is a **correctness tool** that ships early (Milestone 4.5). It makes invisible problems visible.

Create in `domOverlay.ts`:

* fixed position `div` inside `#ui-root`
* `pointer-events:auto` so you can click buttons

### N1) Connection Section

* Connection status (connected/degraded/disconnected)
* Session ID
* Controlled entity UUIDs

### N2) Event Stream Section

* Cursor value (current)
* Last poll: event count, latency ms
* Events/sec (rolling average)

### N3) Sync Cycles Section

* Last visibility fetch: latency ms, time ago
* Last state sync: time ago
* REST calls/min
* Sync triggers/min

### N4) Animation Section

* Queued clip count
* Active clip name + progress
* Global anim speed
* Estimated queue duration ms

### N5) Turn Section

* Active entity name + UUID
* Is my turn (boolean)
* Available actions count
* Round / turn index

### N6) Drift Detection Section (Phase 1+)

* AW drift count (total)
* Last drift: fields that drifted
* Last drift: time ago
* Drift status: "clean" (0 drifts) or "drifting" (recent drift)

### N7) Buttons

* Resync (full `/state` + cursor reset)
* Clear Clip Queue
* Snap PW to AW
* Speed ± (optional)
* Toggle Phase 1/Phase 2 (for testing)

No UI framework.

---

## Part O — Performance Monitoring Framework

### O1) What to measure

| Metric | Source | Ring buffer size |
|--------|--------|-----------------|
| Poll latency (ms) | Events poller | 100 |
| Poll event count | Events poller | 100 |
| Poll response size (bytes) | Events poller | 100 |
| Visibility fetch cost (ms) | After sync trigger | 50 |
| State fetch cost (ms) | Resync / ActionResult processing | 20 |
| REST calls/min | All API calls | Rolling counter |
| Sync triggers/min | Visibility refreshes | Rolling counter |
| AW drift count | ActionResult comparison | Cumulative |

### O2) Storage

Use ring buffers (circular arrays) per metric. Simple implementation:

```ts
class RingBuffer {
  private buf: number[];
  private idx = 0;

  constructor(private capacity: number) {
    this.buf = [];
  }

  push(value: number) {
    if (this.buf.length < this.capacity) {
      this.buf.push(value);
    } else {
      this.buf[this.idx] = value;
    }
    this.idx = (this.idx + 1) % this.capacity;
  }

  average(): number {
    if (this.buf.length === 0) return 0;
    return this.buf.reduce((a, b) => a + b, 0) / this.buf.length;
  }

  max(): number {
    return Math.max(...this.buf, 0);
  }

  last(): number | undefined {
    if (this.buf.length === 0) return undefined;
    return this.buf[(this.idx - 1 + this.capacity) % this.capacity];
  }
}
```

### O3) Debug overlay format

Display in the Sync Cycles section:

```
── Performance ──
Poll:   avg 12ms  max 45ms  (last 50)
Events: avg 2.3/poll  max 8
Vis:    avg 18ms  max 42ms  (12/min)
State:  avg 35ms  (2 fetches)
REST:   24 calls/min
Drift:  0 (clean ✓)
```

### O4) Phase 2 transition criteria

Start Phase 2 optimization for a specific concern when the data justifies it:

| Concern | When to optimize | What to do |
|---------|-----------------|------------|
| Visibility fetch cost | avg > 50ms OR > 10 calls/min | Use SensesUpdateHint (H8) to skip unneeded fetches |
| ActionResult overwrite | awDriftCount = 0 for 5+ minutes of active play | Trust reducer, use ActionResult for drift detection only |
| Poll interval | avg latency < 50ms AND avg events/poll < 1 | Consider increasing interval to 600-800ms |
| Ping interval | Turn transitions are responsive | Consider increasing to 1500-2000ms |

### O5) Phase 2 optimization levers (priority order)

1. **Skip visibility on benign spatial events** — entity_entered/left without light changes
2. **Trust reducer over ActionResult.state** — stop overwriting AW, only detect drift
3. **Throttle visibility refreshes** — batch multiple triggers, refresh max once per 200ms
4. **Increase poll intervals** — only when event rates are low
5. **Use SensesUpdateHint for targeted updates** — update only specific entities/tiles instead of full `/visibility` fetch

---

## Part O2 — Development Milestones (Dependency-Ordered)

### Short-term target: "First Playable Loop"

The first real goal is **Milestone 5 — you can watch a full AI-vs-AI combat play out with animated moves and hits.** Everything before this is scaffolding; everything after adds player control. Reaching Milestone 5 validates the core architecture (AW/PW separation, cursor events, reducer, clip playback) before investing in the complex action targeting UI.

```
M1 ──→ M2 ──→ M3 ──→ M4 ──→ M5  ← "First Playable" (spectator works)
                       │      │
                       │      └──→ M6 ──→ M7  ← "First Interactive" (your turn works)
                       │                  │
                       └──→ M4.5          └──→ M8
                     (can build in parallel)
```

**Milestone 1 — Render + camera** (~2 days)

* Pixi v8 app init, viewport with pan/zoom/WASD
* Iso grid: mesh-based tile layer (diamonds from J4) — hardcoded 10×10
* A few hardcoded entity circles
* **Done when:** you can pan around an iso grid with circles on it

**Milestone 2 — Bootstrap from server** (~2 days)

* API client (Axios + Zod schemas for /state, /session)
* `POST /session/create` + `GET /state` → populate store
* Spawn tiles and entities from real server state
* **Done when:** refreshing the page shows the actual encounter from the running server

**Milestone 3 — Events poller + ping** (~2 days)

* Cursor init (`/events?since=0&limit=0`)
* Events poll loop at 400ms
* Ping poll loop at 1s (turn ownership detection)
* State machine transitions: BOOTSTRAPPING → OBSERVING → MY_TURN_READY
* Console-log received events (no reducer yet)
* **Done when:** you see events streaming in the console as AI takes turns

**Milestone 4 — Reducer (Tier 1 events only)** (~3 days)

* Implement reducers for Tier 1 events only (H1c): `turn_start`, `movement`, `take_damage`, `heal`, `death`, `condition_application`/`removal`
* Skip Tier 2-4 events (parent events, spatial, dice — these don't mutate AW)
* Entity positions, HP, conditions, deaths update live
* **Done when:** AW entities track positions and HP correctly through a full combat (verify by manual /state comparison)

**Milestone 4.5 — Debug overlay + performance monitor** (parallel with M4/M5)

* PerfMetrics ring buffers
* Instrument all pollers and sync calls
* DOM overlay: connection status, event count, poll latency, cursor value
* Drift detection (compare reducer AW vs ActionResult.state)
* **Done when:** overlay shows live metrics during combat

**Milestone 5 — Clip playback (First Playable)** (~4 days)

* EventDirector with FIFO clip queue (Part I)
* MoveClip (path animation along tiles)
* HitFlashClip + DamageNumberClip (floating damage numbers)
* DeathClip (fade out)
* TurnBannerClip (turn start banner)
* AoE grouping in `processEventBatch()` (parallel damage clips)
* Global speed multiplier
* **Done when:** you can watch a full AI-vs-AI combat with animated movement and damage — the "First Playable" spectator experience

**Milestone 6 — Fog-of-war + visibility** (~3 days)

* Mesh-based fog layer (K3)
* `/visibility` fetch + diff-based buffer writes (K5)
* Entity visibility filtering
* Coalesced refresh (K4b)
* **Done when:** fog-of-war renders correctly and updates as entities move

**Milestone 7 — Actions + targeting (First Interactive)** (~5 days)

* Turn detection → `GET /available-actions`
* Action panel UI (M4)
* SELF actions (Dash, Dodge — immediate execute)
* ENTITY targeting (attacks — highlight + click)
* POSITION_PATH targeting (Move — highlight + path preview + click)
* ActionResult handling (M2): AW overwrite, available actions update, turn_continues check
* **Done when:** you can play a full turn — move, attack, end turn — against AI opponents

**Milestone 8 — Phase 2 optimization** (only after M7 is stable)

* Review Performance Monitor data from real gameplay
* SensesUpdateHint-based visibility skip rules
* Switch ActionResult handling from overwrite to drift-detect
* Adjust poll intervals based on measured data
* AoE targeting (POSITION_AOE) and multi-entity targeting (MULTI_ENTITY)
* **Done when:** drift count stays 0 after optimizations; all TargetType flows work

---

## Part P — Testing & Validation (How you know it's correct)

### P0) Backend setup for testing

Start the server:

```bash
cd /path/to/dnd_engine
source .venv/bin/activate
uvicorn server.event_server:app --reload --host 0.0.0.0 --port 8000
```

Create a test encounter from the client:

```
POST /session/create { player_type: "human", name: "TestPlayer" }
POST /simulation/start-human?character_class=fighter
POST /game/join { session_id, entity_uuids: [hero_uuid] }
```

The `start-human` endpoint creates a fighter hero + AI goblin opponents (MeleeAIController). Enemy turns run automatically — you only need to control the hero. This gives you a full combat loop for testing the events poller, reducer, and animations.

For spectator-mode testing (P4), use `POST /simulation/start` instead — all entities are AI-controlled, and you just observe the event stream.

### P1) Truth correctness tests

After running for a while, trigger Resync (`/state`) and compare:

* AW entity positions should match snapshot positions
* AW entity HP should match snapshot HP
* AW entity conditions should match snapshot conditions
* Encounter current_entity_uuid / turn_index / round_number should match
* Floor objects should match

If not, your reducer missed an event type or interpreted fields wrong. The drift detection in Part G3 automates this during your turn (via ActionResult.state comparison).

### P2) Cursor correctness tests

Drop network for 5 seconds (disable the events poller), then restore:

* Events should resume from last cursor — no gap
* No duplicates in the combat log
* No missing events (entities shouldn't teleport or have unexplained HP changes)

If missing, ensure cursor is persisted and used correctly. Check that resync (Part G) recovers cleanly.

### P3) Animation correctness tests

* On movement, entity should traverse exact path (not teleport).
* If multiple movement events occur rapidly, clip queue should grow but still play sequentially — no two MoveClips for the same entity simultaneously.
* On AI burst (5+ events in one poll), animations should queue and play smoothly. PW should catch up to AW within a few seconds.
* On resync, clip queue should flush and PW should snap to AW immediately.

### P4) Performance baseline test

Run a 10-round AI-vs-AI combat (spectator mode). Record all Performance Monitor metrics:

* Total REST calls
* Average/max poll latency
* Average/max visibility fetch cost
* Total events processed
* Any AW drift occurrences

Save this as the Phase 2 optimization baseline. After implementing Phase 2 optimizations, re-run and compare: REST calls should decrease, drift should stay at 0, correctness tests should still pass.

### P5) Systematic reducer correctness protocol

Automated correctness check you can run at any time:

```ts
async function verifyReducerCorrectness() {
  const snapshot = await api.get("/state"); // Fresh server truth
  const drifts: string[] = [];

  // Compare entities
  for (const serverEntity of snapshot.entities) {
    const awEntity = authStore.entitiesById[serverEntity.uuid];
    if (!awEntity) { drifts.push(`Missing entity: ${serverEntity.name}`); continue; }
    if (awEntity.hp !== serverEntity.hp) drifts.push(`${serverEntity.name} HP: AW=${awEntity.hp} server=${serverEntity.hp}`);
    if (awEntity.position[0] !== serverEntity.position[0] || awEntity.position[1] !== serverEntity.position[1])
      drifts.push(`${serverEntity.name} pos: AW=${awEntity.position} server=${serverEntity.position}`);
    if (awEntity.is_dead !== serverEntity.is_dead) drifts.push(`${serverEntity.name} dead: AW=${awEntity.is_dead} server=${serverEntity.is_dead}`);
    // Compare conditions (sorted for order-independence)
    const awConds = [...awEntity.conditions].sort().join(",");
    const serverConds = [...serverEntity.conditions].sort().join(",");
    if (awConds !== serverConds) drifts.push(`${serverEntity.name} conditions: AW=[${awConds}] server=[${serverConds}]`);
  }

  // Compare encounter
  if (snapshot.encounter && authStore.encounter) {
    if (authStore.encounter.current_entity_uuid !== snapshot.encounter.current_entity_uuid)
      drifts.push(`Current entity: AW=${authStore.encounter.current_entity_uuid} server=${snapshot.encounter.current_entity_uuid}`);
    if (authStore.encounter.round_number !== snapshot.encounter.round_number)
      drifts.push(`Round: AW=${authStore.encounter.round_number} server=${snapshot.encounter.round_number}`);
  }

  if (drifts.length === 0) {
    console.log("✓ Reducer correctness: all fields match");
  } else {
    console.warn(`✗ Reducer drift detected (${drifts.length} fields):`);
    drifts.forEach(d => console.warn(`  - ${d}`));
  }
  return drifts;
}
```

Wire this to a "Verify" button in the debug overlay. Run it periodically during development to catch reducer bugs early.

---

## Part Q — Common Pitfalls (and how to avoid them)

1. **Updating AW from non-completion phases**
   Don't. Your endpoint filters phase=completion; keep it that way.

2. **Rendering AW directly**
   You'll jump around. Always render PW.

3. **Mixing camera and world coordinates**
   Keep a clear contract: PW positions are in grid-space; iso conversion happens at render time.

4. **Under-measuring /visibility cost**
   In Phase 1, you refresh visibility aggressively. If you don't measure the cost, you'll never know whether Phase 2 optimization is needed or which events to skip. Always instrument sync calls.

5. **Assuming every event carries hp-after or ac**
   Not guaranteed. Use deltas when necessary (see H4).

6. **Sorting events by timestamp**
   Do NOT sort. Cursor order IS causal order. Sorting by timestamp can reorder events with the same millisecond but causal dependency.

7. **Ignoring ActionResult.state**
   `POST /action/execute` gives you a free world snapshot + updated available actions. In Phase 1, always use it. In Phase 2, at minimum use it for drift detection. Ignoring it means you miss the easiest correctness check available.

8. **Hardcoding sync rules before measuring**
   Don't write "only refresh visibility on turn start" as a rule. That's a Phase 2 optimization that needs data to justify. Phase 1 refreshes after every event batch and measures the cost. Let the Performance Monitor tell you what to optimize.

---

## Part R — Appendix: The "exactly-once" loop (summary)

1. `cursor = (GET /events?since=0&limit=0).total`
2. Repeat:

   * `resp = GET /events?since=cursor&limit=200&phase=completion`
   * for e in resp.events (in response order, NO timestamp sort):

     * reducer(AW, e)
     * clips += buildClips(e)
   * cursor = resp.total
   * **Phase 1**: if events.length > 0, refresh `/visibility` for observer
3. If error → resync (`/state`, cursor init)

That's the entire backbone.

---

## Final word: Why this is the right foundation

With your cursor endpoint, the client can be:

* **Correct first** (Phase 1: aggressive sync, measure everything, no silent drift)
* **Deterministic** (exactly-once event processing, causal cursor order)
* **Self-diagnosing** (Performance Monitor + drift detection catch problems before they become bugs)
* **Optimizable with confidence** (Phase 2 optimizations are justified by real data, not guesses)
* **Scalable** (later add WS live stream, same cursor recovery; later add richer UI; later add shader VFX)

Everything else (fancy UI, adaptive speed, complex rollback, parallel clip mixing) is optional polish — this foundation stays.

---

## Appendix S: PixiJS v7 → v8 Breaking Changes Reference

This project uses **PixiJS v8** with **pixi-viewport v6**. All code in this document uses v8 API. This appendix documents the breaking changes for reference.

### Graphics API (BIGGEST CHANGE)

v7: `beginFill() → drawShape() → endFill()` (state machine)
v8: `shape() → fill()` and/or `shape() → stroke()` (builder pattern)

```ts
// v7 (WRONG):
g.beginFill(0xff0000);
g.drawRect(0, 0, 100, 50);
g.endFill();
g.lineStyle(2, 0x00ff00);
g.drawCircle(50, 25, 10);

// v8 (CORRECT):
g.rect(0, 0, 100, 50);
g.fill(0xff0000);
g.circle(50, 25, 10);
g.stroke({ width: 2, color: 0x00ff00 });
```

Shape methods: `rect()`, `circle()`, `ellipse()`, `poly()`, `roundRect()`, `arc()`, `moveTo()`, `lineTo()`, `bezierCurveTo()`, `quadraticCurveTo()`

Fill/stroke: `fill(color)` or `fill({ color, alpha })`, `stroke({ width, color, alpha })`

### Text Constructor

```ts
// v7 (WRONG):
const text = new Text("Hello", { fontSize: 16, fill: 0xffffff });

// v8 (CORRECT):
const text = new Text({ text: "Hello", style: { fontSize: 16, fill: 0xffffff } });
```

### Application Init

```ts
// v7 (WRONG):
const app = new Application({ width: 800, height: 600, background: 0x111111 });
document.body.appendChild(app.view);

// v8 (CORRECT):
const app = new Application();
await app.init({ width: 800, height: 600, background: 0x111111 });
document.body.appendChild(app.canvas);  // .canvas not .view
```

### Event System

```ts
// v8: eventMode defaults to "passive" (NO events!)
// Must explicitly opt in:
app.stage.eventMode = "static";     // Receives events
app.stage.hitArea = app.screen;     // Stage hit area

// Stage-level pointer tracking:
app.stage.on("globalpointermove", handler);  // NOT "pointermove"
```

### Ticker

```ts
// v7 (WRONG):
app.ticker.add((delta) => { /* delta is a number */ });

// v8 (CORRECT):
app.ticker.add((ticker) => {
  const dt = ticker.deltaTime;  // Access via ticker object
});
```

### Container/DisplayObject

- `container.name` → `container.label`
- **Treat `Container` as the node that owns children; treat `Graphics`, `Sprite`, `Text` as leaf nodes.** In v7 these inherited from `Container` and could technically have children, but v8 enforces stricter separation — always wrap in `Container` if you need a parent-child hierarchy
- `container.cacheAsBitmap = true` → `container.cacheAsTexture(true)`
- `obj.getBounds()` returns `Bounds` object → use `obj.getBounds().rectangle` for Rectangle

### Assets

```ts
// v7 (WRONG):
Assets.add("myAlias", "path/to/file.png");

// v8 (CORRECT):
Assets.add({ alias: "myAlias", src: "path/to/file.png" });
// Assets.load("path/to/file.png") — unchanged
```

### pixi-viewport v6 (for PixiJS v8)

**Compatibility caveat:** pixi-viewport v6's PixiJS v8 support has been community-maintained and may have edge cases with v8's new event system. Verify early (Milestone 1) that `drag()`, `wheel()`, `follow()`, `mouseEdges()`, and `clamp()` all work correctly. If any plugin breaks, the fallback is manual transform math in the ticker (translate `viewport.x/y` on WASD, scale on wheel) — architecturally identical, just more code.

```ts
import { Viewport } from "pixi-viewport";

const viewport = new Viewport({
  screenWidth: app.screen.width,
  screenHeight: app.screen.height,
  worldWidth: 4000,
  worldHeight: 4000,
  events: app.renderer.events,  // REQUIRED for v8
});

// Plugin API (chainable):
viewport.drag({ mouseButtons: "middle" })
  .wheel({ smooth: 3, percent: 0.1 })
  .decelerate({ friction: 0.93 })
  .clampZoom({ minScale: 0.3, maxScale: 3.0 })
  .clamp({ direction: "all" })
  .mouseEdges({ distance: 20, speed: 8 })
  .follow(displayObject, { radius: 100, speed: 5 });

// Remove plugins:
viewport.plugins.remove("follow");
viewport.plugins.remove("mouseEdges");

// Camera control:
viewport.moveCenter(x, y);       // Instant pan
viewport.center;                   // Current center { x, y }
viewport.zoomPercent(0.1, true);  // Zoom in 10% (true = smooth)
viewport.resize(w, h);            // On window resize
```
