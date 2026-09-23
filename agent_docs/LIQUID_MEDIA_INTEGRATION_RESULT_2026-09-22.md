# Liquid barrel media — production result

The approved six materials × three irregular variants are installed. Water,
oil, grease, blood, poison and dread blood now discharge at the barrel's authored
rupture, settle into a coherent surrounding pool and sustain while later actions
continue. This completes the [liquid-media integration plan](LIQUID_MEDIA_INTEGRATION_2026-09-22.md).
The earlier one-cell and static-pool galleries are historical results.

Review the [28 paired gameplay clips](http://127.0.0.1:8767/runs/20260922T075227Z-718226/index.html):
four cameras per clip, two subjective observers per native experiment. All 28
recorder checks pass across 9,630 encoded four-camera frames. Every clip contains
both airborne discharge and sustained floor media. Captured histories and videos are saved under
`.runtime/animation-review/runs/20260922T075227Z-718226/`; the local review server
serves those files rather than storing them temporarily in the browser.

## Ownership and behavior

Existing native spatial conditions and tile residues remain the material owners.
Their observed pieces retain a physical deposit frame: destruction lineage UUID,
world origin and radius. Actual membership supplies coverage; no second pool
registry, hidden map query or renderer-defined reach was introduced. The same
geometry survives serialized replay, wreck retirement, cold acquisition and
partial transformation/removal. Ordinary shaped injury contributions remain.

The shared barrel bank declares rupture frame 6, at 500 ms. Each subjective
timeline starts discharge relative to its own witnessed destruction transition.
Two observers can have different preceding presentation durations; they share
the source identity, selected variant and phase at the same age after rupture.
The six-second settling animation does not extend the gameplay action or stop
movement. Coldly acquired pools start sustained media rather than replaying a
destruction the observer did not witness.

All six barrels retain the earlier native one-cell radius, admitting up to 3×3
connected cells at a common support height. Walls, doors and other native ground
constraints bound that coverage. Water/Grease contact, toxic damage, jumping over
versus landing in a pool, and paid dread-pool retreat use native rules and real
events. No damage or liquid movement was invented to match the art.

## Media and drawing

The [final Godot delivery](</home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/delivery-liquid-depth-v1/HANDOFF.md>)
contains 18 unchanged approved variants and four camera exports each. Each has
1152 observations at 144 Hz: 864 application frames and a 288-frame sustain loop.
The installed atlas payload is 1,072 pages / 67,964,928 compressed bytes.
Separate floor and air images retain the same pivots/crop offsets; raw air
footpoints register droplets in deposit-space coordinates. Their RGBA bytes are
data, not opacity. Existing bounded media caches load these pages lazily.

The storage importer only translates these assets. Passive bindings select
material, physical radius, variants and phase windows. Shared maintained-media
sampling supplies the clock. Floor pieces use existing ground partitions; air
uses exported footpoints and the shared painter partition for clipping and
actor/wreck depth. One common projection transform preserves the source scale.
Old pool output is suppressed only for the deposited pieces handled by this art.

Inspected splash and settled frames for all six materials from all four cameras,
plus open/closed-door boundaries, failed Grease saves, poison jumping and dread
retreat/center landing. Inspection sheets are in
`.runtime/liquid-media-20260922/`: `all-materials-splash.png`,
`all-materials-settled.png` and `boundary-contact-inspection.png`.
The gallery includes a five-second final review hold to show settled material;
this is recorder metadata, not a gameplay delay.

## Verification

WSL uv environment: `/home/tommaso/.cache/dnd-engine/venv`; source remains under
`/mnt/c/users/tommaso/documents/dev/dnd_engine`.

| Boundary | Result |
|---|---|
| Full engine and maintained item registry | 1,480 passed, 161.78 s |
| Review machinery, liquid/blood replay, maintained Silence/Gust | 63 passed, 212.77 s |
| Remaining game suite | 1,830 passed initially; four equipment-helper unpack failures corrected, full affected module then 7 passed |
| Final installed six-material deposition acceptance | 22 passed, 10.52 s |
| Focused sparse media import/storage | 41 passed |
| Shared depth and neighboring feedback | 65 passed |
| Native/game/review/importer typing | 0 errors, 0 warnings |
| Final changed acceptance-test typing | 0 errors, 0 warnings |
| Real native capture → saved public replay → four-camera clips | 28/28 passed |

These lanes overlap; their counts are not a unique-test total. Detailed logs are
in `.runtime/liquid-media-20260922/`, with native/storage reports in the two
companion integration directories referenced by `verification-checkpoint.md`.
The broad game failures were test helpers destructuring six DrawCommand fields
after the new optional depth field; named-field access preserves all existing
pixel assertions. The final six-material test initially assumed equal absolute
rupture times between subjective views. Actual packets show an ActionFact only
in the acting observer's view. The corrected test checks each real destruction
transition and compares source/phase at equal deposit age. Production timing and
subjectivity were not altered to satisfy that incorrect assertion.

Independent native, anti-slop and ECS reviews accepted the existing-owner,
existing-clock and existing-painter approach before final delivery.

## Explicit limits

- Four water clips report the existing public **Wet** condition without a
  condition presentation recipe (`behavior_id: null`). Wet status, damage
  affinities and pool playback are retained and tested. No body-wet effect was
  requested or fabricated in this unit; the gap remains visible in the review
  inventory rather than being suppressed.
- Whole irregular 3×3 patterns were approved. Native clipping is verified, but
  clipped or arbitrary L-shaped patterns have no separate art approval.
- Each resolved air pixel has one nearest droplet footpoint. The exporter
  documents subpixel transparency/ownership limitations; this is not full 3D
  transparency or fluid simulation.
- Older packets without deposit provenance keep the previous presentation.
  Saturated residues retain their admitted contributions; no extra pool history
  is added for material the native owner did not accept.
- Persistent burning-oil/fire artwork remains a separate handoff. Accepted
  Grease barrel media does not mean the separate Grease spell batch is integrated.
- No stacked-floor or flight mechanics, source hashes, eager asset audit or
  runtime Godot/TypeScript dependency was added. No commit was made.

The next user-authorized step is collecting a complete outstanding-asset handoff
from the Godot task, checking it against current production and preparing the
next integration unit. That intake must not reinstall the historical ten-spell
batch merely because an older handoff still labels it pending.
