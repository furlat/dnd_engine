# Summoning packets 1–2: independent anti-slop implementation review

Date: 2026-10-03. Reviewer: `summoning_antislop`, independent local review subagent.

**Verdict: CHANGES REQUIRED for the prepared condition/concentration seam. Packet 1 final acceptance is pending its bounded follow-up; this report does not approve the combined implementation.**

Plan authority: `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md`, SHA256 `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b`.

## Scope and evidence

Reviewed canonical beast/fiend recipe composition, explicit body-weapon usage in the existing attack/equipment owners, exact intrinsic-item rider selection, and the prepared application/removal/concentration/initial-birth seams. Read the condition-seam implementation report and the packet 1 implementation report when it became available. Read repository instructions, recovery/testing guidance and the bug-fix skill. This review ran no tests and changed no production files.

The table below freezes the reviewed working-tree source snapshot. Shared files contain several authors' changes: this is a verdict on the examined methods and findings, not approval of every diff in those files. Retirement, encounter membership/AI, the high summoning controller, spells, presentation and end-to-end fights are not accepted by this review. Retirement work was still being finished separately. No other chats were read or contacted.

## Blocking findings

### AS-1 — P1: removal commit still invokes callbacks and publishes native consequences

`dnd/core/base_block.py:1280` calls `condition.cleanup_own_state(...)` inside `_commit_prepared_condition_removals(..., publish=False)`. `dnd/core/base_conditions.py:1147` still calls arbitrary authored `_remove` and then `_release_owned_runtime_state` before the owning indexes and registry are released. Deferring the outer condition-completion publication therefore does not make this authority phase callback-free.

Concrete existing concentration children demonstrate the breach:

- `dnd/conditions.py:2549`–2556: Invisibility removal calls `set_invisible`, whose perceivability change immediately dispatches through the event queue. `Invisible`, Greater Invisibility and Hidden have the same setter pattern.
- `dnd/spells/transmutation.py:719`–734: Haste removal creates and admits `HasteLethargyEffect` through ordinary `target.add_condition` during the removal commit.
- `dnd/spells/abjuration.py:1443`–1484: Banishment removal moves an occupant and restores spatial presence through the ordinary movement/presence publication paths.
- `dnd/spells/abjuration.py:3228`–3251: Antimagic Suppression removal re-applies a live condition and adds its parent link during this phase.

Replacing concentration with an incoming summon can execute these before the incoming concentration/effect/birth/presence graph is committed. A handler can observe the intermediate graph, mutate it, veto a newly admitted consequence, or raise after only some old conditions have been dismantled. The outer graph-settled callback does not prevent that earlier reentrancy.

Required correction: the existing condition and spatial owners must separate accepted authority changes from publication and authored follow-on effects for the native paths the new shared seam can invoke. Capture the necessary facts/consequences before state is discarded; publish/drain them after the authority graph is complete. Do not solve this by swallowing errors, adding a blanket global event buffer, or declaring only the new Summoned condition safe. The separate independent/spatial removal publication split present in this snapshot improves one path but does not resolve these ordinary hooks.

Acceptance evidence should include replacing concentration whose child is Invisibility, Haste and a spatial-presence effect, with a completion observer asserting that the full committed graph is already visible; publication exceptions must not leave a half-committed owner graph.

### AS-2 — P1: canceled incoming applications retain untracked direct mechanics

`dnd/core/base_conditions.py:880`–893 discards tracked modifiers/handlers and invokes `_release_owned_runtime_state`, but does not undo direct mechanics owned only by existing `_remove` methods. Neither Invisibility Effect nor Haste Effect supplies a corresponding provisional release override.

