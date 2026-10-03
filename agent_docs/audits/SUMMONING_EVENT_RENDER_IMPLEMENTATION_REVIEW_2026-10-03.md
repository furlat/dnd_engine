# Summoning event, rendering and recorded lifecycle implementation review

Date: 2026-10-03. Reviewer: independent events/items/render subagent.

**Final bounded verdict: APPROVED.** The final reconciliation and installed
gallery evidence at the end supersede the historical holds and pending receipts
retained below. No unaddressed finding remains in this review's scope.

## Scope and review state

This review covers the unified summoning implementation's passive birth, initial
condition values, faction changes, terminal departure, subjective replay, shared
body/action selection, Fey material, and native recording evidence. The approved
main plan and visuals addendum remain the scope; decorative arrival/departure
VFX are future work. This is not a review of an arena expansion.

The reviewer read AGENTS.md, RECOVERY_PLAN.md, HOW_TO_TEST.MD, ASSETS.md, the
implementation checkpoint, and the relevant implementation and test sources.
During the initial independent review, no production/test files were edited and
no suites were run by this reviewer. A later root-authorized, proven playback
correction is recorded separately below. No other chats were read or messaged.
Root owns final integration acceptance.

**Initial verdict: hold pending the renderer's final freeze and the concrete
gesture correction below.** A final hash-bound verdict is appended after that
freeze. This initial statement deliberately does not treat gallery `passed`
flags or an unfinished integration run as proof of completeness.

## Finding ER-1 — summoning and dismissal lacked their ordinary caster gesture

Status at initial review: blocking; communicated to root and the renderer owner.

The original implementation had no authored binding for
`spell.conjure_animals`, `spell.conjure_fey`, `spell.conjure_fiend`, or
`action.summon.dismiss`. The recorded gallery at
`.runtime/animation-review-summoning-20261003/runs/20261003T172001Z-edaa88`
explicitly reported unknown authored spell bindings/unbound delivery and a
missing dismissal body-action recipe. Its case descriptions accepted those
gaps. That acceptance was narrower than the approved deliverable: the visuals
addendum's “Summon / dismiss caster gesture” row makes ordinary shared
recipe/data binding current work, while only V1's decorative accent is deferred.

Required correction: use the caster's existing body-only cast/action recipe,
retain the exact native spell/action identity, and release observed birth or
terminal departure at its authored causal effect anchor. No new media, species
event, duplicate birth/departure fact, or summoning-only compositor is needed.
Root agreed and assigned this correction to the renderer owner.

## Source findings retained for the final review

### Native fact ownership and lifetime

- `Entity.prepare_birth` captures one unregistered complete creation event,
  including committed-intent initial condition states and optional passive
  `SummonOrigin`. `commit_birth` commits identity before deployment;
  `publish_birth` publishes that exact staged fact once. Publication failure
  remains a committed failure rather than rolling back a visible identity.
- The summoning owner prepares before mutation, commits the ordinary condition,
  birth, deployment and encounter owners together, and publishes after authority
  commit. Autonomous controller admission follows committed membership/facts.
- `Entity.set_faction` commits the ordinary actor faction and occupancy-path
  invalidation before publishing `EntityFactionChangedEvent`. Fey control loss
  keeps existence, UUID, origin and duration, and changes to its independent
  hostile faction through that owner. Replay copies no faction mutation logic.
- Terminal retirement uses the existing item/equipment/container owners. Real
  possessions retain identity and reach supported ground; intrinsic anatomy
  retires instead of becoming loot. Terminal membership publishes while the
  event-time actor and position remain available, before final registry and
  subscriber cleanup. Reversible spatial detach remains distinct.
- The outer condition-removal scope retains completion until committed graph
  callbacks have attached retirement/faction descendants. Pending completion
  publications then close the native lineage; callback/publication errors are
  collected without undoing already committed state. This is the shared native
  condition boundary, not a second gameplay event bus.

### Subjective disclosure and passive replay

- The finite codec explicitly includes the ordinary faction fact and additive
  birth/origin/initial-condition/terminal fields. The renderer correction also
  adds optional `summon_application` and `release_reason` compatibility to each
  exact registered equipment-event subclass, preserving old absent fields on
  encode/decode. Decode creates no native entities, conditions, rolls or events.
- Private actor reduction retains origin and complete initial conditions. Public
  actors expose only presentation manifestation, faction and presence, rather
  than summoner/cast/existence/control identifiers. Faction disclosure requires
  identified located knowledge; remembered-only contact is insufficient.
- Terminal spatial disclosure captures the departure lineage's own entry senses,
  so cleanup of senses before completion does not erase a witnessed departure.
  Hidden terminal events are not invented from private state. Ordinary sight
  loss leaves historical presence intact; subsequent genuine observations use
  current values rather than replaying hidden birth/control-loss history.
- Public terminal reduction marks the actor absent, clears contact/location,
  and refuses stale observations that would restore an absent actor. Scene and
  choreography visibility both honor that flag; retained historical identity is
  not a corpse or a currently visible body.

