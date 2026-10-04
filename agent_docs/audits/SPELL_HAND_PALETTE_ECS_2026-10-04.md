# Casting-hand palette ECS / import-DAG review — 4 October 2026

**Plan approved; no ECS or import-DAG blocker.** This receipt reviews
`agent_docs/SPELL_HAND_PALETTE_PLAN_2026-10-04.md` before implementation. It is
not final implementation or visual acceptance.

The inspected owners support the proposed change directly:

- `game/animation.py::resolve_cast_recipe` already serves
  `compile_cast` and `game/body_action.py`'s actor-only cast binding. Resolve
  inherited colors into copied, passive layer data there; no renderer or
  native-rule lookup belongs in that function.
- `StudioActorLayer`, `LayerColors`, `ElementColors` and `PaletteTreatment`
  already represent the needed values. Preserve authored draft immutability;
  neither a palette service nor another entity/event field is needed.
- `game/animation_draw.py::load_cast_rows` owns isolated sheet preparation.
  `game/spell_palette.py::recolor_palette` already performs exact ramp
  replacement and preserves source alpha. Keep Pygame/pixel work on this
  existing side of the import DAG.
- `_cast_row_key` currently identifies a source sheet without an effective
  treatment. Include the resolved treatment for automatic layers in both
  preloading and body lookup. `sample_cast`, `BodyActionCue.cast_layers` and
  `sample_body_action` already retain complete layers, so preserve those values
  rather than re-resolving against mutable or original recipes during drawing.
- `adapt_cast_body` removes modular layers when the registered rig supplies its
  own cast gesture. That remains the correct fixed-rig boundary; its original
  clip accents need no modular-hand palette adaptation.

Implementation acceptance must keep `override` source sheets and their offline
`palette` bake semantics unchanged, while `auto` consumes the spell's
tertiary/primary/secondary ramp even for colored sheets. Update the existing
presentation contract/comment that currently describes every layer palette as
offline-only. `LayerColors` also appears on projectile sprite data, so the new
default must not imply a new projectile recoloring policy.

The bounded data migration, Cone's existing isolated hand shape, explicit
electric/solar/exact-ramp exceptions and the planned two-route/cache/pixel
checks fit the authorized scope. Final review must inspect the actual migration
inventory and implementation evidence; it must not infer correctness from
authoring values alone.

Read-only source review only: no production edits, tests, renders, native
execution or external chat access. This receipt is the sole file written by
this reviewer.

## Final implementation review

**Implementation approved within the ECS/import-DAG scope; no blocker found.**
Compared the three runtime files against
`.runtime/spell-hand-audit-20261004/before/`, rather than treating the checkout's
unrelated existing Git changes as part of this task.

- `_cast_palette` creates an immutable `PaletteTreatment` from the owning
  spell's colors and copies only automatic layers. Both existing cast entry
  points continue through `resolve_cast_recipe`; no native/entity lookup,
  stateful service, event field or new dependency edge was introduced.
- `_cast_row_key` distinguishes source and complete resolved treatment, while
  retaining the existing override key. Preloading and body drawing use that
  same key. The automatic branch calls `recolor_palette` before rows enter the
  cache; inherited colors never enter the legacy tint/hue branch.
- Ordinary body samples and actor-only cues still carry the resolved layer
  objects. The existing fixed-rig substitution removes modular overlays before
  drawing; the added Goblin02 case checks a rig with a registered cast context.
- The shared `LayerColors.source` default does not add a projectile consumer or
  recoloring branch. Static inspection found no automatic or source-omitted
  actor-layer records outside ordinary cast fields in current JSON, and the
  attack-generated layers remain explicit overrides. No newly admitted
  unresolved automatic attack layer was found.
- Semantic JSON comparison against the saved seven-file baseline found only
  the intended source/mode migration, Acid Splash's explicit baked-ramp
  override, and Cone's added existing Ray of Frost hand sheet. Geometry,
  delivery, timing and native authoring were not changed by these edits.
  Electric/solar source art and the exact authored ramps remain overrides.
- The schema comments and presentation contract now distinguish automatic
  runtime palette preparation from explicit override bake metadata.

Read the new tests covering actual row colors and alpha, both cache load orders,
ordinary seek samples, a native actor-only cast, the default value, fixed-rig
substitution and selected real migrated spells/Cone. The completed
`.runtime/spell-hand-audit-20261004/verification.log` reports **86 passed in
74.03 seconds**. The initial four failed test assertions remain in the earlier
palette log; current source uses visible-alpha pixels and the registered
Goblin02 casting rig. This reviewer did not run tests or render gameplay.

This approval concerns the inspected source/data and available verification
receipt. It does not claim independent visual inspection of the task's planned
in-engine replay, nor substitute for the root's final typing/gallery evidence.