`InvisibilityEffect._apply` calls `target.set_invisible(True)` at `dnd/conditions.py:2498`; its inverse is only in `_remove` at 2549. Haste installs its restricted action grant at `dnd/spells/transmutation.py:690`–703; its removal is only at 723–726. The new `SpellAction.apply_owned_condition` prepares the incoming effect before required concentration. If that required concentration is rejected, its cancellation path removes the incoming registry/index/trackable modifiers but leaves the target invisible or leaves the Haste grant installed. Invisibility preparation also publishes its provisional perceivability change before required concentration has been accepted.

Required correction: make native incoming preparation and cancellation own all direct state, including grants and perceivability, in the existing condition owners. Preserve surviving independent sources when restoring derived state. Cancellation must not execute ordinary successful-expiry consequences such as Haste Lethargy. Verify vetoed required concentration for these actual authored effects, not only a synthetic condition with tracked modifiers.

### AS-3 — P1: exceptional admissions lose prepared resources before a cancellation owner exists

`dnd/core/base_block.py:1595`–1599 only wraps `condition.prepare_application`. Replacement-tree admission at 1606–1607 runs outside that guard after provisional incoming mechanics are installed. A removal declaration/effect handler raising there escapes without discarding the incoming application or canceling removal admissions already accumulated in `prepared.replacements`.

The cross-owner concentration transfer has the same gap: `dnd/conditions.py:2058` admits each linked removal, but `_prepared_transfer` is not assigned until 2067. If a later child's admission raises, cleanup cannot find the earlier accepted tokens held only in the local `prepared` list. The regular canceled-return case is handled; the exceptional case is not.

Additionally, `cancel_condition_application` at `dnd/core/base_block.py:1636`–1641 marks itself canceled and then performs required-owner cancellation, own-state discard and replacement cancellation sequentially. A failure in an earlier cleanup skips the remaining owners permanently on retry. Correction should drain every already-owned provisional resource and preserve/report the collected errors.

Required correction: establish cancellation ownership as admissions accumulate, and cover the whole prepare/admission operation with exception unwinding. Use the existing prepared owner tokens; no new transaction framework is needed. Validate an actual raising removal admission after an earlier cross-owner acceptance and a cancellation callback failure, asserting that old committed effects remain usable and all incoming/provisional resources are released.

## Finding resolved before this snapshot was frozen

**AS-4 — initial-condition publication drainage: resolved in source; regression execution not independently verified here.** The earlier `Entity.publish_initial_conditions` marked the batch published then aborted on the first failing application. The current `dnd/entity.py:2016`–2028 attempts every application, accumulates errors, and raises after the batch. This fixes the identified skipped-publication control flow. Root reports a matching regression was added; this reviewer did not run it. The resolution does not waive AS-1 through AS-3.

## Packet 1 assessment and remaining verification boundary

The examined creature/body-attack design stays within the approved content scope: canonical ordinary recipes reuse the existing Entity composer; body weapons are passive explicit data interpreted by existing attack/equipment owners; no summon-specific creature constructors, new attack executor, parallel action budget, entity subtype hierarchy or generic transformation framework was introduced. Exact intrinsic-item matching avoids the old display-name rider ambiguity. No additional concrete scope or duplication blocker was found in those examined paths.

The final packet 1 report arrived as this report was being frozen. It records 76 focused passes, 419 expanded passes with one obsolete authored Fighter-reference failure, and clean scoped Pyright. These are author-reported results, not an independently executed test run. Its final body-size damage adjustment and corresponding new assertions need the requested short final packet 1 follow-up before acceptance. The stale scenario reference remains an explicit overall verification exception; it is not grounds to restore a retired factory or expand the content roster in this packet.

No finding here authorizes additional content, new rendering/artwork, arenas or a general-purpose lifecycle framework. Resolve the specific native owner seams and re-review their exact revisions before depending on callback-free prepared commitment.

## Frozen source and report hashes

`dnd/core/base_block.py`, `dnd/conditions.py` and `dnd/entity.py` changed concurrently after this snapshot was captured. Their subsequent edits are not reviewed by this verdict; the findings above refer to the listed hashes and line numbers.