### Shared body/action execution

- Attack selection remains the existing stable item/source-kind route, with an
  additional rig selector. Intrinsic weapons retain their actual `equipped`
  source kind and exact item identity. No natural-attack event is fabricated.
- Nonattack contexts use a finite passive role vocabulary and exact content
  reference or exact movement signature, followed by role default and the
  existing shared fallback. The retained primary/recovery contexts determine
  both marker clocks and sampling. Disabled gestures retain child joins;
  movement and shared damage/death owners cannot disappear behind that option.
- Shove and forced movement have explicit existing owners. Body context changes
  affect clips and timings, not recorded movement endpoints, damage or condition
  after-values. Admission validates clips, marker frames, resources and exact
  references; installed but intentionally unloaded rigs are distinct from a
  misspelled selector.
- The corrected shared Action traversal sequences received child groups, then
  compiles each child's pending conditions and joins its complete subtree before
  starting the next. It uses the existing disabled-body Multiattack alias, not
  a monster-name branch. The normal final state still comes from the same
  recorded reducer, and repeated frame sampling is passive.

### Fey material and evidence boundaries

- Fey manifestation selects a shared palette plus alpha 0.7 from passive public
  actor data. Body drawing applies it to nonshadow layers only; source surfaces
  remain unchanged and the ordinary shadow retains its original pixels/alpha.
  Existing condition appearance composition still owns its normal overrides.
- The reviewer inspected actual four-view jaguar-Fey and huntsman posters from
  the 17:20 native gallery. The Fey body was visibly distinct and translucent;
  ground registration and the huntsman's separate shadow remained plausible.
  This is limited screenshot evidence, not a claim to have watched every video.
- The native scenario source casts the real spells, selects indexed native
  actions and movement, captures real damage/control-loss/dismissal histories,
  then resets the engine before replay. It does not patch event payloads to
  manufacture outcomes. Scripted action selection is not proof of autonomous AI
  decision quality, and ordinary rig/media validation is not native gameplay.
- The all-24 artifact validation reports actual installed/source cells and pure
  selector coverage. Representative paired native recordings cover wolf,
  jaguar, bear, tyrannosaurus, dretch, huntsman and Fey jaguar. Remaining passive
  condition recipe messages must be disclosed as such; they do not authorize a
  perpetual aura or substitute for missing ordinary body-action coverage.

## Verification inspected, not executed by this reviewer

- `tests/game/test_summoning_presentation.py`: real native births/endings, private
  archive and public JSON replay after engine reset, caster/witness disclosure,
  hidden departure, hidden birth/reacquisition, terminal disappearance, and real
  RGBA palette/alpha/shadow/source-preservation assertions.
- `tests/game/test_rig_body_contexts.py`: shared movement/action/condition/heal/
  equipment/shove/forced routes, disabled gesture joins, stable item selectors,
  admission rejection, source cells and marker/recovery behavior.
- `tests/game/test_action_sequences.py`: real bear/dretch/huntsman Multiattack
  with a genuine concentration-removal descendant, authored long removal timing,
  ordered body starts, intermediate/final HP and repeatable seeking.
- `tests/game/test_recorded_history.py`: finite additive codec compatibility,
  retaining absent old fields without native registration.

The running `/tmp/summoning-full-game.log` contained failure/error markers when
inspected and had no final summary. No green full-suite claim is made here.

## Final freeze and verdict

**Bounded approval: no remaining event/render/recorded-lifecycle blocker in the
reviewed snapshot. ER-1 is resolved.** This approves the source contracts and the
focused evidence below; root still owns the fresh whole-game run, overall
integration acceptance, and final visual approval of the newly requested scale
changes. It does not certify future decorative VFX or every full native clip.

The exact correction manifest at
`.runtime/summoning-packet5-component/final-corrections/frozen-files.json`
has SHA256
`39d1a0e9f8b6ceb1753f4ef9087975d0806e79639de130fd513382ca20d4fa9e`.
The reviewer independently compared every entry to the workspace: **zero hash
mismatches**. The normal Action child traversal, passive codec compatibility,
installed-rig admission and the gesture data were inspected directly after the
freeze; this verdict is not inferred only from test counts.

ER-1's correction adds three exact native-definition Studio drafts using the
existing True Seeing body-only Special1 program and its release frame 8. Dismissal
aliases the existing actor-only counterspell recipe with feedback disabled. The
ordinary bundle loader and body-action owner perform the work; no generic
cross-kind binder extension, new media, event family or runtime registry lookup
was introduced. The native three-family/two-view check demonstrates the summon
absent before birth release and present at release, then present before dismissal
release and absent at release, with unchanged recorded final state and stable
backward seeking. Passive condition-decoration diagnostics remain explicit;
assertions isolate gesture gaps rather than suppressing unrelated diagnostics.

Receipts read from the frozen correction directory and corresponding logs:

