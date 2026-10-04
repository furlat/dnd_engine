# Summoning implementation checkpoints

## Human visual corrections — 4 October

Wolf is now exactly 2.00× its original size. Original terminal death art is bound
for all six demons and fifteen Goblins, with intact Prone/downed/recovery retained.
Already fallen bodies do not restart an upright death animation; existing shared
falls keep their clock. No gameplay/event expansion. Current source snapshot has
134 files, SHA256 `96605c30162fc3e2100d12d19d75a844a0083d94299d7d2b68185903aead49e6`.
Latest focused checks pass 75 + 87 cases, changed-code typing is clean, and the
six Wolf2.00 recordings pass. All 18 death-art recordings also pass; the combined
24-clip gallery has 934 checks and zero gaps. Independent source/art/pixel reviews
approve within their stated scopes; see the current [acceptance report](audits/SUMMONING_FINAL_ACCEPTANCE_2026-10-04.md).

## Final-phase completion evidence — 4 October

The approved summoning/Fly phase and all 17 dedicated Goblins are implemented.
The [final acceptance report](audits/SUMMONING_FINAL_ACCEPTANCE_2026-10-04.md)
is the current status record; the earlier packet checkpoints below retain their
historical pending wording and must not be used as the current task list.

- Authoritative injury/death complete before summon retirement; permitted lifecycle
  evidence drives accepted arrival, departure and Fey control-break media.
- Shared ground-to-ground flight uses original airborne source poses, continuous
  lift and existing world clipping. Fly wings preserve equipment, avoid duplicate
  native wings and release with their owning condition. Native-wing demons remain
  distinct; non-winged fixed rigs use the accepted wind art.
- All 17 Goblin kits, original rigs and normal actions are registered. Riders are
  single combatants, Goblin17 uses normal Pistol Attack, all dedicated Goblins/demons
  remain 1.00 scale, and approved animal enlargements remain.
- Full active validation accounts for 2,840 native and 3,228 client cases after
  explicitly documented fixture corrections and passing affected-file reruns.
  Runtime/tool typing 0 errors/warnings. No additional backend/render mechanics were
  introduced to satisfy stale fixtures. Exact logs and per-failure evidence:
  `.runtime/summoning-final-acceptance-20261004/validation/reconciliation.json`.
- The standard final gallery contains 69 clips / 35 native scenarios, 1,563 passing
  checks, 0 gaps and 17,945 frames at 32 FPS. It preserves 68 original passing recordings
  plus a separately captured supported-height case. All originals remain archived.
  Independent reviews cover actual representative lifecycle, blood/death, flight,
  geometry, caster/dual/ranged actions and all 17 Goblin rigs.
- Final source snapshot 131 files SHA256
  `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3`.
  Final independent completion receipts are closing; source and pixel approvals
  are already recorded. No commit has been made.

## Earlier implementation checkpoint — 4 October

The human authorized the complete final-phase plan. Base commit is
`cd6d4ec363c` (`post - first content`); work remains uncommitted on the shared checkout.
They explicitly selected both remaining proposals: single-combatant wolf-riders
and an ordinary Pistol item for Goblin17. No external chat communication.

- Packet A damage/terminal ordering is implemented: retirement follows enclosing
  damage completion; exact causing Death entry sight preserves witnessed terminal
  departure after DEAD removes living contacts. Hidden events remain withheld.
  121 passed in 39.47s across summoning presentation, lifecycle, terminal consequences
  and retirement ownership. Both independent anti-slop/ECS reviewers approve this
  bounded packet. This does not establish final visual acceptance.
- Packet E native and client/data source are complete and independently approved.
  All 17 kits, ordinary Pistol and 83 possessions use existing native builders.
  42 native checks pass. Native rig/attack/cast/reaction playback checks pass,
  including actual Goblin07/15 Multiattack selecting mainhand then offhand clips.
  Source evidence lives in `.runtime/goblin-final-20261003/SOURCE_STUDY.md`;
  499 original PNGs imported through current rig resources. Final gallery pending.
- Packet B shared flight is implemented and double reviewed: 40 focused checks
  passed, covering continuous ground-to-ground lift, real reaction speed/held poses,
  and late/early terrain support clearance. Original measured frame registrations
  preserve the selected sprites/shadows; no flight-to-Run substitution.
