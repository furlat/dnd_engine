# Summoning: independent full implementation anti-slop review

Review date: 2026-10-03. This is a source and receipt review of the authorized
summoning delivery, not another design proposal. Only this audit was edited by
the reviewer; no production changes, tests, other-chat reads or messages, or
additional agents were used.

Authority: unified plan SHA256
`d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`
and visual addendum SHA256
`28dbdf5dec4fcc45afe6a5434ca297ec22da58715a0f044dcd37b9ca18011075`.
The earlier packet 1 and Encounter/AI approvals remain in
[the scoped audit](SUMMONING_PACKET1_2_ANTISLOP_IMPLEMENTATION_REVIEW_2026-10-03.md).
They are not rewritten as whole-delivery approval.

## Current verdict

**APPROVED for the current native implementation and its scoped acceptance.**
No remaining concrete native anti-slop blocker was found after the corrections
below. This closes the earlier lower-condition AS-1 through AS-3 rejection for
the reviewed extraction and exercised native owners. The architecture stays
within the approved owners and bounded content.

Presentation architecture was reviewed, but final presentation acceptance is
**pending its final patch and receipt**. Combined test reconciliation and the
complete visual acceptance receipt remain separate, unfinished gates. This is
not whole-delivery or global-green approval.

Scope reviewed: the 24 ordinary canonical bodies and anatomical Attack route;
42 animal/Fey/fiend choices and three spell adapters; native existence/control,
concentration, birth, deployment, terminal retirement, stable encounter/AI turn
identity, alternate-rig body contexts, passive public projection and Fey
material. No arena expansion, new artwork, undead, Familiar, server feature or
additional spell was considered part of this delivery.

## Findings raised during this pass

### AS-F1 — old summon retained agency during replacement publication

The initial implementation removed Summoned during concentration commitment but
waited until the settled hook or removal completion to revoke the old creature's
agency. Incoming birth/presence observers could therefore run after existence
ended but while the old registered creature could still react.

The current `ConditionRemovalParticipant.commit_condition_removal` callback runs
after the native condition indexes are removed. Summoning's implementation only
revokes the exact existence owner's agency there. Retirement, controller closure
and initiative surgery remain at the existing graph-settled boundary. This
corrects the ordering without a new registry or event route.

**Resolved in source and focused receipt.** The birth observer regression checks
existence, runtime agency and action permission together. The earlier failed
72-case attempt is historical; `/tmp/summoning-lifecycle-dispatch.log` records
87 passing lifecycle/presentation cases after the correction. The reviewer
inspected the source and receipt, and did not rerun tests.

### AS-F2 — old spell and equipment recordings rejected additive fields

`SpellEvent.summon_application` and inherited
`EquipmentEvent.release_reason` were initially absent from the finite
`game/event_record.py` additive compatibility table. `decode_event` requires
every other nonexcluded native field even when it has a default, so existing
archives failed before passive reduction.

**Resolved.** The table now names `summon_application` for SpellEvent and
`release_reason` for EquipmentEvent and all six concrete equip/unequip events.
No codec fallback or alternate recording format was added. The new eight cases
check current payloads, omitted-field decode/encode equality and absence of live
runtime reconstruction. `/tmp/summoning-codec-compat.txt`: **8 passed**.

### AS-F3 — Wet membership removal reentered native removal during commit

The original `WetSurfaceMembership._remove` directly called
`target.remove_condition_by_uuid(Wet)` during `cleanup_own_state`. A summon
standing on water owns Wet before its membership lease; reversed aggregate
removal visits the lease first. That nested ordinary removal could publish
before the outer graph committed. It is directly reachable during dismissal or
expiry, not a speculative unrelated condition case.

The first correction called `add_shared_subcondition` but omitted the new Wet's
primary parent, preserving it as an independent condition after the last lease.
The existing overlapping-water and electrified-water failures exposed that
mistake; it was reported as part of the same finding.

**Resolved.** Newly created Wet now receives the source lease as its primary
parent before registration, while already-existing standalone Wet keeps its
independent ownership. The nested removal hook is gone. Native dismissal/expiry,
overlapping sources and environmental water interactions use the same existing
graph. `/tmp/summoning-wet-terminal-final.log`: **35 passed**. No new ownership
or condition framework was added.

### AS-F4 — unknown attack rig selectors escaped admission

`validate_rig_body_contexts` initially skipped every rig ID absent from the loaded
subset, accepting misspelled IDs as well as intentionally unloaded installed
rigs. This contradicted the addendum's explicit unknown-ID rejection contract.

**Resolved in source; focused receipt pending at this checkpoint.** The loader
now derives known IDs from the existing installed rig JSON inputs and rejects a
profile identifier absent from both that set and the loaded rigs. The new check
contrasts a valid unloaded rig with an unknown identifier. There is no new rig
registry, renderer, profile matcher or runtime resource loader.

### AS-F5 — lit acquired torch could interrupt committed retirement cleanup

`Entity.commit_retirement` originally called `item.drop` outside its publication
error drain. The canonical Torch drop hook extinguishes its light, whose
pre-completion callbacks can propagate an exception. At that point the token
was already committed: Game/controller cleanup could complete while native
entity, grid and intrinsic ownership cleanup was skipped. The prior passive
`on_event` observer test could not detect this propagating callback case.

**Resolved.** The drop hook now contributes its failure to the existing aggregate
and allows remaining possessions, intrinsics, world presence and runtime
registrations to retire. The native test uses a real acquired lit Torch and a
propagating light pre-completion failure, verifies that the caller receives the
error, that every creature membership ends and that the same real torch survives
on the floor. It passes in the 130-case native correction receipt below. This
uses the existing publication-failure contract.

### Integration correction reviewed — effect admission precedes creation

The final spell adapter waits for ordinary EFFECT dispatch to finish before
invoking its exact bound system owner. `EventQueue.invoke_admitted_system_effect`
uses the existing handler registry and dispatch evidence, requires a registered
admitted effect and an enabled empty-trigger SYSTEM handler, and preserves the
event lineage. The high owner returns the original event for duplicate admitted
delivery. Late EFFECT veto/exception therefore preserves the old summon and
concentration after native costs are spent; it cannot cancel after a new birth
has already committed. Those cases pass in the final native correction batch.
There is no second command stream, executable event payload or renderer route.

## Ownership and scope assessment

No additional concrete architectural blocker was found in the inspected scope.

- Canonical recipes, anatomy and ordinary creature composition remain separate
  from being summoned. The high system materializes an installed recipe and
  applies instance provenance/conditions. Fey's creature-type adaptation is
  instance-local. Body weapons use native equipped-item identity and the shared
  Attack/Multiattack costs, access, damage and AI outcomes; there is no parallel
  creature attack resolver. Native Multiattack children now carry explicit
  `action.attack` behavior identity instead of requiring renderer inference.
- The high summoning owner holds native references and admitted tokens. Spell
  discovery is a cold selection query with dedicated unpublished validation;
  actual creation revalidates through native composition/world/encounter owners.
  It does not maintain a second HP, faction, action budget or duration. Native
  BaseAction retains its existing paid-interruption boundary.
- Animals/fiends use direct Summoned or concentration-to-Summoned. Only Fey has
  the extra untimed control marker. The one ordinary duration is interval-
  deduplicated, skips the birth interval and pauses outside an active encounter.
  Losing Fey control changes its native faction to an explicit unique hostile
  value and keeps its body, identity, remaining duration and existing AI. The
  former controller loses dismissal authority.