- `/tmp/summoning-final-focused.txt`: **99 passed** (17 native summoning/material
  cases, six native Multiattack sequence cases, 76 area timeline cases).
- `/tmp/summoning-simultaneous-regression.txt`: **2 passed**, including ordinary
  Prayer of Healing recipients remaining simultaneous at one spell release.
- `/tmp/summoning-final-types.txt`: **0 errors, 0 warnings** for the frozen
  correction's affected source and tests.
- Earlier relevant receipts remain clearly earlier: eight codec checks, 14
  ordinary body/cast regressions and 38 rig-context checks. Their command scope
  and initial failed test setup are disclosed in the owner's `validation.txt`;
  the six corrected sequence tests are included in the final 99-case run.

The earlier `/tmp/summoning-full-game.log` was subsequently identified by root as
an invalid mixed snapshot: Python had been loaded before shared JSON changed,
and the run was terminated. Its failure/error markers are **not** a valid final
snapshot or unresolved final failure count. The replacement
`/tmp/summoning-full-game-frozen.log` was still running at this bounded verdict;
this audit makes no green full-suite claim.

The human-approved artwork amendment now binds the existing vendor T. rex sheets
to `creature.raptor`, with exact `raptor_bite`/`raptor_tail` item selectors and
Animals unlock 5/Fey unlock 6. Canonical Raptor is Large with 51 HP and appearance
scale 1.55; vendor rig and PNG paths retain provenance. Larger approved beasts
use the existing appearance scale owner. These changes add no lifecycle or
render authority. The earlier T. rex gallery is historical evidence only and
must not stand in for final Raptor/scale visual acceptance.

Plan SHA256:
`d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.
Visuals addendum SHA256:
`28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.
The explicit later human Raptor/scale amendment supersedes their old content
assignment only; the reviewed lifecycle and rendering contracts are unchanged.

### Reviewed snapshot hashes

The following initial 67-file source/data/test snapshot has aggregate SHA256
`fd988b8407be5fea9fea0b71db6395d18f67f8d0dd00bd4fc6ce89a633bf7ef3`.
Aggregate method: UTF-8 JSON of the following path-to-SHA256 map, sorted by path,
with separators `(',', ':')`; no trailing newline. Individual values hash exact
file bytes. The rig rows include the installed rig catalog used by admission.

