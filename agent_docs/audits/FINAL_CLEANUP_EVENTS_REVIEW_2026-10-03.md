# Final cleanup review: events, rendering and passive contracts

**Disposition: APPROVE the final reviewed event/render implementation.**
October 3, 2026. The final scheduling and displacement repairs pass independent
checks. ER4 and ER5 below record the discovered defects and verified closure; no blocker
remains in this review's scope. ER1–ER3 from the
[earlier implementation review](CLEANUP_IMPLEMENTATION_EVENT_RENDER_REVIEW_2026-10-03.md)
are resolved. Full-game and visual acceptance remain separate parent-task gates.

## Reviewed snapshot

HEAD/baseline: `981079bc0208dbb23f3ccc927347eef77fef4c30`. All reviewed cleanup and
repair changes remain uncommitted. The approved repair plan reviewed here has
SHA256 `78f6cb43170e26eff5b8f37dbf886838d98070ec33e1b262ea8e93c4e7200c06`.
The final source hashes below matched before and after the final independent
checks. Earlier receipts are preserved separately from the final follow-up.

- SHA256 of `git -c core.safecrlf=false diff --binary
  981079bc0208dbb23f3ccc927347eef77fef4c30 -- dnd game`:
  `de93125f8651ccafd9c203e798476557573c9fc40d817697c0019740c07d5bde`.
- Current Python source manifest: **377 files** under `dnd` and `game`, including
  untracked additions. SHA256:
  `cce92fd9f113f35a5e430a215cbab484c0bf7f533217e37c48c2a64a1442c8ca`.
  The manifest uses sorted repository-relative POSIX paths, one line per file:
  SHA256 of raw bytes, two spaces, path, newline; `__pycache__` is excluded.

Selected reviewed file hashes:

| File | SHA256 |
| --- | --- |
| `game/event_record.py` | `e84bdd668b9613bcbf071cdbad39d6da0e46bb661ecf94e426cfe047d5aa0ba0` |
| `game/recording_compat.py` | `120ed3733cc03376555ccb2ef192c3da3b3189f1ddc6600ba8d3e31cd0621952` |
| `game/player_projection.py` | `6bf1d9ac9a230231d1350ccb53bd1f5472a74b3dcfc1fdc85d1f822dd6041048` |
| `game/choreography.py` | `8059e1cb85407b68735e3179f7d51a52d960eb4c53b34c2ab7c58086dce773f5` |
| `game/export_schema.py` | `0b4c8766d0b0f1561603d883fe08f5e6be771b66cca81c0ffb6cb5389035e83e` |
| `dnd/spells/wall_constructions.py` | `73efd8788e82296ae785dd896df2720604b359550c219a16b052ad492b5380eb` |
| `dnd/spells/transmutation.py` | `bb9de4eb82392238b0e3599852634d609427ab322a21a0f5896977ee3ef8a5b8` |
| `dnd/actions.py` | `f7b0a8b73d4ef3e008f3dd3ac97d73cf790359fe1c6e3f8e79818817bb200c53` |
| `dnd/spells/abjuration.py` | `987db9a0a33ca8b3106988b0ff33e2fbacfd573093cda4dd80963c6742f7231a` |
| `tests/game/test_resolution_contract.py` | `5d3f515075a4facc15befdb31fd687449ff2c3e101bcebc231202edb1508365d` |
| `tests/game/test_forced_movement_playback.py` | `95647be6367835851b18c8e87d25c182494f0dab425e8cc12bac306ddffa2973` |

Read the recovery requirements, approved cleanup/repair designs, prior review
findings and repair evidence. Rechecked the relevant whole-source contracts and
the implementation against the baseline: native causal ownership, capture,
compatibility, public projection, source-version reduction, result indexing,
damage/cast binding, choreography, sampling, persistent lifetime traversal and
schema export. The 377-file manifest identifies the checkout; it does not assert
line-by-line review of every production function. No production or test file was
edited. This final audit is the only file written by this final review.

