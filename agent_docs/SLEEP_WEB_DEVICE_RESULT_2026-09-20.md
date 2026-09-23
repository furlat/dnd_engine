# Sleep, Web, and destructible sustaining devices

## Gameplay contract

The body of a device and its spell grants are independent data. The actual
spell retains its targets, saving throws, effects and application structure.
The device supplies its physical emission point and optional authored range /
operator-directed launch sector. The operator retains causal attribution, DC
and action costs. Nothing silently rewrites ordinary Magic Missile into Sleep.

Sleep uses its existing HP pool, one spell application and ordinary non-
concentration duration. The item-granted cast now selects recipients around
its actual destination. Real damage wakes the damaged sleeper; another sleeping
creature remains asleep. Condition membership supplies the final Die body pose
and Zzz label while alive and idle, with active actions and actual death taking
precedence. Both ordinary mage casting and one cannon shot are exercised.

Web uses its existing zone, saves, difficult terrain, restraint, escape action
and concentration cleanup. It is one spatial zone with a native 20-foot cube
footprint, not sixteen independent spell applications. Device concentration
reuses existing slots and linked-condition removal. Initial devices sustain two
independent zones. A full device refuses another cast before costs or creating
effects. Ordinary mage concentration still behaves as before. Nonlethal device
damage does not manufacture a creature Constitution save; destruction ends its
linked effects within the original damage lineage.

Authored object HP is exact: the existing health helper previously truncated
non-die-multiple amounts, so an authored 12 became 8. The existing health bonus
now retains the remainder. Actual damage and public snapshots test 12 → 7 → 0.

## Events and presentation

Public device observations contain HP, authored capacity and active slot
identities, without private recipients. Observed zones carry their disclosed
device/slot link and only an observed or previously known origin. No native
registry is consulted during saved replay. Visibility rules are unchanged.

The renderer consumes complete lineages on its independent historical clock.
Sleep and Web have explicit Studio recipes, measured hand sockets, their own
palette and media. The shared projectile path faces the instantaneous tangent
for these recipes. Web's nonlooping travel strip fits the actual flight time.
Optional per-phase rotation keeps ground art fixed while the shot turns.

A witnessed native spatial CREATED event starts the existing finite ground
transition for that exact zone at contact. Deployment settles into its final
frame; there is no second area pass or fade-in. Seeing an old zone for the first
time does not replay creation. The single registered pattern is partitioned by
observed native cells, retaining support height, lighting and depth. Independent
zones keep independent creation times. The same shared mechanism serves other
authored spatial creations without a spell-name branch.

Object attacks now use an authored body-action recipe instead of the retained
disabled/zero-duration source recipe. The current default is Attack1, contact
frame 8. Only already-observed item targets survive projection. Device and zones
remain through wind-up and native destruction appears at contact. This is an
authored default; it does not claim all weapon profiles now select an object
attack animation.

Both official bodies now author an optional passive destruction-remnant component.
Normal item destruction clears grants, conditions and placement, then creates an
ordinary inert wreck at the original position, support height and orientation.
The wreck has no health, charges, usable actions or concentration slots, and does
not block movement or appear as loot. Destroying a held/unplaced item does not
invent a ground placement.

The existing DESTROYED item event retains the exact replacement UUID. Public
projection requires observation at removal, not merely stale remembered sight;
an unseen replacement identity is withheld. The finite world transition binds
only that explicit destruction and replacement, never arbitrary removals or
same-tile guesses. At hit contact the device's native effects end and its observed
replacement plays the approved eight-frame / 12-fps fracture, then stays as the
matching static wreck. A later observer sees the wreck without replaying the break.
Historical facing is preserved. The transition carries small contact data, not
the artwork tables.

## Validation and current review