```text
211103423ce0f0422e4d630c59043f107f724691e66e845d5daead8882ac7b5e  devtools/animation_review/catalog.json
8902e7a6ff8ff93fe044e1f23d4f2a1045f456916f6146becd9a61e2513d402a  devtools/animation_review/summoning_cases.py
131c1892d0b1486c1faf1072fcd02d454858a051b3c639b5ce58dfe1c46184fe  dnd/actor_projection.py
0ea5a0b5160eb38d6745be9541e220b98c74272f413fa1a71d06e360547ff405  dnd/core/base_block.py
7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59  dnd/core/events.py
668b500925582c27347835129c20745c853a5adae56b196a765316ab0fe7e15d  dnd/entity.py
b1e5f333a1e6d0d95be749dd05d83aefec9c40dc682f63babd401b6cd52de15f  dnd/monsters/beasts.py
64e17b956869d915f47d35aba694e5a031ae26c3aa884d4a91231c2c9a04140a  dnd/summoning/forms.py
6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009  dnd/summoning/system.py
861905da36883018471c12627f77acb9d5d3e76a9bc8a297e8fa56a42a443ed6  dnd/types/summoning.py
f82b30c25a2eef9a6f89fb11498751f110d827d5e352699a5194f1861a461af1  game/animation.py
54456a3781d14913aab87aac5e907843b073bfe0ef3f3cf900159f80dda4d921  game/animation_data.py
387452a1ea4665aeb1ca9337961295fefb6db81e97aa9c83ac7e857e5d289237  game/animation_draw.py
0d0fc72b71637d7e39706160f66c8f542bbaa1399453fef32fa2070a4a56c4ba  game/animation_types.py
afcbce75a0d6d3130fa67455c4226841168abc7d1461f54a0632909c5b35f7bf  game/attack.py
653e7eef7b36657e79270fd12f2393e76d15f9fbcf26aa68f4748a2711c437cb  game/body_action.py
dd0ea4d61ee234783973556db63c7bc32eb26386c7ddaf2a8926c6a47b5b61cf  game/body_hop.py
89a585aa3e728fe976724e20ac8a0d89ee08615a82a3df502ee3928eab828bdc  game/choreography.py
33ad0825a2c2cc6a179e5690c3d4e45f8d6a290f11795078f0e49fd29b526164  game/choreography_draw.py
582f7aa43e31833dfde5ef6eae361b5340b36e1f0385ec9e0a3075d29f30a1dd  game/combat.py
fae9ef6561b432fa10447a4fdc5cd63ea1be5f89b2b1022d6f9aeb3f23901d45  game/condition_animation.py
f8bd59ace92d9fb501df52fd0537e2ce8f580ac439f5937e15bcc079f689697a  game/data/body-materials.json
1ad1d3c7c3d113bd2a2d807ad7ae2cabd91ceda1d28c0800a9afb21864b35817  game/data/neuroclient/action-recipe-bindings.json
d9e4ccb3e3571e6b3b818e18e27a1f0cd468ea7214b248e02543f6bd853ea9d2  game/data/neuroclient/attack-profiles.json
05d91de45ac9a4dc91f6a258368cc6e5d0b378f0ee0361012b9d97b0292c40be  game/data/rigs/bison.json
0380d76e5239eb256e6b89c367e22848728d72a17a4f440f4f1da363d638ddc0  game/data/rigs/blueraptor.json
dcf9cd93ef3df11ec4c4cecad26f5e8f8b7f1764a10c0725a9e5dda212c0afb4  game/data/rigs/boar.json
7c29d482a4a77fa813154d94397df6c5d579eb61aaf245a4a9886394c894b6d3  game/data/rigs/brownbear.json
390329a74917b098c86a363e39f19d3ce5bad4e9bec9b21f8ae3bf7749955cfa  game/data/rigs/demonbeast01.json
79f164606a7091069a146a5e7c0084a55c7a7c1d01ac54119d1e7dbec95465dd  game/data/rigs/demonbeast02.json
083637f57a53db70b1cb1f4f988f2de90a5b75b6bb67213838fbe504c0995de5  game/data/rigs/demonbeast03.json
61099e25e7742de01cf4b1bf52c3cc0f870b9504db04d9a467383db403029a34  game/data/rigs/demonbeast04.json
eadbce8a4d489dddaa0089fc2da908051ee88fc88744ad603d403d7c0d0e525e  game/data/rigs/demonbeast05.json
2f1ffa97de92b0633413698c39eca13f76e9c7faf59567620f5a9eb06369a63f  game/data/rigs/elephant.json
84f980f5e3fe026763228788f69cd2c79e68d094c8acd56c14f04b6e9d6c34d3  game/data/rigs/goblin01.json
6c03d7d9e406a0dd6efa3398c88b66ff4db3622b925b595c052c6243fc349df6  game/data/rigs/greywolf.json
a37168b5df9cb92ca40e031a82516718fe7a7b122fc509febe595b6399008b5d  game/data/rigs/imp05.json
7b5429660aeb366b68e6f636190e15b9ed90eb06f7b60cd70c08192ee9c50b9e  game/data/rigs/jaguar.json
894bd17870c3e4d22e43666e8fca264b3c3ed2de5688cd35ddb6e5b3a92a86bf  game/data/rigs/lion.json
65f10092c0418887189dc6d544b07efab5a8e3d64b2dccae6b028d6a1b42f427  game/data/rigs/mammoth.json
ba2c8c9824ac857f62a8658e45dcf16780e77cf3acddb3e07490fc9ab282848c  game/data/rigs/orc01.json
df72753abc1c80a2c2330a8448515ee60953ba8d4fae82e26229c5f11acdbaaf  game/data/rigs/ostrich.json
1676ad3e4e02e6279b6f8c12cbdedd31fff7fdaac750bc0f038d37bdf0e333d7  game/data/rigs/polarbear.json
58fdad112fb8730a9ce6e40cefb37776ea71d81f075338b0165f866c5d22d48b  game/data/rigs/rhino.json
539ac12f1c35f528b03792db0be830b52a42bb9d7ec32fde39a0efdaa4cbec31  game/data/rigs/shepherddog.json
2b28501e9dd5a931e2d7bd22ced44f29721745eef8ea87c38cf4169ddd18e038  game/data/rigs/skeletonarcher05.json
ad031feb7d8331b0b29f0c4e62216a1e18e97ea61968fa94299fb3f728c0d6ba  game/data/rigs/stag.json
ab72c74211f20d1963eabaf79893ce032287b1ffa5635b046c2441dfd2d62f0c  game/data/rigs/stegosaurus.json
00181410f7ca6b802e0b08eadd5b472460726ac4738566515797e1e7ba5ea8c7  game/data/rigs/tiger.json
11d57a1b54431841b005880eead7fa84c7fbac1800d207b40d8d1e8185f8e665  game/data/rigs/triceratops.json
5c61dd730a06c6f9e1c94bfb6c41824771e45a95ae42c62071f13649afad7856  game/data/rigs/tyrannosaurus.json
66c56e88dcd33aca3f5e7587cabcd90253db0a3fe004f5a01289f2ba7c17c279  game/data/summoning_spells/README.md
65e39a703b8170d881d94f79b9a714fd6154bbf10b42489c54a5cd01ada5a0e5  game/data/summoning_spells/bindings.json
37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570  game/data/summoning_spells/projectile-assets.json
3cf11e7ccb8d98715a66751e366f488912f6518bb58b1ad17dec1b587f09c118  game/data/summoning_spells/spell-studio-drafts.json
2ab4e86c93a91b7098fbd434edca3213ebe85e79c42cf939a22aad933202dbdc  game/event_record.py
0b0cd7988438b43cdf709a38060b994c60807dfa2d34574d5346c4cda697fde5  game/forced_movement.py
5a50c70d3c2fd2309658cc1d628d9ec1f7634de5ce0d6bfc1f158c2acbdf671a  game/player_facts.py
68def23141df22d7e1bd9be77b8216bf873e5761345915f7fdfed0f1a11158b9  game/player_projection.py
ad40dc6044d4a535f12c1bf488c9c30b56168eb4627dee0d853469c569c109b3  game/player_reduction.py
72e5d5d2e097a8fcba27cdf1c9fdbf51dd31004e340e098a43745142d4f9288f  game/presentation.py
7729dc83cb808334bb8f602cb66ddaf4ce513a48646ec99599e5395692621333  game/scene.py
d7ffdd7e664546c16c8754893f7a8c6cef860ca64057cfa5b95abf5e06559d30  game/session.py
b2cc18bef18d4519abc3a52a794f97c390a5a203a00cd9da248fca3122fe82f5  tests/game/test_action_sequences.py
badb12a76ceb6782f6485cb88ff97a4686747e9d25ef8f417244d6c606994a48  tests/game/test_recorded_history.py
6fd7a2dd81a10795a74328311a536099a351960d26cd4d14b310bf0a2c78ff0a  tests/game/test_rig_body_contexts.py
f51e9eee649ad0e6f186a95b9c087c888bf6b10a16868fc57beb2ce14c7e4e43  tests/game/test_summoning_presentation.py
```