## Finding closure

### ER1 — legacy callback ownership: resolved

`game/event_record.py:202–206` no longer assigns a nested legacy damage request
to its nearest Attack/Spell parent. The shared legacy rule at
`game/recording_compat.py:44–54` accepts a root request's own identity and diagnoses
missing proof for a nested operation. `game/player_projection.py:897–906`
distinguishes an omitted historical field from an explicit current unknown.
Public version-1 migration uses the same missing-proof policy.

The independently run real-retaliation regression casts Fire Shield, executes
the incoming attack, records both results, and cold-replays them. Current
retaliation retains its own request lineage despite being directly parented to
the incoming attack. Current playback has one ordinary attack cue and one
5-damage standalone retaliation cue, with exact final actor state. Removing the
new ownership fields to exercise the old contract produces the precise diagnostic
through both native-to-public projection and public version-1 input. The complete
native record still reduces to the same settled state.

This intentionally means old child-damage archives without sufficient evidence
cannot claim successful timed playback, including superficially ordinary attack
records. Native settlement remains available; ambiguous ownership is neither
invented nor relabeled as an explicit current unknown. The repair evidence
discloses that limitation for the preserved device archive.

### ER2 — undisclosed-cause HP timing: resolved

`game/choreography.py:888–893` now obtains result identities directly from the
bound standalone damage cue when its resolution is unknown. Those identities use
the same existing `DamageTiming` placement as other results. There is no new
temporary-HP scheduler or private-source disclosure.

The independently run native hidden-owner scenario passes through saved public
bytes with the source identity absent. At authored number frame 3, normal and
temporary HP are `(40, 5)` at 0 and 249.999 ms and `(38, 0)` at 250 ms. Backward
and repeated sampling preserves those values, with an empty native event queue.
This closes the previously reproduced early temporary-HP commit.

### ER3 — missing authoring schema roots: resolved

`game/export_schema.py:22–30` now exports 16 schema roots using the existing
passive definitions. These include all seven missing owners from the approved
repair: DamageContext, DeathContext, AttackRecipe, VoluntaryMovementContext,
ConditionRecipe, BodyRig and RigTables, plus related timing contexts. The schema
export test runs in a fresh process and rejects imports of Entity, native events,
the content runtime, server or Pygame.

An additional independent production-data probe loaded the full default authored
data and validated JSON round trips for **161 records across 14 actual types**:
the damage/death/healing/life/equipment/movement contexts, all loaded attack and
condition recipes, loaded body rigs, rig tables and the admitted world-binding
document. These are the actual admission models, not duplicated transport types.
The public packet and spell-draft roots remain part of the export. This establishes
the agreed contract availability; it does not implement a TypeScript renderer.

## Additional contract checks

- **Persistent exposure:** `dnd/spells/transmutation.py:183–185` gives each Spike
  Growth entry its own existing damage-request resolution and retains the field
  origin separately. The real Thunderwave push and ordinary Move scenarios pass.
  The push presents a 2-damage cast application and two independently owned
  2-damage exposures. Results appear once, final actor state matches pure native
  fact reduction, and repeated/backward sampling remains passive.
- **Recipe-independent ownership and repeated recipients:** a separate probe used
  one real three-application Magic Missile recording against the same 20-HP target.
  It replayed the identical public lineage with the installed recipe, with half
  projectile speed and zero stagger/equal contact times, and with the draft
  removed. All three variants retained the same three result owners and final
  target HP **5**. The first two had one cast cue and no gaps; missing art produced
  explicit gaps and three standalone damage cues. It did not donate results to
  another action. Native event cursor stayed zero.
- **Construction publication and identity:** `SolidWallZone` commits actual
  sections and their owner data inside the existing activation-footprint boundary
  before the completed CREATED observation. The old later replacement
  STATE_CHANGED publication is removed. Ice/Stone formation, independent local
  fracture, intact concentration retirement and both observer views pass. Native
  formation displacement and placement/removal veto checks also pass, including
  refusal of the second section leaving no created objects or live field.