- Packet C Fly condition appearance is implemented and double reviewed: 15 focused
  Fly checks plus 23 existing condition/lifetime checks pass. Bag8 wings preserve
  backpacks and do not duplicate native/equipped wings. Native same-spell Fly
  replacement is unchanged; passive overlapping visual memberships are tested
  separately. Two original wind pages are reused without introducing another spell.
- Packet D source is implemented and its retained-pose correction is independently
  approved by both reviewers. S1 uses existing cast
  media and original measured hand points (42 existing/focused checks and 6 final
  S1 checks). S2/S3/S5 follow minimal witnessed native provenance, shared scheduling
  and finite contact-media tails. Public birth facts expose no private recipe or
  summoner record. Optional explicit initial condition identity fixes lost trait
  bindings without guessing from legacy semantic keys. Thirty-two original media
  pages (4,640,796 bytes) are installed privately and locally with exact hashes.
  Retirement now preserves the permitted pre-cleanup appearance/pose, including
  Prone, while current damage/death owns its life state. Final focused lifecycle
  checks: 52 passed in27.11s; dnd/game typing:0 errors/warnings. Earlier combined
  flight/appearance/lifecycle check:77 passed in40.39s. Both reviewers verified
  the pre-cleanup Prone/Die retention and passive appearance override. Combined
  final source/footage acceptance is still in progress.
- Packet F is captured and frozen:35 native experiments,69 actual observer inputs,
  875 complete lineages/5,669 retained nodes. Fresh-data presentation preflight
  binds all873 presentation heads without gaps, exceptions, unsupported conditions
  or missing observed metadata. Final serial32-FPS gallery and the remaining client
  suite are running; no final-phase completion or full visual acceptance is claimed.
  A missing Fly cast binding now selects the existing Special1 gesture; four passive
  innate traits explicitly declare state-only membership. No additional artwork or
  gameplay system was added. These data corrections are independently approved by
  both reviewers, and24 affected Fly/lifecycle checks pass.

October4 receipts: `.runtime/fly-condition-20261004/receipt.json`,
`.runtime/summoning-cast-20261004/receipt.json`,
`.runtime/summoning-final-media-20261003/manifest-install.json`.
Full native/AI/architecture/progression/packaging run:
`/tmp/final-phase-native-suite.log`:2,838 passed,2 failures in412.42s. Both failures
were outdated Goblin test inputs/expectations: the stance test assumed the newly
art-matched Goblin01 still owned a bow, and the structural-owner inventory omitted
the two approved Goblin Multiattacks. The stance scenario now explicitly equips
its required bow; the inventory checks exact unique ownership of the two new
definitions without changing historical evidence. Both complete affected files
then passed all10 checks in7.12s (`/tmp/final-phase-native-reconciliation.log`).
All2,840 native cases are accounted for; no backend fix was needed for these two.
The full game run reached the first884 client cases, then its old loaded demo
entered a stale two-cast turn loop after killing the now7-HP Goblin on cast1.
The demo now uses a seeded nonlethal4-damage first hit; the real second cast still
exercises miss/death. Other initial failures were obsolete Goblin01 bow/attack
pose assumptions and the explicit new flight-media field. Corrections use canonical
Goblin03 for bow scenarios and original Goblin01 strike/release timing. The affected
attack/projectile/map files pass76 checks; combat-history file passes5.
The remaining2,344 client cases restart at `test_combat_play.py` in
`/tmp/final-phase-game-remainder.log`, with a JUnit receipt. Final reconciliation pending.

Current final source snapshot: `.runtime/summoning-final-acceptance-20261004/source-final-snapshot.json`,
SHA256 `8059df6cbab94bafb519a18fc7faba0b6615a34d241a19fb6b6f9e08e83b4585` (119 files).
Original recorded input remains unchanged. Binding evidence:
`.runtime/summoning-final-acceptance-20261004/binding-preflight.md`.
Final gallery render: `runs/20261003T231132Z-2970cd` beneath that acceptance root.

Packet A reviewed SHA256: system.py `cbde6afd2cff196910df31f46a5a5e3248c729e936eec8bd6e25354c56c22516`;
player_projection.py `4b26621c2acc24799342f1ea996a696c1d9568873eea503b3648b4086270ee38`;
regression `9d5f7742af1a57815ba07cd69d60519b5b67a970bafe8dcc14e7cb50c0540b5c`.
Earlier checkpoint wording below records prior state, not the active status.