## Subsequent native-gallery finding ER-2 — placed contacts restored old child HP

The real gallery exposed a missing production-input boundary in the earlier
sequence checks. Root explicitly authorized this reviewer to investigate and
fix only a proven Multiattack prestate/ordering error. This section supersedes
the earlier approval for the two changed files; the other scoped findings remain.

Evidence: saved public input at
`.runtime/animation-review-summoning-20261003/runs/20261003T175125Z-eb3951/cases/summoning-animals-brown-bear/input.json`,
root `9b7b476e-3522-43df-8c7d-5d7f4529031e`, recipient
`6b537f8a-15f2-4f1b-84f3-9411a82240c7`. Native facts reduce HP from 488 to 483
after the first child. The second child misses and the head's final HP remains
483. Without supplied contacts, playback also remained 483. With the ordinary
scene's placed contacts, it restored 488 at the second child's start, 1750 ms,
and retained that incorrect display through the miss. The original native
rules and generic sequential scheduling were correct.

Cause: `bind_attack` preferred the complete contact supplied at the enclosing
head's entry. That contact correctly retained the visual placement but carried
old HP. The shared child prestate already contained 483. The correction in
`game/attack.py` preserves the contact's placement/facing fields and replaces
only HP and life state with the retained child's public actor values. It adds no
live-registry access, native rule, special Multiattack branch or art change.

The existing native sequence fixture now covers each of bear, dretch and
huntsman with a second hit and a second miss, passes ordinary scene contacts,
and checks HP at the second child's start as well as the final reducer value.
All six HP cases failed before the production change, including the hit cases'
brief precontact restoration. Afterward:

- `/tmp/summoning-multiattack-contact-red.log`: **6 failed**, before the fix.
- `/tmp/summoning-multiattack-contact-green.log`: **29 passed** across native
  sequences and summon/material presentation, after the fix.
- `/tmp/summoning-multiattack-attack-regressions.log`: **45 passed** across
  existing attack animation, combat misses and object-attack animation.
- `/tmp/summoning-multiattack-contact-types.log`: **0 errors, 0 warnings** for
  the changed production and test files.
- `/tmp/summoning-multiattack-saved-input.log`: the exact saved Brown Bear
  input remains at 483 at 1600, 1749, 1750, 1751, 2200 and 2916.667 ms; the
  missed second attack's retained target contact is 483 and has no damage result.

Correction hashes:

```text
fbb165b6b927fa2fe0c7848e9d1567ab7e2cc50ba47c829be0a3321de26be47a  game/attack.py
505ee1116600f7356c2634c0efce2298e4b5abfd83e2e91bdfc43793aeeb4de3  tests/game/test_action_sequences.py
```

ER-2 is fixed with focused evidence. Because this reviewer authored these two
changes under the later instruction, root inspected the target-state-only
correction independently and reported agreement with its acceptance.
The running whole-game process had loaded older Python and cannot alone certify
this correction. Animal shadow data is separately being corrected by its owner;
the initial rig hashes above are historical until that work's final freeze.

## Subsequent bounded review — ordinary archer profile and shadow opacity

**Approved at the source boundary.** Root requested this independent check after
the whole-game run identified a real missing-media failure in the existing
residue-workshop encounter. This is an ordinary compatibility correction, not
new undead summon content.