- Prepared condition/concentration ownership remains below summoning. The
  extraction separates state commitment from membership consequences and
  completion publication. The previous admission/cancellation exceptions,
  initial publication drainage, Haste/Antimagic terminal consequences, spatial
  light/senses and wall-section issues have targeted corrections in those
  owners. AS-F3's final correction and native receipts close the remaining
  concrete callback-in-commit finding from this pass.
- Game/Entity retire exact owned composition, while current containers decide
  possession ownership. Real acquired items survive on supported ground;
  intrinsic anatomy ends. Unrelated effects sharing a source UUID are not
  treated as owned descendants. Encounter owns membership and turn identity;
  the existing NativeAIController and assignment path own decisions.
- Alternate body selection extends the existing BodyRig and attack-profile
  schemas. Nonattack selection is a pure exact-qualifier/role-default lookup.
  It retains the selected primary/recovery playback and markers in existing
  cues, including movement/connector, Shove, forced motion, condition poses and
  neutral disabled gestures. It does not add an event consumer or animation
  runner, or select art from native creature code.
- Public projection retains manifestation, observed faction and typed terminal
  presence without exposing summon provenance or resolving live identities.
  Ordinary sight loss is separate from terminal departure; reacquisition uses
  currently disclosed state. Fey uses the existing body material path and
  preserves the independent shadow. Deferred summon VFX remain deferred.

## Evidence and acceptance limits

Read AGENTS.md, RECOVERY_PLAN.md, HOW_TO_TEST.MD, the approved plan/addendum,
implementation ledger and packet reports. Review used current whole owners as
well as relevant diffs; it was not a diff-only or test-count assessment.

Receipts inspected include: 87 lifecycle/presentation checks; 8 omitted-field
codec checks; 105 alternate-rig focused checks with one separately deselected
case; 38 mixed spatial/ordinary completion/replay checks; earlier 23 live
membership checks; and full active typing with **0 errors**. These are author
executions inspected by this reviewer, not independent reruns.

The final native correction batch at
`/tmp/summoning-native-corrections-final.log` records **130 passed**, plus two new
Wet test-fixture errors caused by calling `activate` without its required parent
event. The fixture was corrected, then
`/tmp/summoning-wet-terminal-final.log` passed all **35** cases, including those
two exact tests. Together these account for every one of the correction batch's
132 checks. Late EFFECT exception/veto, duplicate delivery, immediate terminal
agency and the lit Torch failure-drain case pass. The reviewer re-read the final
source and tests and inspected both receipts.

The earlier broad native/AI/architecture run recorded **2,520 passed and 5
failed**. Its final rerun at `/tmp/summoning-full-native-final.log` and the broad
game run are not complete acceptance evidence at this checkpoint. Neither stale
failed logs nor partial fresh logs establish final combined acceptance. Actual
native recordings, all-24 rig/pose validation, final presentation review and
remaining broad-suite reconciliation must be reported before whole-delivery
completion is claimed.

## Exact reviewed snapshot

The manifest below binds this checkpoint, including corrections whose focused
receipts remain pending. A later correction needs a dated follow-up verdict;
this snapshot does not approve future edits or unreviewed existing code merely
because it shares a file.


Snapshot recorded at 2026-10-03T17:42:50.718096+00:00.

Each group digest is SHA256 of its lexically sorted member lines, each encoded as
`relative-or-absolute-path + " " + SHA256(raw-file-bytes) + "\n"` in UTF-8.
The full member lists below make the digest reproducible without relying on a
mutable external manifest. Native acceptance is limited to the reviewed changes;
the presentation group remains explicitly provisional.

### Native summoning and spell adapter

**Group SHA256:** `1881d5f20291dd167bd0b532e86f4157ab24bc9b603b63240dbc906420a3a8f3`

```text
dnd/spells/catalog_content.py f5507ea9530e71933d7bd4f7fa5d03663e948b4b4d90e6523c2a0aa69255e5f3
dnd/spells/summoning.py a18ddb8c702f89986bff296507469e33efe98199d6f713177f110b05d8b158fb
dnd/summoning/actions.py db5ded8cb35967b350a853adaa1759a22f2d2bb62eaf92e49adc4c5fa765110a
dnd/summoning/conditions.py 909880597f3a082bde34cdcc4ca35cf33e4d0f325329b91dd56ff62f1e3d22d4
dnd/summoning/forms.py 145d4c0c4c6c2d89572ee4a9de876794da4c76584fe81c6fde53770646c0b3dd
dnd/summoning/system.py 6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009
dnd/types/summoning.py 861905da36883018471c12627f77acb9d5d3e76a9bc8a297e8fa56a42a443ed6
```

### Native condition, world and retirement owners

**Group SHA256:** `7323d64ec3ed39623078f8eb01b30beb2dff45ef75de76198c67576e1cd60950`

```text
dnd/actions.py 2934d3374572188a6e152e5d6b042ddaa994ace500d2af249d181ddb4b2b2ad3
dnd/actions_functional.py 18dc90b1a9d795daf001194148682143c57fe701de40a198142dcf498c6a733a
dnd/blocks/base_item.py 187528f66182b6028ee7079e75a8a9112311b22b31dc60798827455dc935fe7e
dnd/blocks/equipment.py c4fc444fe9fde70638210ce96f5d8e3c1ac47a654abfe07834f4240b2c1b027f
dnd/blocks/health.py fe1dd60829b44df54d6fdaa72d26fed9de6ec8cd4e782e5d77306ef6b611fba8
dnd/blocks/inventory.py 23d06b624c7f6cccbbce4e208d9f6828bf2447596d01264d5420c73133ac1f22
dnd/blocks/spellcasting.py 5f065f7d996ce645a9328fb2ce787473deab23bf0c089c2817d65648945d0a77
dnd/conditions.py 332700c8e3d2870f42f4c968ea879ea9c74df7fb044528c0364af28b403eb4b4
dnd/core/base_actions.py 439fdf1467a825a54c5c48b99b50ba5b28535419c3d0b5415f03b43a73101ee5
dnd/core/base_block.py 0ea5a0b5160eb38d6745be9541e220b98c74272f413fa1a71d06e360547ff405
dnd/core/base_conditions.py 2198c803c05fc771fc76dd22992d22aa3f13a5416a3045f9aeed58312c5dd01f
dnd/core/condition_types.py fa8f1925d172c3b6d1f487f048204e99b25965196bcaff304c8d84e6eda4069e
dnd/core/events.py 7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59
dnd/core/gridmap.py c5808bfba32961491a86c5ded8847ce51c8f0e7434de82e252020197f4eeea23
dnd/core/item_types.py fc4dcb8ea6c5229210947d559c8ff3c4458c2f67ea56cb2e2172e0028b27b290
dnd/core/values.py 3c8ac004dc669bec37ffe15a1efae20afc06aec04ff62eb472677961f6e2a122
dnd/entity.py 17fe81d7636e478fa05e0ff2f26fee4a8035dc92af0fe3a0e957bef5c5f5649a
dnd/game.py dee158751f31d3bba15a76cd1088775eca15f43935362566e60fc748f8692eba
dnd/spatial/area_conditions.py 21dc0944eac2c088699da3eea81949d9e8d9ba186f5e53de1e6ecb162f599c00
dnd/spatial/environmental_conditions.py 7288db6270c4f86487e4d84fba411083f83d14b8e0f21270ccc61c52dee0421c
dnd/spatial/restraints.py dfcfa4618e5f497d315723436b35008fc2724f1b2bb3c27e65ada4a86d825cba
dnd/spells/abjuration.py ab475a88c457f025c4c335c1e6fce33dc8dae03f8c7f81e38e8406df4f437f8f
dnd/spells/conjuration.py d104472865b7981718699d1def12136d74429d5e69f7abf2ffb2aa03f18757b7
dnd/spells/divination.py d4f487f1de7a6298d5ee344162814b79ce8ab08d47afdf69a48404e151d33210
dnd/spells/evocation.py 27dc2e30b07b74ec3c7ef07476f2dece4a6202f6d1b113c6610c813908203d70
dnd/spells/transmutation.py 4704405af6bba947d0d796fee58b5aedd246c98ef8df62e642a068bfef8703d9
dnd/spells/wall_constructions.py e712beea40faa8b5cfe7fd9c6484650519e8bd1658deb4b3499b91ee52803c24
```

