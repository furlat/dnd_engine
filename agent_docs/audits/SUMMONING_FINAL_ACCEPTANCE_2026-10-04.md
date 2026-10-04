# Final summoning, Fly and Goblin acceptance — 4 October 2026

Status: human-requested Wolf/death corrections complete. Focused checks pass; independent source, original-art and bounded pixel reviews approve. Original full-suite reconciliation remains preserved below.
No commit has been made. Base: `cd6d4ec363c0640595ec1f9b1b6ad9cda11baaef`.

## Human visual corrections after the original gallery

Wolf now uses exactly **2.00× original artwork scale**, as explicitly requested.
The six new native recordings cover ordinary injury/death, summon defeat/departure
and Fly grant/travel/removal. All six pass and both body and shadow were inspected
in four cameras. Earlier 1.30/1.80 recordings remain historical.

All six demon rigs now select their genuine original explosion death; fifteen
Goblins select original Die2. The two riders have only one source death and retain
it. Forty-eight original PNGs (9,505,401 bytes) were installed byte-for-byte with
private source receipts; no artwork was generated or repainted. Death effects use
existing clip layers and their original final ground residue. Source-side edge
contacts in Huntsman/Goblin sheets remain explicitly recorded in the source audit.

The existing rig body-context data selects terminal death through one shared
helper. No new gameplay effect, event, species handler or backend death rule was
added. Prone/DYING/STABLE retain intact falls and recovery. The later human
correction forbids standing up to die: an existing shared fall keeps its clock;
already fallen bodies skip an alternate death's upright wind-up and settle directly
to its terminal resting frame. Full death playback is reserved for upright kills.
The ordinary Wolf demo deliberately includes a native turn standing up before its
later lethal attack; this is not a death-triggered stand-up.

Independent review found and corrected fresh-cache Prone retirement preload and
overlapping downing/death priority. Focused validation after these changes:
75 lifecycle/rig/projectile checks and 87 animation/blood/damage/Fly checks passed;
changed runtime/tools/test typing reports zero errors/warnings. Earlier affected
attack/palette/lifecycle files also passed 107 checks. Original failing logs are
retained, with corrected complete-file receipts under
`.runtime/terminal-death-review-20261004/validation/`. These bounded reruns support
the new corrections; the full-suite figures below belong to the earlier phase.

Current frozen source: 134 files, snapshot
`.runtime/terminal-death-review-20261004/source-final-snapshot.json`, SHA256
`96605c30162fc3e2100d12d19d75a844a0083d94299d7d2b68185903aead49e6`.
The source/asset and footage receipts remain separate so original events,
recording clocks and source images can be checked independently.