The `skeleton-archer-ranged` attack variant matches only
`smallscale.skeletonarcher05` and projectile delivery. Its existing precedence
owner selects it ahead of generic ranged data. Comparison with that generic row
shows the same body, clock and projectile payload: Attack3 maps to the fixed
rig's existing 15-frame/12-FPS QuickShot, with release/recovery frame 10. The
only presentation change is removal of the unavailable modular Slash1 overlay.
The generic ranged row remains unchanged; no source event, action executor or
projectile path was added. `/tmp/summoning-workshop-gap-fixed.log` records the
actual native workshop passing. Its test still requires no presentation gaps;
the assertion change adds the actual gap list to failure diagnostics.

The shared `BodyRig.shadow_alpha` field is constrained to [0, 1], defaulting to
the prior fixed-rig value 0.5. `resolve_actor_layers` passes the authored fixed
rig value to the existing shadow `RigLayer`; the modular root keeps its previous
0.5 setting. `_body_image` applies that value once as surface opacity while
retaining the PNG's per-pixel alpha. Thus a derived shadow that already owns
opacity uses 1.0 and is not halved again. `_actor_blit` excludes the shadow from
Fey palette/alpha application, and the existing painter keeps it on support.
This is passive rig data consumed by the existing renderer, with no species
branch or mechanics lookup.

Exact reviewed source/data/test hashes for this bounded correction:

```text
73e2704c47f2ee924c5e25c9afeeda1ce99cd228d421509f35a1a27ff8e76eb0  game/animation_types.py
e8fb46a8000a0e90c489aeb2d4601b64b3083f431ce4c064838f5486bab8a56c  game/animation_data.py
add6f095abdf951ed71bfdac96f4fcea8561f708b48d1dca0bc2436049fd77b5  game/data/neuroclient/attack-profiles.json
badb226053071a6966958606f2dba3be8f82a3361e641a71821a2ad6db0d8091  tests/game/test_encounter_play.py
```

The final 18-rig shadow data/provenance freeze and actual new shadow pixels remain
with the art owner until its handoff. This source review does not claim those
still-changing files were frozen or inspected yet.

## Final staged shadow review

**Approved for the reviewed source and staged binding/pixel contract.** Root
retains installation, final native gallery and integration acceptance. No source
blocker remains from the bounded event/render review; ER-1 and ER-2 are resolved.

The art owner froze 18 staged bindings under
`.runtime/summoning-art-20261003/shadow-bindings/`, held outside active data
until root's loaded-code suite finishes. The reviewer independently verified:

- All **98 PNG files**, totaling **3,655,700 bytes**, match the exact sizes and
  SHA256 values in `shadow-receipt.json`.
- Removing only the additional shadow slot/category/sheet references, opacity,
  resource entries and shadow provenance produces the active rig's exact
  existing body/content data for every one of the 18 bindings. Remaining
  provenance changes are confined to `summoning_body_review`.
- The normal animation loader admits the staged files directly using its
  existing `rig_files` parameter; no patched registry or special render path is
  involved.
- A bounded real-pixel check using the normal layer resolver, media loader and
  `actor_draw_commands` confirms Jaguar Idle's derived per-pixel shadow alpha is
  unchanged in all four views. The ordinary and Fey shadow RGBA and surface
  opacity match exactly; the Fey body retains material alpha 0.7, and cached
  source surfaces remain unchanged. Receipt:
  `/tmp/summoning-shadow-alpha-review.log`.

The art owner's paired-source receipt reports exact visible recomposition with
source alpha. It explicitly records that original shadow pixels underneath an
opaque body cannot be recovered and are left transparent; a lifted or translucent
body may expose that region. This review preserves that limitation and does not
claim reconstruction of hidden source pixels. Root was asked to include final
Fey Jaguar pixels in visual acceptance.

Shadow receipt SHA256:
`a9d5ed100dd0eb276513a448eddde192eb2381baad1841481de5de893865d7ea`.
Staged binding map aggregate SHA256, using the sorted JSON method defined above:
`a626866e654ef5722bd953a5518bea4f3ccea67eecd7907d6bde93e6a17a3d24`.
These hashes bind the staged bytes; they apply after installation only if those
exact bytes are copied to the corresponding active rig paths.