### Native encounter and AI

**Group SHA256:** `9d5290b372c598acfcca649c93c57f9daed74b9404783f18419d04d5a669c7e8`

```text
dnd/ai/contracts/control.py ca4c24e0adab46d9e84c2ad9cda3335e15e67cc9e206d8a206b89d7df7633b42
dnd/ai/policies/basic.py 87ac6f764dffeab9e15ce4a01e374d21944d7e39e0508afb91ed2154c1237d32
dnd/ai/runtime/assignment_lifecycle.py 053be8eb375df442ab5c9e1fec441bfb271ddc699a2ad7198043240421582127
dnd/ai/runtime/decision_epoch.py aa38db5224c207d43b11378bffe919b37f6b232d47a2f4c722af1fd1a34d409c
dnd/ai/runtime/knowledge_reduction.py bb8a2ec1c87392b2341fd96b929c18b2d74c5a402729ab095ddea0c691431da1
dnd/ai/runtime/movement_revalidation.py f30b3abeeeb916ad78537906cda004d5378c64cecd2b8257af04e4190b3de27f
dnd/ai/runtime/state_projection.py f135859d9878fa45a64e05bf1554c87125e25706a5a9792419418d2940730c71
dnd/controller.py 724a323bb32a8397b98f4494bb16b09a1ba39369b80023f645271ae046251551
dnd/encounter.py ad10b9b964dc601865bf12755af2b3e2e5f7d0abecbfce37b1e8768c0ce718a8
```

### Canonical body content

**Group SHA256:** `ee313f7b943b1afee0774e8d4a6cd0f65b3e939bd6e21e46023cabeb5589a4e9`

```text
content_data/sources/srd_5_2_cc.json 5813bf68f91a06880e610adce7c643acdda931c68f7c656cb15c311de3950b5b
dnd/content/items/authored_item_builders.py 271f95a121d56b1106b251ab4508d8a7baf8b2f89aa4dcbb6599cf9e221fd595
dnd/content/items/authored_item_definitions.py 902b6a6d1a4fa778ffa08314489a5da5b7328f94368fabff905531c9945fc3a2
dnd/content_system/action_definitions.py fac7705cca5ab10c4be54758b6a295bdc5f6690047f812c90c36edef3c36914c
dnd/content_system/builtin.py 0192d5ec65769c9fdee4048ede61a8e7504cdcad7bf32d4b45479b37c826914e
dnd/content_system/builtin_inventory.py 733312dde223d59e7480351f4f5758a4bfaf5d7de20552add2e89ec8d1273549
dnd/content_system/condition_definitions.py 48fc9f1fd7bde42b0031b4fc72eb349ed0fe770d9b7823165abaf768d761c951
dnd/core/content/provenance.py adebb860339e17f9e7ac0472212db748ddb08e7fa531ed6eaf4c500164bbe56a
dnd/core/equipment_types.py 2b23b91c53bf016a8a6b1ae52d68b6225b886fafa62f8b71ec14bcb2360e31e4
dnd/monsters/beasts.py 7d0565c1ca045ee377761a2a0fb33415daf80029abdb4a4d9595f40cf449b5ee
dnd/monsters/fiends.py 01850efda56fbbd4193d48578f87324d3745042708944f9882df24816fc26513
dnd/monsters/multiattack_definitions.py 57f186b79f76aa1daa5e966ae462a7d6fbcecaa6c34bcb2a8200b4d68d21baa0
dnd/monsters/srd_roster.py 380267c62cceca67f470689f8c00de07c8fe495949673d01a86824bfb976f41a
dnd/monsters/traits.py 9c524d7b59cde21a0e399fd5e9f14d90cd192f792066d2c1005fc9e4b5494137
```

### Native correction tests

**Group SHA256:** `59d4e74e05fedeb498143ace9ecde4cb33c740dbcbc5badb9d3f5c6b655dc83e`

```text
tests/engine/test_action_template_ownership.py cf1b0bb52a6ba1f24e9505a28d712b70f906e06c8b3b1d8c4ee9ac343f28162b
tests/engine/test_condition_return_placement.py 3453773427fcfc7798bc80946a6c30c78bdc1750dcb0255024c69034963ac899
tests/engine/test_condition_silent_removal.py aaea6fa5dcc896e819db15032c7e26e0f8e9e9313cad0088d8a808f39c0ce074
tests/engine/test_live_encounter_membership.py 7a62c18a88742b5f907c72494a121090e358f256fdfa5ca8f50547e49398fdbf
tests/engine/test_prepared_condition_lifecycle.py 26dac70baa071b86163a240f28876f5bfd18ac3d0f30abbb4f8855b3216cdbec
tests/engine/test_prepared_entity_birth.py af2b1437fc3a71794396748f743927c288cce049f11d83bc5291c2a9eea57667
tests/engine/test_retirement_admission_failure.py be8b7ff55142fbdb59b9115b793a452cd42d939a84db31d083c4add454cd31fb
tests/engine/test_summon_retirement_ownership.py f345e144f430a43d4af313d733abe8d3daf417f29c4ac608a83d15bbd4946039
tests/engine/test_summon_terminal_consequences.py 571777b5c820b359a5097d3a0a534b5790bd0898f45a9d9cef69ec11c67f3591
tests/engine/test_summoning_lifecycle.py 7e4c49e4eddd718a0b9e28ef69d4098dab5b424d39250a55c879a0543a893a89
tests/engine/test_wall_retirement_commit.py 7ea9b6ae648d7688afe07367103ea3b35f91fe59025ee43c4d6e7e27ad529540
```

### Presentation source inspected, final acceptance pending

**Group SHA256:** `c0e45134e61e9e85f5a77e3e3ded720e7267768aa42895f50eb9347d89bc344b`