- **Earlier cleanup contracts retained:** attack/cast binders select typed ordered
  results rather than recipe availability; application contact lookup uses the
  application resolution rather than target/time equality. Spatial reduction uses
  the producer's exact membership commit version. The formation-specific synthetic
  sensory split stays deleted, and straight/ring formation-before-injury checks
  pass. The four lifetime policies continue to use the shared resolved walker
  with accumulated offsets and actual construction/slot owner identities.

## Independent execution receipts

Environment: Python 3.13.12, WSL source checkout on `/mnt/c`,
`UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv`, using
`/home/tommaso/.local/bin/uv run --no-sync`. Full default authored bundles were
used. No expected failures or failure filters were added.

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m pytest \
  tests/game/test_resolution_contract.py \
  tests/game/test_player_projection.py \
  tests/game/test_construction_presentation.py \
  tests/game/test_wall_heat_presentation.py \
  tests/architecture/test_presentation_schema_export.py -q --disable-warnings
```

**34 passed in 209.07 seconds.** The parent full-game validation was running
concurrently; this is process wall time, not isolated renderer timing.

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m pytest \
  tests/engine/test_remaining_walls.py \
  -k 'canceled_later_section_placement or canceled_whole_wall_retirement or ice_formation_displaces or refused_section_removal' \
  -q --disable-warnings
```

**4 passed, 29 deselected in 1.88 seconds.** This is an explicitly bounded native
contract check, not a substitute for the whole engine suite. The production
round-trip and same-record/multiple-recipe probes described above were additional
stdin scripts through the same environment and passed.

## Earlier bounded decision and limits

The first bounded review closed the previous three event-review findings but
did not catch incorrect intermediate HP or early position in the push sequence.
Its checks asserted final settlement and ownership, which was insufficient for
that claim. The final follow-up below covers the subsequently discovered timing
defects with intermediate state assertions and independent samples.

This review does not independently certify every spell, every combination of
coalesced observations, complete physical pixel appearance, the paused server or
a future TypeScript client. It does not reuse the earlier seven clips as broad
coverage: those represented only three scenes. Full active-suite totals and the
final expanded in-engine visual evidence remain the parent task's separate
acceptance receipts. The approval here is for the reviewed event/render/passive
contract implementation, supported by the independent checks above.

## Final follow-up — ER4: displacement state precedes displacement playback, resolved

**P1, closed after independent reproduction and correction.** Existing timing
defect exposed by the expanded real scenario and
made visibly longer by the new damage barrier. The inherited `state_at_effect`
behavior is present in baseline `981079bc0208`; it is not a new native movement
failure. The current cleanup nevertheless requires the event-to-render timing
contract to hold through this accepted Thunderwave/Spike Growth sequence.

Independent reproduction uses the saved public round trip of
`resolution_history('push')`, the installed default authored data,
`bind_choreography`, and absolute `sample_choreography` calls. Before the head,
Recipient has 20 HP at `(4, 3)`. Both its application-state contact and bound cast
contact correctly remain `(4, 3)`. At **1118.055556 ms**, the displayed state moves
directly to final `(6, 3)` while HP remains 20 and the sampler emits no forced
contact. The forced cue begins at **1701.388889 ms**, now providing contact
`(4, 3)` again, and travel begins at **1951.388889 ms**. This independently confirms
the final-position leak observed in the parent's acceptance capture.

Before correction, the displacement branch retimed `at` from the displacement's
exact arrival map but retained the enclosing cast's `state_at_effect`. The
state-node path and `commit_milestones` preferred that inherited cast time, so
received spatial/sensory changes published before their owned movement. The
native facts and bind_cast target were correct; changing the target contact
would have masked the defect.

The correction at `game/choreography.py:841–849` clears the inherited effect
time when ordinary forced movement takes ownership; `:454–460` assigns the actual arrival
time to both scheduling values before matching sensory commit handling. No
spatial facts or recorded coordinates are synthesized or changed.

