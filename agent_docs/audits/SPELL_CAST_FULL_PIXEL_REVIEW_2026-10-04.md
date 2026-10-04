# Spell casting gallery pixel review — 2026-10-04

**Combination verdict: all 19 distinct assignment motion/layer combinations
have sampled pixel evidence, with no blocking visual defect found.** Blight,
Harm, Disintegrate, Circle of Death and Antimagic close the initial evidence
gaps. Complete-gallery coverage and export acceptance remain a separate review;
this receipt does not claim every frame of the planned 298 recordings was seen.

## Provenance and method

Persistent recordings reviewed:

- Part 1: `/home/tommaso/Dev/neurodragon_art/reviews/spell-casting-20261004/part-1/runs/20261004T175326Z-132ebd`
- Part 2: `/home/tommaso/Dev/neurodragon_art/reviews/spell-casting-20261004/part-2/runs/20261004T175326Z-d05ba7`

The manifests were still growing during this review. Retained first-pass
snapshots contain 99 cases each and are provenance, not proof of full export
completion. Their SHA-256 values are
`05167da8b59aed24e530ff3e03aa5bce4871fb5ac0e3c7ab114b03f6fd72180d` and
`dbd9d47fdfa964fa7b7f4b51ec74a0c96952a948bd9d1d5c2c02b93bd3b24963`.

The reviewer viewed 74 exact video frames from 16 persistent recordings as 296
four-camera caster crops. The already inspected smoke run supplies the eight
additional combination representatives below and fixed-rig evidence; its
separate receipt documents 34 sampled frames across nine recordings.

Extraction uses ffmpeg frame indices, followed by crops positioned from the
same frame's recorded actor draw rectangle. Crops are enlarged with nearest
neighbor solely for inspection. The source scene, rig scale, camera and timber
floor are unchanged. No newly rendered or invented animation frames are used.
Trace bindings identify the actual caster, clip and categories; they match the
approved selection for each new sample. Independent ffprobe frame counts match
the corresponding traces (1280×960, 32 fps).

## Combination coverage

All rows include Magic2; the table lists additional layers. “Smoke” refers to
run `20261004T174847Z-03847e`, documented in
`SPELL_CAST_SMOKE_PIXEL_REVIEW_2026-10-04.md` in this directory.

| Motion | Additional layers | Inspected representative |
|---|---|---|
| Attack5 | none | Guidance, part 2 |
| Attack5 | Effect1 | Fire Bolt, smoke |
| Attack5 | Effect5 | Cure Wounds, part 2 |
| Attack5 | Effect5 + Effect1 | Guiding Bolt, part 2 |
| Attack5 | Effect4 | Fireball, part 2; Bestow Curse, part 1 |
| Attack5 | Effect4 + Effect1 | Disintegrate, part 2 |
| Attack5 | Effect4 + Effect3 | Blight and Harm, part 1 |
| Attack1 | Effect5 | Shocking Grasp, smoke |
| Attack4 | Effect5 | Grease, part 1 |
| Attack4 | Effect4 | Wall of Ice, part 2 |
| Attack4 | Effect4 + Effect1 | Wall of Stone, smoke |
| Attack6 | Effect5 | Burning Hands, part 2 |
| Attack6 | Effect4 | Cone of Cold, smoke |
| Attack6 | Effect4 + Effect1 | Lightning Bolt, smoke |
| Special1 | none | Shillelagh, smoke |
| Special1 | Effect5 | Bless, part 1 |
| Special1 | Effect4 | Daylight and Heal, part 1 |
| Special1 | Effect4 + Effect3 | Mass Heal, smoke; Circle of Death, part 1; Antimagic, part 2 |
| Actual weapon pose | none | True Strike longsword/Attack1, smoke |

The True Strike row represents the assignment's weapon-driven policy; it does
not certify every weapon clip. Goblin02's separate original Attack2 accents
were also inspected in the smoke review.

## Exact new samples

Each cell records video `frame index @ milliseconds`. All four camera views
were inspected for each listed frame. These are selected phases, not continuous
playback or an exhaustive review of all facings.