```text
dnd/actor_projection.py 131c1892d0b1486c1faf1072fcd02d454858a051b3c639b5ce58dfe1c46184fe
dnd/types/actor_facts.py 19b6977c0a4becb368276af5fda3e431932d50c8bea5fe005fbb38be8946a2b4
dnd/types/event_facts.py ead2190dd9803beaba12846d21c962a93a4ffb83c12dd3d51489274a6e6b7257
game/animation.py f82b30c25a2eef9a6f89fb11498751f110d827d5e352699a5194f1861a461af1
game/animation_data.py 441fe5ade31085312b312f0e3eaf075ddd903345000bd4888a0e5821fa418d34
game/animation_draw.py 387452a1ea4665aeb1ca9337961295fefb6db81e97aa9c83ac7e857e5d289237
game/animation_types.py 0d0fc72b71637d7e39706160f66c8f542bbaa1399453fef32fa2070a4a56c4ba
game/attack.py afcbce75a0d6d3130fa67455c4226841168abc7d1461f54a0632909c5b35f7bf
game/body_action.py 653e7eef7b36657e79270fd12f2393e76d15f9fbcf26aa68f4748a2711c437cb
game/body_hop.py dd0ea4d61ee234783973556db63c7bc32eb26386c7ddaf2a8926c6a47b5b61cf
game/choreography.py 89a585aa3e728fe976724e20ac8a0d89ee08615a82a3df502ee3928eab828bdc
game/choreography_draw.py 33ad0825a2c2cc6a179e5690c3d4e45f8d6a290f11795078f0e49fd29b526164
game/combat.py 582f7aa43e31833dfde5ef6eae361b5340b36e1f0385ec9e0a3075d29f30a1dd
game/condition_animation.py fae9ef6561b432fa10447a4fdc5cd63ea1be5f89b2b1022d6f9aeb3f23901d45
game/event_record.py 2ab4e86c93a91b7098fbd434edca3213ebe85e79c42cf939a22aad933202dbdc
game/forced_movement.py 0b0cd7988438b43cdf709a38060b994c60807dfa2d34574d5346c4cda697fde5
game/player_facts.py 5a50c70d3c2fd2309658cc1d628d9ec1f7634de5ce0d6bfc1f158c2acbdf671a
game/player_projection.py 68def23141df22d7e1bd9be77b8216bf873e5761345915f7fdfed0f1a11158b9
game/player_reduction.py ad40dc6044d4a535f12c1bf488c9c30b56168eb4627dee0d853469c569c109b3
game/presentation.py 72e5d5d2e097a8fcba27cdf1c9fdbf51dd31004e340e098a43745142d4f9288f
game/scene.py 7729dc83cb808334bb8f602cb66ddaf4ce513a48646ec99599e5395692621333
game/session.py d7ffdd7e664546c16c8754893f7a8c6cef860ca64057cfa5b95abf5e06559d30
tests/game/test_recorded_history.py badb12a76ceb6782f6485cb88ff97a4686747e9d25ef8f417244d6c606994a48
tests/game/test_rig_body_contexts.py 6fd7a2dd81a10795a74328311a536099a351960d26cd4d14b310bf0a2c78ff0a
tests/game/test_summoning_presentation.py dd3cb060224cbb9da30fc53af660bff6615d403365af4ec8330b3aab108af29a
```

### Existing-art binding data inspected

**Group SHA256:** `72411753ead26319b877c50356264afddd4d6d727ca786048ed8d68001ea6dd5`

```text
game/data/body-materials.json f8bd59ace92d9fb501df52fd0537e2ce8f580ac439f5937e15bcc079f689697a
game/data/neuroclient/attack-profiles.json 56de58249696aa90f4cec554502a5e1823858900f0e65bb63abdfb880646225b
game/data/rigs/bison.json 05d91de45ac9a4dc91f6a258368cc6e5d0b378f0ee0361012b9d97b0292c40be
game/data/rigs/blueraptor.json 0380d76e5239eb256e6b89c367e22848728d72a17a4f440f4f1da363d638ddc0
game/data/rigs/boar.json dcf9cd93ef3df11ec4c4cecad26f5e8f8b7f1764a10c0725a9e5dda212c0afb4
game/data/rigs/brownbear.json 7c29d482a4a77fa813154d94397df6c5d579eb61aaf245a4a9886394c894b6d3
game/data/rigs/demonbeast01.json 390329a74917b098c86a363e39f19d3ce5bad4e9bec9b21f8ae3bf7749955cfa
game/data/rigs/demonbeast02.json 79f164606a7091069a146a5e7c0084a55c7a7c1d01ac54119d1e7dbec95465dd
game/data/rigs/demonbeast03.json 083637f57a53db70b1cb1f4f988f2de90a5b75b6bb67213838fbe504c0995de5
game/data/rigs/demonbeast04.json 61099e25e7742de01cf4b1bf52c3cc0f870b9504db04d9a467383db403029a34
game/data/rigs/demonbeast05.json eadbce8a4d489dddaa0089fc2da908051ee88fc88744ad603d403d7c0d0e525e
game/data/rigs/elephant.json 2f1ffa97de92b0633413698c39eca13f76e9c7faf59567620f5a9eb06369a63f
game/data/rigs/goblin01.json 84f980f5e3fe026763228788f69cd2c79e68d094c8acd56c14f04b6e9d6c34d3
game/data/rigs/greywolf.json 6c03d7d9e406a0dd6efa3398c88b66ff4db3622b925b595c052c6243fc349df6
game/data/rigs/imp05.json a37168b5df9cb92ca40e031a82516718fe7a7b122fc509febe595b6399008b5d
game/data/rigs/jaguar.json 7b5429660aeb366b68e6f636190e15b9ed90eb06f7b60cd70c08192ee9c50b9e
game/data/rigs/lion.json 894bd17870c3e4d22e43666e8fca264b3c3ed2de5688cd35ddb6e5b3a92a86bf
game/data/rigs/mammoth.json 65f10092c0418887189dc6d544b07efab5a8e3d64b2dccae6b028d6a1b42f427
game/data/rigs/orc01.json ba2c8c9824ac857f62a8658e45dcf16780e77cf3acddb3e07490fc9ab282848c
game/data/rigs/ostrich.json df72753abc1c80a2c2330a8448515ee60953ba8d4fae82e26229c5f11acdbaaf
game/data/rigs/polarbear.json 1676ad3e4e02e6279b6f8c12cbdedd31fff7fdaac750bc0f038d37bdf0e333d7
game/data/rigs/rhino.json 58fdad112fb8730a9ce6e40cefb37776ea71d81f075338b0165f866c5d22d48b
game/data/rigs/shepherddog.json 539ac12f1c35f528b03792db0be830b52a42bb9d7ec32fde39a0efdaa4cbec31
game/data/rigs/skeletonarcher05.json 2b28501e9dd5a931e2d7bd22ced44f29721745eef8ea87c38cf4169ddd18e038
game/data/rigs/stag.json ad031feb7d8331b0b29f0c4e62216a1e18e97ea61968fa94299fb3f728c0d6ba
game/data/rigs/stegosaurus.json ab72c74211f20d1963eabaf79893ce032287b1ffa5635b046c2441dfd2d62f0c
game/data/rigs/tiger.json 00181410f7ca6b802e0b08eadd5b472460726ac4738566515797e1e7ba5ea8c7
game/data/rigs/triceratops.json 11d57a1b54431841b005880eead7fa84c7fbac1800d207b40d8d1e8185f8e665
game/data/rigs/tyrannosaurus.json acf5c0f54caf38c4498e72e388e6604e730a5c5833c1ba9b75dd9c067edc5c82
```

### Correction receipts

**Group SHA256:** `84792986f4c95a9d170f3a8714207198acd16b12ad794769df65989cc339c17b`

```text
/tmp/alternate-rig-final-focused.txt 9891f38c6c0ccce1708288c19616f64c6b8d45de00c1f453d8e2ffaa82bbe05e
/tmp/summoning-codec-compat.txt 4647c43850c79b8513a02f81e615a24dd333de22ea11dc3c22a2b330ae6f95f6
/tmp/summoning-full-types.log 46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb
/tmp/summoning-lifecycle-dispatch.log ddc399123354e37efac10b87836a2f15d7b502dd57589c3b4d322079d6b07151
/tmp/summoning-mixed-closure-tests.log ccb31c213aec79c282dfecced9bc03f70dcff4d526e40b01af26263c4c2dd6b2
/tmp/summoning-native-corrections-final.log f8391b10cc68c83c6ed1f06c55c1e224eec5f60d2acb278ca3adcbab9bd4b1b4
/tmp/summoning-wet-terminal-final.log 093addcbc498dcac675cabd1fed6411f54196dad5bade0064430478167df4942
```

## 2026-10-03 amendment review: Raptor, appearance scale and original shadows

