# Cleanup implementation anti-slop review — 2026-10-03

**Verdict: REQUEST CHANGES.** Two reproduced resolution-ownership defects remain in the implementation of cleanup steps 5–6. The module removal, semantic item eligibility and movement changes are substantive improvements; these findings do not justify replacing them or broadening the gameplay scope.

## Reviewed boundary and snapshot

Independent implementation review against baseline `981079bc0208dbb23f3ccc927347eef77fef4c30`, which is also current HEAD. The working changes are uncommitted. I read the repository instructions, the active recovery contracts and review discipline, the cleanup plan, both source audits it names, and HOW_TO_TEST.MD. I applied the bug-fix review guidance. Plan approvals and the implementation checkpoint were not treated as proof.

I inspected the actual diff and relevant surrounding native, projection and presentation code: action economy/modifiers, Move/Attack/SpellAction, item resource preparation/commit, wearable building and fire coating, the six relocated spells, innate traits/Multiattack, concentration teardown, typed event/player facts, record migration, causal indexing, attack/cast/damage binding, choreography, lifetime traversal, world-binding admission and selected changed tests. This was a targeted semantic review of the cleanup, not a claim of exhaustive inspection of every function in the repository.

The end-of-inspection snapshot contains 100 changed, new or deleted production Python paths under dnd/game/devtools. Its canonical path-to-SHA256 JSON digest is `22273712a7b6fb924976fb036feb30d84b126212543af811a346c9a9288843fa`. The complete manifest is below. Only this review document was written. No production/test edits, new agents, commits or unrelated chat messages were made.

## Blocking findings

### F1 — P1: legacy migration silently reparents real Fire Shield retaliation to the incoming attack

**New migration defect, reproduced.**

The native migration at [event_record.py:196](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/event_record.py:196) treats an immediate AttackEvent or SpellEvent parent as sufficient evidence that a TakeDamageEvent belongs to that parent. The public v1 migration repeats the same rule at [recording_compat.py:79](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/recording_compat.py:79).

Fire Shield is a concrete counterexample within the retained scope. Its retaliation's actual trigger is the incoming attack, while its resolution is its own damage-request lineage. The baseline producer already used `parent_event=attack.uuid` (baseline `dnd/spells/roster_support.py:313`); the current producer correctly records independent resolution at [evocation.py:5266](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/evocation.py:5266). Removing the newly added resolution field recreates precisely the relationship the old recording contains. Migration then assigns the retaliation to the incoming attack instead of diagnosing missing ownership.

I exercised a real melee hit against Fire Shield with fixed faces 15, 2, 3, 4, captured its native lineage, encoded/decoded those events with only `resolution_ref` omitted, and ran the ordinary migration. The retaliation changed from its own request lineage to the incoming attack lineage; the ordinary target damage retained its correct owner. Using the maintained encounter fixture and ordinary projection/binding:

```text
F1 current attack binds True
F1 migrated attack: Attack result belongs to a different recipient
```

The exception comes from [attack.py:300](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/attack.py:300), because the migrated attack now owns damage to both its target and its attacker. The historical record is accepted with false causality before presentation fails. This violates the plan's explicit instruction to diagnose ambiguous legacy ownership rather than guess. It is not a native Fire Shield damage regression.

**Minimal correction:** repair both migration boundaries so they inherit ownership only from sufficient recorded evidence. A trigger parent alone does not establish resolution ownership. Where the old permitted/native record cannot establish the independent callback relationship, report that precise ambiguity and preserve the recording. Do not restore target-direction or artwork-based inference.

**Test gap:** [test_resolution_contract.py:58](/mnt/c/users/tommaso/documents/dev/dnd_engine/tests/game/test_resolution_contract.py:58) models an ambiguous callback by substituting a nonexistent parent. It tests broken ancestry, not the actual ambiguous direct-attack parent used by Fire Shield. Add the real recorded retaliation case to the migration acceptance boundary.

### F2 — P1: Spike Growth entry damage still inherits the pushing spell's resolution and is presented twice

**Incomplete producer migration with a reproduced current presentation defect.** Spike Growth's original entry-damage producer predates this cleanup; the new resolution contract and indexed result aggregation require migrating this producer too.

