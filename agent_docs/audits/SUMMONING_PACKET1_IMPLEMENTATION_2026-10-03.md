# Summoning packet 1 implementation — 2026-10-03

Status: implemented and frozen for independent review. This is the ordinary-creature/body-attack prerequisite of `SUMMONING_BACKEND_PLAN_2026-10-03.md` §§2.3–2.4. It does not claim downstream summoning, renderer or artwork acceptance.

## Behavior and boundaries

A normal creature recipe materializes the creature independently of summoning. The same native Attack action resolves each selected anatomical attack against native creature/object targets, with the selected intrinsic item identity and the ordinary action economy. Both possession policies retain intrinsic anatomy and prevent dropping it. Existing Wolf, Dretch, Corrosive Demon and Dread Demon recipes are reused, not cloned.

Twenty new canonical recipes join the existing content inventory: Hound, Boar, Stag, Jaguar, Bison, Ostrich, Brown Bear, Lion, Tiger, Polar Bear, Rhinoceros, Blue Raptor, Stegosaurus, Elephant, Triceratops, Mammoth, Tyrannosaurus, Claw Mote Devil, Huntsman Wing Devil and Fellwing Devil. Each new recipe is `content.neurodragon:creature:creature.<key>@1`, using the keys in the plan. `BEAST_RECIPES_BY_ID` and `FIEND_RECIPES_BY_ID` expose ordinary references for downstream form authoring.

The full cold stat/trait rows live in `beasts.py` and `fiends.py`. New anatomical damage and armor identities live in the existing authored item inventory: 28 weapons and13 hides. HP uses the existing HealthConfig bonus to preserve the approved printed total rather than silently taking the engine's player-style hit-die average. No health subsystem or entity subclass was introduced. SRD5.2 Allosaurus/Ankylosaurus numerical ancestry is explicitly attributed through one source document entry; mechanics remain the exact adapted 5.1-style choices in the plan.

## Existing owners changed

- WeaponDefinition/Weapon add explicit HELD/BODY usage, default HELD. BODY validates intrinsic natural ownership. The existing secondary melee selector admits it without LIGHT or a dual-wield talent.
- Attack's existing default-cost validator supplies one action for either anatomical selector. Explicit `costs=[]` Multiattack children remain free; ordinary held off-hand defaults remain bonus actions.
- Existing weapon/equipment damage owners provide full ability damage for body attacks in either selector. Entity physical access resolves them as NATURAL while retaining the exact item source facts.
- Entity's existing size-dice query now treats body dice as already authored for the creature's original size. Enlarging the creature adds only the size increase. Runtime and outcome-profile callers use the same query; ordinary held/natural-spec paths retain their prior policy. Without this adjustment a Huge T-Rex incorrectly received an extra2d4 on top of the approved4d12+7.
- Existing Multiattack discovery exposes its normal action and authored substitutions, without restricted-budget variants. Normal Action Surge still buys its ordinary action; Haste does not buy a whole Multiattack, including under the existing BG3_HONOUR policy. No new budget or executor.
- HitSaveRiderFeature now matches the selected intrinsic item identity in AI profiles and recorded attack facts. Renaming Claws cannot move its Prone rider onto Bite. Existing Wolf/Dire Wolf/Ghoul callers and the four existing scenario/test configurations use exact item IDs.
- The existing SRD EntityConfig composer is now named `create_creature_entity` and reused by both new family modules. Existing factory calls retain their behavior.
- Content inventory includes the20 creatures,5 configured Multiattack declarations and the two shared existing parameterized trait identities. Creature factories import no summoning runtime.

## Explicit authored scope

The primary attacks, knockdown DCs, bear Bite+Claws, Stegosaurus two Tail attacks, Huntsman two Claws and Fellwing two Claws+Gore match plan§2. T-Rex exposes Bite OR Tail and no holding/grapple/split-target sequence. Flying devils use existing ground-to-ground InnateFlight. Source passive senses and the chosen devil defenses are explicit data. No charge tracking, automatic follow-up attacks, hovering, swimming/climbing, new spells or additional devil traits were added. Bison's metadata explicitly omits a new Sure-Footed extension. Unrelated anatomical weapon definitions retain their pre-existing usage semantics.

## Verification

Environment: shared `/mnt/c/users/tommaso/documents/dev/dnd_engine` checkout, existing uv environment, Python3.13. Commands use `uv run --no-sync`; no application/media jobs were started.

- `tests/engine/test_canonical_body_creatures.py`: **76 passed**. All24 canonical recipes under both possession modes; exact new HP/AC/ground speed; intrinsic ownership; body secondary admission, full damage and one-action cost; typed recorded attack identity; six configured Multiattacks; ExtraAttack/Haste/ActionSurge/Slow combinations; item-identity knockdown matching; body enlargement formulas; grounded flight; primary-only opportunity attack spends exactly one reaction.
- Expanded native/content regressions: **419 passed,1 failed** across manual53 SRD monster traits, manual51 SRD roster, manual125 Haste, manual155 content inventory, equipment ownership, psychic items, residue fear and trap ground contact. The first414-check attack/equipment/economy run was fully green. The remaining failure is described below; it is not concealed as a packet pass.
- Changed production modules (including shared `actions.py`/`entity.py`): **Pyright0 errors** across15 files.
- No renderer changes. The two `tests/game` files only change the existing generic rider's authored selector from display name to item ID.

Receipt logs: `.runtime/packet1-tests.log`, `.runtime/packet1-regressions.log`, `.runtime/packet1-pyright.log`, `.runtime/packet1-encounter.log`.

### Expanded-regression failure outside this packet

`tests/manual/test_51_srd_monster_roster.py::test_authored_srd_encounters_build_through_canonical_recipes` fails while assembling a stored scenario with `Unknown content reference content.neurodragon:creature:creature.player.fighter@1`. It also fails standalone. The current and HEAD builtin inventory do not provide the retired player-creature factory; `dnd/scenarios/authored_catalog.json`, `dnd/content/characters/class_definitions.py` and that test are unchanged by this packet. The obsolete encounter still stores this old reference. This packet neither restores a retired factory nor rewrites scenario content. Root has the exact failure for reconciliation in the overall implementation.

## Ownership and review snapshot

Shared files `dnd/actions.py`, `dnd/entity.py`, and `dnd/blocks/equipment.py` also contain root's separate lifecycle work. This packet owns only the Attack default-cost validator, Entity physical-access/size-damage query and its two callers, and Weapon usage/admission/damage-profile changes. Do not attribute other current diffs in those files to packet1.

The following files are the packet-specific review snapshot. Independent anti-slop/ECS review is required before downstream acceptance; it has not been self-approved.

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
