# Spell palette → casting hands — completed 4 October 2026

User contract: automatic unless explicitly overridden; palette replacement,
never tint multiplication or hue rotation.

**Completion correction:** the initial pass below left 27 enabled spells without
hands and incompletely covered True Strike weapon poses. Those omissions are now
fixed in [the follow-up receipt](SPELL_HANDS_COMPLETION_2026-10-04.md). The linked
inventory is current; the counts below describe the earlier pass.

## Implementation

- `LayerColors.source` defaults to `auto`. `resolve_cast_recipe` resolves the
  owning spell's existing tertiary/primary/secondary colors into the existing
  palette treatment. Both ordinary delivery and actor-only casting use it.
- `load_cast_rows` swaps isolated pixels with that exact ramp, including already
  colored source sheets. Original alpha, geometry, frame selection and timing
  are preserved. Source plus effective treatment form the cache identity, so
  shared artwork cannot leak colors between spells or after seeks.
- Explicit overrides retain original source pixels. Their palette remains
  offline bake metadata and is not applied twice. Fixed creature rigs keep
  their existing authored gestures and accents.
- No new registry, backend mechanic, event, artwork or external communication.

## Data changes and complete inventory

18 canonical spells now select automatic hands: Beacon of Hope, Continual Flame,
Daylight, Divine Word, Fear, Flame Strike, Globe of Invulnerability, Hold Monster,
Hold Person, Hypnotic Pattern, Mass Healing Word, Slow, Wall of Force, Wall of Ice,
Wall of Stone, Wall of Thorns, Wind Wall and Cone of Cold. The copied Aid/Haste
sheets keep their geometry but use their owner's colors. Cone uses the existing
Ray of Frost Attack5 hand shape. Acid Splash explicitly retains its approved
22-color baked ramp; its old `auto` flag was incompatible with that intent.

The [complete inventory](SPELL_HAND_PALETTE_INVENTORY_2026-10-04.csv) accounts for
all 126 canonical spells: 18 automatic hand layers, 80 explicit isolated layers,
and 28 using existing other representations without an isolated hand layer.
These 28 are not claimed to have newly added hand effects. Original Aid/Haste,
exact baked ramps and accepted electric/solar/utility hand artwork stay explicit.
No spell palette itself was reauthored in this task.

## Verification

Before the fix, four focused tests reproduced unchanged automatic colors,
cache collisions, missing default selection and the actor-only mismatch.
After implementation, 86 tests passed across `test_spell_palettes.py`,
`test_body_action_playback.py`, `test_animation_draw.py` and
`test_production_gap_delivery.py`. Actual source/loaded pixels cover palette
replacement, byte-identical overrides, partial alpha, both cache load orders,
seek stability, four camera facings, fixed Goblin casting, native actor-only
casting, and the actual Slow/Flame Strike/Hold Person/Cone bindings.
Changed-file Pyright reports zero errors and zero warnings.

[Standard in-engine review](http://127.0.0.1:8768/spell-hand-palette-20261004/acceptance/index.html):
5 clips, 53 passing recorder checks, 0 presentation gaps. Slow, Hold Person and
Cone replay retained inputs; Flame Strike has current caster/recipient captures.
The old 2 October Flame Strike input was correctly rejected by the existing
legacy ownership validator, preserved, then replaced for review by one current
native capture. No compatibility rule or damage event was changed.

Acceptance copies only successful recordings into the normal gallery while
preserving each original run ID, input and trace, so export/replay stays valid.
Source logs and inspected frame stills are in
`.runtime/spell-hand-audit-20261004/`. This is bounded verification, not a new
full-engine-suite claim.

Independent final reviews: [anti-slop](SPELL_HAND_PALETTE_ANTISLOP_2026-10-04.md)
and [ECS/import DAG](SPELL_HAND_PALETTE_ECS_2026-10-04.md). Both approve with no
implementation blocker; their receipts distinguish reviewed logs from tests
and visual inspection performed by the implementing agent.