```text
3079d4feeb7ca513b98d74572825320959b4e43b1144a5563589c5cb5288ed43  .runtime/summoning-art-20261003/shadow-bindings/bison.json
912987778b312a4302ed3c8b6e674b6d446e15b330d18f3a4b0594e44aa5ecb6  .runtime/summoning-art-20261003/shadow-bindings/blueraptor.json
0520b908d7d00c4bbcd4a3f5c3a07dd6d974ed83e017d34da2d45f38fe74233e  .runtime/summoning-art-20261003/shadow-bindings/boar.json
193ade504a25743919611f7eecd559a6cd11f5d704cc84881b143d37c666463c  .runtime/summoning-art-20261003/shadow-bindings/brownbear.json
3ccbd813f6688620c292678a28a0587ba62cf9f6381961956275b189f04be811  .runtime/summoning-art-20261003/shadow-bindings/elephant.json
79f2bde48976bf34bf619377b4f5224f14719cabbf7621d57ebdf2c1e70caa9b  .runtime/summoning-art-20261003/shadow-bindings/greywolf.json
ae6d16aa68bd48c562fefd46c45a573e2c0095b681563e8246bb8007063f258c  .runtime/summoning-art-20261003/shadow-bindings/jaguar.json
fd2bdc923bf27a247dca6fd77f09e07ca75588703789893792bcab2d6d6b4e1e  .runtime/summoning-art-20261003/shadow-bindings/lion.json
1d3001b120ed1f8d1b4f87c2cf29c4b04c484d197e9745b2595706204477d0aa  .runtime/summoning-art-20261003/shadow-bindings/mammoth.json
ccbcd313bcb33a143b44661da07a5051d0f305522b7880d731371a44329f9127  .runtime/summoning-art-20261003/shadow-bindings/ostrich.json
8f755e0ed362e22d529ed045180c4a80ee3831291260881aadd166036e3fc3cf  .runtime/summoning-art-20261003/shadow-bindings/polarbear.json
895fdbc0b6f201d7b2fb1a48719dae36797b774f9ef8d1f593aa7076ed2326d2  .runtime/summoning-art-20261003/shadow-bindings/rhino.json
cefb52d22bf85fa3b4b23a505bb04a2af061eb36249d0ca8a30d33ed287f8adc  .runtime/summoning-art-20261003/shadow-bindings/shepherddog.json
6df6a464c749f9f0ddd55d9180979346476fae3a391c93abe0b6a894a18f7a09  .runtime/summoning-art-20261003/shadow-bindings/stag.json
7c768203d94199a14c5669dbf383157f814a56b7d9ba3608f3f23844bf1ed946  .runtime/summoning-art-20261003/shadow-bindings/stegosaurus.json
0e516f03b8c4882d16a487eb6aae2d572c480a5ffee28f4f8040b6c8abe441f0  .runtime/summoning-art-20261003/shadow-bindings/tiger.json
8675ea92c297fb89e5a6e95b99cdd8be1612957ce239f302c4d8f4cdc007dd06  .runtime/summoning-art-20261003/shadow-bindings/triceratops.json
2062f1e490d9209227ca6845607b91a7332646cb1be075d5e04d5275927a0caf  .runtime/summoning-art-20261003/shadow-bindings/tyrannosaurus.json
```

## Final source refinement — commands sequence; passive consequences share the anchor

**Independent bounded approval; source freeze recorded below.** The broad game
run found an actual ordinary portal regression from the earlier generic Action
sequencing. In the native occupied-hatch activation, a direct
`SpatialEffectStateFact` started the opening and returned its finite visual end.
Treating every received child as a subsequent command delayed the sibling
`PortalTransferFact` until the entire opening ended, violating the existing
authored fall milestone 50 ms after opening. The red reproduction is
`/tmp/summoning-portal-game-probe.log`: **20 passed, 1 failed**.

Root's correction changes only which children advance the existing
`sequence_at` cursor: Action, Attack, Spell, Movement, Shove and Equipment facts.
These are the existing typed command owners. Passive state/condition/portal/
faction consequences retain the current effect anchor, while all children still
have conditions compiled and subtrees joined, and still contribute to the
parent's completion. There is no portal-specific branch, new delay, field,
timer or queue. Spell roots remain outside generic Action sequencing; ordinary
Multiattack Attack children retain their complete sequential child joins.

The reviewer inspected the shared traversal, its timing helper, the unchanged
native three-perspective portal assertions and the completed receipt.
`/tmp/summoning-portal-sequence-fixed.log` records **40 passed in 62.59 s** across
portal presentation, native hit/miss Multiattack and summoning presentation.
The tests retain the original opening/fall equality and 50 ms assertions,
subjective endpoint grants, damage after ground settlement and backward-seeking
checks; no acceptance assertion was weakened. This also retains the previously
corrected target HP prestate behavior and postcondition joins.

Final relevant source hashes after this refinement:

```text
d751297601a793cf96fb2903039aa0f0978a3f9636a12cb1fba2ccb446f84686  game/choreography.py
fbb165b6b927fa2fe0c7848e9d1567ab7e2cc50ba47c829be0a3321de26be47a  game/attack.py
505ee1116600f7356c2634c0efce2298e4b5abfd83e2e91bdfc43793aeeb4de3  tests/game/test_action_sequences.py
```

No remaining scoped source blocker. The core whole-game process had loaded
older modules, so root must reconcile its eventual result with these focused
final-source receipts. This review does not claim that still-running process is
a green run of the corrected source or that staged shadow installation is done.

## Final closure — full-game reconciliation and installed gallery