[transmutation.py:183](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/spells/transmutation.py:183) still calls `receive_damage` without independent resolution or the field's effect origin. The new default at [events.py:5117](/mnt/c/users/tommaso/documents/dev/dnd_engine/dnd/core/events.py:5117) inherits its spatial-trigger parent's reference. An ordinary Move through the field therefore produces a damage request owned by Move, not by the exposure. A Thunderwave push produces an even clearer failure: each spike-entry request inherits Thunderwave's application reference.

I exercised the existing encounter fixture with a caster at (3,3), target at (4,3), Spike Growth centered at (5,3), then a failed-save Thunderwave directed at (4,3). The spells were registered through the normal spell registration path; fixed dice faces were all 1. The actual native results were 2 thunder, 2 piercing at the first entry and 2 piercing at the second entry. Native damage remained correct.

Through ordinary capture → player projection → binding, the result was:

```text
native results [('Thunder', 2), ('Piercing', 2), ('Piercing', 2)]
standalone cues [(2, 1491.0707074572053), (2, 1788.0555555555554)]
forced movement [(1368.0555555555554, 1788.0555555555554)]
cast cue damage_total 6 hp_ms 1701.3888888888887 displayed HP loss 4 cast afterHP 74
gaps ()
```

[combat.py:211](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/combat.py:211) gathers all three packets under Thunderwave's application, sums them into a 6-damage cast cue and takes the final spike packet's HP/damage type. [choreography.py:832](/mnt/c/users/tommaso/documents/dev/dnd_engine/game/choreography.py:832) separately clears the presentation owner for forced movement and binds both spike requests as standalone damage cues. Thus the cast cue claims the same piercing results that already have their own entry cues. Its after-HP includes the final entry before that entry's 1788ms milestone. The accepted result collection has hidden the missing ownership migration; a zero-gap binder is not evidence of correct ownership.

**Minimal correction:** mark the existing Spike Growth entry request as its own resolution at the producer, and retain its existing field origin separately, using the already introduced receive_damage contract. Keep the movement/spell as trigger ancestry. Then verify this same two-entry push has a 2-damage Thunderwave application and two independently owned 2-damage entry results, each consumed once by presentation. Do not patch the caster binder with effect-name exclusions or introduce another event/executor.

The simpler normal-Move case also reproduced the incorrect reference:

```text
resolution_owner: Move
self_owned: False
effect_origin: None
```

This is directly within the approved “later persistent-field entry/turn exposure” mapping, rather than additional spell mechanics.

## What the implementation actually accomplished

- The three task-owned runtime modules and ammunition-only module/hooks are deleted. Searches of active dnd/game source found no surviving roster runtime imports, selected ammunition fields, AttackAmmunition contracts, supports_arrow_payload, permits_use_by or movement_speed_factors. No ammunition executor, ordinary grapple action or new artwork was introduced.
- The six spells are in school owners. Innate flight owns a speed grant and uses Move; it no longer inherits FlyEffect. The three backpacks use cold definitions, the canonical builder and SpellGrantingWearable. Ember Quiver uses the shared timed coating and semantic bow/crossbow eligibility.
- Weapon kind/material replace recipe-ID eligibility in the inspected Shillelagh, Ember and Multiattack paths. The replacement choice is one validated record; its discovery label comes from its action.
- Speed and expenditure now have separate meanings in action economy. Queries read existing values without copying/pruning state; normal modifier ownership carries exact factors and both supported modes share the debit ledger. The focused tests exercised effect ordering, flight added after buffs, independent grants, vetoed removal and query purity.
- Item consumption and recharge remain in one native family with the historical wire name. Terminal history prevents repeated/stale preparation commits, and BaseAction closes outstanding preparations. The selected lifecycle tests cover admitted interruption, release and effect failure without new refunds.
- The inspected world schema and lifetime code genuinely share a passive document and one resolved timeline walker. The old literal cardinal-only wall coverage claim is gone. These changes are not just renamed copies of the removed task buckets.
- Native result variants and ordered result references improve the contract. F1/F2 show why that contract is not yet complete across its actual producers and archive boundaries.

## Verification and limits

The focused existing suite ran with source on WSL /mnt/c, Python 3.13.12 and:

```text
PYTHONDONTWRITEBYTECODE=1
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv
/home/tommaso/.local/bin/uv run --no-sync python -m pytest -q -p no:cacheprovider
  tests/engine/test_roster_support_spells.py
  tests/engine/test_roster_ability_batch.py
  tests/engine/test_item_resource_lifecycle.py
  tests/engine/test_modifiable_value_semantics.py
  tests/game/test_resolution_contract.py

111 passed in 19.34s
```

