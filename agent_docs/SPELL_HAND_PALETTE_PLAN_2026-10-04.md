# Automatic casting-hand palette — 4 October 2026

The user requires spell palette → casting hands automatically unless explicitly
overridden, using palette replacement, never multiplicative tint or hue shifting.
This follows the read-only inventory in `.runtime/spell-hand-audit-20261004/`.

## Bounded implementation

- Reuse `StudioActorLayer.colors.source` (`auto` / `override`); make `auto` its
  default. The spell's existing `elementColors` is the automatic palette owner.
  Its tertiary/primary/secondary colors are the dark/middle/light entries of the
  replacement ramp. No new palette registry, engine field or event is needed.
- Resolve automatic cast-layer palettes once in the existing shared
  `resolve_cast_recipe`, which serves normal delivery and actor-only casting.
  Keep the recipe's authored layer geometry, sheet, alpha, slot and timing.
  Reuse `PaletteTreatment` and `recolor_palette` for the actual pixel replacement.
  This applies even when the selected source sheet is already colored.
- Include the effective palette in the existing cast-row cache key. Two spells
  sharing the same source sheet must not reuse differently colored cached rows.
  Preserve the prepared palette when body samples select their cast overlays.
- Explicit `override` retains the current authored hand treatment, including
  the source-colored sheet and its existing offline palette-bake contract.
  Existing exact multi-color ramps and accepted special electric/solar hands
  remain explicit exceptions. Inherited `auto` never uses the hue/tint path.
- Migrate accidental copied overrides (Aid/Haste hands and other generic reused
  hand geometry) to `auto`. Keep intentionally authored palettes/source art
  explicit. Record the complete migrated/retained inventory, rather than using
  runtime spell-name cases. Add the already-available matching hand shape to
  Cone of Cold, with automatic colors. Do not invent hand glows for word, eye,
  weapon or body effects whose existing representation intentionally differs.
- Fixed creature rigs keep their own registered cast gestures and accents.
  Do not paint their complete body sprites or paste modular hands onto them.
  This bounded change affects the shared isolated cast-layer palette consumer.

## Verification and review

Verify actual pixels: changing the spell palette changes automatic hand colors;
explicit overrides remain unchanged; source alpha/geometry and frame timing are
identical; differently colored spells sharing a sheet remain isolated during
replay/seek and on four camera facings. Cover both ordinary and actor-only cast
routes, and the newly present Cone hand. Keep existing approved exact-palette
checks passing, then run the affected cast/replay checks and typing. Show a small
standard in-engine replay using retained inputs, not replacement gameplay.

Independent anti-slop reviewer checks scope, palette replacement, exceptions,
cache correctness and actual pixel evidence. Independent anti-OOP/ECS reviewer
checks passive authoring, shared resolution, import DAG and no native-rule/event
changes. Both review this plan and the final implementation. No external chats
or new artwork production are part of this task.

## Completion

Implemented and independently reviewed. The [implementation receipt](audits/SPELL_HAND_PALETTE_IMPLEMENTATION_2026-10-04.md)
links the complete inventory, regression checks, typing, standard replay clips
and both final reviews. No new native rules or artwork were introduced.