## Current amendment — native injury, flight and accepted summoning artwork

**Human scale correction, 3 October:** all six demons now use original scale
1.00. The canonical Dretch factory overrides the inherited Small multiplier;
Corrosive/Dread inherit that corrected appearance. The shared authored-fiend
factory likewise uses 1.00 for Claw Mote/Huntsman/Fellwing. Rules Size, stats,
footprints and source pixels are unchanged. Both independent reviewers approve
this bounded correction and the amended plan (receipt linked below).

Direct construction of all 24 canonical recipes verified six demon values of
1.00 and no animal value below 1.00. Animals: Hound/Boar/Jaguar 1.00; Wolf 1.30;
Stag/Ostrich/Lion 1.50; Tiger/Raptor 1.55; Bison 1.65; Brown Bear 1.70;
Polar Bear/Blue Raptor 1.80; Rhinoceros 1.85; Stegosaurus 2.35;
Elephant/Triceratops 2.40; Mammoth 2.60. Existing approved enlargements remain.
**Subsequent human Goblin correction:** the canonical dedicated Goblin01 now
uses1.00 in `bestiary_content._build_goblin`; direct canonical materialization
verified1.00 and unchanged modular archer/caster0.82. Source pixels and gameplay
Size remain unchanged. The human requested the remaining dedicated Goblins too;
the [17-sheet Goblin amendment](GOBLIN_ROSTER_FINAL_PHASE_PLAN_2026-10-03.md) is
part of the final-phase plan, with source/item/action evidence and double review.
No new Goblin roster, artwork import or ability has been implemented in this
planning pass. Previously rendered clips retain the old scale until regenerated.

The human requested a planning checkpoint for the
[final phase](SUMMONING_FLY_FINAL_PHASE_PLAN_2026-10-03.md), and explicitly accepted
the artist's summoning effects. Fly only joins this phase, with shared flight
motion for modular bodies/native-wing demons and actual trajectory/clipping work.
The original gallery lacked incoming injury/death coverage; its pass count did
not establish those outcomes. A new lethal-summon capture exposes native terminal
retirement before DamageApplied completion captures location evidence, so permitted
replay loses its blood result. Native blood itself exists. That ordering repair
and new visual integration remain pending; do not weaken observer filtering.

Already bounded corrections: canonical normal/special blood composition and five
native injury histories (201 focused checks, scoped typing clean); measured modular
fall painter depth (8 direct checks, 120 affected game checks, source reviewed);
Wolf scale 1.30 and Huntsman ground Run. Four correction clips completed with
124 recorder checks/862 frames at
`.runtime/animation-review-summoning-corrections-20261003/runs/20261003T191110Z-35b4bf/`.
These do not establish lethal summon blood or Fly acceptance. The temporary
flying-to-Run binding was withdrawn; source airborne poses are being selected.

The original implementation receipts/table below describe the preceding scope.
The linked final-phase amendment now owns the remaining work; no commit or new
integration is claimed at this planning checkpoint.

## Original implementation scope and receipts

The human authorized the complete unified plan on 2026-10-03, including
independent review after each packet and final combined review. The reviewed
scope is `SUMMONING_BACKEND_PLAN_2026-10-03.md` (SHA256
`d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`)
and its linked visual addendum (SHA256
`28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`).
This authorization supersedes the documents' planning-only gate, not their
bounded design. No external chat or artist communication is authorized.

Start: clean tracked checkout at
`5ff3d983c0912d2419473b394384ec08742d84a6`, WSL source under
`/mnt/c/users/tommaso/documents/dev/dnd_engine`.