The two reported findings were additional in-memory diagnostics through real native operations and passive replay/binding. They were not added as test files. Initial exploratory diagnostics needed fixture/attribute corrections; those setup errors are not classified as implementation failures. The final F2 diagnostic completed successfully. No visual screenshot review or complete-suite rerun was performed by this reviewer.

Changed movement assertions in the inspected tests migrate to movement_remaining for expenditure; the removal of arrow tests follows the explicit scope removal. I did not find evidence in those edits of weakened expectations used to conceal a failure. The new synthetic two-result test verifies its selected final HP, but does not exercise the independently triggered field results that expose F2.

Remaining limits, separate from verified defects:

- The public PlayerSequence container does not itself cross-validate application membership against the enclosing node/root and resolution reference. I did not observe a current producer emitting that invalid combination, so this is a schema-completeness risk, not a reproduced gameplay failure.
- The observed-change implementation publishes field/owner references at refresh boundaries, while choreography currently resolves one time for an entire SensoryFact when its sources collapse to one lineage. I inspected the removal of the old formation split; I have not independently verified every mixed-cause sensory batch or all formation/destruction regressions. Do not infer complete coverage from this review.
- The implementation checkpoint discloses broad native/AI, architecture and game-suite failures. I have not independently reclassified every one. Their claimed baseline status is not an approval of those failures, and no such failure is being quietly added to this cleanup's repair scope.
- ECS/import direction received targeted source scrutiny here. This report is the anti-slop implementation verdict, not a substitute for the separately requested independent ECS/import-DAG review.

The minimal remaining work is to correct F1/F2 and rerun their real producer-to-replay cases along with affected existing checks. Approval should be reconsidered on that concrete revision.

## Production snapshot manifest

SHA256 values are exact working-tree bytes. DELETED entries existed at the baseline. The manifest covers the changed production snapshot; it does not claim every file received equally deep semantic inspection.