**Review complete: approved within the stated event/render/recorded-lifecycle
scope.** Root owns the overall delivery ledger. All identified source blockers
have concrete corrections and final focused receipts; the original findings and
historical failed checks above are retained rather than erased.

The complete broad game run finished with **3,109 passed and 6 failed in
3,053.47 seconds**. It had loaded the earlier modules. The six failure IDs are
reconciled as follows:

| Broad-run failures | Exact disposition |
| --- | --- |
| Existing workshop: 1 | Fixed the rig-scoped archer profile's unavailable modular slash; same body clock/projectile. |
| Occupied portal: 1 | Commands advance the sequence cursor; passive consequences share their effect anchor. Existing 50 ms hatch/fall assertions retained. |
| Lever/spikes, two observer views: 2 | The same command/consequence anchoring correction fixes these original contact clocks; assertions unchanged. |
| Ranged True Strike hit/miss: 2 | Corrected stale test literal 8 to the preexisting accepted bow release frame 10; no production timing change. |

For True Strike, the reviewer independently verified pre-summoning commit
`5ff3d983c0912d2419473b394384ec08742d84a6` already contains ranged release/recovery
frame 10. The earlier `.runtime/bow-release-fix/before.log` demonstrates native
shortbow failures at frame 8, while `after.log` records 87 passed and the saved
11:22 native gallery documents that earlier change. True Strike's draft supplies
weaponGlow child poses, not a replacement child clock; its parent cast is
disabled. The corrected test still requires equality with ordinary Attack's
profile, contact/release/completion and projectile, plus exact weapon identity,
native outcomes, final HP and its authored overlay. Changing that literal is a
stale expectation correction, not weakening the ordinary-attack contract.

The final seven-file rerun at `/tmp/summoning-final-game-reconciliation.log`
passed **96 checks in 120.20 seconds**, covering every one of the six original
failure IDs and the surrounding attack, sequence, summon, portal, trap and
encounter cases. `/tmp/summoning-source-freeze-types.log` reports **0 errors,
0 warnings**. This is an honestly reconciled broad run plus targeted final-source
reruns; it is not described as a new all-green 3,115-case single run.

The final gallery is
`.runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/index.html`.
Its receipt records **38 paired-perspective clips, 1,350 passing checks, 8,638
frames and no HP increases**. The remaining declared gaps are passive Summoned/
control/trait/initial-condition decoration messages, not missing summon/dismiss
body gestures. Decorative arrival/departure VFX remain the previously deferred
work.

The reviewer independently compared all **27 gallery rig snapshots** and their
binding receipt against active `game/data/rigs` files: **zero mismatches**. All
18 staged shadow files are now installed byte-for-byte, as recorded by
`.runtime/summoning-art-20261003/shadow-activation-receipt.json`; the staged hashes
above now apply to the corresponding installed paths. The prior staging/install
caveats are closed.

Representative final video frames were inspected directly, not inferred from
posters: the controlled Fey Jaguar's attack, its attack against the former caster
after real control loss, and Brown Bear's second missed attack. The Fey material
and support shadow persist with the same living creature across control loss;
the Brown Bear miss displays opponent HP 483 in all four views. Exact extracted
frames are under `inspection-shadow-final/` in the gallery's output root:
`summoning-fey-jaguar-4-0-Attack2.png`,
`summoning-fey-jaguar-33-0-Attack2.png`, and
`summoning-animals-brown-bear-22-1-Attack2.png`. The art owner additionally verified
all 30 second-child samples per observer. This reviewer does not claim to have
watched every full video. The documented limitation on original shadow pixels
hidden beneath opaque source bodies remains a provenance limitation, not an
unverified claim of reconstruction.

Final closure hashes, supplementing the exact source hashes above:

```text
4aa03213c9dc45101a7d797f89f8320237a66ae8196a13c05eb88a6f091277e3  /tmp/summoning-full-game-frozen.log
0343bfe908ec527fc23fc5d45e748aab102402a8b52f3457d5514e5b48821fe1  /tmp/summoning-final-game-reconciliation.log
46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb  /tmp/summoning-source-freeze-types.log
2c59ec525fc835d17a42cc825ea1e1b8fecfe25ace7500cbe5a3bfc47ad3e6f0  tests/game/test_true_strike_presentation.py
ed16f71dda73ccee0963da72d407e902b352a7d79ad1746f443dc490f18d749c  .runtime/summoning-art-20261003/shadow-activation-receipt.json
1fe9826587f01ad48657e00ee8d09d428b9ed195e47b140f670e1a61b2d3ef2c  .runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/manifest.json
49d7caccb1f142671ec9c165916608265829c4924dd2e7cbe7eb361726ebf189  .runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/binding-receipt.json
122f7415fb475165860c7669223902b8fe709364c9c78aa0f09dad70b5b93a42  .runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/acceptance-receipt.json
7cee5118658ae6e6697731f1b7b56c859ea7c29fba1fc930766064017aa54e60  .runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/native-lifecycle-visual-receipt.json
```
