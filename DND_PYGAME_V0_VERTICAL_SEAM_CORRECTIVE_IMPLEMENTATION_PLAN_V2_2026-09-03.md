# Pygame V-0 vertical-seam corrective implementation plan V2

Status: candidate. No implementation is authorized until correctness,
anti-OOP/ECS, and anti-slop reviewers accept this exact plan.

This plan repairs the first pygame vertical slice without importing the
server/content-pack architecture into the game loop. It is a bounded correction
to `DND_PYGAME_V0_MINIMUM_V1_VERTICAL_SEAM_IMPLEMENTATION_PLAN_2026-09-03.md`.
The rejected first correction remains in the repository as evidence and has no
authority.

## 1. The system being built

The complete runtime path is:

```text
authored engine world
    -> existing concrete engine action
    -> existing EventQueue Events
    -> detached copies of those same Event subclasses
    -> existing sensory/world reduction
    -> pygame drawing from the reduced target
    -> presentation-complete signal
```

There is no server, wire protocol, content-pack bootstrap, event encoding,
asset authentication, behavior authentication, or second event model in this
path. The two existing `asyncio.Queue` objects are ordinary in-process
handoffs:

1. completed engine cursor intervals move toward reduction/rendering; and
2. presentation completions move back toward the game side so later player
   commands can wait while autonomous turns need not.

This slice keeps the already implemented interval and presentation data
structures. It does not add another wrapper or abstraction. The actual state
payloads crossing the seam remain copied instances of existing engine Event
subclasses.

## 2. Evidence and failures

The current checkout fails for four independent reasons:

1. `Wall D6` was bound as every wall even though it is a doorway arch/lintel.
   `Wall D2`, a corner family, was bound as the doorway frame. The result is a
   line of repeated arches and corner chunks.
2. `game.app` imports the built-in content system, a premade level-five fighter,
   and a portable torch. Cold `import game.app` takes about 11.4 seconds;
   `dnd.content_system.builtin` alone accounts for roughly 7.3 seconds and
   loads 142 `dnd` modules. None of it is needed by this scripted visual proof.
3. `build_demo_intervals()` constructs startup/open/close before the producer
   queues anything, so the apparent async pipeline is actually batched.
4. The main loop exits when the third interval settles, closing a successful
   manual run after a few seconds.

The external task `Audit MapEditor Asset Semantics` is the governing asset
study. It established that engine/map mechanics remain authoritative and the
client table only chooses presentation; asset filenames and old MapEditor
movement/vision flags never define gameplay. It also verified Ground A1,
Door A1/A2, Water, pivots, and explicit four-pose direction handling. Direct
inspection of the selected stone families establishes this slice's exact set:

| engine meaning | visual family |
|---|---|
| straight stone wall | `Wall D8_{E,N,S,W}` |
| stone doorway opening | `Wall D6_{E,N,S,W}` |
| closed wooden leaf | `Door A1_{E,N,S,W}` |
| open wooden leaf | `Door A2_{E,N,S,W}` |

The existing engine `DirectionalWall` reports `Material.STONE`; therefore the
stone D8/D6 set is consistent with the authored world. The client choice must
not mutate movement, optics, propagation, door state, light, or visibility.

## 3. Boundaries

- Change only `game`, `tests/game`, and the copied D2/D8 image files.
- Do not change any `dnd` engine rule, server, SDK, transport, TypeScript,
  NeuroClient, MapEditor, generated file, character/VFX phase, dependency file,
  or the 64-by-64 authored battlefield.
- Add no event class, event bus, DTO family, callback, controller, manager,
  service, receipt, transaction, registry, thread, process, network path,
  dynamic import, local/late import, `sys.path` mutation, `getattr` dispatch, or
  runtime type-dispatch workaround.
- Keep the existing canonical Events, subjective sensory reducer, world
  snapshots, light computation, four cameras, mouse-to-grid diagnostics,
  animated Water, flame animation, evidence accounting, and two bounded
  queues.
- The scripted demo defines its actions a priori. It does not exercise action
  discovery or external content-pack provenance.
- Run only as a module from the repository root with the project environment:
  `.venv/bin/python -m game`. Do not make `python game/app.py` work through a
  path hack.

## 4. Correction

### C1 — Correct the finite visual set

1. Copy the four unmodified `wall-d8-{e,n,s,w}.png` files from
   `/home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/environment` into
   `game/assets/environment`.
2. Bind the four straight stone wall poses to D8 and the four doorway-frame
   poses to the already copied D6 family.
3. Keep Door A1 as closed and Door A2 as open.
4. Update the existing semantic resource rows in place: `wall.stone.*` points
   to D8 and `door.frame.*` points to D6. Delete only the four copied D2 files;
   do not rename or churn the semantic resource IDs. The D2 originals stay in
   NeuroMapEditor.
5. Do not add another asset family. Four D8 files replace four D2 files, so the
   local resource count remains 37.
6. Remove `sha256` from `AssetSpec`, every local resource row, catalog loading,
   and tests. This local presentation catalog records only asset ID, relative
   path, native size, pivot, and scale. Loading still fails plainly for a
   missing file, path outside `game/assets`, malformed dimensions, unknown
   referenced ID, or image that pygame cannot load.
7. Remove the source/image SHA fields from
   `tests/game/data/unity_water_oracle.json`. Retain its source note and every
   numerical Water sample unchanged; the hashes do not participate in the
   oracle calculation.