| Packet | Implementation | Independent review |
| --- | --- | --- |
| 1. Ordinary anatomical attacks and 24 canonical creatures | Implemented; 76 focused checks | Anti-slop and ECS approved; scoped receipts below |
| 2. Passive contracts and native owner seams | Implemented; exact retirement, shared condition and publication corrections verified | Final native ECS and anti-slop approved |
| 3. Lifetime and live encounter membership | Implemented, including native retirement, later-encounter survival and autonomous controller turns | Final native ECS and anti-slop approved |
| 4. Three spells and selection | Implemented: 42 choices across 24 bodies; one destination per cast; native Dismiss Summon | Native lifecycle/selection suite: 75 checks pass; final native ECS and anti-slop approved |
| 5. Recorded presentation and existing artwork | All 24 body bindings, lifecycle/material, shared action sequencing and target HP correction complete; 18 exact reviewed shadow bindings active | Source/data independently approved; final 38-clip acceptance and 60 active-data checks pass |
| 6. Combined acceptance | Complete: broad suites reconciled, 96 final game checks, 60 installed-asset checks and 38 native clips | Final anti-slop, native ECS/import-DAG and event/render approvals recorded below |

The sections below are chronological checkpoints; the packet table above records
the original batch status before the current amendment.

## Public acceptance boundaries

Packet 1 constructs every creature through canonical content and executes its
ordinary attacks through native actions. Expected results are authored costs,
damage, rider outcomes and unlootable anatomy; held weapons keep their current
rules. Subsequent packets exercise real casts, retained events, native turns,
replay and shared rig bindings using the unified plan's acceptance matrix.

Each checkpoint records actual commands/results and reviewer findings. A plan
approval is not an implementation approval. Deferred summon VFX remain deferred;
all ordinary action bindings and spirit material are part of this delivery.

## Packet 1 independent acceptance

[Anti-slop review](audits/SUMMONING_PACKET1_2_ANTISLOP_IMPLEMENTATION_REVIEW_2026-10-03.md)
and [ECS review](audits/SUMMONING_PACKET1_2_ECS_IMPLEMENTATION_REVIEW_2026-10-03.md)
approve the ordinary creature/body-attack slice. Their approvals do not cover
summoning lifecycle or presentation, which remain unfinished.

## Native membership checkpoint

Reviewed corrections cover stable execution identity after insertion/removal,
last-current departure through the actual controller-action boundary, and
preventing reactions while terminal membership removal waits for native unwinding.
23 checks pass in `/tmp/summoning-membership-reviewed-corrections.log`; scoped
typing reports zero errors in `/tmp/summoning-native-corrections-types.log`.
Independent re-review is pending. Lower spatial removal publications now retain
the original child-first order instead of grouping independent owners first.

## Lifecycle and targeting checkpoint

`tests/engine/test_summoning_lifecycle.py`: 64 checks pass in 21.68s
(`/tmp/summoning-lifecycle-tests.log`). This includes all 42 authored form/slot
choices, native indexed dismissal, mandatory expiry and zero-HP departure,
acquired gear remaining on the floor, Fey control loss, and later-encounter
survival. The approved first batch chooses one creature and one destination;
extra positions are rejected before spending the action. Higher slots unlock
stronger creatures, not additional bodies.

Review found exact equipment/container validation missing before retirement.
The fix retains original containers and exact admitted equipment slots; 14
ownership tests pass (`/tmp/summoning-retirement-locations.log`). Two additional
integration corrections are under verification: terminal retirement must not
create Haste lethargy or restore Antimagic-suppressed conditions on the departing
actor; removal event lineages must stay open until native lifetime consequences
are published. No final approval is claimed while these corrections are open.

## Final review corrections and regression runs

The exact creator handler now executes after ordinary CAST_SPELL/EFFECT vetoes
have completed, through the existing direct system-handler dispatcher. Late
veto/exception preserves the previous summon while retaining the paid action;
duplicate delivery cannot create a second body. Existence removal revokes agency
at native commit, before the replacement birth is published. Condition lineages
stay open through settled native consequences and close child-first, including
spatial owners. ECS review approves these native corrections.

Wet uses the existing shared-child graph, retaining one public manifestation
until the last dependent surface releases it. Independently applied Wet remains
independently owned. Acquired lit-torch drop publication failures are drained
after committed retirement so the actor cannot remain as a ghost authority.
The broad focused correction run passed 130 checks and exposed two erroneous
new fixture calls (missing activation parent); the corrected Wet/terminal batch
then passed all 35 checks. These receipts account for all 132 unique tests:
`/tmp/summoning-native-corrections-final.log` and
`/tmp/summoning-wet-terminal-final.log`.