**APPROVED for this bounded content amendment and shadow implementation
strategy. No concrete anti-slop blocker found.** This does not approve the
pending installation of staged bindings, final shadow/Fey/scale visual quality,
or whole-suite acceptance. The preceding native approval remains scoped to its
reviewed owners; no lifecycle redesign was requested or reviewed here.

Current amended plan SHA256:
`6fa3185abc6e79c3d47667277541476192622f2af922a3d4f3365e17f7a7811c`.
Current visual addendum SHA256:
`a8b38482d69680fe2dfdfa850f2889b00c69fc32a37c4a4fc72f741d475b11e9`.
The documents correctly retain the earlier accepted plan hash and identify the
later human amendment instead of presenting it as the original proposal.

The vendor T-Rex body now maps to the ordinary canonical Raptor. Its declaration
uses the already selected Allosaurus numerical baseline: Large, 51 HP, AC 13,
speed 60, the specified ability scores and Perception expertise. Native body
weapons are Bite 2d10+4 piercing OR Tail 1d8+4 bludgeoning, each reach 5. There is
no added Multiattack, rider, bonus attack, grapple or special executor. Animals
unlock at slot 5 and Fey at slot 6. Creature/item identifiers and the exact rig
content reference agree. Vendor rig/PNG names remain provenance; Raptor retains
appearance scale 1.55. Other authored Large/Huge values, 1.5–2.6, flow through
the existing Appearance.visual_scale and leave native one-anchor placement
unchanged. They still require the user's requested visual quality inspection.

The importer implements one explicit `paired-visible-shadow-v1` derivation. It
requires equal source dimensions, binary body alpha and exact equality of every
opaque body pixel with the combined original. It copies visible combined pixels
outside that body and leaves occluded pixels transparent. Both input members,
the original archive and the derived output have byte/hash validation. Import
admission finishes for the entire selection before writes begin; `--check`
compares without writing. There is no runtime source scan or guessed geometry.
Existing bodies/originals are preserved rather than overwritten by the derived
shadow layer.

`BodyRig.shadow_alpha` is a single bounded passive float, defaulting to the old
0.5. The existing fixed-rig layer resolver uses it only for the shadow slot;
the staged recovered layers select 1.0 to avoid attenuating their already
authored alpha twice. Existing rigs retain the old default. This is a minimal
extension of the existing rig/layer owner, with no new renderer, schema family,
event route or creature-specific rendering branch.

Read ASSETS.md and the staged receipt/probe. A read-only comparison of all 18
staged animal bindings against their active counterparts found no changes to
creature identity, body sources/provenance, existing geometry, context mappings
or timing: only the shadow additions/policy differ. The source probe reports 98
paired sheets with zero partial-body-alpha or opaque-pixel mismatches. The
staged receipt reports 3,655,700 derived bytes and explicitly says active
bindings have not yet changed. No staged art was activated by this reviewer.

The limitation is accurately disclosed: the original pairs contain no shadow
information beneath opaque body pixels. Those regions can become visible with
body lift or Fey transparency. Source-exact recomposition of an opaque original
does not establish complete separated shadow geometry or final in-game visual
quality. Final receipts must retain that distinction; this review does not
authorize inventing missing pixels.

Inspected `/tmp/summoning-raptor-content-corrected.log`: 76 canonical checks
passed. The earlier combined run passed the 75 lifecycle cases and exposed one
canonical fixed-dice-input failure, then corrected by that rerun. Inspected the
zero-error active typing receipt. Shadow extraction tests exercise source
recomposition and invalid pair rejection; final execution/install/visual
receipts remain pending. No tests or production edits were performed by this
reviewer during the amendment review.

### Amendment source snapshot


The same path/hash line convention defined above applies. Group SHA256: `a794da942c75b812dde8475778ce2dfc13aaea94d99811aa09403492ed803e29`.

```text
.runtime/summoning-art-20261003/shadow-bindings/bison.json 3079d4feeb7ca513b98d74572825320959b4e43b1144a5563589c5cb5288ed43
.runtime/summoning-art-20261003/shadow-bindings/blueraptor.json 912987778b312a4302ed3c8b6e674b6d446e15b330d18f3a4b0594e44aa5ecb6
.runtime/summoning-art-20261003/shadow-bindings/boar.json 0520b908d7d00c4bbcd4a3f5c3a07dd6d974ed83e017d34da2d45f38fe74233e
.runtime/summoning-art-20261003/shadow-bindings/brownbear.json 193ade504a25743919611f7eecd559a6cd11f5d704cc84881b143d37c666463c
.runtime/summoning-art-20261003/shadow-bindings/elephant.json 3ccbd813f6688620c292678a28a0587ba62cf9f6381961956275b189f04be811
.runtime/summoning-art-20261003/shadow-bindings/greywolf.json 79f2bde48976bf34bf619377b4f5224f14719cabbf7621d57ebdf2c1e70caa9b
.runtime/summoning-art-20261003/shadow-bindings/jaguar.json ae6d16aa68bd48c562fefd46c45a573e2c0095b681563e8246bb8007063f258c
.runtime/summoning-art-20261003/shadow-bindings/lion.json fd2bdc923bf27a247dca6fd77f09e07ca75588703789893792bcab2d6d6b4e1e
.runtime/summoning-art-20261003/shadow-bindings/mammoth.json 1d3001b120ed1f8d1b4f87c2cf29c4b04c484d197e9745b2595706204477d0aa
.runtime/summoning-art-20261003/shadow-bindings/ostrich.json ccbcd313bcb33a143b44661da07a5051d0f305522b7880d731371a44329f9127
.runtime/summoning-art-20261003/shadow-bindings/polarbear.json 8f755e0ed362e22d529ed045180c4a80ee3831291260881aadd166036e3fc3cf
.runtime/summoning-art-20261003/shadow-bindings/rhino.json 895fdbc0b6f201d7b2fb1a48719dae36797b774f9ef8d1f593aa7076ed2326d2
.runtime/summoning-art-20261003/shadow-bindings/shepherddog.json cefb52d22bf85fa3b4b23a505bb04a2af061eb36249d0ca8a30d33ed287f8adc
.runtime/summoning-art-20261003/shadow-bindings/stag.json 6df6a464c749f9f0ddd55d9180979346476fae3a391c93abe0b6a894a18f7a09
.runtime/summoning-art-20261003/shadow-bindings/stegosaurus.json 7c768203d94199a14c5669dbf383157f814a56b7d9ba3608f3f23844bf1ed946
.runtime/summoning-art-20261003/shadow-bindings/tiger.json 0e516f03b8c4882d16a487eb6aae2d572c480a5ffee28f4f8040b6c8abe441f0
.runtime/summoning-art-20261003/shadow-bindings/triceratops.json 8675ea92c297fb89e5a6e95b99cdd8be1612957ce239f302c4d8f4cdc007dd06
.runtime/summoning-art-20261003/shadow-bindings/tyrannosaurus.json 2062f1e490d9209227ca6845607b91a7332646cb1be075d5e04d5275927a0caf
.runtime/summoning-art-20261003/shadow-pair-probe.json aa2440691da181f328121dd7a7235274505d4c1db4ff25d7ebbda5ccdab5ed3a
.runtime/summoning-art-20261003/shadow-receipt.json a9d5ed100dd0eb276513a448eddde192eb2381baad1841481de5de893865d7ea
/tmp/summoning-final-types.log 46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb
/tmp/summoning-raptor-content-corrected.log eee37770aac698133c4f9781fbe627a6ea47b1504fa6fee449b040368cb60f2f
/tmp/summoning-raptor-content.log f123b5ba68f19ab845d491ddad931ff2ac72de1a42114f3f0cd7787fc13585ac
agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md 6fa3185abc6e79c3d47667277541476192622f2af922a3d4f3365e17f7a7811c
agent_docs/SUMMONING_VISUALS_ADDENDUM_2026-10-03.md a8b38482d69680fe2dfdfa850f2889b00c69fc32a37c4a4fc72f741d475b11e9
devtools/import_fixed_rig.py ff6c7092e29d95f9b32f33d11b20ca197ba22ffe8e8923574ba2566bac45f11d
dnd/content/items/authored_item_definitions.py 7625ef04c218bf17d17ce949d8762cffb2df3137ea9bf6d51933a7267685ad69
dnd/monsters/beasts.py b1e5f333a1e6d0d95be749dd05d83aefec9c40dc682f63babd401b6cd52de15f
dnd/summoning/forms.py 64e17b956869d915f47d35aba694e5a031ae26c3aa884d4a91231c2c9a04140a
game/animation_data.py e8fb46a8000a0e90c489aeb2d4601b64b3083f431ce4c064838f5486bab8a56c
game/animation_types.py 73e2704c47f2ee924c5e25c9afeeda1ce99cd228d421509f35a1a27ff8e76eb0
game/data/neuroclient/attack-profiles.json d9e4ccb3e3571e6b3b818e18e27a1f0cd468ea7214b248e02543f6bd853ea9d2
game/data/rigs/tyrannosaurus.json 5c61dd730a06c6f9e1c94bfb6c41824771e45a95ae42c62071f13649afad7856
tests/engine/test_canonical_body_creatures.py 6f173c6b34d379e98eea30834c7a84945462ac41c1b3839e7752186ab3570578
tests/game/test_fixed_rig_shadows.py 042ba0e634874a9b6bc104ae381ddaea181f63226246c12875ec8c0080317cc5
```

