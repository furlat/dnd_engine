# Material selection and evidence trace — ECS checkpoint review

2026-10-05. Independent current-source review; no production edits. Scope is the shared effective cast/attack layer palette and expanded bound trace. Earlier condition-body material changes were already reviewed separately; no scheduler/narrative implementation is claimed here.

**Disposition: approve this bounded checkpoint for ECS/data ownership and import direction.** No blocking findings in the inspected changes. Pixel/regression acceptance remains supplied by the implementation tests, not this source receipt.

## Palette ownership

`animation.effective_layer_palette` is a pure function over authored `StudioActorLayer`. It introduces no registry, mutable entity behavior, hidden state query or alternate spell selection. Explicit isolated override sheets remain source artwork. A resolved layer palette is used directly; unresolved automatic layers fail rather than guess. Explicit unbaked layers obtain exact replacement colors from their own declared colors.

Both `_cast_row_key` and `load_cast_rows` consume the same function. Thus cache identity includes the same source/palette/noise/gamma treatment that actually produces the pixels. The loader's old category-hue/tint selection and Magic3 special repaint are removed from this route, rather than left as a competing fallback. `load_animation_media` validates that same policy.

`attack._attack_layers` continues to select attack outcome/profile and rig capability using the existing paths. Its elemental colors come from already projected `AttackFact.damage_types`, not a private engine lookup. Explicit numeric/white literals generate a one-color replacement palette; only authored `$element...` references opt into elemental palette colors. This preserves literal ownership rather than accidentally injecting weapon damage colors into every slash. Fixed-rig missing separable slots remain explicit media limitations and do not discard mechanical attacks.

## Evidence ownership and clocks

`StateCommitEvidence.version_rows` retains source rows whose events participate in the selected node/observation batch. Selected WorldUpdates already require a selected node identity, so their source event is included by the same filter. Native rows are retained in their existing order. The original `reduce_nodes` call still receives the complete version tuple; instrumentation neither becomes a second reducer nor changes its arguments/timestamps.

Trace expansion serializes already bound movement body context, recovery, world changes, residue reveal, and contact cues. It does not recalculate movement durations, infer hidden trajectories or remap geometry. Residue output excludes the resource object and emits its logical asset ID. Stationary output excludes AnimationData. These traces are developer evidence, not a replacement public protocol or lifetime store.

World/observation content remains the observer-projected input already admitted to the relevant bound timeline. No new engine access, private entities or outcome inference was found. Nonrendering outcomes and motion provenance still require the later common semantic work; this checkpoint does not assert those gates complete.

## Independent checks executed

- AST dependency scan over all current top-level game modules: no cycles among explicit game-module imports.
- Fresh process rejecting every Pygame import: choreography and effective palette selection import successfully.
- Pure smoke check: explicit literal yields exactly its declared color; an explicit isolated source sheet yields source preservation.

No test-suite rerun or visual review performed by this reviewer. The reviewed new palette tests check exact visible pixel colors, separate cache treatments and the actual full cast loader; commit tests check public packet/version provenance at the HP boundary and movement landing/body trace. Their test results should be reported by the implementation agent.