The first full engine/AI/architecture run passed 2,520 tests with five failures:
actor-owned weapon handlers changed the ownership count; mixed spatial removal
completion order regressed; five new current content declarations were absent
from a frozen historical inventory test; and two documentation gates required a
new initiative field description. All five were corrected without rewriting the
historical content evidence. Current full-suite follow-up is running; no final
whole-suite green claim is made yet.

All 24 rigs admit their real source media: 198 resources / 13,485,442 bytes,
17,760 nonempty frame cells, 1,120 attack selections, and 242 body-context queries.
Seven native fighting scenarios produce 14 paired four-camera recordings.
Visual inspection caught overlapping Multiattack child motion: their shared
generic-action sequence is being corrected using existing authored child joins.
Legacy optional event fields and unknown rig selector validation are also under
final event/render review. New summon/despawn VFX remain deferred as approved.

## Full native follow-up

`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync pytest tests/engine tests/ai tests/architecture -q --assert=plain --tb=short`
completed with 2,531 passes and one new test asserting a completed light
publication inside an unfinished outer condition-removal scope. The operation
intentionally closes independent spatial publications at that outer boundary;
the assertion now checks the exact same single publication after the boundary.
All 19 tests in that file pass afterward. Receipts:
`/tmp/summoning-full-native-final.log`,
`/tmp/summoning-silent-removal-corrected.log`. All 2,532 collected native checks
are reconciled; no native production change was made for the last test fix.

The human approved bounded enlargement of the new large beast artwork only
where visual quality remains sound. Explicit per-creature values use the
existing passive Appearance.visual_scale; native rules size and the approved
one-anchor placement are unchanged. All 76 canonical creature checks still
pass (`/tmp/summoning-scale-content.log`). In-game comparison is in progress.

## Human artwork amendment and final shared gestures

The human reassigned the small vendor T-Rex sprite to a **Raptor**, keeping its
original 1.55 appearance scale. The ordinary creature uses the existing
Allosaurus-derived numerical baseline (Large,51HP,AC13,speed60), Bite or depicted
Tail as separate normal attacks, and unlocks at Animals5/Fey6. Native names,
canonical item references, exact rig assignment, attack selectors and review
scenario all change together; vendor PNG names/rig identity remain provenance.
The general size/dice regression now uses the existing Mammoth; its normal Prone
save is represented in the fixed-dice input. All76 canonical tests pass, and all
75 summon lifecycle tests passed in the preceding combined run. No new action,
condition or rendering behavior was introduced by this content amendment.

Three summon spells now use existing Special1/release-frame8 body-only cast
programs through the normal spell data schema. Dismiss uses an existing authored
actor-only action binding. Multiattack children wait for their complete native
condition/removal/recovery subtree before the next attack begins. Simultaneous
multi-recipient healing remains simultaneous. Final focused presentation99 +
healing2 checks pass; whole active dnd/game Pyright reports0 errors. Independent
event/render review approves this source snapshot, pending final artwork and
whole-game evidence. Receipts are in
`.runtime/summoning-packet5-component/final-corrections/`.

The first whole-game run mixed earlier loaded Python with actively edited JSON
and was stopped; it is not a valid final acceptance snapshot. It did not respond
to ordinary termination and retained excessive failure data, so only that exact
owned test process was force-stopped. A fresh full game run uses frozen bindings:
`/tmp/summoning-full-game-frozen.log`. No pass/failure reconciliation is claimed
for the abandoned mixed run.

Animal paired-original shadow layers were found available but omitted from the
first import. Recoverable original shadows are being separated and registered
through the existing rig shadow slot; no inferred under-body pixels or new art.
Final neutral-shadow/Fey/scale inspection and source hashes remain pending.

Current human-amended plan hashes:

- `SUMMONING_BACKEND_PLAN_2026-10-03.md`: `6fa3185abc6e79c3d47667277541476192622f2af922a3d4f3365e17f7a7811c`.
- `SUMMONING_VISUALS_ADDENDUM_2026-10-03.md`: `a8b38482d69680fe2dfdfa850f2889b00c69fc32a37c4a4fc72f741d475b11e9`.

## Ordinary birth cleanup and user-delivered VFX handoff