Proof: assert the exact D8/D6/A1/A2 path tables, render closed/open/closed in
all four camera quadrants, and inspect saved frames at original resolution.
Adjacent walls must be continuous D8 walls; exactly one D6 opening surrounds
the A1/A2 leaf. No D2 or repeated-arch wall may appear.

### C2 — Use only the required engine mechanics

1. Remove imports and calls for `bootstrap_content_system`,
   `SERVER_CONTENT_SYSTEM_RUNTIME`, the premade fighter, `execute_use_action`,
   and the portable `Torch`.
2. Create one observer with the existing ECS composition path:
   `Entity.create(..., config=EntityConfig(...))`, `compose_entity()`, and
   `Game.deploy_entity()`. It has ordinary sight, the authored observer
   coordinate, and no inventory. Do not add an actor factory.
3. Because this encounter's actions are scripted a priori, construct the
   existing `OpenDirectionalDoorAction` and `CloseDirectionalDoorAction`
   directly as non-template actions with the observer UUID and authored door
   UUID, then call their existing `apply()` method.
4. This is the real action lifecycle, not direct state mutation: each action
   must reach COMPLETION; `DirectionalDoor.open/close` must publish the linked
   spatial change; the sensory system must publish the resulting visibility
   and light change. Never assign `door.is_open` in game code.
5. Behavior/content-pack provenance fields may remain absent. They are not
   mechanics and are not required by a locally scripted action. Do not install
   or recreate a binding gateway to populate them.
6. Preserve the checks that the standing torch owns exactly one active light
   source and no portable light exists.

Proof: a fresh process imports and runs the demo without importing
`dnd.content_system.builtin` or installing the global content runtime. The
objective rail still contains the action, spatial, sensory, and light events
caused by open/close, and final door/senses state matches them.

### C3 — Make the engine producer genuinely incremental

1. Put the existing startup/open/close mechanics in one private synchronous
   iterator. It yields each captured interval immediately after that mechanic
   settles. `build_demo_intervals()` remains a test convenience implemented as
   `tuple(the_iterator())`; it is not a second script.
2. `_produce_intervals` uses `put_nowait` on the existing bounded queue and
   performs one `await asyncio.sleep(0)` after each enqueue. That await is only
   a cooperative scheduler handoff; it is not pacing, completion, or a timer.
3. The producer does not await presentation completion. Therefore engine work
   may continue while the renderer holds earlier intervals at human speed.
4. Keep the existing presentation-completion queue. Do not add acknowledgments,
   futures, callbacks, or orchestration objects.

Proof: after the first producer turn only startup is available and the door is
closed; after the next turn open is available and the door is open; after the
next turn close is available and the door is closed. A normal run must show
the engine cursor ahead of reducer/display cursors before all three converge.

### C4 — Keep a successful game window alive

1. Manual lifetime ends only on Escape or `pygame.QUIT`, not when the script
   settles.
2. Before the first interval, draw and flip the normal background so pygame is
   responsive. Once a target exists, draw it every frame, including after the
   final interval. Water and flame continue advancing from presentation time.
3. After settlement, show one text line: `script complete — Esc closes`.
   Introduce no menu, loading screen, or UI state machine.
4. Closing before settlement remains a failure. Closing after settlement
   returns the existing `RunSummary`.
5. `max_frames` remains the single deterministic test stop: reaching it before
   settlement fails; reaching it after settlement returns successfully.

Proof: a finite dummy-driver run settles startup/open/close, draws at least
three later frames, and exits only at `max_frames`. The final frames must differ
where Water/flame animation advances. Manual mode must remain responsive after
settlement.

## 5. Completion gates

All commands run from the repository root with `.venv/bin/python`.

1. A fresh `import game.app` completes in at most 4.0 seconds on this host and
   leaves `dnd.content_system.builtin` absent from `sys.modules`.
2. A fresh SDL-dummy process runs the zero-hold public `run(...)`, settles
   E=R=D, renders at least three post-settlement frames, and exits at
   `max_frames` in at most 8.0 seconds. The current equivalent baseline is
   about 13.8 seconds.
3. `tests/game` passes, including the direct incremental-scheduling, lifetime,
   exact asset mapping, four-view capture, Water/flame, visibility/light, and
   E=R=D proofs.
4. Run the accepted focused engine tests covering world creation, door state,
   spatial/sensory cascade, light, and runtime reset. Run dependency/cycle
   architecture gates, pyright, and compileall.
5. Inspect every captured quadrant at original resolution. Test assertions do
   not substitute for this visual review.
6. Scan the complete active `game` and `tests/game` trees for content
   bootstrap/runtime imports, asset-SHA machinery (`hashlib`, `sha256`, and
   catalog/oracle SHA fields), encoding/serialization, server/transport
   references, path manipulation, callbacks, new Event subclasses, and the
   forbidden abstractions in Section 3. Legitimate engine sensory facts such
   as `sense_modes_hash` are unrelated and remain. There must be no prohibited
   match except assertions explicitly proving absence.

Any code, test, catalog, or image change after these gates invalidates the
affected measurements and visual review and requires rerunning them.

## 6. Stop conditions

Stop and return to the user if completion would require:

- changing engine content-runtime ownership or action-discovery rules;
- weakening the existing visibility/light/world-event behavior;
- adding transport, content authentication, asset authentication, another
  event representation, or another scheduling layer;
- generating/mirroring/rotating a missing asset rather than using its explicit
  four-pose file; or
- expanding beyond this failed slice.