## 2026-10-03 bounded follow-up: ordinary birth failure cleanup

**APPROVED. No remaining anti-slop or ECS/import-DAG blocker in this correction.**

Compared `Entity.compose_entity` with HEAD and traced the ordinary direct-character
caller, `EventQueue.publish_completed_fact`/indexing and summoning's explicit birth
caller. HEAD discarded the provisional ordinary aggregate when publication failed.
The extracted wrapper had set `creation_committed` but stopped performing that
cleanup, leaking the undeployed character and its attached torch light when a
pre-completion callback raised.

The convenience wrapper now restores its previous unpublished-failure behavior
only when the entity is undeployed and its exact birth UUID is absent from the
existing event index. It does not discard an already indexed birth or a deployed
actor. The explicit prepare/commit/publish APIs remain unchanged: their caller
owns the larger committed operation and publication failure retains committed
state. `SummoningSystem` uses those explicit APIs, so this correction does not
reintroduce rollback after a committed summon birth.

The prepared-birth regression now actually calls prepare/commit/publish rather
than the ordinary convenience method. That correction is consistent with its
stated contract; the pre-existing direct-character and torch tests still assert
ordinary cleanup rather than relaxing their expected outcome. Source wording
about publication is read as the exact indexed-fact boundary: pre-completion
callbacks can already have executed, and this change does not claim to roll back
arbitrary external callback side effects.

Only the existing Entity convenience boundary and queue lookup are used. No new
transaction owner, registry, import edge or reflection mechanism was added.
Inspected `/tmp/summoning-birth-regression-fixed.log`: **336 passed in 41.12s**,
covering progression/root packaging, prepared birth, summon lifecycle and entity
composition. This reviewer ran no tests and edited only this audit. Whole-art
and whole-delivery acceptance remain the separately stated gates.

### Ordinary birth correction snapshot

```text
dnd/entity.py 4ce58ebff96cf967e0ed45940ab0665d7cd9e13e02260a09d86ae00d1891d453
dnd/core/events.py 7bf91ba0330a9882a3b54c27c0d93d1cdba3c87806ce99c3b85b9ce986dbbf59
dnd/content/characters/builds.py f775586f384c43990a0155254832575973fe073b780556955dc4d6fb71dd8665
dnd/summoning/system.py 6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009
tests/engine/test_prepared_entity_birth.py 66f0aead6cd447330118c704d3329dd8b3e5773f1c0dd75cf137b911ecdf011d
tests/progression/test_direct_character_builds.py d956d9477f8baf5451e84abc674a276ddba717fff27414efd36fd130ce1823a0
/tmp/summoning-birth-regression-fixed.log 682c54594eae5c7847a3e653a12e10b5a334aaa7780001c3a4de25f7e84969c6
```

`Entity.compose_entity` AST source-segment SHA256 (universal-newline UTF-8): `92fc1cd1db34635de46960bc025bd66907cfb3a14edd947e7928da1b84c53f07`.

## 2026-10-03 — Provisional end-to-end completion audit

**Provisional verdict: no additional implementation omission found in the approved
scope. Final combined acceptance remains open for the final source/artwork freeze,
whole-game reconciliation and independent validation of the two tests authored
below. Earlier scoped native approvals remain in force.**

Reviewed the unified plan and visual addendum against the implemented owners,
the packet/final review receipts, the current implementation ledger, and the new
human-delivered VFX brief. The accounting remains 24 ordinary canonical creatures,
42 family/form choices and three spells. The human's Raptor amendment changes
its unlock and body statistics without increasing that scope. Neither the
withdrawn arena nor new VFX production has re-entered the implementation.

The plan-to-delivery cross-check accounts for the required boundaries:

- Ordinary content and body attacks use the same canonical recipes, intrinsic
  item ownership and native Attack/Multiattack rules with and without summoning.
  The existing 76-case canonical receipt covers the complete body roster;
  summoning does not supply alternate statistics or attack executors.
- Concentration-dependent existence, direct finite existence and Fey-only
  control use the reviewed native condition graph, one creature interval clock,
  exact terminal retirement and ordinary controller assignment. Replacement,
  cancellation, irrevocable committed birth, retirement publication failures,
  real possessions, stable turn IDs and rebind cleanup have the scoped receipts
  retained above and in the packet audits.
- Three registered spell adapters, pure discovery, objective admission and
  indexed dismissal feed that same system. Native form rows admit the authored
  boundaries; released Fey cannot use its former controller's dismissal grant.
- Retained presence/faction/manifestation facts, finite legacy codec additions,
  existing fixed-rig/body-context selection and the shared Fey material account
  for the presentation requirements. These are shared consumers of recorded
  state, not a creature-specific renderer or a native-mechanics replay path.
  The event/render audit separately records the proven placed-contact HP rewind
  correction and root's independent acceptance of its target-state-only fix.
- The VFX handoff accurately separates current body gestures, ordinary rigs,
  neutral original shadows and Fey body material from later arrival/departure
  effects. It specifies finite markers and native fact ownership rather than
  introducing extra lifecycle events or clocks. The human alone delivers it;
  this reviewer did not contact another chat or artist.

### Concrete gaps closed in this audit pass

The plan's cumulative choice table still reflected the removed slot-9 T-Rex.
With root's authorization, corrected only those counts to the current Raptor
form data: Animals slots 3/4/5/6/7/8–9 expose 7/10/14/16/17/18 forms; Fey slots
6/7/8–9 expose 16/17/18. The underlying 42 rows and production form data did
not change.

Existing outcome-profile checks, controller-identity checks and manually
submitted native gallery attacks did not demonstrate an actual summoned
controller choosing an action. Root explicitly authorized this reviewer to add
and run that bounded missing acceptance. The new
`tests/engine/test_summoning_autonomous_turns.py` uses real summon casts and
`Encounter.advance_one_controller_action_boundary`, without policy substitution:

1. An allied wolf with both the caster and enemy adjacent chooses and damages
   the enemy, preserves caster HP and spends its ordinary action.