| Path | SHA256 |
| --- | --- |
| `devtools/animation_review/capture.py` | `4daa695b7bf58acb38bb394ae0158e71fdac80c93da674bd8cfd1b7b46824ce3` |
| `devtools/animation_review/cases.py` | `81bd90949e410b81bdef19ec99070849e0a7d5e7591750e7778db9d219294bc6` |
| `devtools/animation_review/cli.py` | `db7eb94da8197db021546389726044bd62d2300bf778cc457c940f0b24cdd3d3` |
| `dnd/actions.py` | `49d929db1db01accb8fc46b76981ee21ba7d797405b4039c38b76aa2956f396f` |
| `dnd/actions_functional.py` | `78b09eb254b2e9e80c9fc83083a1ff65f7783fc77102209ac4e4f7cdaef466b4` |
| `dnd/actor_projection.py` | `0680c5ce69bc2834e5f51ca24f14d50debd526f71d88d734f0048243936c7057` |
| `dnd/ai/runtime/knowledge_reduction.py` | `d2a7bdf8fe9430d143be0db99c9c76077e62cbffb4394baf6cc1a5e3a33ade7b` |
| `dnd/analytics/game_summary.py` | `8eb4b9d1475165b92cc6404cf74a3228387c9b568b7ef81164d818c601a0f34c` |
| `dnd/blocks/action_economy.py` | `ab7b4b7f28bebf984b3ad79dc865fcc09c11e294924d73683770142acff97b9a` |
| `dnd/blocks/appearance.py` | `acad55f1b0aa839ce23ec565c5bc8cc7d1a21031424a13355c5cc2156b861d07` |
| `dnd/blocks/base_item.py` | `fd65c7032cd5bc115cc025f31494c74c2bb1f003f5f37683a8dee3cb8aaa0224` |
| `dnd/blocks/equipment.py` | `12e526a382fa88bd379617f7ced603d11066af30b530a4c5c171ea38aed39aec` |
| `dnd/blocks/sensory.py` | `4ae4fbbe3c8b2ca1216537ef8fe219e26c3fadb3e60c89fc03ede1797e344f3f` |
| `dnd/classes/barbarian.py` | `fff06a46b3723936a194443c69477a647920a18348fb241829c6ec1487001dcd` |
| `dnd/classes/sorcerer.py` | `6bdbc3be60a1c3f9cdf980d356ff9059ae65dd3af4ca9cd4fb3fc8fbf7691efb` |
| `dnd/conditions.py` | `2279e56c06cd3b97466db261e0e10f3be5428d751f61ffb38f424da4472e5511` |
| `dnd/content/characters/barbarian_grants.py` | `434045bd0e0d30170f205ef9df1c23b930e873e46bbcfdaada9533b95bbec32c` |
| `dnd/content/characters/class_definitions.py` | `e9a1837045fe929d5c4e1fe71c5d1d0fab42bde4ab7e79fbbdd21c46317afcd1` |
| `dnd/content/characters/origin_grants.py` | `bce307fdc224287ed81b77daeed2b33dccc39aecb781cae5be1a0bf7008ca201` |
| `dnd/content/characters/sorcerer_grants.py` | `590105af213d0016b6c078e537379f9ca23c19a5faee8e9c7677a6e56e2f7c83` |
| `dnd/content/items/authored_item_builders.py` | `0c3c16e6f54663fc11d693d9b8e2076737dbbd98b6f661ab144b6c1e3593f953` |
| `dnd/content/items/authored_item_definitions.py` | `3d6c51aa29fe69a3e9ac3c8f7013d7deb9121c407dacc3e2fb545993298cb309` |
| `dnd/content/items/roster_item_definitions.py` | `0999657488e3eb79d86024c9fb1e229d4840cd15b0e34a8271599b3965716c93` |
| `dnd/content_system/action_definitions.py` | `2ac833b6397ccdcd93379e1f960fb4f8d3316b9f694b2c212e507e04cd614760` |
| `dnd/content_system/condition_definitions.py` | `f90800fe589c20ea97868ae7607d3d69eeee40af855403b15cde45bdd5fafbd5` |
| `dnd/core/action_execution.py` | `077501141726dcf3acf4b09abf7f0e626129dedeeccedc3edcbd440ef0f5bbf5` |
| `dnd/core/attack_types.py` | `7a3d9701d283df3e1ed00a3cf68a3a1df85800d5a12db047e1627df7d2f8a74d` |
| `dnd/core/base_actions.py` | `9ea65c77cd5e6621810d37e5bd639fd28d38fd24b342cf17ebf0ce9785d0f078` |
| `dnd/core/base_block.py` | `f47a0d368848771b386a45e29cbb8a370c1199504c8319a7c1816b2c3913aa76` |
| `dnd/core/base_conditions.py` | `39a166b6d765a4b0bfa8ae359fde163d7874c186912b17d0f25c9ac77bfb159e` |
| `dnd/core/content/identities.py` | `51fcb6daab19754baf804295768e2969b5ff8ebfcf70d11d8517e1c66b2ffcfa` |
| `dnd/core/content/runtime.py` | `f6d832d08b8df56a1fed37570717df594c8df4cee7e1f8bfeef320e177439eb3` |
| `dnd/core/creature_types.py` | `a01bf5228211629fc18a7fe3e7bc704e6e97e3c83c03efc15ad68a497d4bc3fb` |
| `dnd/core/dice.py` | `e6ca7fc948731a9672c747ef2013303b09a6bc60921c619cc524a6f0f4a3ff7b` |
| `dnd/core/effect_types.py` | `f27d6b0e4235deed2cde5c90bb3d860d7770aa8c2cea0e7cab2b6470103bca91` |
| `dnd/core/equipment_types.py` | `b656a6173fc3028a1e2b8aa24cc85e2f99616a3dba6fd63276cdfc12e8b1d332` |
| `dnd/core/events.py` | `311f2fc1b5d27494518f350f1f9330284d6416191b5504909e9e92da580cc52d` |
| `dnd/core/gridmap.py` | `2ad8af21e82ecefe2ea26721eeb1617c69e760276a387c0b7edaf8ce063d33e8` |
| `dnd/core/item_properties.py` | `8c65aaee4f66eb8379409fff3c0a08b956f16515d7926af383a47e63b3ffd795` |
| `dnd/core/item_types.py` | `9d99c9ff66c0ee6587ff69fc045df6fee4ba675b847b6bd3da55702aae16bf56` |
| `dnd/core/modifiers.py` | `ffb95f52ea8386e69031d8011e0dc726898c1458c3fdba2b87d0f72984897681` |
| `dnd/core/values.py` | `5c5eed5f140b235d2d98061d4b195c5a42b50149b936752de02aff635d382f40` |
| `dnd/creature_transforms.py` | `8e9060db5c305a82110502e7526f83bdd807406c7e6e6eeb8c62bf25ee00d215` |
| `dnd/damage_payloads.py` | `DELETED` |
| `dnd/entity.py` | `001078733ea7a5b74e4a7023539c88b3578c18fff42f788c99242c25ca59f5ce` |
| `dnd/extensions/field_focus.py` | `92d398300d400300b49c72a8e5a45dd4fd4a727ac871dbac4f939ca78fd9ed7f` |
| `dnd/items/consumables.py` | `39430f55ed14a3fc0de5dc48b071a1e84c0b7324311fdc870fe659a38289ab3c` |
| `dnd/items/property_composition.py` | `97efe49a283ed81fdbbeba651b9005d1dd608d5ded329cd68de50134a1ca4728` |
| `dnd/items/roster_carried_powers.py` | `DELETED` |
| `dnd/items/spell_items.py` | `b2540ff72abb4bea6a4544ebbdefd0c893a6099013da76f88a8fa1b542fa2150` |
| `dnd/monsters/circus_fighter_conditions.py` | `f9e6e6e00d5b659df29f146cbb0a3812c4c8e6f3af4057e6d10938eeb4ea6c24` |
| `dnd/monsters/roster_abilities.py` | `DELETED` |
| `dnd/monsters/traits.py` | `2f1c110f4250b6656b3b3a1ba2f50e34c64e56ae08fcf2b6547246e5dafd3daf` |
| `dnd/residues.py` | `1dc5dcd0d20084dfeaaeec6408390de96ca0ce575917e725427e34f65e0b6b6b` |
| `dnd/spatial/area_conditions.py` | `e35fdf776c7dbb805bd6bae4af2d829d09be29092907fd9075af19f78d1c8622` |
| `dnd/spatial/environmental_conditions.py` | `87cc9b8b3872eb0e9cd267be3d80291c03646d17e922b1ea56109dae67d84dbb` |
| `dnd/spatial/gas_traps.py` | `440c3e2ae01f147997eab0c1c3184a303449317ec36e419f6ebb035523290d81` |
| `dnd/spatial/trap_payloads.py` | `b0e8bf006e551e8453813f974f30f9b5851daa03a981cf2519db9fd2a98078e4` |
| `dnd/spells/abjuration.py` | `49334898d030606b0a05b367c2061e5e7fb517192ae71315f746d9ce3db6be9d` |
| `dnd/spells/catalog_content.py` | `ff919207ac318a1f8bbc51085d5a5ad2dfcaa2909352aa9dbb0c062638b2ae41` |
| `dnd/spells/conjuration.py` | `aa67d3e1215d1df940fa28b38b62498bd0fcdda0a1e1a846694f033bbbf6dde5` |
| `dnd/spells/evocation.py` | `a511c8f60a443c28111c6f2513a7b17df65368ec5f38ae8d4d0a319852d6c3dd` |
| `dnd/spells/ice_knife.py` | `dc0b07374dbd2a086e511198a45c936fbb47d9d2cb9036f0bddafb121167fd6d` |
| `dnd/spells/roster_support.py` | `DELETED` |
| `dnd/spells/transmutation.py` | `7c77f4294c8cdb642ae6b29ebea68f04f74ffa3fa7d872394ec6a52d97718af8` |
| `dnd/spells/wall_constructions.py` | `84406387494909c6794f59e92988d79d0d62af7e6aced0f1f341b78a8e51b031` |
| `dnd/spells/wall_fields.py` | `30b24fbc7a48eca91d8fdf93d2b94494129dbb821571ae36ee66441f197be3e1` |
| `dnd/spells/walls.py` | `b119a4592760933b1b8f4a764a0f74676cb20645f21cde9e95dc3bad085ac2f0` |
| `dnd/types/actor_facts.py` | `db0c1640337561f46a6da2b5c975520263d258c3b87950f6190079f94d0f776c` |
| `dnd/types/appearance.py` | `ad07246b376d0f954d47c0012a06c960f62b77783169bcead928449ecc0a8849` |
| `dnd/types/event_facts.py` | `c75d59273a6b339211d4112c0e28b549899fbad112a726a96c07e62772626834` |
| `dnd/types/world.py` | `8ba59b240d62abdc3dbeaf31750c0897eec302e361e5d568ed3cf911a0b65544` |
| `dnd/world_facts.py` | `2b4e5274321ffbf2bd3b52f1ebbedfbd57117f1305ff06997bf1270c5b9c93a4` |
| `game/animation.py` | `a8905a4e858504e590e4a3e50cc24ea48a051cfb101079c75e688442f3588902` |
| `game/animation_data.py` | `5af572f7a43225db623ff8e44045306348d8b6cfbf57c0fe89acda4bd2128947` |
| `game/assets.py` | `75ff1b3bb6fb432965bd8feb7d2b6bdfb59e99bbfd1253b64f765019e2a0ae20` |
| `game/attack.py` | `e1ffd44afde4211e424f491e95aa35a98c5f71df1cc1d90029ee2b86e9456741` |
| `game/authoring_conversion.py` | `6928349220f6351742a84ff7a5c2fa06fd1f840f00d6b97198c23dcb535b5ead` |
| `game/choreography.py` | `2c307a7418ce98f03f9a07b8bfe3b3a0f7fe44b72c73d1f3f3db3398e48cff4f` |
| `game/combat.py` | `d07f382aea3ba49cdef29acf466d67243ecb115336e3701c1596bab48b8b58aa` |
| `game/concentration_media.py` | `f4cbb38d61f400c310692eca0e508b0d6c69c851a4547457219b9c7aa862f366` |
| `game/condition_media_lifetime.py` | `9e135286c42270cd6ebaa8f5d23cc9fbddaf1d4c48c871984c1c519d951b5103` |
| `game/condition_reaction.py` | `e5b2dcc461a388e4705ea50285b18714fc4fc3cfda4a39e99cb5b3101aa06c94` |
| `game/construction_media_lifetime.py` | `014896ad3c10a8ccd2899b16dfa28f30f44b3591272bf8f61fe27e3f502337ef` |
| `game/construction_transitions.py` | `a113f71a3c1f0687d111a078683c878f0b358cb9f0640453498d02c0baf32543` |
| `game/damage.py` | `098bd8e0905e27bfc33080eacede7dc629a95c3897f91460b24adc9646244472` |
| `game/encounter_play.py` | `7b85545179c5253f2a7887244c351b7119aaf74cf1c83237f588898030440403` |
| `game/event_record.py` | `2785c69ee432d511dcb259316c418a48b0e415467887c7da40bfea680b04757d` |
| `game/export_schema.py` | `8bdc67725225b9ae3fc2631bea9a51a598d36969eacc0e93704da7b09efab2ed` |
| `game/play.py` | `9e37fc07a4bf87e037c8ef2af57d384af0abf524fae11f0bd6682b1fa388dcea` |
| `game/player_facts.py` | `d6508e126c340df34ded13f5efbede662cf2213c964260781a9792aa5df65563` |
| `game/player_projection.py` | `aa7b0c64c63bc02200eec33ed4e0cd55beca7cfac6cbcdab1d693e6785b23acb` |
| `game/player_reduction.py` | `f4e68929a92f4dd3acd98badf9f8225d955c51d96456e33e6e7f4dd396df0ac4` |
| `game/presentation.py` | `7a03b57d78f2b8f05fdb55a6b81eec29856d1cb1709195940e1eea369a4efe48` |
| `game/presentation_coverage.py` | `80a776b153dce3d940a05f02f4a591dc94091f8a55c0d2d788c1554ff57eab28` |
| `game/recording_compat.py` | `4530337d89a76bbcaf23104fa8411d976963cf3216626c67a51c48ba7815dba1` |
| `game/spatial_contact_media.py` | `cd1162aa12387720c0fed7830643e28493bc14d907b5a6bee7c7588e0a3cab86` |
| `game/spatial_media_lifetime.py` | `08910313b4473442f19a9ede97f826b71aafc8723dd1dcec67c3eadde3959019` |
| `game/world_animation.py` | `460cb9184342019b5ff49e3c794b6c933b3243bf437345284fda82fa95805153` |
| `game/world_binding_types.py` | `2e36cbb993f446b7bcf63d1d2ffa6b0fa935ce473213923f5e3cc60e2c40c74e` |