The full progression/root-packaging run exposed two existing birth-failure
regressions: the convenience composition path retained a failed unpublished
character and its light. `compose_entity` now discards only an undeployed birth
whose exact fact was never indexed. Explicit prepared/committed summon birth
retains its irrevocable owner semantics. The unchanged ordinary-character
regressions and the summon/birth/composition suite pass: 336 checks in 41.12s
(`/tmp/summoning-birth-regression-fixed.log`). An additional interruption after
storage verifies that an observed birth is retained: all six prepared-birth
checks pass (`/tmp/summoning-observed-birth-corrected.log`). Independent bounded
anti-slop/ECS review approves this correction.

Active `pyright dnd game` after the passive shadow-opacity field reports zero
errors/warnings (`/tmp/summoning-final-types-after-shadow.log`). The full game
run remains in progress and has one failure to reconcile; this is not a final
acceptance claim. Manual gallery inspection also found a Multiattack child HP
rewind; its retained-state correction is in progress.

At the human's request, the [VFX production handoff](SUMMONING_VFX_HANDOFF_2026-10-03.md)
is ready for them to send. It specifies shared casting/arrival/departure effects
and optional Fey halo/control-break cues. No external chat was contacted.

## Final source corrections and independent native acceptance

A complete native controller check now proves that an allied summon chooses and
attacks an enemy without harming its nearby caster. A released Fey keeps the
same identity, controller, remaining lifetime and spent movement, then chooses
the former caster as an enemy. The reviewer-authored two tests also pass in an
independent root run (`/tmp/summoning-autonomous-root-review.log`). Final
ECS/anti-OOP review approves native completion; its bounded import inspection
found no cycle in the 203-module closure.

The full game run exposed two presentation regressions. Skeleton Archer's fixed
QuickShot now has an exact rig-scoped profile without the unavailable modular
Slash layer; projectile/clock and generic modular profile remain unchanged.
Its unchanged native encounter acceptance passes. Generic Action sequencing now
advances for typed command children; state consequences retain the current
effect anchor. This restores the existing hatch-open/fall contract while
keeping Multiattack command subtrees sequential. Portal/sequence/summon checks:
40 passed; independent event/render review approves both changes.

Manual native gallery inspection also proved a Multiattack HP rewind caused by
a stale placed contact. Each attack now takes target HP/life state from its
retained child prestate while keeping contact placement/facing. Focused checks:
29 passed plus 45 existing attack regressions. The exact Brown Bear recording
now keeps 483 HP through its second missed swing, independently confirmed in
all four rendered views. Final active typing after these source changes: zero
errors/warnings (`/tmp/summoning-source-freeze-types.log`).

Finished logs are preserved in
`.runtime/summoning-acceptance-20261003/validation/`; the final whole-game log and
shadow installation/38-clip receipts will be added when complete.


## Final whole-game reconciliation

The frozen full game run completed with **3,109 passed and six failed** in
3,053.47 seconds. It collected 3,115 cases; earlier collection estimates included
later-added tests and are not the receipt's count. Every failure is accounted for:

| Failed acceptance | Cause and correction |
| --- | --- |
| Native workshop encounter (one case) | Fixed Skeleton Archer used an unavailable modular Slash layer. Its exact rig profile now keeps the existing arrow and clocks without that layer. |
| Occupied portal activation (one case) and lever/spikes (two observer cases) | Generic Action sequencing delayed passive consequences. Only actual command children advance the sequence; effects retain the command's contact anchor. The unchanged trap cases pass on this correction. |
| True Strike ranged child (hit and miss) | Two tests retained frame 8 from before the accepted bow fix. Pre-summoning HEAD already uses release frame 10. Only that obsolete literal was changed; ordinary-attack equivalence, exact overlay and HP assertions remain. No production timing was altered. |

The final combined affected run includes all six failed IDs and the complete
trap, True Strike, attack-animation, portal, action-sequence, summoning and
native-encounter files. Its result is recorded in the final acceptance table.
This is a full-suite run followed by verified corrections, not a claim that a
second complete suite was run against the final snapshot. The earlier mixed
Python/JSON run remains excluded.

The separate progression/root-packaging run had 237 passes and two ordinary
birth-publication failures. Both unchanged failing cases pass in the corrected
336-check progression/root/birth/summon run. Together with the explicit
post-publication interruption tests and independent native reviews, that closes
the two failures rather than relabeling them as unrelated.


## Final acceptance evidence

