# Pygame V-0 vertical-seam corrective implementation plan

Status: REJECTED AND SUPERSEDED.  This document is retained as evidence of the
rejected design.  It must not authorize implementation.  Its runtime asset
hashing language and its ambiguity around content-system behavior provenance
were rejected in favor of the smaller V2 correction.

This is a bounded correction to
`DND_PYGAME_V0_MINIMUM_V1_VERTICAL_SEAM_IMPLEMENTATION_PLAN_2026-09-03.md`.
It does not replace that plan or expand the vertical slice.  Its purpose is to
repair four observed failures in the first implementation: invalid visual
bindings, excessive cold start, batched rather than incremental interval
production, and an application lifetime tied to the scripted encounter.

## 1. Reproduced facts

The current checkout was measured with `.venv/bin/python` from the repository
root:

| operation | observed time |
|---|---:|
| `import pygame` | 0.22 s |
| create the SDL window | 0.06 s |
| `import game.app` | 11.41 s |
| build all three scripted intervals | 2.06 s |
| validate the asset catalog and construct the cache | about 0.81 s |

`dnd.content_system.builtin` accounts for about 7.29 s of the import.  The
demo loads that entire catalog only because `game.app` creates a level-five
premade fighter with a portable torch and installs the global content runtime.
Neither is necessary to exercise visibility, a fixed standing torch, or the
door's real actions.  A measured narrow import without the premade/bootstrap
path is about 3.3 s on the same checkout.

The async producer currently calls `build_demo_intervals()`, which constructs
all three intervals before returning its tuple.  Consequently the queue cannot
publish the startup interval to the reducer while the open and close mechanics
are being executed.

The main loop condition is `terminal_count < 3`; therefore successful script
completion closes the application.  This is a normal exit, which explains the
absence of an error.

The copied MapEditor catalog and direct image inspection establish these exact
visual roles:

| role | reviewed family | reason |
|---|---|---|
| straight stone wall | `Wall D8_{E,N,S,W}` | full-height straight stone wall |
| stone doorway frame | `Wall D6_{E,N,S,W}` | stone arch/lintel leaving the doorway opening |
| closed door leaf | `Door A1_{E,N,S,W}` | full closed wooden leaf |
| open door leaf | `Door A2_{E,N,S,W}` | open/profile wooden leaf |

The implementation incorrectly bound D6 as every straight wall and D2, which
is a corner wall, as every doorway frame.  Ground A1, the Unity-derived Water
material, and the standing-torch body/flame are not implicated by this defect.
The authoritative source remains
`/home/tommaso/Dev/NeuroMapEditor/public/assets/fantasy/catalog.json` and its
`environment` asset directory; no image inference or generated substitute is
allowed.

## 2. Non-negotiable boundaries

- Keep the engine and pygame renderer in-process and separated by the existing
  two bounded `asyncio.Queue` boundaries.
- Continue reducing and rendering detached copies of the existing engine Event
  subclasses.  Do not add a second event hierarchy, DTO family, callback bus,
  controller, manager, service, transaction, or receipt.
- Do not add `sys.path` mutations, local/late imports, dynamic imports, import
  cycles, threads, subprocess workers, or a loading-screen mechanism.
- Do not touch server, SDK, transport, TypeScript, NeuroClient, MapEditor,
  generated, editor, or Phase-2 character/VFX work.
- Do not alter engine mechanics to make the renderer convenient.  This repair
  changes only `game`, `tests/game`, the four wrong copied D2 files, and the
  four reviewed copied D8 files.
- Preserve the accepted 64-by-64 battlefield, objective/subjective reduction,
  visibility and light computation, water material, four-view projection,
  mouse diagnostics, and renderer evidence accounting.
- Direct execution remains `python -m game` from the repository root.  Running
  `python game/app.py` is not supported and will not be made to work by a path
  hack.

## 3. Corrective implementation

### C1 — Repair the authenticated visual subset

1. Copy the four exact `wall-d8-{e,n,s,w}.png` files from the MapEditor asset
   root into `game/assets/environment` without transforming or recompressing
   them.  Record these source SHA-256 values in `game/data/assets.json`:
   `380872fd3bc2bd4dde12988c0c2732104df3f8c57a6dd286bc5622102ea93222`,
   `1b5214567325530aae96ed1e87c02282194e6c12431385cc33800ca90048056c`,
   `316f90e2db15e68dc0f80997a6c1518fb903da4c57f2bf785723c14d2d776c4c`,
   and `17c2881619f3c5dac3522f9bad1a6565299a4809e92b75ca43f50e5e3009df8d`
   in E/N/S/W order.
2. Bind `wall.stone.{e,n,s,w}` to the copied D8 files.
3. Bind `door.frame.{e,n,s,w}` to the already-copied D6 files, retaining their
   existing authenticated bytes.