| Part | Case directory | Samples |
|---|---|---|
| 2 | support-guidance | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | pending-bless-lifecycle | 20@625, 28@875, 42@1312.5, 58@1812.5 |
| 2 | batch-burning-hands-axis | 20@625, 28@875, 42@1312.5, 44@1375 |
| 2 | support-cure-wounds | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | persistent-grease-true | 20@625, 28@875, 36@1125, 42@1312.5, 52@1625 |
| 2 | spell-handoff-guiding-mark-consumed | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | divine-daylight | 20@625, 28@875, 42@1312.5, 58@1812.5 |
| 2 | spell-handoff-fireball-open | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | healing-batch-heal | 20@625, 28@875, 42@1312.5, 58@1812.5 |
| 1 | bestow-curse-1-lifecycle | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 2 | construction-ice-retirement | 21@656.25, 29@906.25, 37@1156.25, 43@1343.75, 53@1656.25 |
| 1 | necrotic-blight-hit | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | necrotic-harm-hit | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 1 | necrotic-circle-of-death-hit | 20@625, 28@875, 42@1312.5, 58@1812.5 |
| 2 | disintegrate-survives | 20@625, 28@875, 31@968.75, 42@1312.5, 47@1468.75 |
| 2 | antimagic-moving-field | 92@2875, 100@3125, 114@3562.5, 130@4062.5 |

Additional uncropped views: Guiding Bolt frame 47, Fireball frame 47 and Wall of
Ice frame 53; Blight frame 42, Harm frame 47, Circle of Death frame 58,
Disintegrate frame 47 and Antimagic frame 114. The prior smoke receipt records
its own uncropped delivery views. Video times above are distinct from the
presentation-clock label inside recordings that contain multiple actions.

## Visual findings and limits

- Guidance's bare hand treatment is substantially quieter than the sampled
  directed bolt accents. Guiding Bolt's extra hand flare stays close to its
  release, leaving the moving projectile readable.
- Bless and Cure Wounds use restrained patterned accents. Daylight and Heal
  retain the same gathering motion with fuller body contours; Heal's blue/white
  palette makes those contours particularly visible. This supports progression
  without requiring each higher-level spell to add a large spatial signature.
- Grease has a thin gray body accent during the downward gesture. Wall of Ice
  has a broader pale body accent, while Wall of Stone's previously inspected
  ring deliberately extends onto the floor. The later actual walls remain the
  clear persistent result.
- Burning Hands' local orange body energy gives way to its larger directional
  main effect. Fireball's explosion dominates its scene; the caster is very
  small under that native framing, so Bestow Curse also supplies a larger-screen
  check of the Attack5 + Effect4 shape.
- Bestow Curse's red material has low contrast against this red outfit. Its
  accents are therefore less conspicuous than similarly layered pale or blue
  spells. This is a visibility limitation, not evidence of missing layers;
  layer count or spell level alone must not be presented as a guaranteed
  brightness ordering. No replacement palette is inferred or recommended here.
- Blight and Harm share the violet skull treatment: it grows above/over the
  caster, obscures much of the upper body near release, and then dissolves.
  This is the deliberately selected large signature, not a quiet hand accent.
  In the uncropped samples the distant recipient feedback remains separate;
  the skull does not become a second traveling projectile. Its use should not
  be generalized beyond the selected spells.
- Circle of Death's violet invocation column precedes its much larger red/dark
  ground effect. Native framing makes the caster small, so fine pixel detail
  is limited, but the distinct caster-versus-area roles remain clear. Antimagic
  shows the same selected invocation family in lavender: an early broad ring,
  a tighter column near release, then clear ordinary movement. The prior Mass
  Heal sample supplies the blue/white comparison for this combination.
- Disintegrate's compact green hand charge and body accent remain distinct
  from its longer main ray. The sampled preparation, release and later beam
  align with the pointing pose across the four camera views.
- No sampled geometry drift, pasted rectangular effect background, gross
  whole-body recolor or added competing projectile was observed. The main
  Godot media remains readable in the inspected uncropped views. Palette
  membership and exact alpha cannot be certified from lossy MP4 pixels; the
  source-surface tests supply that evidence.

The requested combination and alternate-signature checks are now complete.
No palette or geometry correction is requested from this sample review. Full
gallery manifest/coverage reconciliation is still separate. Unsampled frames,
continuous timing and all 126 individual spells are not manually certified by
this receipt; exact palette/alpha evidence still belongs to source-surface tests.

Private derivatives and exact video/trace hashes are retained at
`.runtime/spell-casting-20261004/full-pixel-review-antislop/` in `samples.json`,
`coverage.json`, the two interim manifest copies, extracted PNGs and contact
sheets. The helper `sample_cases.py` only extracts recorded frames. A recipient
view of the Thorns cast ceased showing the caster before its release; it was
not counted as complete cast evidence, and Wall of Ice was used instead.
Only private inspection derivatives and this receipt were written; no
production/source/gameplay changes or external chat communication occurred.