The independent saved-public-replay probe now passes with number frames 0 and 3.
Retained contact remains `(4, 3)` at 0, 1118.056, 1701.388889 and 1951.388889 ms.
Immediately before the first arrival it remains `(4, 3)`, while the drawn contact
approaches `(5, 3)` continuously. It commits `(5, 3)` at 2074.404041 ms and `(6, 3)`
at 2371.388889 ms. The probe repeats the same samples in reverse and checks an
empty native event queue. The exact intermediate HP assertions also pass.

### Final scheduling/helper review and receipts

The shared `preceding_damage_commit` at `game/choreography.py:319–324` reads only
already-bound result UUIDs, their typed applied result and recorded source order.
It delays subsequent movement and independently owned damage for the affected
actor until earlier HP has committed. It neither assigns causal owners by target
or time nor computes HP from damage arithmetic. Existing `DamageTiming` remains
the authority; there is no parallel spell-specific timing path. The real push
and walk tests now check each HP milestone (push: 20 → 18 → 16 → 14), pre-milestone
values, reverse seeks and exact-once result ownership at number frames 0 and 3.

`dnd/actions.py:4999–5024` now discards provisional effect data for a canceled
spell effect and uses existing condition admission before linking concentration.
Resistance delegates to that same path at `dnd/spells/abjuration.py:2615`.
The independent roster-support run exercised condition vetoes at declaration,
execution and effect, canceled self-spell effects, failed concentration
replacement, flight ownership and retaliation. No event-owner or cancellation
regression was found. The devtools additions for damage resolution, construction
and flight call existing native scenario helpers and capture their actual facts.

Additional independent commands in the same environment:

```bash
uv run --no-sync python -m pytest tests/game/test_resolution_contract.py \
  tests/engine/test_roster_support_spells.py -q --disable-warnings
```

**59 passed in 27.91 seconds.** This was after the HP sequencing/helper repairs
and before the subsequent displacement correction.

```bash
uv run --no-sync python -m pytest tests/game/test_resolution_contract.py \
  tests/game/test_forced_movement_history.py tests/game/test_forced_movement_playback.py \
  tests/game/test_player_projection.py -q --disable-warnings
```

**44 passed, 2 failed in 58.24 seconds.** Both failures were the old assertion
that the whole actor remained identical to pre-movement state after the first
cell had actually been reached. They were the success and goblin two-cell shove
cases; only `last_visual_position` differed, `(5, 3)` versus `(4, 3)`. The corrected
test explicitly checks that reached cell and the final `(6, 3)` cell, while
preserving the other actor-state, sprite, continuous-contact and reverse-seek
checks. An independent rerun of the entire changed four-case test passed:

```bash
uv run --no-sync python -m pytest \
  tests/game/test_forced_movement_playback.py::test_native_displacement_plays_brace_travel_release_and_idle_without_latest_leaking \
  -q --disable-warnings
```

**4 passed in 10.03 seconds.** All cases from the final focused run therefore pass
at the recorded source/test snapshot, with the failed intermediate receipt
retained here rather than represented as a clean uninterrupted run. The separate
per-arrival probe described above also passed.

**Final decision: APPROVE within the event/render/passive contract scope.**
ER1–ER4 are closed; no unresolved concrete blocker remains in this review.
The source manifest and diff hashes at the top are the final reviewed snapshot.
The earlier bounded snapshot was manifest
`f75a66134fea9e0b936d851a8331d7f43a90d3f0df78298d9dbe2d9fbb7ce173`.
The full-suite and expanded visual acceptance receipts remain the parent's
separate verification; this review makes no exhaustive coverage claim.

## Final capture delta and 42-clip trace review

**Disposition remains APPROVE within the cleanup event/render scope.** The
subsequent item-power capture introduces no new renderer or gameplay mechanism.
At this capture-delta review, the frozen 377-file core source manifest remained
`52bbbff046f704495f016969303b30b9f987b80c1e886a69b3d403470bc40bd8`, and its
baseline diff remained
`9d2677c2eadd69f84838a8129fad14c41f6b93885e8e338fc639c50f5403f90a`.
Additional reviewed file hashes:

