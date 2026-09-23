# Destruction playback and revealed space

User feedback: the new environment content looks good, but destroying a solid
object reveals things behind it while the break strip still shows the intact
frame. This is a presentation timing defect, not a request to delay native rules.

## Observable contract

- Input: a saved subjective lineage in which destruction clears an obstruction
  and reveals an actor or world geometry.
- Boundary: historical playback, including reverse seeking and all four cameras.
- Expected: the hit starts the authored break immediately. Received world and
  sensory after-values become visible when the authored shape has cleared, not
  on intact frame zero. The final state still equals ordinary event reduction.
- The engine, visibility rules, completed lineage queue and latest state stay
  unchanged. No image analysis or native visibility calculation runs per frame.

## Bounded correction under review

Add a passive `state_change_frame` to the existing environment bank metadata.
Use its sample time as the world/sensory commit anchor within an observed
destruction lineage. Keep break start and hit flash at the existing contact.
Retain the prior received shape until the anchor; draw the active break bank
independently of whether that historical object has reached its final integrity.
Actor observations owned by that destruction must share the anchor, including
the action-entry staging path. Other causal branches retain their own times.

Inspect the shipped prop strips and author the marker in their existing source
declarations, which the offline importer preserves. An absent marker preserves
existing contact timing. Author it for the six inspected opaque props in the new
batch: wardrobe, bookshelf, storage shelving, ingredient shelves, pottery cluster
and large crate stack. Do not invent a fixed frame fraction or derive gameplay
from pixels. Keep barrel rupture/release and device cleanup independent. Other
banks can author the same field when their clearance timing is reviewed.

Reproduce the reported wardrobe reveal from saved inputs, then cover both
observers, world/actor visibility, unchanged native after-values, finite media,
late snapshots and seeking. Re-render a focused subset from the same saved
inputs rather than recapturing native actions. Run affected presentation tests
and scoped typing. Preserve the approved assets and unrelated timing.

Anti-slop and anti-OOP/ECS reviewers approved this bounded correction after
rejecting a global final-pose default: barrels need surface membership available
for their existing frame-six release. Both require retiming only destruction-owned
physical/sensory updates and actor admissions, not damage or condition effects.
They also require active break drawing independently of historical integrity,
and exclusion of destruction-owned observations from initial action staging.
Recheck the final changes against these findings.

## Evidence and result

The saved wardrobe attack has its break start, lowered placement, sensory reveal
and newly observed witness all at 666.67 ms. The destruction strip is still its
exact intact frame at that instant. Investigation confirms this is historical
state scheduling; native visibility correctly opens after actual destruction.

Implemented through the existing compiled state timeline. The ancestry index is
keyed by stable lineage IDs; observation version UUIDs are normalized through
received version rows. Only destruction owners with an authored nonzero marker
participate. Initial staging and ordinary observation admission use that same
ownership. No backend or native data changed.

The six markers were inspected across all four source views:

| Bank | State-change frame | Delay after impact |
| --- | ---: | ---: |
| Wardrobe | 8 | 666.67 ms |
| Bookshelf | 10 | 833.33 ms |
| Storage shelving | 10 | 833.33 ms |
| Ingredient shelves | 10 | 833.33 ms |
| Pottery cluster | 8 | 666.67 ms |
| Large crate stack | 10 | 833.33 ms |

These are authored clearance samples, not a runtime formula. Remaining fragments
continue settling normally. Unmarked prop/door/trap banks and device staging keep
their previous timing. This change does not claim their individual clearance
frames have all been authored. No opening/closing transition was retimed.

The original regression failed for wardrobe, storage shelves and large crates
because visible cells appeared at intact frame zero. The corrected regression
covers all six props, both observers and four cameras. It checks the old received
shape, visibility and absent actors before clearance; the actual new shape,
sensory snapshot and actors at clearance; and identical output after seeking
back. Ordinary after-state reduction stays immediate. Existing break/late-wreck,
door, device and deposit tests were included in neighboring validation.

Scoped Pyright reports zero errors/warnings. Offline prop re-import into a
temporary directory reproduces shipped metadata, including both independent
clearance and rupture markers. No runtime audit or raster analysis was added.
Both final reviewers approved after the original-version UUID lookup and the
unmarked-bank staging scope were corrected.

[Twelve updated clips](http://127.0.0.1:8767/runs/20260923T151946Z-aef733/index.html)
replay the same saved inputs as the original 42-clip capture; all twelve pass and
report no presentation gaps. The other 30 clips are unaffected. Four-camera
wardrobe frames before/after clearance were visually inspected: the witness and
floor beyond the cupboard now appear during collapse, not its intact opening.
The user approved the remainder of the original batch's appearance.

### Archived fixture issue observed by neighboring checks

The broader run also reaches three older compressed native recordings in
`tests/game/fixtures/`: `legacy-device-destruction.json.gz`,
`legacy-door-destruction.json.gz` and `legacy-web-destruction.json.gz`.
Five tests fail while decoding these before playback: the current complete-event
schema requires `action_economy_spent`, and SpellEvent also requires `harmful`,
`harmful_target_entity_uuids` and `target_type`. Those fields were not present in
the archived packets. This is separate from destruction scheduling; the decoder
and native event models were not touched here. Tests remain enabled. No missing
historical facts were invented and no runtime validation was weakened.

Final run: **100 passed, 3 failed, 2 setup errors in 121.82 seconds** across
`test_prop_destruction.py`, `test_environment_presentation.py`,
`test_device_destruction.py` and `test_deposit_media.py`. All five nonpassing
cases are the archived decoding issue above; every test reaching playback
passed. This is not a clean full-suite claim. Final scoped typing is clean.

The final gallery was checked for identical saved sequence values against its
original capture, twelve passing cases and zero trace gaps. Native actions were
not regenerated to obtain a different result.