| Boundary | Completed evidence |
| --- | --- |
| Engine, AI, architecture | Full run: 2,531 passed and one new test fixed at its proper outer-publication boundary; all 19 affected tests pass. All 2,532 collected cases reconciled. |
| Progression and root packaging | Full run: 237 passed, two ordinary unpublished-birth regressions repaired; corrected combined regression run: 336 passed. Six explicit prepared/indexed-birth checks also pass. |
| Game/presentation | Full run: 3,109 passed, six failures reconciled above. Final affected seven-file run: **96 passed in 120.20s**, including every failed ID. |
| Active creature assets | **60 passed in 53.08s** after installing the exact 18 reviewed shadow bindings. All 24 creature rigs reference 296 installed resources (17,141,142 bytes). |
| Native autonomous turns | Two accepted controller scenarios pass independently: allied choice and surviving hostile Fey choice with spent resources preserved. |
| Types and patch hygiene | Active `pyright dnd game`: zero errors/warnings; asset/import scope typing also clean; `git diff --check` clean. |
| In-game visual acceptance | **38 clips, 1,350 recorder checks, 8,638 frames**, two observer perspectives and four cameras. No failed checks or HP increases in these damage-only fights. |

[Open the standard native gallery](http://127.0.0.1:8768/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/index.html).
The [visual acceptance](../.runtime/animation-review-summoning-20261003/acceptance.md)
names the actual cases, inspected scales, body/shadow policy and limitations.
The [activation receipt](../.runtime/summoning-art-20261003/shadow-activation-receipt.json)
proves active JSON matches the captured gallery bytes. No unavailable pixels
under opaque source bodies were invented during original-shadow separation.

Receipts are preserved in
[the validation folder](../.runtime/summoning-acceptance-20261003/validation/).
The [final source snapshot](../.runtime/summoning-acceptance-20261003/source-snapshot.json)
records all 1,326 source/test/authored-data file hashes at acceptance, based on
`5ff3d983c0912d2419473b394384ec08742d84a6`; it is not a Git commit.
Its SHA256 is `bfd1b47b41d2e5b34967acd2a8e01d1062fd2c9d95690d4036cbf7ec9bdce206`.

The completed batch includes all three spells, 24 independent ordinary creature
recipes, 42 form choices, one chosen ground destination per cast, stronger
upcasting choices, autonomous native AI, concentration/lifetime/hostility,
dismissal/defeat/expiry, exact equipment cleanup and retained-event rendering.
The Raptor uses the small vendor T-Rex art at its original 1.55 scale. New summon
arrival/departure effects and optional spirit accents remain the approved later
[VFX delivery](SUMMONING_VFX_HANDOFF_2026-10-03.md). This does not defer any required
native lifecycle or existing-art integration work. The short clips demonstrate
genuine dismissal and Fey control loss; full-duration expiry is verified by the
native tests, not misrepresented as a shortened video.


## Final independent approval — closed

No unresolved blocker remains within the unified approved scope.

- [Anti-slop final completion approval](audits/SUMMONING_FULL_ANTISLOP_IMPLEMENTATION_REVIEW_2026-10-03.md): source, broad-suite reconciliation, exact activated data and final gallery accepted. SHA256 `0f1c406dd12cbf58f353252f60087e389e2e7473ab34b4cfa55aa094a914ae29`.
- [Native ECS/anti-OOP/import-DAG approval](audits/SUMMONING_PACKET1_2_ECS_IMPLEMENTATION_REVIEW_2026-10-03.md): native owner/lifecycle closure, ordinary birth cleanup and autonomous-turn evidence accepted; 203-module dependency closure has no cycle. SHA256 `36af45a6d4d11b72a7b763ae4a22caef0fef099b46ea98d84fb16a963d3d83ee`.
- [Event/render final completion approval](audits/SUMMONING_EVENT_RENDER_IMPLEMENTATION_REVIEW_2026-10-03.md): all six game failures reconciled; all 27 gallery rig snapshots match active data, including the 18 shadow updates; actual Fey and Brown Bear final frames independently inspected. SHA256 `08ab737a0a61fd95887d034b02e692ba41b94b5d2f8226a6ef22e69910e2a649`.

The packet table is the current disposition. Earlier pending language remains
only as labeled chronological evidence. This concludes the approved batch;
new roster families and the deferred VFX handoff require their own next work.