4. Keep Door A1 as closed leaves and Door A2 as open leaves.
5. Remove D2 from `assets.json` and remove the four copied D2 files.  They were
   introduced by this failed slice, are not a doorway frame, and must not
   survive as unused vertical-slice assets.  Their authoritative originals
   remain recoverable in MapEditor.
6. Keep the finite resource count unchanged: four D8 files replace four D2
   files.  Do not import any additional family.

Proofs must assert the exact resource paths and hashes for all four wall and
frame poses, render the wall/frame/leaf combination in all four camera
quadrants, and prove closed/open/closed uses A1/A2/A1 while the frame remains
D6 and adjacent walls remain D8.

### C2 — Remove the accidental full-content dependency

1. Remove the imports and calls for `bootstrap_content_system`,
   `SERVER_CONTENT_SYSTEM_RUNTIME`, premade fighter construction,
   `execute_use_action`, and the portable `Torch` fixture.
2. Create the observer through the existing low-level ECS composition seam:
   `Entity.create` with an explicit `EntityConfig`, followed by
   `compose_entity()` and the existing `Game.deploy_entity()` call.  The actor
   has ordinary sight, the authored observer position, and no items.  Do not
   create a new actor factory.
3. Execute the existing concrete `OpenDirectionalDoorAction` and
   `CloseDirectionalDoorAction` classes as non-template independent actions,
   with the observer as source and the real authored door UUID as source item.
   Their ordinary `apply()` path must publish the same ActionEvent phases and
   drive `DirectionalDoor.open/close`; do not mutate `door.is_open` directly.
4. Retain the checks that each action reaches COMPLETION, the door state agrees,
   the standing torch owns exactly one live light source, and no other active
   light source was introduced.

The fresh-import proof must show that importing `game.app` does not import
`dnd.content_system.builtin` and that no global content runtime is installed by
the demo.  Existing content-system behavior elsewhere is out of scope.

### C3 — Make interval production genuinely incremental

1. Express the existing mechanics script as one private iterator that yields
   startup, open, and close envelopes immediately after each interval is
   captured.  `build_demo_intervals()` remains the deterministic public test
   convenience and returns `tuple(iterator)`; it must not become a second
   implementation.
2. `_produce_intervals` iterates that same source and awaits the existing
   bounded queue after every yield, explicitly returning control to the render
   loop.  It does not create a worker, callback, or new orchestration object.
3. Prove that the startup envelope is reduced and displayed while the engine
   cursor is already ahead of the reducer/display cursor, and that all three
   terminals remain ordered startup/open/close with final E=R=D.

### C4 — Decouple window lifetime from encounter lifetime

1. The pygame loop remains alive after the third interval settles.  It keeps
   pumping SDL input and rendering Water and flame animation from the final
   subjective target until Escape or `pygame.QUIT`.
2. Once settled, add one plain diagnostic rail line stating that the script is
   complete and Escape closes the window.  Do not add a menu or UI state
   machine.
3. Preserve failure when a human closes the window before all three intervals
   settle.  A successful post-settlement close returns the existing
   `RunSummary`.
4. Retain `max_frames` as the sole deterministic test stop.  Reaching it before
   settlement is an error; reaching it after settlement is a successful stop.
   No test-only lifetime parameter is added.
5. Prove that multiple frames are rendered after final settlement, that camera
   controls remain accepted, and that Water/flame frames continue advancing.

### C5 — Measured completion gates

Run all measurements in fresh `.venv/bin/python` processes from the repository
root.  Warm-process timings are not evidence.

1. `import game.app` must complete without importing
   `dnd.content_system.builtin` and in no more than 5.0 seconds on this host.
2. A dummy-driver cold finite run through its first represented frame must
   complete in no more than 8.0 seconds on this host.  Record both the observed
   value and the former measured baseline; do not loosen the budget if it
   fails.
3. The finite full script must settle E=R=D, render at least three subsequent
   frames, and stop successfully only at `max_frames`.
4. Capture startup, open, closed, and post-settlement frames for quadrants
   0/1/2/3.  Inspect them at original resolution for continuous D8 walls, a
   single D6 doorway frame, correct A1/A2 leaf pose, coherent Water, correct
   torch composition, and absence of corner-wall or repeated-arch artifacts.
5. Run `tests/game`, the accepted focused engine/renderer lane, dependency
   direction and cycle gates, pyright, compileall, and `git diff --check`.
6. Scan the changed files for forbidden imports, path manipulation, callbacks,
   new Event subclasses, managers/controllers/services, and runtime type or
   `getattr` dispatch.

## 4. Stop conditions

Stop without implementation if any of these is required:

- changing engine content-runtime ownership rules;
- replacing the in-process queues with threads, processes, networking, or a
  new event bus;
- inventing or transforming an asset rather than using exact catalog bytes;
- expanding beyond the four D8 replacements;
- weakening visibility/light/evidence assertions to obtain a passing frame;
- changing the 64-by-64 world or the scripted startup/open/close semantics.

After implementation, any production, test, asset, or catalog change
invalidates timing results and visual captures and requires rerunning C5.