| File | SHA256 |
| --- | --- |
| `agent_docs/SUMMONING_BACKEND_PLAN_2026-10-03.md` | `d2c83849488ebe40a2fe01ca36cc09fdd9fcede13724207e82d22739545f375b` |
| `agent_docs/audits/SUMMONING_CONDITION_SEAMS_IMPLEMENTATION_2026-10-03.md` | `af5479df847c3bc0e09f93768b83b347299a060b58e9af77ab177403946b2f20` |
| `dnd/core/base_block.py` | `2092bfd33bb6e79b98410fa24550600e381cb88ed1d440932053524b2c2f75a7` |
| `dnd/core/base_conditions.py` | `8341d05d604e5ff76448e80db7b76db914a8c21003b329f5627e5c23de2cc361` |
| `dnd/core/condition_types.py` | `fa8f1925d172c3b6d1f487f048204e99b25965196bcaff304c8d84e6eda4069e` |
| `dnd/conditions.py` | `ffba54f68fb9c39e25a1fc8d0b541f00fe9aba7cd0f3537d4afe00832a35da6c` |
| `dnd/actions.py` | `c6f80514f1fe304d931d9e334ff5ad44287391a707c737cc2f223a6cb65aaf7f` |
| `dnd/entity.py` | `ba3345a99e5d1c6c4a54ccdba086d990258a1ceef0e3e33eed76aaf80f454e5c` |
| `dnd/game.py` | `dee158751f31d3bba15a76cd1088775eca15f43935362566e60fc748f8692eba` |
| `dnd/core/gridmap.py` | `817fb0c51fae009bb7c4494ba8fe487c5b43e4c5d999db605269194253b7f742` |
| `dnd/types/summoning.py` | `b0cdb827fca5b692011a1be2ad24c6b9049ba4177dbc3fe422620e2b7b7e9c79` |
| `dnd/types/actor_facts.py` | `19b6977c0a4becb368276af5fda3e431932d50c8bea5fe005fbb38be8946a2b4` |
| `dnd/types/event_facts.py` | `ead2190dd9803beaba12846d21c962a93a4ffb83c12dd3d51489274a6e6b7257` |
| `dnd/actor_projection.py` | `131c1892d0b1486c1faf1072fcd02d454858a051b3c639b5ce58dfe1c46184fe` |
| `game/event_record.py` | `239755cc08368ff1da213494ee394b862004f72adedf93ee54bc00585c38133a` |
| `dnd/spells/transmutation.py` | `bb9de4eb82392238b0e3599852634d609427ab322a21a0f5896977ee3ef8a5b8` |
| `dnd/spells/abjuration.py` | `987db9a0a33ca8b3106988b0ff33e2fbacfd573093cda4dd80963c6742f7231a` |
| `dnd/spatial/restraints.py` | `49e6acf0da137b36ce8de13cc01c2eacc0216c726ad1db3717be96077efc2930` |
| `dnd/spells/conjuration.py` | `2e4d206e75f3875405c13e5de9b0aab40b2775fd0fde38e270785d46364941e7` |
| `dnd/core/item_types.py` | `fc4dcb8ea6c5229210947d559c8ff3c4458c2f67ea56cb2e2172e0028b27b290` |
| `dnd/core/equipment_types.py` | `2b23b91c53bf016a8a6b1ae52d68b6225b886fafa62f8b71ec14bcb2360e31e4` |
| `dnd/blocks/equipment.py` | `fc010396a8ed626a693d9b8c36e0e291305fb3423a198c30d04d9eefffc7647d` |
| `dnd/blocks/base_item.py` | `eb98792ff59e344c7de58c107d8fb6e81fd83336d2be8e2847e4adc2b2d3e18a` |
| `dnd/monsters/beasts.py` | `7d0565c1ca045ee377761a2a0fb33415daf80029abdb4a4d9595f40cf449b5ee` |
| `dnd/monsters/fiends.py` | `01850efda56fbbd4193d48578f87324d3745042708944f9882df24816fc26513` |
| `dnd/monsters/srd_roster.py` | `380267c62cceca67f470689f8c00de07c8fe495949673d01a86824bfb976f41a` |
| `dnd/monsters/traits.py` | `d9c679ac5a3358cafe6480a508cb20c22e8c8bb76d8506a2920ca77aa48b7da5` |
| `dnd/monsters/multiattack_definitions.py` | `57f186b79f76aa1daa5e966ae462a7d6fbcecaa6c34bcb2a8200b4d68d21baa0` |
| `dnd/content/items/authored_item_definitions.py` | `902b6a6d1a4fa778ffa08314489a5da5b7328f94368fabff905531c9945fc3a2` |
| `dnd/content/items/authored_item_builders.py` | `271f95a121d56b1106b251ab4508d8a7baf8b2f89aa4dcbb6599cf9e221fd595` |
| `dnd/content_system/builtin.py` | `0192d5ec65769c9fdee4048ede61a8e7504cdcad7bf32d4b45479b37c826914e` |
| `dnd/content_system/builtin_inventory.py` | `733312dde223d59e7480351f4f5758a4bfaf5d7de20552add2e89ec8d1273549` |
| `dnd/content_system/condition_definitions.py` | `a609737ad785cd1656e42b289159095b353b7f8cc19b6a9566cbe3a6b8df2750` |
| `dnd/core/content/provenance.py` | `adebb860339e17f9e7ac0472212db748ddb08e7fa531ed6eaf4c500164bbe56a` |
| `content_data/sources/srd_5_2_cc.json` | `5813bf68f91a06880e610adce7c643acdda931c68f7c656cb15c311de3950b5b` |
| `tests/engine/test_canonical_body_creatures.py` | `6aee3b8048c7dc222083c278f67fbc48e1a5d3be28ea57c8ba9c0530d596435e` |
| `tests/engine/test_prepared_condition_lifecycle.py` | `5e4074d889a9a2256ae8566aa1396b00ed7c4b1dc42732f2f351b501335fa582` |
| `tests/engine/test_prepared_entity_birth.py` | `af2b1437fc3a71794396748f743927c288cce049f11d83bc5291c2a9eea57667` |
| `agent_docs/audits/SUMMONING_PACKET1_IMPLEMENTATION_2026-10-03.md` | `c5e85bb1ce39dcd5f04dc54ee93ab6c5a12de5506f55df2c6358749aae6bcbed` |