2. A Fey wolf first spends five feet through native Move. Voluntary concentration
   loss preserves its controller, actor identity, turn execution ID, remaining
   duration and all remaining resources. Its native controller then chooses and
   damages the adjacent former caster instead of the distant original enemy.

The fixture supplies the positions and deterministic dice; no summoned attack is
manually selected. The controller gets at most four decisions. Final frozen test
bytes passed **2 checks in 2.32s**, with source under WSL `/mnt/c` and the existing
`/home/tommaso/.cache/dnd-engine/venv` environment:

```text
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv uv run --no-sync python -m pytest -q tests/engine/test_summoning_autonomous_turns.py
```

This reviewer authored these two tests and therefore does **not** independently
approve their evidence. Root has been asked to review the tests and receipt.
No production code was changed and no broad suite was run by this reviewer.

### Existing receipts and remaining completion gates

Inspected the completed receipts: full engine/AI/architecture run **2,531 passed**
plus one new test-boundary assertion correction; all **19** checks in that file
then pass, reconciling the **2,532** collected native checks. The ordinary birth
regression receipt has **336 passed** and the explicit observed-birth follow-up
has **6 passed**. Active dnd/game typing after the passive shadow-alpha addition
has **0 errors and 0 warnings**. These are inspected receipts, not tests rerun
by this reviewer.

Final acceptance still requires the complete game's final result and reconciliation
against the actual later HP/contact and archer-media corrections, activation and
inspection of the 18 original-shadow rig updates/98 source pairs, and final
native recording/scale/Fey-shadow evidence on that frozen data. The still-running
full-game log is not a completion receipt and cannot certify Python changes made
after that process loaded them. The implementation ledger's top-level pending
rows and old amended hashes also need the final receipt merge. These are
completion/evidence gates; no additional policy, creature mechanic, rendering
framework, arena or VFX project is requested.

### Scope-audit snapshot

These hashes identify this provisional comparison and its new acceptance file;
they do not claim that the changing artwork or whole-game receipt was frozen.

```text
agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md 0d686551f9b38d285f0b84d633a14b7604a6e388f9bc287463816ea7624b176a
agent_docs/SUMMONING_VISUALS_ADDENDUM_2026-10-03.md d8a877522c05b0f9d39104d6be990bf9042a07a08f7608e2f937244bd037d896
agent_docs/SUMMONING_VFX_HANDOFF_2026-10-03.md 0441892db4bbf582269babba451fe0ea7303cb8860f304ec5738c3c53e8911aa
dnd/summoning/forms.py 64e17b956869d915f47d35aba694e5a031ae26c3aa884d4a91231c2c9a04140a
dnd/summoning/system.py 6d2dbbda64b924d3389da7848319c56ff521a93ffbccb2570c97009f5177e009
dnd/encounter.py 71bc0ef26342e47e8faeb671b9d4f18c9d75583addabbecbdb869c4ea473576c
tests/engine/test_summoning_autonomous_turns.py 4c3e0dbdcb353d38cde1e6bc78a8a42330f87f52e2cccae17272996d8ecd12dc
/tmp/summoning-autonomous-turn-acceptance.log bc20d09e92d3dfc8aaff0369aadac27757c89f913c2c7ab5420d49297626ba31
/tmp/summoning-full-native-final.log 3713bfc5d9d46aec9362026882c5bdc8b338ebfe9295905338af0e42dbc228da
/tmp/summoning-silent-removal-corrected.log 353cd58b3ad0caa858f182bf3a57d300e83ba84a1c949b2ef3ae1580aae56988
/tmp/summoning-observed-birth-corrected.log 08677330b64a7f09506f9a0a0740c5ef87a70d15d31a580f66be55294a6ddb3d
/tmp/summoning-final-types-after-shadow.log 46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb
```

## 2026-10-03 — Final anti-slop source closure

**APPROVED for the final bounded implementation source. No remaining concrete
anti-slop/source-architecture blocker is identified. This closes the preceding
provisional source verdict, not the still-pending whole-game reconciliation,
artwork activation or final visual acceptance.**

Independently inspected the final `game/choreography.py` child traversal/timing
helper and `game/attack.py` retained contact binding, the exact archer attack
profile and passive shadow-opacity consumer. Read the appended independent
ECS/import-DAG and event/render reviews and their completed focused receipts.
The additional comparison adds no requested production work or scope.

- Generic authored action groups advance their existing sequence cursor only
  for typed child commands (Action, Attack, Spell, Movement, Shove, Equipment).
  Passive consequences keep the current anchor. Every child still contributes
  condition/subtree completion. This preserves complete sequential Multiattack
  children while a portal opening and its resulting fall retain their shared
  authored timing. No portal-specific scheduler, synthetic wait or new queue
  was introduced. The **40 passing** portal/sequence/summoning checks retain
  the original timing and subjective-view assertions.
- Attack target contacts keep their supplied scene placement and take HP/life
  state from the current retained child prestate. The correction therefore
  removes the real second-child HP rewind without consulting native entities
  or manufacturing a Multiattack-only result path. The inspected receipts
  report **29** native-sequence/summon-presentation and **45** existing attack
  regression passes. The event reviewer and root also record the exact Brown
  Bear second-miss input remaining at 483 HP in all four shadowed views; that
  visual inspection was performed by them, not independently rerun here.
- `skeleton-archer-ranged` is a single exact fixed-rig/projectile profile using
  existing Attack3/QuickShot and normal projectile data, omitting the unavailable
  modular Slash1 overlay. It fixes an existing compatibility path and adds no
  undead summon content, executor or fallback selection mechanism.
- `BodyRig.shadow_alpha` stays one constrained passive value with the prior 0.5
  default, consumed by the existing fixed-rig layer resolver. The staged 18-rig
  update uses original recoverable shadow pixels and 1.0 layer opacity. The
  separate event/render receipt verifies all 98 staged PNG hashes and unchanged
  body binding data, plus actual Jaguar shadow alpha/Fey neutrality in four
  views. Hidden under-body source pixels remain unrecoverable and transparent;
  that disclosed limitation is not relabeled as reconstructed artwork.

The reviewer-authored autonomous tests now have independent acceptance: root
reviewed and reran the unchanged file, **2 passed in 2.34s** in
`/tmp/summoning-autonomous-root-review.log`; the final ECS reviewer also inspected
and approved those public-boundary cases. This closure relies on their independent
review and does not self-certify the new tests. The final ECS receipt additionally
checks the nine new native modules and their **203-module** dnd dependency closure:
no cycles, late imports, reflection or checked lower-owner import of the high
summoning system. Gameplay receipts and static architecture evidence remain
separate claims.

Both the section-2 choice table and the repeated paragraph now match current
Raptor unlock data. The final native source retains the already-approved owner
split, ordinary birth cleanup, direct/required existence and Fey control rules.
No new creature, rule, framework, arena or later VFX production is needed to
close the reviewed source scope.

Root still owns completion of the broad game's actual final result, reconciliation
of its two reported failures with later corrected-source receipts, copying the
exact staged shadow bindings into active data, final native 38-clip/scale/Fey
inspection, and the final ledger merge. Neither this review nor a partial
outcome count represents a completed green whole-game run. No production/test
edits or reviewer-run tests occurred during this closure pass.

### Final bounded source/receipt snapshot

