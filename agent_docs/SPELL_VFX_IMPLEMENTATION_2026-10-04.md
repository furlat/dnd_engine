# Spell VFX implementation ledger

Authorized October4 against baseline `95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`.
Scope is the [approved plan](SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md).
Telekinesis's final human choice is4d8 force+2d6 bludgeoning landing damage,
plus actual lower-ground fall damage; allies remain safe. It supersedes the
reviewed proposal's3d6/larger-of balance. No numerical re-review is requested.

## Acceptance boundary

Real spell/action input must produce correct native state, retained causal
events and subjective replay, rendered through the current shared operators.
Source artwork is accepted; production integrations still need verification.
No new spell executor, condition manager, physics engine or renderer is authorized.

## Current status — implementation and final reviews complete

All eight approved packets are implemented within the explicit delivered-art and
installed-rig boundaries. The current [full feature change trace](audits/SPELL_FEATURE_CHANGE_TRACE_2026-10-04.md)
separates rules, shared-core changes, presentation extensions, regression fixes
and limitations. Its file inventories account for all59 native/AI and209
client/authoring changed files against the committed baseline.

| Packet | Final implementation | Bounded review / evidence |
| --- | --- | --- |
|1 Senses/support/control/words | Complete for installed rigs; separate Ogre rig still outside this port | Native, source intake and shared-condition reviews; final variants in coverage matrix |
|2 Item/body/fire | Complete, including actual item-owned Continual Flame and source-consumed Produce Flame | Independent native/client reviews and transfer/release recordings |
|3 Directed/necrotic/electric | Complete, including linked lightning, three Eyebite modes and explicit Disintegrate outcomes | Source/material/privacy reviews; actual saved/failed/terminal/object variants |
|4 Weather/solar | Complete, including sunlight and source-removal expiry rules | Independent native/presentation reviews and actual weather/solar recordings |
|5 Holy/Feast | Complete, including corrected Eat intake and ten-turn benefits | Independent native/source/compositor review and observed outcome recordings |
|6 Transport/TK/falls/Antimagic | Complete, including witnessed-only Banishment return and retained suppression | Independent native/projection/selection review; actual lower-ledge enemy/ally/Shove captures |
|7 Walls/surfaces | Complete for accepted available forms; G1–G4 remain as declared later art | Final Force eight perspectives, Ice eight, Stone cuts, Wind joins, Thorns contacts and native quench; independent geometry/privacy/source reviews |
|8 Class presentation | All21 sets complete, with original equipped-clip measurements and explicit unavailable fixed-rig sockets |78 selected recordings/630 checks; independent source/handler/privacy reviews |

Final checks: 3,009 engine/AI/progression passed; 120 architecture/packaging
passed; active dnd/game/AI and changed authoring-tool typing has zero errors and
warnings. The full 3,522-case frozen client run completed: 3,517 passed and five
failed. Two production regressions and two stale fixtures were corrected in four
files; all five cases pass in 167 complete affected-file checks. Independent
anti-slop and ECS/event reviews closed with no unresolved blocker. See the
[final report](audits/SPELL_VFX_FINAL_ACCEPTANCE_2026-10-04.md) for precise
reconciliation, source hashes and limitations; the original run is not relabeled
as a zero-failure run.

The standard gallery selects283 passing recordings,4,681 recorder checks,
46,928 frames and zero reported presentation gaps, preserving original clocks
and native bytes. [All34 spell entries are mapped](audits/SPELL_VFX_VISUAL_COVERAGE_2026-10-04.md).
These counts supplement whole-suite/source review; they are not a proof that
every possible playthrough or every frame was manually inspected.

Earlier first-run results remain preserved. Concurrent class schema/data saves
invalidated many old-process failures; an obsolete shard also exhausted time and
memory while handling failures and was terminated without an XML receipt.
The complete frozen rerun replaces that incomplete run; no failed case is
silently counted as passing. Genuine regressions and fixture revisions have
separate explanations and focused passing evidence.

The sections below are historical checkpoints. Their then-pending tasks are
superseded by the completed status and final report above. No external chat or
commit is involved.

## Packet 1 checkpoint — implementation continues

Native sensory durations, touch/upcast admission and control ownership are corrected.
Darkvision is non-concentration/4800 rounds; See Invisibility and True Seeing are
600 rounds. Power Words gate on normal HP, retain actual death prevention and do
not invent damage. Hold Monster validates all recipients and preserves independent
paralysis. Power Word Stun repeats its recorded save even after caster removal.

Sensory application/hold/removal uses 12 original four-camera banks. Longstrider
reuses the installed ankle-wind bank. Power Word V2 contacts and shared Stunned V1
use six original billboard banks; authored application/life-outcome selectors read
committed player facts. Generic Incapacitated now owns the existing pause cue,
with Hypnotic Pattern no longer duplicating that layer.