## 2026-10-03 follow-up: packet 1 final scoped verdict

**APPROVED for packet 1 canonical creature/body-weapon implementation only.** This supersedes the pending packet 1 assessment above. It does not clear AS-1 through AS-3 or approve later lifecycle, spells, AI integration, presentation or whole-game completion.

Read the final packet 1 report and verified every file hash in its table against current source. Rechecked the final shared body-size query and both runtime/profile callers, the primary-only opportunity-attack assertion and the resulting test receipts. Body dice are authored for `structural_base_size`; only a positive subsequent size difference adds the existing d4 increment. Held weapons and NaturalWeaponSpec retain their prior size policy. Secondary body attacks use the same native Attack/Multiattack cost and damage owners, while their recorded source remains the exact equipped intrinsic item. No new resolver, budget or summon-specific creature construction is introduced.

Evidence inspected: `.runtime/packet1-tests.log` records **76 passed**; `.runtime/packet1-regressions.log` records **419 passed, 1 failed** for the explicitly identified stale `creature.player.fighter` scenario reference; `.runtime/packet1-pyright.log` records **0 errors**. The focused assertions exercise native outcomes, printed content data, budget combinations, source identities and a movement-triggered opportunity attack. The old authored scenario remains a disclosed overall validation exception. This reviewer inspected receipts and source; no additional test execution occurred.