| File | SHA256 |
| --- | --- |
| `devtools/animation_review/cases.py` | `c7cbba182bfdcd7aa76a7b68ddb58e1b1f55158074928f0e0a49864d76f766eb` |
| `devtools/animation_review/produce.py` | `d4acbc53c77860c2b764a27de0fd0c16097fd64e249d646885c278847e09170b` |
| `devtools/animation_review/catalog.json` | `8b815fa365da8108530a3825b0b38e57ec2eb8c592f5641dacaaae8f4eaf7fca` |
| `tests/game/item_appearance_scenarios.py` | `3dddb85d4e0ec326439b3488dbb86cb4d5928d4d92f3403847a29b8fd890f3b5` |

`ItemPowerCase` (`cases.py:56–58`) is a frozen discriminated capture input;
`produce.py:91–92` dispatches to the native scenario. The helper at
`item_appearance_scenarios.py:29–49` equips the real Warden pack, invokes its
discovered use, invokes the real concentration dismissal, and calls the existing
item rest hook. It records both observers without inserting synthetic facts.
`dnd/blocks/base_item.py:1038–1051` publishes that hook's genuine recharge event.
This is evidence for the existing recharge hook, not for execution of a complete
long-rest command. The catalog description correctly discloses that the video
HUD does not display inventory charges.

Independent cold replay of the actual two saved item captures confirms the
wearer's three roots include CONSUME to 0 and RECHARGE to 1 for the same item UUID
`d78628fc-583a-4622-a177-11c9a7d4356a`. The witness's two roots contain no item-charge
facts. The trace shows Concentrating/Resistance appearing at video 968.75 ms and
clearing at 2843.75 ms, while HP and placement remain unchanged. Native source
capture and passive replay remain separate.

The selected acceptance receipts are under
`.runtime/cleanup-20261003/acceptance/runs/`:

| Run | Selected clips | Manifest SHA256 |
| --- | ---: | --- |
| `20261003T021219Z-abe536` | 30 | `12ecc5c3b315976656be7db8cf91b877d5eb637183a542861d9120352d83b15f` |
| `20261003T021756Z-043126` | 9 of 10 | `f336bbca6b18bc684b823e59f03f1799e847b5d1331d3d6877a1633e811b210c` |
| `20261003T022901Z-4ba612` | 1 replacement push | `ca8008b1d39b59a5652154c4e7a36e7668ef3bb839590da81a680f191f0f2f2d` |
| `20261003T023352Z-6e63a6` | 2 | `28e833c856af36d63a3982af6af54fde06631fb11159c057f954b57947349ec0` |

The earlier `damage-resolution-push` clip is excluded. Its saved input document
is exactly equal to the replacement's input, so the corrected recording replays
the same facts. A sorted manifest of the four run manifests and 42 selected raw
trace files, using `SHA256(raw bytes)`, two spaces, repository-relative path and
newline, has SHA256
`3814e68746ac6a8205d25de9761aca0c78bb48597662278cdfb58e20455aeef9`.

Independent read-only scripts checked every selected trace and decoded input:

- **42 perspective clips / 10,805 frames**: every existing receipt check passes;
  final frame state equals recorded latest; each frame has four views whose
  actor coordinates agree. These captures contain no paused frames, so they do
  not provide additional pause-test evidence beyond earlier independent seeks.
- **367 retained roots / 1,606 event nodes**: cold decoding and pure reduction of
  every saved public input reproduce each trace's latest state. All 62 results
  present in the typed causal indexes have unique ownership within their
  respective lineages. Native event cursor remains zero throughout.