Evidence (bounded; no full-suite claim):
- 105 native checks passed before the later target-count additions.
- Current native/replay/import selection: 67 passed, `/tmp/dnd-packet1-current.log`.
- Six Power Word cases, both observer views: 12/12 recorder cases passed,
  `.runtime/spell-vfx-20261004/packet1-control/runs/20261004T025308Z-675afc`.
- Sensory replay: all three passed. Earlier capture had a self-target fixture bug;
  fixed source and passing replay supersede that failed case, not the failed log.
- Native anti-slop review approves the corrected target count and source-owned saves.
- Importer review identified and verified fixes for destination containment,
  archive-metadata conflicts and all-bank preflight. Tests preserve original bytes.

Hold Monster body fits and remaining shared condition materials are still in progress.
Packets 2–8, current-source typing, final galleries/full suites and final reviews
remain pending. No completion claim and no external chat contact.

## Current continuation checkpoint

Shared Restrained/Petrified/Sickened original cues are installed. Petrification
retains the actual preceding pose; Stunned's source-ground/head registration was
corrected and visually checked. Ogre rig is not imported in this spell lane; its
accepted Hold fit remains for the separate character port unless human directs
otherwise. Sickened hold duration still needs a representative native recording.

Packet2 now has exact-item Shillelagh material ownership, accepted Barkskin
material math and energy/source-owned Fire Shield responses. Produce Flame's
retained hurl is an ability using shared spell-attack arithmetic, not a fresh
cast; Silence/metamagic and Sanctuary use the recorded classification. Critical
hits retain death-save meaning. Held-flame sockets/media are in progress;
Continual Flame remains pending. Current shared response typing has zero errors.

Packet3 native Finger/Blight/Eyebite/Harm/Circle and packet6 Telekinesis/shared
landing are being implemented in disjoint local lanes. Their changes are not
accepted until independent reviews and checks complete. No external chat is used.

## Latest bounded continuation

Produce Flame source membership and light now end at source release, while target
damage remains at projectile contact. This uses the existing consumed condition
fact and cast clock. Compatible nature buffs have separate composition groups.
Ordinary falling recognizes committed damage absorbed by temporary HP for Prone,
while immunity causes neither damage nor Prone. Focused native/client checks:
65 passed, `/tmp/dnd-nature-fall-corrections.log`. The earlier18-clip nature gallery
predates the release correction and must be rerendered before acceptance.

Accepted HarmV3/CircleV9 original pages are imported; recipe/operator work remains.
No final acceptance or full-suite claim is made.


## Current-source media and targeting checkpoint

The native thirteen-case Produce Flame/Blight/Harm/Circle capture passed recorder
checks at`.runtime/spell-vfx-20261004/packet23-contact/runs/20261004T050114Z-92f8f2`.
Harm/Circle four-camera contact frames have been inspected; full visual acceptance
is still pending. The finite current-pose material review caught hardcoded colors:
operators now use the authored palette, with original wither base/light/scar/pulse
colors retained. Independent12checks pass and the finding is closed.

Continual Flame native real-item/light transfer and Telekinesis entity+destination
selection receipts are in`agent_docs/audits/`. Both initial and paid-repeat targeting
use the same typed selection across native discovery, controls, session, AI intent
and item-use adapters. Root independent review of those changes remains required.

Finite movement facts retain admitted cells, actual support heights/drop and landing
kind. Rendering uses the straight admitted transfer, existing authored flight body
capability and registered grab/hold/release banks. Direct damage children start at
landing. Ordinary Shove remains separately tested. Original clear-path cells are
not rendered as a zigzag. Early recordings lacking the hand binding and a later
negative-clock recording failure remain failed evidence; they are not acceptance.

Antimagic still requires retained contribution/item/created-presence completion,
review and visual integration. Remaining electric/transport/wall/class work and
complete suites are open. No completion claim is made.

## Current independent corrections and electric delivery

Chain Lightning native and player/AI selection are implemented and independently reviewed. Exact recorded edges originate from its primary recipient. The review corrected Antimagic to test those edges rather than a fabricated caster-to-every-target path. Partially disclosed branches retain sparse application identities without publishing unseen targets.

Original electric five-texture material, isolated hand sheet and source composition are imported with private original preservation. Typed arc delivery extends the existing finite cast/application clocks and per-pixel world compositor. Three native replay tests pass (full Bolt, empty Bolt, Chain); broader source-frame and gallery checks continue. The first gallery exposed an incorrect authored slot for Magic2; it was corrected to the established weaponGlow slot and actual media loading is now part of the replay test. No failed gallery is accepted.