No concrete packet 1 anti-slop/ECS blocker remains in the reviewed changes. Canonical creatures remain independent of being summoned and use the existing content registry/composer.

### Packet 1 exact acceptance snapshot

The final implementation report has SHA256 `c5e85bb1ce39dcd5f04dc54ee93ab6c5a12de5506f55df2c6358749aae6bcbed`. Its verified packet-specific file manifest follows. Shared files undergoing unrelated lifecycle work are accepted only for the named body-attack methods below.

| File | SHA256 |
| --- | --- |
| `dnd/monsters/beasts.py` | `7d0565c1ca045ee377761a2a0fb33415daf80029abdb4a4d9595f40cf449b5ee` |
| `dnd/monsters/fiends.py` | `01850efda56fbbd4193d48578f87324d3745042708944f9882df24816fc26513` |
| `dnd/monsters/multiattack_definitions.py` | `57f186b79f76aa1daa5e966ae462a7d6fbcecaa6c34bcb2a8200b4d68d21baa0` |
| `dnd/monsters/srd_roster.py` | `380267c62cceca67f470689f8c00de07c8fe495949673d01a86824bfb976f41a` |
| `dnd/monsters/traits.py` | `d9c679ac5a3358cafe6480a508cb20c22e8c8bb76d8506a2920ca77aa48b7da5` |
| `dnd/core/equipment_types.py` | `2b23b91c53bf016a8a6b1ae52d68b6225b886fafa62f8b71ec14bcb2360e31e4` |
| `dnd/content/items/authored_item_definitions.py` | `902b6a6d1a4fa778ffa08314489a5da5b7328f94368fabff905531c9945fc3a2` |
| `dnd/content/items/authored_item_builders.py` | `271f95a121d56b1106b251ab4508d8a7baf8b2f89aa4dcbb6599cf9e221fd595` |
| `dnd/core/content/provenance.py` | `adebb860339e17f9e7ac0472212db748ddb08e7fa531ed6eaf4c500164bbe56a` |
| `content_data/sources/srd_5_2_cc.json` | `5813bf68f91a06880e610adce7c643acdda931c68f7c656cb15c311de3950b5b` |
| `dnd/content_system/builtin.py` | `0192d5ec65769c9fdee4048ede61a8e7504cdcad7bf32d4b45479b37c826914e` |
| `dnd/content_system/builtin_inventory.py` | `733312dde223d59e7480351f4f5758a4bfaf5d7de20552add2e89ec8d1273549` |
| `dnd/content_system/condition_definitions.py` | `a609737ad785cd1656e42b289159095b353b7f8cc19b6a9566cbe3a6b8df2750` |
| `tests/engine/test_canonical_body_creatures.py` | `6aee3b8048c7dc222083c278f67fbc48e1a5d3be28ea57c8ba9c0530d596435e` |
| `tests/engine/test_residue_fear.py` | `de275a75166de1481a470c1251522a156079aec419bf7761d19384f47ac01da5` |
| `tests/engine/test_trap_ground_contact.py` | `1addd1489d901333c2cac375e2a10a73add46deb7a7c66ab1a0a1f8088512de5` |
| `tests/game/ground_contact_scenarios.py` | `d33c5913151da43b2e28a17307314ef69c53116ad280c9d68ffad86c7d6c034d` |
| `tests/game/scenarios.py` | `1b890e91a649c83b180ee95f8840edb7b627afd836fea3c93f18f64a3cfc0de3` |

Shared method hashes use `ast.get_source_segment` on UTF-8 source with universal-newline normalization; unrelated changes elsewhere in these files are excluded.