The [correction gallery](http://127.0.0.1:8768/summoning-visual-corrections-20261004/runs/20261004-wolf-and-death/index.html)
contains 24 clips: six Wolf2.00 perspectives plus eighteen paired perspectives
for all six demons and Goblin01/03/17. All **934 recorder checks pass, with zero
presentation gaps**. Videos and native inputs are unchanged; the standard gallery
composition preserves source trace hashes and export identity. These ordinary
death demos include a native Prone recovery before the later upright death; the
no-refall-on-prone-death rule is additionally verified by the focused native and
projectile tests. Art playback was recorded before that last fallen-only sampling
correction; these upright death recordings do not claim to exercise it.

Independent anti-slop review approves the current source and all six demon / three
Goblin sampled deaths. Independent ECS/event review approves the shared selection,
no-refall correction, original assets and Wolf2.00 pixels; it also inspected the
first three demon terminal programs and independently verified all 24 composed
recording/export identities. Both additive final reports are complete. The parent
combines these independent scopes without claiming every frame was manually
watched. No unresolved implementation blocker remains.

Final audit hashes: anti-slop `7cff5617a12bf9c4d6b1b1402afc3afb8dd91b70fdca134c4ff4feac0fb54a6e`;
ECS/event `d820f596b987c96ea60858573cba25c0e5eb4fe5dc65bc083ea8a0f177a78fbf`.

## Delivered scope

- Ordinary creature definitions remain independent of summoning. Existing native
  summon membership owns lifetime/control/retirement; authoritative damage and death
  complete before summon retirement. Public evidence retains exact witnessed birth,
  departure and control-loss provenance, without revealing hidden births.
- The accepted summon artwork uses shared cast/contact media, recorded event timing,
  finite reveal/dissolve, and palette replacement. Fey control loss changes the same
  living entity's allegiance; it does not respawn or heal the creature.
- Ground-to-ground Fly uses shared continuous trajectory and source-frame registration.
  Modular bodies use their existing airborne pose and temporary Bag8 wings; the two
  winged demons use their own original selected poses. Native/equipped wings are not
  duplicated, and real backpack equipment remains intact. Existing wind art serves
  bodies without modular wings. No hovering or other spell integration was added.
- All 17 original Goblin sheets have canonical gear/content and shared action bindings.
  The two riders are single combatants. Goblin17's Pistol uses normal ranged Attack;
  modular loot uses the disclosed existing Musket donor, with no new weapon artwork.
  All dedicated Goblins and demons use 1.00 artwork scale. Approved animal enlargements
  remain, including the subsequently requested Wolf 2.00; the vendor T-Rex is the user's Raptor.

The original source pose for a second-weapon attack and modular Pistol geometry remain
explicit approximations. They do not alter the weapon's native rules. No mount system,
new ammunition system, unrelated spell, or commissioned weapon artwork is included.

## Source review and validation

[Anti-slop review](SUMMONING_FINAL_ANTISLOP_REVIEW_2026-10-04.md) and
[ECS/event/render review](SUMMONING_FINAL_ECS_EVENT_REVIEW_2026-10-04.md) preserve
independent packet approvals and final source review. Authors do not certify their own
production changes; the other reviewer covers those edits.

Source inventory before the terminal-death extension: `.runtime/summoning-final-acceptance-20261004/source-final-acceptance-snapshot.json`,
131 files, SHA256 `7975e7086cbceecf396594a9dc8d613ab48dc63f5e241a083834f97cd0faf7c3`.
Earlier 111/119/128/129-file snapshots remain intact for packet review. The last
12 additions after the 119-file snapshot are test/catalog reconciliation; the
previous production file hashes are unchanged.

All **2,840 native and 3,228 client cases** are accounted for after documented
corrections. This is a reconciled full-suite result, not a claim that the first
run passed unchanged or that a fresh combined run was repeated. Previously passing
cases remain accounted for alongside focused checks for subsequent changes; every
failure has passing affected-file evidence.

| Evidence | Original result | Reconciliation |
| --- | --- | --- |
| Native/AI/architecture/progression/packaging | 2,838 passed, 2 failed | Both complete affected files: 10 passed |
| First client segment | 875 passed, 9 failed (884 cases) | Complete attack/projectile/map files: 76 passed; combat history: 5 passed |
| Remaining client segment | 2,326 passed, 18 failed (2,344 cases), no errors/skips | Every failure maps to passing affected files below |

The original client process was stopped when its old loaded demo attempted to
continue after killing the newly canonical 7-HP Goblin on the first cast. Its
first 884 cases are retained against the saved collection. The complete remaining
2,344 cases were restarted from `test_combat_play.py` using the corrected native
demo. Three already-passing combat-play cases repeated at that boundary are counted
only once. The demo keeps an actual nonlethal 4-damage first volley followed by the
real second-cast miss/death; no event result was fabricated.

Remaining failures were outdated Goblin gear, HP, pose and attack-result fixtures,
plus exact float equality for the midpoint 1.9999999999999998 versus 2.0. Corrections
retain exact damage/life/identity/replay outcomes. Native handaxe seed27 gives a
noncritical 5-damage hit, preserving DYING versus instant death; close encounters
assert their actual lethal 13-damage opportunity attack. The original Goblin brace
uses frame5; a root-specific profile override preserves its authored Goblin profile.
The existing synthetic multi-result ownership test now starts from a verified
nonlethal hit instead of contradicting its retained death commit. Midpoint tolerance
is absolute 1e-9 with zero relative tolerance; lift and landing stay exact.

Affected-file evidence after the remaining run: six fixture files account for
29 distinct cases (28 passed plus one literal correction, then all10 lifecycle
checks passed); forced-movement/history files16 passed; movement routes22 passed;
resolution/rig-context files50 passed. These repeated checks are not added to the
3,228 total. No backend or renderer mechanic was altered to satisfy these fixtures.

Permanent logs, the complete remainder JUnit, exact per-failure mappings and hashes:
`.runtime/summoning-final-acceptance-20261004/validation/reconciliation.json`, SHA256
`d13b9f089b36deb54902cd95e77970bc7c0f7a1e0a3ea49906cf89cbb10dc17f`.
All original failing results remain available alongside their passing evidence.

Focused final Fly/lifecycle binding check: 24 passed. The saved-input audit identified
and corrected a missing Fly cast gesture binding plus four passive trait declarations.
Fly uses existing Special1; the condition alone owns wing/wind appearance. InnateFlight,
MagicResistance, HitSaveRider and KeenPerception explicitly have no separate effect.
Both reviewers approved these bounded data corrections.

Final typing across dnd/game and changed authoring tools: zero errors or warnings
(`validation/final-phase-types-final.log` under the acceptance root).
The existing test-resolution module retains ten identical pre-edit typing diagnostics;
the final fixture correction adds none. This is not a claim of whole-repository typing
cleanliness. The paused server remains outside this active-engine/client phase.

## Recorded gameplay evidence

Capture is frozen: 35 native experiments, 69 actual observer inputs, 875 completed
lineages and 5,669 retained nodes. Public saved bytes are decoded and replayed without
re-executing native actions. All 873 grouped presentation heads bind with zero gaps,
exceptions, unsupported scene conditions or missing observed metadata entries.

Original review SHA256: `660ad30a753ec56a1e9ee3d6b0c6e6075893431421ddba2f1f8cb74761a49e7c`.
Evidence root: `.runtime/summoning-final-acceptance-20261004/`.
See `matrix.json`, `freeze-receipt.json`, `input-verification.json`,
`binding-preflight.md` and `binding-identity-receipt.json`.

The [standard final gallery](http://127.0.0.1:8768/summoning-final-acceptance-20261004/runs/20261004-final-acceptance/index.html)
contains 69 passing recordings across 35 experiments: 1,563 checks, zero gaps,
17,945 frames at 32 FPS (560.781 seconds in total). All four camera views use the
same retained presentation sample and original scene floors.

The first render, `runs/20261003T231132Z-2970cd`, completed 68 clips and rejected
one height test scene with an unsupported three-support stair arrangement. Its
failed artifact and original inputs remain intact. The corrected height case
was captured separately on the existing wooden terrace in
`battlefield.visual_vertical_seam`: native support heights 0→2→0. Its single clip
passed all 15 checks in `height-correction/runs/20261003T233842Z-2d43aa`; independent
inspection approved ascent, landing and descent in all four views. No map or
renderer workaround was added.

The final gallery packages those 68 recordings plus this separately corrected
height case. `composition-receipt.json` records source manifest, input, trace and
video hashes. Videos and saved inputs remain the original bytes; derived traces
change only their gallery envelope and retain their original run and trace hash.

All 17 Goblins exercise original artwork and native gear; additional cases cover
caster spells/reactions, native-wing flight, Fly grant/removal, wall/window/actor
geometry, height changes, opportunity interruption, ordinary and summoned
injury/death, special blood, and Fey control loss. Reviewers inspected representative
action and death frames for all 17 Goblins, the original body/shadow composition,
Wolf/Fey/Mammoth lifecycle, native wings, Fly lifetime, and boundary/height cases.
Detailed sample times and the scope of each pixel verdict remain in their reports.

The window case tests visual occlusion beside an actual boundary; it does not claim
physical flight through a window. Hidden birth/reacquisition, replacement/expiry and
inventory transfer/Protection remain explicit native/presentation test evidence,
not invented claims about events shown by every clip. The independent reviews do
not claim that every frame of all 69 clips was watched.