- **Corrected push**: at the first 32-fps frames after its milestones, Recipient
  is 18 HP at `(4, 3)` (video 2093.75 ms), 16 HP at `(5, 3)` (2468.75 ms), and
  14 HP at `(6, 3)` (2750 ms). The earlier final-position leak is absent. Exact
  boundary and reverse-seek checks are recorded in ER4 above.
- **Other damage captures**: ordinary walking commits two 2-damage entries;
  retaliation separately settles incoming 4 damage and return 5 damage;
  hidden-owner damage changes `(40 HP, 5 temporary HP)` to `(38, 0)` together.
  The hidden capture uses the default immediate number frame; the separate
  delayed-frame checks above remain the timing proof for authored frame 3.

### Existing Call Lightning presentation limitation

The set is **not gap-free**. Both Call Lightning perspectives report the same two
diagnostics for granted repeat-action root
`94a90a43-d58a-4f35-9d1f-f1796725b478`: `recipient-free cast requires source-anchored
media` and `Authored action delivery is not bound`. Their status remains passed
because the recorder's checks cover state/placement/frame invariants; that status
does not certify all authored action delivery. The other 40 selected traces have
no gaps.

Source comparison with baseline establishes the existing restriction:
`game/combat.py` already selected direct application/target tracks in this way,
and baseline `game/animation.py:1180–1183` already rejected recipient-free casts
without the required source media. The granted action has no direct target, and
the lightning bindings/drafts are unchanged. This is not a new result-ownership
failure; the final trace presents 12/6/12 damage on both the initial and repeated
strike, leaves the outside actor at 108 HP, and removes concentration at video
8500 ms. I did not claim a complete baseline runtime re-execution of this scene.
Adding new bindings/art remains outside the approved cleanup scope.

This supplement reviews trace evidence and passive cold replay, not all movie
pixels. Source metadata in the run manifests reports the baseline commit with
`dirty: null`; those fields alone do not identify the uncommitted checkout. The
explicit frozen-source and receipt hashes above are therefore retained. No
source/test files were edited, no broad suite was launched, and full-suite totals
remain the parent's separately indexed receipts. Approval does not mark the
Call Lightning repeat-action artwork complete or expand the tested flight pose.

## ER5 — authored-hop landing timing, introduced regression resolved

**P2, closed.** The broader frozen-source game run exposed an actual regression
introduced by ER4's unconditional effect-time reset. It is not an old test
expectation: an authored successful jaw avoidance really lands at `(2, 2)`, but
after its hop cue ends the displayed actor fell back to `(3, 2)`. The parent's
isolated failure receipt is
`.runtime/cleanup-20261003/validation/final/jaw-hop-exposed.log` (1 failed in
7.48 seconds). The earlier bounded approval did not exercise this alternate
owner of a forced-movement fact.

`game/choreography.py:442–448` already matches the native movement UUID to its
authored hop and sets `at = state_at_effect = owned_hop.end_ms`. Clearing that
time later omitted the landing's spatial state from timed reduction. Once
`sample_body_hop` finished, ordinary retained-state contact lookup correctly
exposed the uncommitted starting position. Native motion and hop geometry were
correct; the shared fact scheduling was at fault.

The one-line correction moves `state_at_effect = None` inside the existing
`if owned_hop is None` branch at `game/choreography.py:843–844`. An explicitly
owned hop therefore retains its landing time, while ordinary forced displacement
continues to clear the enclosing cast's time and use its reached-cell arrivals.
This introduces no second scheduler, trap-name branch, invented position or
extra event. I reviewed the applied source without editing production or tests.

Independent validation in the documented runtime:

```bash
uv run --no-sync python -m pytest \
  tests/game/test_jaw_hop.py::test_hop_is_one_seekable_cycle_and_lands_at_recorded_previous_cell \
  tests/game/test_jaw_hop.py::test_other_authored_reflex_traps_reuse_the_actual_retreat_hop \
  tests/game/test_resolution_contract.py::test_spike_growth_entries_have_independent_owners_and_present_each_result_once \
  -q --disable-warnings
```

