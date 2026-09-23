# Spells and barrels — completed integration and feedback handoff

**Historical collection — superseded for current review.** The user requested only
the latest fourteen spells and barrels. Use the [focused 90-clip gallery](http://127.0.0.1:8767/runs/20260922T113258Z-latest-spells-and-barrels/index.html)
and its [handoff](SPELL14_AND_BARRELS_FEEDBACK_2026-09-22.md), which also replaces
36 injury clips after correcting missing blood-response composition in review actors.
The larger inventory below remains a historical record.

[Open the complete feedback gallery](http://127.0.0.1:8767/runs/20260922T111403Z-spells-and-barrels/index.html). This collection contains
181 saved clips, covering all 59 registered spell presentations and six
liquid-barrel materials. Every clip contains four synchronized camera corners;
paired cards contain the actual subjective histories of the participants.

Use Search or the `review:new-14`, `review:earlier-spells`, and `review:barrels`
tags to select a group. Pause a clip, pin the frame, mark **Issue**, name the
camera corner and add a note. Select the relevant cards and export the review;
it retains their original saved inputs and complete traces. Filtering a spell
before playing a group keeps the number of simultaneous videos manageable.
Automated checks passing is not a claim of human visual approval.

## What changed in this unit

All fourteen requested presentations now use the existing native spell behavior,
retained subjective events, shared presentation primitives and authored JSON:

- Mage Armor, Shield and five Protection from Energy variants have application,
  maintained state and removal. Shield contacts come from actual intercepted
  attacks, including ranged attacks and Magic Missile. Armor equipment and real
  resisted/unresisted damage are exercised.
- Grease and Spike Growth use native ground footprints and contacts. The matrix
  includes saved/failed entry, actual fall and next-turn recovery, jumping over,
  landing inside, raised terrain, and discovered/hidden Spike Growth.
- Fog Cloud, Cloudkill, Stinking Cloud, Darkness, Incendiary Cloud and Insect
  Plague use four actual source camera views and per-pixel world coordinates.
  Native ownership, visibility, walls, elevation and upcast radius constrain the
  rendered field. Moving clouds consume native position changes. Their visual
  clocks continue through movement and clear; they do not impose a six-second
  casting lock.
- Blur samples bounded body history; Mirror Image follows the live pose and
  retained duplicate count; Enlarge/Reduce scales body, gear and attachments
  together. Incoming and outgoing targeting are covered in both size modes.

Native additions retain condition duplicate count, transformation mode, chosen
energy, resolved size and actual interception provenance. These are gameplay
facts, not renderer commands. Complete canceled child lineages remain under
their causal parent. Ground hazards no longer trigger on airborne intermediate
jump cells. Field geometry/elevation remains separate from whether an anchor
was actually seen. Recordings made before the optional interception field remain
readable without inventing old attribution.

The data remains passive JSON; Python/Pygame executes shared capabilities.
Godot is an offline asset source, with no Godot or TypeScript runtime required.
The extensions are documented in `game/data/PRESENTATION_CONTRACT.md`.

## Spatial and visual verification

The spatial review compares actual saved native footprints with raw asset
coordinates, rather than judging size from a screenshot. Grease covers its
four native cells; Spike Growth places its 49 authored clumps. Cloud/swarm
pixels are admitted by native observed cells and sorted using world depth.
Blocked cells are not filled by enlarging the picture. Cloudkill's wall case
excludes 13 cells. Fog base/upcast/raised checks pass both perspectives and all four cameras:
20-ft radius with 49 native cells, 40-ft upcast with 157 cells bounded by this
map, and native support elevation 2. Color, pivot and world coordinates scale
together; rendering adds no gameplay cells. The review camera includes full volume canvases even when the field
obscures its own center floor. The large upcast Fog clip uses a conservative
wide view to keep the whole field visible, so its actors look small; use fullscreen.
This is a review-framing limitation, not a smaller gameplay footprint.
The Stinking Cloud clips exercise a successful Constitution save; they do not
demonstrate its failed-save nausea branch.

## Barrel status — existing production clips

The barrel group contains 28 clips: water, oil, grease, poison, normal blood
and dread blood, including actual destruction, entry/exit, jumping and doorway
cases. These are the existing production captures, not a newly reauthored
barrel batch. Some occupied cells have visually dry centers in these source
variants even though their native surface effects apply there. Corrected exports are queued; they were deliberately not substituted
while completing the spells. Existing Wet has no body presentation recipe;
its native condition and water floor state work. Persistent burning-surface
artwork is also still outside this delivery. The gallery keeps those recorded
gaps visible.

## Verification record

- Full engine suite: **1,476 passed**.
- Full game suite: **2,120 passed** before the final fixture-only correction.
  The persistent gameplay module then passes **11 tests**, including three
  new saved-event entry/sight/recovery cases for Darkness, Fog and Stinking Cloud.
- Final anchor/geometry correction: **247 focused regressions passed**, plus
  the full engine rerun above.
- Offline media importer: **9 tests passed**.
- Darkness entry/exit coverage was corrected before this final gallery: the
  earlier demonstration stopped one cell outside its smaller radius. The final
  pair uses a real entry and exit, with a saved-event visibility regression.
- Native/game and changed importer, fixture and review modules: typing clean.
- The final gallery passes browser filtering (62 / 91 / 28 clips) and actual
  mixed-source trace export; all 181 videos, posters, inputs and traces exist.
- The repository-wide typing command also includes the retired server and AI
  modules: it reports 132 server errors and one unused AI import. Those are
  recorded separately; this spell unit did not revive or rewrite that layer.

Evidence and independent reviews are under `.runtime/spell14-20260922/`:
`native-review.md`, `visual-18/`, `visual-ground-body/`,
`visual-volumes-final/`, `visual-fog-final/`, `visual-last-volumes/`,
`visual-darkness-entry/`,
`final-volume-registration/` and the test logs.
The gallery references immutable source runs and preserves their timestamps,
video dimensions, public inputs and trace identities. Barrels remain from their
original source capture; earlier spell inputs were replayed through the current
presentation implementation.

## Files and reproduction

The review files live under `.runtime/animation-review/`, not a temporary system
folder. The local HTTP server serves those saved files; it does not rerun combat.
If the server stops after a reboot, run from this repository:

```sh
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv /home/tommaso/.local/bin/uv run --no-sync python -m devtools.animation_review.serve --directory .runtime/animation-review
```

Authoring lives in `game/data/persistent_spells/` and the existing
`game/data/world_bindings.json`; shared schema/semantics are recorded in
`game/data/PRESENTATION_CONTRACT.md`. The implementation record is
`agent_docs/SPELL14_INTEGRATION_2026-09-22.md`. The gallery is generated output;
it keeps the original real-event inputs available for replay and debugging.

## Complete spell inventory

Search the gallery by spell name or the representative case ID below. Additional
variants and both observers are retained alongside those representative cards.

| Spell | Representative case | Group |
| --- | --- | --- |
| Acid Splash | `spell-handoff-acid-two-saves` | Earlier authored spell |
| Bane | `pending-bane-lifecycle` | Earlier authored spell |
| Bless | `pending-bless-lifecycle` | Earlier authored spell |
| Blindness/Deafness | `control-blindness` | Earlier authored spell |
| Blur | `persistent-blur` | New fourteen |
| Burning Hands | `batch-burning-hands-axis` | Earlier authored spell |
| Charm Person | `control-charm` | Earlier authored spell |
| Chill Touch | `ice-handoff-chill-hit` | Earlier authored spell |
| Cloudkill | `persistent-cloudkill` | New fourteen |
| Color Spray | `control-color-spray` | Earlier authored spell |
| Command | `control-grovel` | Earlier authored spell |
| Cure Wounds | `support-cure-wounds` | Earlier authored spell |
| Darkness | `persistent-darkness` | New fourteen |
| Eldritch Blast | `spell-handoff-eldritch-5-repeated` | Earlier authored spell |
| Enlarge/Reduce | `persistent-enlarge-reduce-enlarge` | New fourteen |
| Expeditious Retreat | `pending-retreat-dash` | Earlier authored spell |
| False Life | `pending-false-life-depletion` | Earlier authored spell |
| Fire Bolt | `firebolt-level` | Earlier authored spell |
| Fireball | `spell-handoff-fireball-open` | Earlier authored spell |
| Fog Cloud | `persistent-fog-cloud` | New fourteen |
| Grease | `persistent-grease-false` | New fourteen |
| Greater Invisibility | `conceal-greater-invisibility` | Earlier authored spell |
| Guidance | `support-guidance` | Earlier authored spell |
| Guiding Bolt | `spell-handoff-guiding-mark-consumed` | Earlier authored spell |
| Gust Of Wind | `batch-gust-of-wind-axis` | Earlier authored spell |
| Haste | `pending-haste-actions` | Earlier authored spell |
| Healing Word | `support-healing-word` | Earlier authored spell |
| Hellish Rebuke | `pending-hellish-failed-save` | Earlier authored spell |
| Ice Knife | `ice-handoff-ice-hit` | Earlier authored spell |
| Incendiary Cloud | `persistent-incendiary-cloud` | New fourteen |
| Inflict Wounds | `pending-inflict-hit` | Earlier authored spell |
| Insect Plague | `persistent-insect-plague` | New fourteen |
| Invisibility | `conceal-invisible-enemy` | Earlier authored spell |
| Jump | `pending-jump-long` | Earlier authored spell |
| Light | `support-light` | Earlier authored spell |
| Mage Armor | `persistent-mage-armor` | New fourteen |
| Magic Missile | `missile-repeated` | Earlier authored spell |
| Mirror Image | `persistent-mirror-image` | New fourteen |
| Misty Step | `pending-misty-both` | Earlier authored spell |
| Poison Spray | `batch-poison-range-diagonal` | Earlier authored spell |
| Prayer Of Healing | `support-prayer-of-healing` | Earlier authored spell |
| Protection From Energy | `persistent-protection-from-energy-fire` | New fourteen |
| Ray Of Frost | `ice-handoff-ray-hit` | Earlier authored spell |
| Resistance | `support-resistance` | Earlier authored spell |
| Sacred Flame | `batch-sacred-range-diagonal` | Earlier authored spell |
| See Invisibility | `conceal-see-invisibility` | Earlier authored spell |
| Shatter | `pending-shatter-open` | Earlier authored spell |
| Shield | `persistent-shield` | New fourteen |
| Shield Of Faith | `support-shield-of-faith` | Earlier authored spell |
| Shocking Grasp | `batch-shocking-adjacent-diagonal` | Earlier authored spell |
| Silence | `control-silence` | Earlier authored spell |
| Sleep | `spell-sleep-normal` | Earlier authored spell |
| Spike Growth | `persistent-spike-growth` | New fourteen |
| Stinking Cloud | `persistent-stinking-cloud` | New fourteen |
| Thaumaturgy | `support-thaumaturgy` | Earlier authored spell |
| Thunderwave | `batch-thunderwave-axis` | Earlier authored spell |
| True Seeing | `conceal-true-spell-enemy` | Earlier authored spell |
| True Strike | `support-true-strike-melee-hit` | Earlier authored spell |
| Web | `spell-web-mage` | Earlier authored spell |

## Exact source runs

- `20260922T095752Z-6d4e25`
- `20260922T093321Z-32266a`
- `20260922T094255Z-68da20`
- `20260922T101726Z-b8777a`
- `20260922T104813Z-cbffd4`
- `20260922T110051Z-489b2e`
- `20260922T075227Z-718226`
- `20260922T100321Z-54d944`
- `20260922T111213Z-b0daed`
