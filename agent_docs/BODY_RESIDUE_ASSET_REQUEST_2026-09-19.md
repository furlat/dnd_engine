# Body release and ground residue artwork request

The backend now records the profiles below through real injury, tile-condition,
entry, saving-throw and movement events. The initial native body/residue suite
passes 26 cases; eight initial dread-retreat cases pass, including the user's
Misty Step rule. Additional integration checks continue. This request is for
those working contracts, after backend implementation, not a new mechanics plan.

## Requested art

| Body release | Persistent tile membership | Artwork |
| --- | --- | --- |
| `body.blood` | `residue.blood` | Short blood splash; subdued red bloodstain |
| `body.bone` | `residue.bone_fragments` | Small bone chips scattering; scattered bone fragments |
| `body.corrosive_blood` | `residue.corrosive_demonic_blood` | Demonic fluid splash; clearly distinguishable corrosive pool |
| `body.dread_blood` | `residue.dread_blood` | Dark demonic fluid splash; distinguishable dread pool |

Blood and bone are inert ground state. Corrosive blood deals 1d4 acid on entry.
Dread blood causes a Wisdom DC 10 save, with paid retreat toward the entry origin
on failure. These rules are implemented in the engine; pictures express material,
not a damage pulse, save roll, forced recoil or scripted expiration.

Prioritize the four persistent floor assets. They make current native gameplay
readable immediately. Then deliver the four short, non-looping release strips.
The user's follow-up asks ordinary humanoid blood to range from a small splat
to an almost-full pool: provide small/medium/pool variants for `residue.blood`
with matching pivots and style. The native amount-selection rule is a recorded
follow-up, not yet implemented; art does not choose damage thresholds or stack
mechanics. This does not expand the other three material profiles.
Do not add new creature rigs, floor damage stages, spreading, mixing, disappearing
pools or a particle runtime. Poison, smoke and fireball/scorch are other queued
work. The bloodied spike overlay already exists and is integrated; do not redo it.

## Matching and geometry

Use the existing SmallScale environment pixel art and the delivered spike sheets
as references. The active repository is
`/mnt/c/users/tommaso/documents/dev/dnd_engine`.

- Floor reference: `game/assets/environment/ground-d1-e.png` and matching N/S/W.
- Existing blood overlay: `game/assets/environment/spikes-blood/e-6.png` and
  matching N/S/W. Its hue should agree with ordinary blood.
- Skeleton references: `game/assets/rigs/skeletonarcher05/body/TakeDamage.png`
  and `game/assets/rigs/skeletonarcher05/body/Die.png`.
- Demons: `game/assets/rigs/demonbeast02/body/Idle.png` (corrosive) and
  `game/assets/rigs/demonbeast03/body/Idle.png` (dread).

Persistent floor frames use transparent 256×256 RGBA PNGs, ground contact/pivot
`[128,208]`, scale 1, matching the existing 128×64 isometric tile diamond.
Provide E/N/S/W views with consistent world orientation. The stain should sit
inside the support footprint, work on stone/wood/earth, and coexist with bone
fragments and trap fixtures. Do not bake terrain, a creature, UI, grid, glow haze
or ground shadow into the overlay. Bone fragments may have small authored local
shadows; keep the floor contact unchanged across views.

For each transient release, provide a short nondirectional RGBA horizontal strip
with fixed 128×128 cells, about 12 frames at 24 fps, contact/attachment pivot
`[64,64]`. Document actual frame count, fps and pivot. One-shot timing and body
attachment will be authored in presentation data; they are not backend fields.
The burst should finish without leaving permanent pixels in its last frame;
the separate ground membership owns the enduring trace. A release in AIR can
play without a floor stain. A later observer sees only the current stain, never
an old burst. Several injuries can play several bursts over one persistent stain.

The runtime uses the existing NeuroStudio schema and shared media/ground drawing
primitives. Deliver assets and passive metadata rather than executable code or
a new timeline type. The producer should inspect the supplied visual references
and may adjust strip cell size/frame count if needed, documenting that decision.

## Delivery and review

Keep source files and production exports in the art task's existing output area.
Return a manifest with semantic ID, file path, size, pose, frames, fps, pivot,
scale and a plain-language description. Include contact sheets and previews on
the supplied terrain, with one ordinary character for scale. No hashes or
automatic integrity audit is required.

Main-task integration checks will cover known tiles, hidden donors, later first
sight, mixed residues, raised/lowered/bloodied spikes, four cameras and replay
from saved subjective inputs. The anti-slop review must keep these as four
material profiles on shared presentation behavior. The ECS/anti-OOP review must
keep mechanics on native composition and tile conditions; no art-specific rule
belongs in backend state.

## Delivery received and selected integration

The existing artwork task delivered `body-residue-v2` with the four requested
profiles, nondirectional release strips, four floor directions and the requested
ordinary blood size variants. Its core manifest is
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/body-residue-v2/exports/body-residue-manifest.json`.
The integration selected 16 floor images and four strips, preserving their PNGs
unchanged. Ordinary blood uses the small variant until native amount rules are
selected; unused size/shape variants remain in the artwork delivery. The separate
full export inventory, coatings/walls and fireball/scorch queue were not pulled
into this task. Existing bloodied spike overlays remain integrated.

The [implementation result](BODY_RELEASES_AND_RESIDUES_PLAN_2026-09-19.md#13-bodyresidue-implementation-and-review)
owns gameplay, replay evidence, review status and remaining limits. The request
above is retained as the delivered contract, not an outstanding asset blocker.

### Subsequent artwork review — pending, separate from spell integration

The artwork task reports that the user rejected the `body-residue-v2` "A lot"
composition (seven stacked whole bursts) and the connected geometric blood
tiles. These are not approved replacements. Its static source study is at
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/blood-hit/GODOT-PARTICLE-STUDY.md`.
It proposes wound-origin particles, independent velocity/gravity, landing marks
and count/volume tiers; natural contiguous puddles remain outstanding. This is
queued artwork guidance only, with no new runtime or approved replacement assets.

The artwork task subsequently reports a procedural candidate in
`/home/tommaso/.codex/worktrees/23a9/dnd_engine/output/environment-sprites/blood-fluid/`,
with integration limits in its `HANDOFF.md`. Preview:
`http://127.0.0.1:8778/blood-fluid/?review=particles-organic-pools`.
It uses wound-origin ballistic droplets, landing deposits, depth sorting and
12/28/56/96 art-volume tiers. Its blood painter now uses continuous lobed fields
across cell boundaries. These remain visual candidates, not approved final art
or selected native blood-amount rules.

Reported exports are 16 aftermath variants and 129 occupied transparent 64px
top-down tile slices plus world images. They are neither final isometric sprites
nor a reusable 47-tile atlas. The art task reports passing its preview/export
checks; the game task has not independently validated or integrated this delivery.
No production/backend change follows from this queue update.
