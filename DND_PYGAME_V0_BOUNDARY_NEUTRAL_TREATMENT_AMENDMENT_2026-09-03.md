# Pygame V-0 Boundary Neutral-Treatment Amendment

Date: 2026-09-03

## Purpose

Correct the visually false dark wall run found in the accepted full-map
candidate without adding a shadow system or changing engine optics.

The current wall and door assets are composite sprites. They do not expose
independent inner-face and outer-face pixels. Applying one incident support's
light multiplier to the whole sprite therefore pretends that the renderer can
shade a physical face that it cannot actually isolate. The result changes with
camera quadrant and makes one continuous wall material look arbitrarily dark.

## Exact rule

The engine remains the sole authority for light propagation, visibility, and
blocking. Terrain and Water continue to use observer-effective light values
already present in the reduced sensory snapshot.

For a wall or door frame:

- if either incident support is currently visible, disclosure is `current`;
- otherwise, if either incident support is remembered, disclosure is
  `memory`;
- otherwise it is objective `authored` structure;
- `current` and `authored` structure use the neutral authored multiplier;
- `memory` structure uses the existing fixed memory multiplier.

The same treatment applies to a disclosed door leaf. Its open/closed state
still requires current door-object contact exactly as before.

Boundary treatment is camera-invariant. The renderer does not select an
incident support by camera quadrant, take an incident maximum, read objective
resolved light, cast rays, create shadows, or store a second lighting model.
The visual proof that a wall blocks light is the engine-provided treatment of
the supports on either side of it, not invented shading of the composite wall
sprite.

## Scope

Production changes are limited to `game/app.py`. Tests may change only under
`tests/game/`. No engine, event, reducer, catalog, asset, map-authoring, server,
SDK, TypeScript, or MapEditor change is authorized.

## Required proofs

1. A current boundary whose owner side is lit and reverse side is undisclosed
   renders with the neutral structural treatment in all four quadrants.
2. A memory-only boundary retains the fixed memory treatment.
3. A current door frame and contacted leaf share the neutral structural
   treatment; removing object contact still hides only the leaf/state.
4. Terrain on the lit side remains engine-lighted and terrain beyond a closed
   blocker does not receive that light.
5. The complete pygame suite, affected engine optics lane, architecture DAG
   checks, compileall, and diff-check pass.
6. The four-angle detail and door transition captures are visually inspected.
7. The exact actual-interaction performance protocol is rerun; grid-off
   medians remain at or below 16.67 ms.

## Review gates

Before implementation, obtain independent correctness, anti-slop, and
anti-OOP/ECS/dependency approval of these exact bytes. After implementation
and validation, obtain the same three reviews on the frozen code candidate.

Any production or test repair invalidates the frozen candidate reviews and
requires the affected validation and reviews to be rerun.