**7 passed in 20.05 seconds.** These cover exact jaw landing, post-hop contact,
reverse seeking, blade/crusher reuse of the same owner, and push/walk HP and
position milestones at number frames 0 and 3. Thus the minimal correction closes
the new regression while retaining ER4's ordinary displacement behavior.

A separate recursive scan of all 42 selected trace compositions found no
authored-hop cues. The one-line branch correction does not change those recorded
paths; their earlier receipts remain identified by their original hashes, not
relabeled as renders of the new source. The parent is producing an additional
jaw-save perspective pair and running affected neighbors. Those receipts and
the broad run's final dispositions remain separately indexed; the earlier
frozen game process must not be described as having run this edited source.

**Final delta verdict: APPROVE.** Updated 377-file source manifest:
`cce92fd9f113f35a5e430a215cbab484c0bf7f533217e37c48c2a64a1442c8ca`.
Updated baseline core diff:
`de93125f8651ccafd9c203e798476557573c9fc40d817697c0019740c07d5bde`.
Updated `game/choreography.py`:
`8059e1cb85407b68735e3179f7d51a52d960eb4c53b34c2ab7c58086dce773f5`.
ER1–ER5 are closed within this independent review's bounded scope; existing
Call Lightning presentation diagnostics and all prior coverage limits remain.

## Final jaw-capture supplement — 44 clips verified

**Approval retained.** The new receipt pair under
`.runtime/cleanup-20261003/acceptance/runs/20261003T031028Z-5b9d74/` contains
`mechanism-jaw-save` and `mechanism-jaw-save--witness`, 195 frames each. Both have
no gaps and all their existing receipt checks pass. `game/choreography.py` still
has the approved SHA256
`8059e1cb85407b68735e3179f7d51a52d960eb4c53b34c2ab7c58086dce773f5`.

The independent read-only check was extended across the complete selected set:
**44 clips, 389 retained roots, 1,706 event nodes and 11,195 frames**. Every saved
input cold-decodes and reduces to its recorded latest state. Every final frame
equals that state, every frame's four camera views agree on actor coordinates,
and the 62 results in typed causal indexes retain unique ownership within their
lineages. Native event cursor stays zero. The set contains no paused frames;
earlier direct reverse-seek tests remain the separate seek evidence.

For each of the two actual retreats in each new perspective, the check traversed
the nested motion/reaction offsets and examined the recorded frames after the
authored hop's landing at head-local **1013.333333 ms**. The first available
32-fps frames are at video **1406.25 ms** and **5031.25 ms**, respectively. In all
eight remaining frames of each head, both retained position and drawn contact
remain `(2, 2)` with zero body lift. Earlier in each hop, positive body lift is
present. This directly covers ER5's post-hop contact failure in the rendered
trace, in addition to the seven independent exact-boundary/seek tests above.

| New receipt | SHA256 |
| --- | --- |
| Run `manifest.json` | `36c1fd833c3209c141b7519bc6d5fd603c48f2c55b44e9de4fd0c4b9b5297198` |
| `cases/mechanism-jaw-save/trace.json` | `1055e4bee83405102c268063e54318953b9d6a13d1bea93021198bce27c4fccc` |
| `cases/mechanism-jaw-save--witness/trace.json` | `737b27da31a3b297ffe48d0db7570789962a562841ab23d89a4a0db185fa5381` |

The combined sorted manifest of all five run manifests and 44 selected trace
files, using the same raw-byte/path algorithm defined above, now has SHA256
`7448022a12cb6c25cb550fff8a4e90728a8338d2aa7749ef0da73e5c24c0c594`.
The original push recording remains superseded. The only nonempty gaps remain
the paired, explicitly disclosed Call Lightning repeat-action diagnostics.
This supplements trace/cold-replay evidence without asserting exhaustive pixel
inspection or a completed full-suite reconciliation. No source or tests were
edited for this check.

## Closure addendum — final active-suite reconciliation