| Method | SHA256 |
| --- | --- |
| `dnd/actions.py::Attack.adjust_cost_for_off_hand` | `c7c98dc03f471e8bc2c5ecb4793d4628a9dc7ce97dbedbcc3d2c48f1f5572c49` |
| `dnd/entity.py::Entity.get_size_damage_dice` | `2a30fc4907c973e5c7f55e90519f85f8671a1fb79d0accae2fb9e8032674d011` |
| `dnd/entity.py::Entity.weapon_damage_outcome_baseline` | `99609fa88bbaefa555a3d8504096b4a86e144c85dec1d836cad4257d82b9096a` |
| `dnd/entity.py::Entity.get_damages` | `e39d12d1e7432404fe01a3cf1aa007c5f61a0ccfc4b5c6c9cfc37143ed39622d` |
| `dnd/entity.py::Entity.get_weapon_physical_access` | `cd667d71809ca60c678b4b98d732363bee66d25c6a09443d4db5542a84bbdcad` |
| `dnd/blocks/equipment.py::Weapon.is_body_attack` | `e0f8de3d7ffd4d1519e634257a480c10e33d5e36f1a93ad396ff7cac69c139a3` |
| `dnd/blocks/equipment.py::Weapon.validate_body_usage` | `58c90ece405aabbe4bf33fe9702dfbd00edda248ad031a7b0398d18f76dc1b59` |
| `dnd/blocks/equipment.py::Weapon.compatible_equipment_slots` | `94cb44b2893c67cf86d23148aeffd0ccfeb297b0fad869ad2b0e994bfbab70f7` |
| `dnd/blocks/equipment.py::Weapon.get_base_damage` | `78079795d7cca25fca5e13a475e67d5c532ef03750d90cf03cd7240947531b46` |
| `dnd/blocks/equipment.py::Equipment.get_weapon_damage_profiles` | `2911136268070551f2b07578f66e449b622eadc7ec6b1509affe472eb40f892f` |


## 2026-10-03 follow-up: Encounter membership and stable AI turn identity

**APPROVED for this native membership/turn-identity prerequisite only, after the two findings below were corrected.** No outstanding concrete anti-slop/ECS blocker was found in the requested slice. This is not acceptance of packet 3's high summoning lifecycle or of the lower condition, concentration, retirement or spatial corrections. The earlier AS-1 through AS-3 findings remain unapproved until their separate re-review.

Scope: Encounter's prepared live join/cancel, queued departure and native execution boundaries; `TurnContext.turn_execution_id`; DecisionEpoch construction and projection, assignment decision-budget keys, basic-policy per-actor turn memory, faction-sensitive movement revalidation; Entity terminal-agency methods and the shared BaseAction permission check needed to enforce them. No new summon scheduler, party-assignment resizing, second AI executor, duplicate action resources or creature-specific controller rules appear in this slice. The stable identity comes from the existing native turn execution, while initiative index remains positional.

### Findings raised and resolved during this pass

1. **Last current departure stalled the production controller boundary.** Previously `finish_combatant_leaves` left the successor index one past the shortened initiative list when the last acting actor departed. `next_turn` consumed the successor marker, but `_advance_one_controller_action_boundary` read the current actor first and repeatedly returned `error`. The corrected entry point now drains pending leaves and consumes the successor marker before looking up the actor. The added regression exercises both `next_turn` and the actual public `advance_one_controller_action_boundary`, preserving one round wrap and the next actor.
2. **Pending departure did not deny reactions.** Previously terminal revocation only made `can_take_actions` false, which the existing BaseAction pure-reaction exception deliberately bypassed. A registered departing actor could still use its remaining reaction before the membership scope unwound. The corrected shared check asks `has_runtime_agency` first, before ordinary incapacitation/reaction exceptions. Entity supplies its revoked/live-identity predicate; BaseBlock preserves the existing non-entity default. It does not spend or refund action resources. The new native regression keeps the departing actor in encounter membership, moves a hostile actor out of its threatened tile, and verifies no opportunity Attack completion, no damage and no reaction expenditure before the outer scope exits.

### Evidence and acceptance limits