```text
agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md 2037908ca8d4880bf61cf4dbc4afa98563c8da7e2a5f51ed35704b09cd7d36c6
game/choreography.py d751297601a793cf96fb2903039aa0f0978a3f9636a12cb1fba2ccb446f84686
game/attack.py fbb165b6b927fa2fe0c7848e9d1567ab7e2cc50ba47c829be0a3321de26be47a
game/data/neuroclient/attack-profiles.json add6f095abdf951ed71bfdac96f4fcea8561f708b48d1dca0bc2436049fd77b5
game/animation_types.py 73e2704c47f2ee924c5e25c9afeeda1ce99cd228d421509f35a1a27ff8e76eb0
game/animation_data.py e8fb46a8000a0e90c489aeb2d4601b64b3083f431ce4c064838f5486bab8a56c
tests/game/test_action_sequences.py 505ee1116600f7356c2634c0efce2298e4b5abfd83e2e91bdfc43793aeeb4de3
tests/engine/test_summoning_autonomous_turns.py 4c3e0dbdcb353d38cde1e6bc78a8a42330f87f52e2cccae17272996d8ecd12dc
/tmp/summoning-autonomous-root-review.log 73c9079bcf0cf5962ac22b776dff3c79349392f5e91e036e959d4b069cd1a5a1
/tmp/summoning-portal-sequence-fixed.log e0b1f2c0575697b59720bfba1b5bfd50aa231336040a4ada3c0514bc2335cb40
/tmp/summoning-multiattack-contact-green.log 25c79e63ad37eb10af5c5841de3dc0cfd0c0849e61fa7f2b705d77ff743a1cdd
/tmp/summoning-multiattack-attack-regressions.log 112d736408006298513863396578810f0da8c1dad5e36ef809644be2791cae4f
/tmp/summoning-final-ecs-static.json 8f3e14b497037e6a1c4d43a9dfe7080b170d8f07476a4bb262940679321960c5
/tmp/summoning-shadow-alpha-review.log 220e804f3345e3b1c73fe7a74278f57ed88bd91f7a5267aa53bdba98c6bd9cad
```

## 2026-10-03 — Final independent completion acceptance

**APPROVED for the complete implemented scope of the unified summoning plan and
its visual addendum. No unresolved scoped blocker remains.** This closes the
whole-game reconciliation and artwork-activation gates retained in the preceding
source approval. The approved later VFX delivery remains explicitly deferred.

### Complete-suite reconciliation

Read the finished broad game receipt: **3,109 passed and six failed in 3,053.47s**,
accounting for **3,115** cases. The six failures have concrete, reviewed closure:

| Failure | Final disposition |
| --- | --- |
| One native workshop case | Existing fixed Skeleton Archer now selects the exact existing-rig projectile profile without the unavailable modular Slash layer. Previously approved source correction. |
| One occupied-portal case and two lever/spikes observer cases | The reviewed shared sequencing correction advances only typed command children; passive consequences retain their authored contact. The original portal/trap assertions remain. |
| Two ranged True Strike hit/miss cases | The test expected frame 8 despite pre-summoning HEAD already authoring the normal ranged release at frame 10. Independently inspected HEAD's profile and the one-line test diff. The correction to frame 10 preserves ordinary-attack equivalence, projectile, exact overlay and HP assertions; production timing did not change. |

The final seven-file affected run includes every failed ID, plus all cases in
trap presentation, True Strike presentation, attack animation, portal
presentation, action sequences, summoning presentation and native encounter play.
Inspected its actual command and completed receipt:
`/tmp/summoning-final-game-reconciliation.log`: **96 passed in 120.20s**.
This reconciles the six failures against corrected source and the justified test
literal. It is **not** represented as a second complete game-suite run.

The native **2,532-case** reconciliation, **336** progression/root/birth/summon
checks, **6** explicit observed-birth checks, independent **2** autonomous AI
checks, **203-module** import-DAG receipt and final active typing with **zero
errors/warnings** remain the separately scoped evidence already inspected above.
No abandoned mixed-source run contributes to this acceptance.

### Activated art and retained native recordings

Independently compared all **18** active shadow rig files against both the
reviewed staged bytes and their activation receipt hashes: all match exactly.
Then compared all **27** rig bindings captured by the final recording run with
the active rig files: all match the recording receipt. Thus the final gallery
uses the exact artwork bindings now active in the product.

Read the final manifest and checked its completed artifacts: **38 passed clips**,
**1,350 passing checks**, **8,638 frames**, and every listed video present. The
acceptance receipt records no HP increases. The native lifecycle receipt covers
all 38 observer clips and retains the exact birth/release timestamps and terminal
contacts. This verifies the recorded artifacts and receipts, not a claim that
this reviewer watched all frames. The previous independent pixel/source and
root visual reviews supply the bounded scale, source-shadow and Fey inspection.

The gallery remains native retained-event playback with four camera views and
paired observers; it does not substitute artwork animation for rules execution.
Existing all-24 canonical and binding checks account for the complete body roster,
while these recordings exercise representative and large-body fighting paths.

The recorded remaining recipe diagnostics are disclosed: Summoned, SummonControl,
passive attack-hit-save/flight/perception traits and an unbound generic condition
identity have no dedicated standalone condition animation. The approved plan
does not require a new perpetual effect for those passive mechanics. Ordinary
body contexts, faction, existence, actual hit/condition results and retained Fey
material are delivered. New arrival/departure particles and decorative casting,
halo or bond-break accents remain the later human-delivered VFX brief. The
original-shadow extraction still makes no claim to reconstruct pixels hidden
under opaque bodies. Neither limitation has been concealed as finished new art.

The bounded implementation continues to use canonical ordinary creatures, native
AI, shared conditions/clock/retirement, typed retained facts and existing rig and
playback owners. No additional mechanic, renderer, arena or art production is
requested. The final ledger may consolidate these finished receipts and approvals;
that documentation merge does not reopen the accepted source scope.

This final pass edited only this audit. It ran no tests, changed no production
or artwork, and contacted no external chat or artist.

### Final completion evidence hashes

```text
agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md 0b15c8450cd9b5a6fe19a336315da9fb417fcea3e0a1b985a76597af3fb14e56
agent_docs/SUMMONING_VISUALS_ADDENDUM_2026-10-03.md 1d9035220c142b73e47a41bd3ec7e22d0b522cb2d7b3ac8fb6cc6e5aaee6b5e0
agent_docs/SUMMONING_VFX_HANDOFF_2026-10-03.md c842723439f3a2eecfd494b053178bb82dd11b2e43bd2a89be504c1b5528f38d
tests/game/test_true_strike_presentation.py 2c59ec525fc835d17a42cc825ea1e1b8fecfe25ace7500cbe5a3bfc47ad3e6f0
/tmp/summoning-full-game-frozen.log 4aa03213c9dc45101a7d797f89f8320237a66ae8196a13c05eb88a6f091277e3
/tmp/summoning-final-game-reconciliation.log 0343bfe908ec527fc23fc5d45e748aab102402a8b52f3457d5514e5b48821fe1
/tmp/summoning-source-freeze-types.log 46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb
.runtime/summoning-art-20261003/shadow-activation-receipt.json ed16f71dda73ccee0963da72d407e902b352a7d79ad1746f443dc490f18d749c
```

The following files are under
`.runtime/animation-review-summoning-20261003/runs/20261003T182436Z-original-shadows/`:

```text
acceptance-receipt.json 122f7415fb475165860c7669223902b8fe709364c9c78aa0f09dad70b5b93a42
manifest.json 1fe9826587f01ad48657e00ee8d09d428b9ed195e47b140f670e1a61b2d3ef2c
binding-receipt.json 49d7caccb1f142671ec9c165916608265829c4924dd2e7cbe7eb361726ebf189
native-lifecycle-visual-receipt.json 7cee5118658ae6e6697731f1b7b56c859ea7c29fba1fc930766064017aa54e60
```