- Added the requested **Fireball-loaded cannon destruction** experiment. It fires
  once, deals actual 16 damage to each recipient, then takes real 4- and 8-damage
  object attacks on following turns. The [combined six-clip review](http://127.0.0.1:8767/runs/20260920T170809Z-c00dc0/index.html)
  includes Fireball and both Sleep body variants, paired observers/four cameras,
  1,328 frames and no reported gaps. The existing replay/pixel test matrix covers
  this new scenario. Selected typechecks pass. No game rules, rendering or art
  changed. The Fireball case authors actor-focused review framing so the full
  source canvas does not make the cannon tiny; all device/wreck bounds remain
  inside each viewport. This small tooling choice passed anti-slop/ECS review.
- Follow-up: both cannon bodies now flash on confirmed damage, including the
  lethal contact. The existing authored damage palette/duration drive the tint;
  no backend mechanic or artwork changed. The [four-clip hit-flash review](http://127.0.0.1:8767/runs/20260920T165429Z-b93c49/index.html)
  passes across 972 four-camera frames, reprojecting the previous native captures
  without rerunning gameplay. Twenty focused device tests and fifteen projection /
  coverage checks pass (one overlap); selected typechecks and independent
  anti-slop/ECS review pass. Tests compare actual pixels before, during and after
  the flash for both bodies/observers/cameras, including backward seeking and
  zero, canceled or unseen damage. Other prop bodies are outside this flash binding.
- The final [Sleep and breakdown gallery](http://127.0.0.1:8767/runs/20260920T163754Z-bf4705/index.html)
  passes **10/10 clips / 2,210 four-camera frames**, with no reported gaps. Both
  device bodies cast real Sleep; Fire Bolt wakes one recipient; later longsword
  object attacks take the device through 12 → 8 → 0 HP and leave the other sleeper
  asleep. Both observers replay their own saved inputs. Additional paired clips
  cover ordinary mage Sleep and different spells through one cannon body.
- Final breakdown checks passed: 81 native item/equipment/device regressions;
  72 presentation/projection regressions; 10 focused destruction tests after the
  last stale-sight case; 6 recorded device-replay tests after the trace fix.
  These batches overlap. Selected changed presentation modules and tests have
  zero Pyright errors/warnings. Independent anti-slop and ECS review passed.
  Actual gallery frames were inspected during Sleep, fracture and settled wreck
  for both bodies across the four cameras.
- 47 active direct-item, equipment, equipment-replication and device tests pass.
  This includes fixing the stale 150-entry test after the prior True Seeing
  potion became the 151st public item; all independent-construction checks stay.
- 167 focused native and presentation regression tests pass, including Sleep,
  Web, device targeting, serialized replay, condition appearance and tangent
  projectiles. A separate 54-test batch passed for spatial creation, trap transitions, projection,
  seeking and presentation coverage; affected modules typecheck clean.
- The first full paired capture contains 12 clips / 2,338 four-camera frames,
  with no reported media gaps:
  [review run](http://127.0.0.1:8767/runs/20260920T160407Z-a16cbc/index.html).
  A suspected missing-cable defect was disproved with actual app evidence:
  both links draw through wind-up (51–54 raster sections/camera) and end at hit
  contact. The playback trace lists actor commands, not the ground renderer
  commands; its missing cable rows were not evidence of missing rendering.
  At gallery zoom the pale strands are thin, so the raw frame was also inspected.
  Eight additional shipped-art tests now cover both observers/four cameras and
  destruction removal. Independent art registration review confirmed all four
  terminal field images exactly match the supplied persistent image and pivot.

The experiments are actual engine actions, recorded once as native and public
event sequences. They cover Fireball then Sleep through the same body, Sleep
from mage/projector, refusal and repositioning, Web from mage/cannon, failed and
successful saves, escape, movement, two simultaneous device zones, and a real
longsword attack destroying the cannon. Media revisions replay saved inputs.

The first breakdown capture exposed a diagnostic serialization error: timeline
traces tried to dump the entire loaded emitter artwork, including its immutable
mapping tables. The trace now retains body identity, pitch and contact metadata
while omitting those redundant loaded tables. Replay reads the separately saved
public event input, so this changes no replay facts. The final gallery above
replayed the same captured inputs successfully; no serializer fallback or runtime
source validation was added.

## Explicit limits and handoffs

The user paused Web artwork and body-wrap work. Its current ground-growth candidate
is not presented as approved. Experimental wrap-specific status changes were
withdrawn; core Web mechanics and device sustaining remain. Simply being in Web
or having any Restrained condition does not cause a Web body wrap.

First seeing only an edge of a zone whose origin has never been disclosed cannot
register this whole-field picture. Current rendering leaves that picture absent;
this is a concrete presentation limit, not permission to expose hidden geometry
or infer an origin from the visible cells. Previously known origins are retained.

The cannon artist delivered and the user approved fractured-body breakdowns and shared terminal wreck
sprites in `output/environment-sprites/device-destruction/device-destruction-v2.zip`
under worktree `/home/tommaso/.codex/worktrees/23a9/dnd_engine`. They are now imported
and bound for both bodies, including all four pitch banks, eight yaws and four
cameras. The authored break begins from idle; arbitrary firing-recoil interruption
is not claimed by these turn-sequenced attack clips.

Existing creature-specific follow-up actions such as Call Lightning are outside
the validated device scope. General concentration-owner support is not evidence
that every such follow-up action supports devices unchanged. Six separate retired
manual item-lifecycle probes still omit required item IDs before exercising any
behavior; they are not failures in the active 47-test scope above.