Inspected `/tmp/summoning-membership-reviewed-corrections.log`: **23 passed**; inspected `/tmp/summoning-native-corrections-types.log`: **0 errors**. Re-read the final regression source and both corrected owners. Existing focused cases cover anchored insertion order, preserving the active actor and consumed AI budget through an index shift, removal before/current/future, exactly one normal departing-turn completion and last-slot wrap. This reviewer ran no additional tests and made no production changes.

The queue of pending removals and the encounter-owned execution depth are bounded extensions of the existing initiative owner. The inspected AI changes reuse its actual turn identity rather than derive a second identity from mutable list position. The tested terminal gate protects actions and reactions during native unwinding. High-level summon binding, actual condition-driven expiry/hostility/rebinding, publication-failure cleanup and full native fights remain later acceptance work; these source and test receipts do not claim them complete.

### Encounter prerequisite exact acceptance snapshot

File hashes bind the reviewed changes, not unrelated existing behavior in the same files. Lower-condition work continues elsewhere in the shared files; only the terminal-agency methods listed separately are accepted here. Method hashes use the same AST source-segment convention as the packet 1 receipt.

| File or receipt | SHA256 |
| --- | --- |
| `dnd/encounter.py` | `498cfea7c1cd1895fbc8297852ee1fbb1386377912018e8fbe0fab9b4211c6bb` |
| `dnd/controller.py` | `724a323bb32a8397b98f4494bb16b09a1ba39369b80023f645271ae046251551` |
| `dnd/ai/contracts/control.py` | `ca4c24e0adab46d9e84c2ad9cda3335e15e67cc9e206d8a206b89d7df7633b42` |
| `dnd/ai/runtime/assignment_lifecycle.py` | `053be8eb375df442ab5c9e1fec441bfb271ddc699a2ad7198043240421582127` |
| `dnd/ai/runtime/decision_epoch.py` | `aa38db5224c207d43b11378bffe919b37f6b232d47a2f4c722af1fd1a34d409c` |
| `dnd/ai/runtime/state_projection.py` | `f135859d9878fa45a64e05bf1554c87125e25706a5a9792419418d2940730c71` |
| `dnd/ai/runtime/movement_revalidation.py` | `f30b3abeeeb916ad78537906cda004d5378c64cecd2b8257af04e4190b3de27f` |
| `dnd/ai/policies/basic.py` | `87ac6f764dffeab9e15ce4a01e374d21944d7e39e0508afb91ed2154c1237d32` |
| `tests/engine/test_live_encounter_membership.py` | `7a62c18a88742b5f907c72494a121090e358f256fdfa5ca8f50547e49398fdbf` |
| `/tmp/summoning-membership-reviewed-corrections.log` | `62a2dac9cf44f644b8bee1b518dc688c2d5eec544df5ee5329c4ecda83537823` |
| `/tmp/summoning-native-corrections-types.log` | `46a6c7834c9080ada23a415afd925abecc37d531f5c6e3d14ad0a7ff579096cb` |

| Shared method | SHA256 |
| --- | --- |
| `dnd/entity.py::Entity.can_take_actions` | `873e4578cd654286b6161226b6bb2f59d8fb703395559e347454c1ee274e3ad3` |
| `dnd/entity.py::Entity.has_runtime_agency` | `68ef9f263c99bfe66f73bf886296c1b5e19553efacd1dea4c161a153063ddaa8` |
| `dnd/entity.py::Entity.revoke_runtime_agency` | `31cfdef08c75f183f5d9349650b9626a3e8e169a98a8b845c1c35211b8fef918` |
| `dnd/core/base_block.py::BaseBlock.has_runtime_agency` | `6fa98acd33156bbc545803129972649c89d9f680968dab731ffe26697ce7238b` |
| `dnd/core/base_actions.py::BaseAction._source_cannot_take_actions` | `71e7df362611e9c5dde0b5e7f219bb0cbc676f92dfba368ab40d81169fefa190` |
