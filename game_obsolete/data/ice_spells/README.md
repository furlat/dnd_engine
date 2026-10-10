# Approved ice/necrotic spell delivery

Local Python/Pygame playback of production-v8 Ray of Frost, Ice Knife and Chill
Touch from `/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/ice-spells/production-v8/`.
No authoring project, TypeScript runtime or source audit is needed to play.

All 21,888 source samples remain in 368 PNG pages (about 96 MiB compressed).
Storage layers address firstFrame/frameCount/columns by direction and retain
alpha versus additive blending and exported gain. Travel at 512px and impact at
256px or 512px use separate asset records, matching the existing Fireball
pattern. Fixed facing pivots remain registration space; frames are not cropped
or independently centered. The shared cache loads requested pages/crops only,
with a 640 MiB ceiling supporting four cameras and two 512px layers. No such
allocation or decode happens at startup.

Small serializable adaptations to the original Studio data:

- `anchorsByFacing` supplies each exported fixed pivot, normalized to the cell.
- `projectile.travel.overlapContactMs` keeps animation advancing at its reached
  destination while fading; contact and damage are not postponed.
- `projectile.targetLocal` expresses a stationary effect with an independent
  contact-after-release delay. The optional approach depth offset puts the
  incoming hand on the caster-facing side through the authored approach phase:
  contact occurs at source frame 236 and the depth offset ends at frame 240.
- `impact.timeMap` maps elapsed milliseconds to source frames. Chill samples
  0–206 span 416.67ms, then 144fps; sample 236 contacts at 625ms. The original
  sequence completes once. It is not a projectile fired at artificial speed.
- `cast.enabled=false` lets an already-created nested native effect play its
  media without another caster gesture. The burst recipe in `spell-studio-drafts.json.effectDrafts`
  retains Ice Knife's real ContentRef and selects native effect_id
  `spell.ice_knife.burst`; it is not a separately paid/catalog spell.
- `damage.hitFlash.palette` is shared exact palette/noise data, baked onto each
  actual actor's animation during media preparation. Casting overlays use
  existing `sourceSheet` bindings, baked separately from body/clothing.

Reimport media, then rebuild declared casting sheets if their authoring changed:

```sh
uv run --no-sync python -m devtools.import_ice_spells --source /path/to/production-v8
uv run --no-sync python -m devtools.bake_spell_palettes --draft-file game/data/ice_spells/spell-studio-drafts.json
```

The supplied Chill artwork remains the authored demonic hand mesh used in the
approved preview. Native identity is the legacy ranged necrotic Chill Touch,
with its existing NoHealing duration; this import does not change it into cold
damage, invent persistent hand art or introduce a ground-freezing rule.

`spell-studio-drafts.json` owns spell and child-effect behavior, including their
separate damage palettes. The importer copies delivered pages, registration and
noise; it never clones Guiding Bolt or edits those recipes. The baker consumes
the casting layers' explicit `palette` and `sourceSheet` fields and writes PNGs
only. See [the shared contract](../PRESENTATION_CONTRACT.md).