**Final acceptance verdict: APPROVE for the reviewed cleanup event/render scope.**
I independently reconciled the final collection, raw JUnit, disposition map and
source/recording identities. This is receipt verification plus the independent
runtime/trace checks above; it is not a claim to have personally rerun all suites.

The full game run contains exactly the **3,046 distinct collected node IDs**:
3,045 pass and the sole retained failure is ER5's jaw-hop landing test. The
34-test affected rerun has no failures/errors/skips, contains that failing ID,
and contains only IDs already in the collection. Overlaying that explicit rerun
leaves all 3,046 verified, without inventing a single all-green full execution
on the later bytes. The logs confirm 2795.65 seconds for the original run and
46.78 seconds for the rerun.

The native/AI/progression JUnit contains 2,386 passing cases, and architecture/root
JUnit contains 120. Their identities are disjoint from one another and the game
suite: **5,552 unique active tests**, with no skipped active cases. All XML/log
hashes in `acceptance-receipts.json` match the actual receipt files.

All **344 original game diagnostic entries** are preserved by exact original
file/test identity in the final disposition map. Of these, 340 map to the same
test identity, two collection failures map to every collected test in the
corresponding module, and the two named glyph cases map to the reviewed sustained
glyph contracts. Every mapped destination is present and passing in the explicit
full-run/rerun reconciliation; no unresolved original entry remains.

| Final receipt | SHA256 |
| --- | --- |
| `acceptance-receipts.json` | `a1ae037e7d217cc9b32768378ed1eae448008ebc4ac03c7ef5beee521850b9da` |
| `game-repair-dispositions-final.json` | `92e1bcd50175b881c0f3a9cf54bbbf2b01adcfc14c435fdd1e2b09bbfafbaa6b` |
| `source-final.json` | `3168602d154d796980b30eb45b317ee23e44d628780f16ecf7c627d0930feb8a` |
| `game-final.xml` | `8b7a2b70789235c448850741d7f22733699b6a89fa24ac1706df9a3d73a54484` |
| `hop-forced-final.xml` | `57c287bb656680612db120d78652c5e7d45efd729deb23c0bd07d2ade1cb0bef` |

All receipts in this table are under
`.runtime/cleanup-20261003/validation/final/`. I recomputed the source path-map
digests using sorted compact JSON and checked every one of the **1,284 recorded
paths** against current raw bytes or deleted status. Final digest
`723bc6198c189c65358880edff89190acd0149a05b2e1782dab34807870b3727` matches. Against
the frozen map `1afbfeb3a79e4a308dd2d3deb74a61757be97ce973c0b43f417f28a0493d8226`,
only `game/choreography.py` differs within that declared scope, at the reviewed
`8059e1cb85407b68735e3179f7d51a52d960eb4c53b34c2ab7c58086dce773f5` revision.

That path-map scope excludes top-level `ai/`; it is not a hash of the whole
repository. I separately confirmed the changed AI registry's raw hash,
`202febf89f6276104a0bc83bd2042e11a7913ca14ea3b8c95f024b2f54769bcf`, matches the
already recorded independent anti-slop and ECS reviews. The implementation
report now makes this scope distinction explicit instead of rewriting the old
freeze. The five manifests/44 selected traces also rehash to the same
`7448022a12cb6c25cb550fff8a4e90728a8338d2aa7749ef0da73e5c24c0c594` receipt identity
verified above.

I read `agent_docs/CLEANUP_REPAIR_IMPLEMENTATION_2026-10-03.md` and verified the
active typing receipt reports zero errors. Its explicit limits are retained:
paused-server collection/cold-start failures, configured server typing errors,
the historical offline generator's broader typing errors, and excluded manual
material are not counted as green active tests. Legacy archives without causal
proof still diagnose instead of inventing ownership; Call Lightning's existing
repeat-action presentation diagnostics and the existing flight pose remain
disclosed. There is no remaining concrete event/render blocker within the
approved cleanup scope. ER1–ER5 are closed, and no source or test files were
edited during this closure review.