The existing line/cone projection incorrectly required the direction-pick endpoint to be visible, although the native origin and corridor were visible. It now checks the actual recorded geometry origin. Sunburst self-blindness also exposed final-visibility filtering erasing a witnessed footprint; recorded declaration visibility now participates in that disclosure. New regressions and affected area tests are underway.

Root independently approved current Continual object attachments and Telekinesis selection after31checks: see `audits/SPELL_CONTINUAL_FLAME_AND_SELECTION_ROOT_REVIEW_2026-10-04.md`. Antimagic review found structural item UUIDs were passed to condition-only registry lookup; those consumers now use the existing typed contribution-owner lookup. A further magical transfer-path case is being checked before its receipt is closed.

This is an in-progress checkpoint. Holy, transport, remaining directed outcomes, walls/surface transitions, class presentations and final full-suite/independent acceptance remain required.

## Transport and current broad verification checkpoint

Dimension Door uses original paired portal banks and faithful additional camera
views, the existing transfer fact and one shared group clock. Six native observer
recordings pass. Banishment retains actual spatial disposition in the existing
actor projection and uses the accepted fixed-pose departure echo; four native
recordings pass. Permanent and deferred returns are still under verification.
Transport importer rejects malformed camera/crop metadata before publication;
six integrity cases pass. Current relevant logs remain in `/tmp/dnd-transport-*`
and `/tmp/dnd-banish-*` until final evidence is consolidated.

An initial broad command accidentally included the historical `tests/manual`
server lane and stopped on 70 collection errors. That failed log is retained at
`/tmp/dnd-spell-native-broad-preflight.log`; it is not a native-engine result.
The documented active command now runs engine, AI, progression and architecture
in `/tmp/dnd-spell-active-native-preflight.log`. It is a preflight while source
work continues, not final acceptance. Every active failure requires diagnosis.

## Active preflight reconciliation and independent packet reviews

The active native preflight finished with **3,062 passed and 10 failed**. Eight
failures exposed a real touch-target regression: self-cast Longstrider from the
Wayfarer Pack was rejected by entity-only validation. The shared touch validator
now resolves SELF to the caster before applying the same contact/filter rules.
The other two fixtures expected obsolete representations: one inspected innate
senses instead of the effective owned sense contributions; one omitted the new
retained remains disposition from the complete birth-state fields. No gameplay
rule or expected damage was weakened. Complete affected files and touch/economy
regressions subsequently passed **196 tests** in
`/tmp/dnd-native-preflight-corrections.log`. Final full-suite acceptance is still
required after the remaining packets finish.

Root's independent bounded native Disintegrate, holy presentation/screen blend,
weather/solar and delegated electric-fix reviews are recorded in
`audits/SPELL_PACKET_IMPLEMENTATION_ROOT_REVIEW_2026-10-04.md`. They do not
self-approve root's work or claim completion of the entire plan.

Banishment's actual early, permanent and delayed return paths now pass the
complete eight-case replay/privacy file. A permanent departure clears only the
caster's already-known ownership without revealing the absent recipient's
current HP, position or private return-pending state. Latest relevant typing is
zero errors for choreography, projection, reduction and touch validation.

Continual Flame now attaches to disclosed legacy wall/door/corner objects too,
using their original sprites and actual per-object anchors. Hidden topology does
not acquire an item effect. The complete object attachment file passes five
cases, including original-byte replay and all four cameras. Current gallery and
independent review of these root-authored additions remain open.

## Current review corrections and recording results

Banishment's unseen native return followed by later sight reacquisition no longer
replays its portal. The existing condition lifetime accepts a return edge only
when that lineage contains the witnessed, noncanceled spatial entry. A native
Blinded/Deafened return regression failed before correction; the complete
transport and Dimension Door selection files now pass11checks. The independent
reviewer repeated the original native probe and18checks, closing that finding
in `audits/SPELL_TRANSPORT_UTILITY_ECS_REVIEW_2026-10-04.md`.

Root's wall review found camera zoom leaking into the world coordinates used for
partial cuts. Passing the actual camera zoom to the existing registered sampler
keeps physical/material-rest positions fixed. All three native cut/dust/fracture
cases pass, including cut alpha consistency across four cameras and .35/.5/1
zoom. Independent inspection approves this bounded correction. An initial test
used unsupported1.5zoom; its failure is retained and is not claimed as a
reproduction of the production defect.

Current root recordings:26/26passed at
`.runtime/spell-vfx-20261004/root-final/runs/20261004T083914Z-b29409`.
This includes original Produce directional travel, Continual transfer,
Telekinesis initial/resisted/ally, electric line/empty/branched and moving
Antimagic views. Selected four-camera frames are under `inspection/`.
Current Banishment:11/11passed at
`.runtime/spell-vfx-20261004/banishment-current/runs/20261004T084548Z-abb50b`.

Active walls/class work, complete stable-source suites, matrix reconciliation
and final independent reviews remain required. No whole-plan completion claim.

The complete active native/AI/progression run now passes **3,004 tests** in
473.86s; architecture and root packaging pass **120 tests** in107.83s. Permanent
logs/XML are under `.runtime/spell-vfx-20261004/validation/`. Class mechanics
were frozen before this run. Client wall/class presentation is still in progress.

The native ledge cases now use the existing rendered ten-foot terrace, with the
recorder framing both displaced bodies and their attached Telekinesis hands.
Both Jump and Telekinesis four-camera framing regressions pass. The six ledge
views pass at `ledge-current/runs/20261004T091030Z-1456fe`; its Shove views are
superseded by the actual successful Shove at `20261004T091356Z-817165` (2/2),
which records a ten-foot drop. The earlier seed resisted the Shove, so its passing
recorder checks were not evidence of falling and those views are not accepted
for this coverage. The enemy Telekinesis records17force+8bludgeoning+6actual-fall
damage; the safely placed ally remains at40HP. Native bytes remain unchanged
when only reframing existing recorded inputs.

## Final wall closure checks (implementation still in progress)

The independent Thorns review found two source-integration defects before final
acceptance: non-cardinal modules were spaced at whole cells instead of their
canonical arclength slots; and dissolve alpha was evaluated after depth selection.
Both are corrected. The shared rasterizer now admits original UV cutouts before
choosing a surface; its default numeric outputs remain unchanged. Thorns contacts
use current body elevation and actual damage dates. Four-camera local-contact,
all-eight-heading, disclosure and lifecycle checks pass: **22 passed**, 216.97s,
`/tmp/dnd-thorns-final-semantics.log`.

Source inspection also identified Thorns' actual CIE76 palette/1.12 boost and its
energy-alpha gate. Those are explicit source parameters on the shared sampler;
Wind/Force/Ice keep their original nearest-RGB policy. Original two-pixel source
sampling follows camera zoom. The accepted raster and current native source mesh
were compared in all four views; the previous coarse screen-pixel blocks are gone.
This does not claim bit-identical Godot lighting/rasterization. Original source,
RGBA and revoked-XYZ boundaries remain preserved.

Normal Attack now admits a targetable, invulnerable object without requiring a
health block. This corrects the existing mismatch between Force's targetable flag
and its immunity: active state, sight and physical reach still gate the ordinary
attack; its existing damage receiver returns zero. No object-specific action,
new health pool or damage rule was added. Real See Invisibility followed by a
discovered attack verifies spent action, unchanged Force barrier and zero damage;
the combined wall/object/window checks pass **59 tests**, 12.84s,
`/tmp/dnd-force-targetability-final.log`.

The staged acceptance directory selects **189** passing recordings from **27**
original runs. It preserves each run's FPS, original clip/input/trace bytes and
explicit supersession filters; unfinished final Force/Wind/Thorns/class recordings
are added only after their checks pass. It is not yet whole-plan acceptance.
The final native suite is rerunning after the bounded class provenance and Force
admission corrections. Stable-source full game, architecture/packaging, typing and
independent final class/wall reviews remain required before completion.

Validation command correction: one attempted native invocation also included
`tests/manual` directly. It stopped with 70 collection errors in historical
server/tutorial migrations (receipt `validation/native-closed.log/xml`). This
was the wrong suite boundary, not 70 executed active-game failures. The already
accepted cleanup report defines active collection as `tests/engine tests/ai
tests/progression`, `tests/game`, and `tests/architecture tests/test_*.py`;
applicable old spell assertions are re-exported through active engine tests.
The final native rerun uses that exact established boundary and records
`validation/native-active-final.log/xml`. No test was skipped or reclassified
by this implementation, and the failed invocation is preserved.

The final active native invocation completed with **3,009 passed**, 464.89s,
`validation/native-active-final.log/xml`. Wind final4/4 and Thorns final4/4
recordings are now included in the staged197-clip index. Client/class closure
and final independent reviews are still required.

A real Mindless Rage replay then exposed cleanse children being attached to an
already-completed condition event. Both Rage/Frenzy calls now keep the existing
active action as parent while still cleansing after Raging commits. The existing
progression assertion checks that action causality and ordering. The complete
barbarian progression file passes28tests (`/tmp/dnd-mindless-native-final.log`).
No event framework or class rule changed. The new real Encounter replay fixture
is still being finalized; transient import/dice failures are preserved.
