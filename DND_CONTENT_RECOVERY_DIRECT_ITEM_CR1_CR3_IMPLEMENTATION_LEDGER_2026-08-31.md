# Direct-item recovery CR-2I/CR-I implementation ledger

Date: 2026-08-31  
Status: `SLICES_1_6_IMPLEMENTED — READY_FOR_INDEPENDENT_REVIEW`

## 1. Boundary and outcome

This is the single Slice 0 ledger authorized by
`DND_CONTENT_RECOVERY_DIRECT_ITEM_HARD_CUT_CR1_CR3_IMPLEMENTATION_PLAN_2026-08-31.md`.
No production or test behavior was edited while producing it.

The preflight freezes:

- the exact 147-key public direct-item inventory;
- the one private Guardian of Faith `BaseItem` identity;
- all current and accepted construction/value evidence;
- the complete CR-2I behavior prerequisite set;
- current item-runtime callers, import edges, durable records, Events,
  proficiency state, holders, visuals, door collision, and Guardian family;
- the maintained affected-node union and planned CR-I successor nodes; and
- the one unresolved authored datum that forbids production work.

This ledger does not authorize server, SDK, transport, renderer, MapEditor,
Pygame, CR-4+, or general CR-9 work. It adds no compatibility path, manager,
service, registry, resolver, materializer, callback transaction, OOP content
hierarchy, late import, reflection, or circularity exception.

## 2. Governing bytes

| Authority | SHA-256 / identity |
|---|---|
| Checkout HEAD | `205fd679fde51d5319d332f12ec241d7aecd93a6` |
| Accepted direct-item plan | `51b06ddd6c67742fe32dee8f7bb729a72134d54df1805d6b434ad68dba24ae0b` |
| Accepted plan substantive bytes | `cf4a85a6fbb2e1021dbab87a7b7a79495dba8b853ffcafbd414c1096243e8107` |
| Master recovery plan | `3e6a38a534331f0cdf92127fe5d9b765bf7e81a7d44baee08876bfd1613bec7b` |
| CR-0 completion ledger | `b04eb0ed05d8e8d17a3c2136f9454aa9d08c22712c0ed63da551832eec1f09ef` |
| CR-0 evidence manifest | `fdcd5c32b7ded90bb52e94fbb492181416b735eaddc4a3e0956540b613dbaa65` |
| `AGENTS.md` | `296ce0a99c52fab93261a15e193258b928c0b56c161b91ef8e412f5d27897668` |
| `HOW_TO_TEST.MD` | `96ba573eb50504f9e2c9c8676acc2f352ae198466d79f46e75c57d3f29995013` |
| Accepted behavioral checkpoint | commit `513dd97` |

The uncommitted CR-0 proof bytes present at preflight are also frozen because
they participate in the maintained node union:

| Path | SHA-256 |
|---|---|
| `tests/architecture/test_content_recovery_cr0_evidence.py` | `087571cdda3b8ec5adee13787bb93daa352e2373dcdb45da7c42a46919ebbb70` |
| `tests/engine/test_content_recovery_behavior_semantics.py` | `a7275fcb8bd0c897eb6e7513f79dccb381952140f09ea5c2b3fb167e53b34c9a` |
| `tests/engine/test_content_recovery_item_semantics.py` | `2fa4ad865a8a792cef6f0ed973d82f2f2cbc24b45348893ed633a4786f3674c5` |
| `tests/progression/test_content_recovery_character_semantics.py` | `0bd09985c058039f4c007325aa3761d67b66f9196a6379e4c7ac20acb2f0c79c` |
| `tests/progression/test_sorcerer_spell_source_materialization.py` | `2c9d97457d6c743fafb3432bdb540c74240ad2b36feae27dde71454c99db3665` |

## 3. Exact public inventory reconciliation

The canonical set is regenerated from the non-null
`direct_item_reconciliation.reconciled_public_semantic_id` values on CR-0
`implemented_content` rows whose kind is `item` or `environment_object`.

| Set | Rows | Normalized SHA-256 |
|---|---:|---|
| Canonical sorted, newline-terminated public IDs | 147 | `04966a28ddf9fae4b413f0d101b61a262e26f76395475d54a4029874b583436d` |
| All 149 CR-0 item/environment rows, canonical JSON by `row_id` | 149 | `0d8b1ce9d2ae0d6087916002f5e612449e1c17020680816a7ec5aed08d1e69cd` |
| 147 public CR-0 rows, canonical JSON by `row_id` | 147 | `388e5265b0f8d98273b73854e9a54d0396bd2b73fd379c5ad3edcecf2e2d2698` |
| Current-owned public rows | 126 | `5b2b3264ce27c391b86a7b35368fee68a4c90ad2ed7fb0493784c0dab726782e` |
| Accepted-only public rows | 21 | `f6adc2cea7f3f6d103c3dd220c57c1031120e3a64cf42c44609deed33daab718` |
| Non-public current collision/private rows | 2 | `d61d2cca7a389b965a72de8f11e3472a23cc4cc775d2f963f0b0ea384e2c6450` |

Current runtime authority contains 128 item/environment declaration refs,
whose sorted newline identity hash is
`36b6e534d94f7613e5bf5c1499ce387ed8cbfbbc2b084dbb99c5cd367902ad0d`.
It also contains 205 recipe-preset refs, hash
`be8943e7f889f57ef219b077e69a739ef443a6bcaba2a215a6fc5d32353864a0`.
The 128 are the 126 current public roots plus `environment.door` and the
private Guardian object. The 21 accepted-only public rows close the public
set to 147. There is no count conflict.

### 3.1 Canonical public IDs

```text
apparel.armored_boots
apparel.bracers
apparel.chain_coif
apparel.cloth_hood
apparel.cloth_shoes
apparel.cloth_shoes.blue
apparel.cloth_shoes.dark
apparel.cloth_shoes.red
apparel.common_clothes
apparel.common_clothes.farmhand_tunic
apparel.common_clothes.peasant_rags
apparel.costume
apparel.costume.pit_fighter_wrap
apparel.crown
apparel.fine_clothes
apparel.gauntlets
apparel.great_helm
apparel.horned_helmet
apparel.iron_helmet
apparel.iron_helmet.steel
apparel.leather_boots
apparel.leather_boots.brown
apparel.leather_boots.dark
apparel.leather_gloves
apparel.leather_hood
apparel.leather_shoes
apparel.leather_shoes.brown
apparel.monster_hands
apparel.monster_helm
apparel.robes
apparel.robes.acolyte_vestments
apparel.robes.dark_cultist
apparel.robes.hedge_wizard
apparel.robes.necromancer
apparel.robes.priest_vestments
apparel.robes.red_mage
apparel.robes.wizard
apparel.sandals
apparel.sandals.rope
apparel.spellblade_crown
apparel.travelers_clothes
apparel.travelers_clothes.thief_garb
apparel.wizard_hat
apparel.wizard_hat.red
armor.armor_scraps
armor.breastplate
armor.chain_mail
armor.chain_shirt
armor.circus.performer_leather
armor.cloth
armor.creature.dire_wolf_natural
armor.creature.wolf_natural
armor.half_plate
armor.hide
armor.leather
armor.padded
armor.plate
armor.ring_mail
armor.scale_mail
armor.splint
armor.studded_leather
consumable.acid_flask
consumable.healing_potion
consumable.potion_greater_invisibility
consumable.potion_haste
consumable.weapon_coat.concentration_fire
consumable.weapon_coat.fire
consumable.weapon_coat.lightning
consumable.weapon_coat.timed_fire
environment.arcane_device
environment.arcane_machine_gun
environment.blocker.barricade
environment.blocker.boulder
environment.blocker.crate
environment.blocker.oil_barrel
environment.campfire
environment.cliff_face
environment.directional_door
environment.directional_wall
environment.fireball_cannon
environment.spell_object.heroes_feast
environment.storage_chest
environment.trap_lever
environment.wall_torch
equipment.portable_torch
gear.common_clothes
gear.field_kit
gear.holy_symbol
gear.incense
gear.prayer_book
gear.vestments
shield.shield
shield.wooden
spell_item.scroll_fire_bolt
spell_item.scroll_fireball
spell_item.scroll_hold_person
spell_item.scroll_invisibility
spell_item.scroll_mage_armor
spell_item.scroll_magic_missile
spell_item.scroll_spike_growth
spell_item.wand_fire
spell_item.wand_magic_missiles
weapon.arcane_staff
weapon.assassin_dagger
weapon.battleaxe
weapon.circus.flaming_scimitar
weapon.circus.longsword_plus_one
weapon.circus.rusty_dagger
weapon.circus.soul_draining_morningstar
weapon.club
weapon.creature.bandit_captain_thrown_dagger
weapon.creature.bugbear_morningstar
weapon.creature.dire_wolf_bite
weapon.creature.ghoul_bite
weapon.creature.ghoul_claws
weapon.creature.kobold_sling
weapon.creature.ogre_greatclub
weapon.creature.ogre_thrown_javelin
weapon.creature.ogre_zombie_morningstar
weapon.creature.spy_hand_crossbow
weapon.creature.thrown_javelin
weapon.creature.wolf_bite
weapon.creature.zombie_slam
weapon.dagger
weapon.dart
weapon.double_bladed_sword
weapon.greataxe
weapon.greatsword
weapon.handaxe
weapon.heavy_crossbow
weapon.javelin
weapon.light_crossbow
weapon.light_hammer
weapon.longbow
weapon.longsword
weapon.mace
weapon.morningstar
weapon.quarterstaff
weapon.rapier
weapon.scimitar
weapon.shortbow
weapon.shortsword
weapon.sickle
weapon.sling
weapon.spear
weapon.trident
weapon.warhammer
```

The 21 accepted-only members are the 20 authored apparel variants listed in
the accepted plan plus `environment.cliff_face`. Their exact CR-0 rows are
covered by the accepted-only hash above. Their accepted value/build evidence
is additionally frozen by these accepted-checkpoint bytes:

| Accepted source | SHA-256 |
|---|---|
| `513dd97:dnd/content/items/authored_item_definitions.py` | `b81a69f7a0ef6b52887b388cc2db73f664094af48fb14b813556827c05327294` |
| `513dd97:dnd/content/items/authored_item_builders.py` | `47660f9800dbdc1daca6ebbb0c7dae977a5efc715059d49a025b26288dd6f52e` |
| `513dd97:dnd/content/items/environment_item_builders.py` | `af5132f7cbdb9d16a97fa1f1eb6738da69f9de68161554a97300fba0b8b25320` |
| `513dd97:dnd/content/items/item_catalog.py` | `bce7cd163d2fa8ecdea77fe1bdd91ed2202835f784ced6a42f2ee4b37c621f04` |
| `513dd97:dnd/content/items/item_loadouts.py` | `0b7f7baaa529d43b1ccab8dea6d1b14115d6eb7e581db1584661a3ce40799374` |
| `513dd97:dnd/content/items/item_placement.py` | `521a24e47e4da4022cea81a254a74593519b3f81e6f6f164af8583a9edf04108` |
| `513dd97:tests/manual/test_neurodragon_apparel_content_factories.py` | `bda0ec5f29d932a269eca83057d76f3ff402d3a91cd9d5dbe0d7e51824acb92e` |
| `513dd97:tests/engine/test_direct_scenario_deployment.py` | `76f3223eb55c29cc27dcb4f131e51596df01afa390aebe3fc8567fd76d09972f` |

The exact current owner-path set contains 12 files and has normalized path
hash `a97fcc88424991f7294b2dc1beb0ed4abffcbd8b865b09fefec145e30a606db5`.
The file hashes at preflight are:

| Current owner source | SHA-256 |
|---|---|
| `dnd/extensions/field_focus.py` | `d813ac5c296e56a0064dd4457036a674189b5c9980cd53cb930656db1af5a998` |
| `dnd/items/acolyte_gear.py` | `07d7f3dc7122fa2958ff67e0a28db1c49c5e3ae055e3a3ae0d5ddc2ce42e3123` |
| `dnd/items/armors.py` | `0f0624155f80fdd405d45312f1968d2d031771e0002c888465426f410579d056` |
| `dnd/items/consumables.py` | `a0bb91a4aad63edb14b311ac87a18907ff2048c4448896c1e6c03cb5ac3a99ca` |
| `dnd/items/environment_content.py` | `10987cbee45421f15d44ce9c34ae96b5fb04aa034883e6f9dd703c7140b9a604` |
| `dnd/items/spell_items.py` | `5bc9089b9c8c2eb3228490c9c0ea3cc151be788c3588e0179b726ba698fc9cc1` |
| `dnd/items/torches.py` | `a3210bd43ca154da099a5d8e532695adaf03c5d632897fd0b74a3922e4511088` |
| `dnd/items/weapons.py` | `fa91f6551b49b226cf52dc81aeacee9141ab6bd4901239a7b7ada3f1aecc28bc` |
| `dnd/monsters/bestiary_items.py` | `a9461b23d9cba96bc3beac71b076615e06af19484a4b0048a52456d95be0561e` |
| `dnd/monsters/circus_fighter_items.py` | `e42b4392012f04493bb42400d32dceb1ea540e9a90005cb85f4e26d417dd5d4d` |
| `dnd/monsters/srd_roster_items.py` | `a13ac55fac8c80a5c081fa8184511258e8ef55462ae8e686f7fca00d9e9aacd1` |
| `dnd/spells/conjuration.py` | `230a357a3578f4604e56199a46d3bd7f4c08cdf0f33aa77eac3b338746e78556` |

The two non-public rows have exactly these dispositions:

- `environment.door` is a current-only collision retired into
  `environment.directional_door`;
- `environment.spell_object.guardian_of_faith` becomes a private direct
  `BaseItem.item_id`, never a public builder key.

## 4. CR-8 visual evidence freeze

No visual authority moves in CR-2I/CR-I. The following source artifacts remain
preserved exactly and are not deleted:

| Artifact | Rows | SHA-256 |
|---|---:|---|
| Current authored item visuals | 283 | `7850493fb83395a363110e0c5e99d9da69a287a7b1f663c4906715af41ce7a4a` |
| Accepted authored item visuals | 283 | `267ef479048dfd2fc52d78037e29becbd74d7ccc8939194a94dc44fa49118f08` |
| Current icon bindings, complete artifact | 874 (`669` definitions, `205` presets) | `2129a753a0ad13d5fa472ad9dd9a3b354ae0f73299b753d12ef520ac17736ec8` |
| Accepted icon bindings, complete artifact | 876 (`671` definitions, `205` presets) | `308d849b8e6e930409a611ace81fe86f819d9b370979882f7d3c0543252c7bbd` |
| Current game-icon asset index | 515 | `da24829f890902b37e79ea4e31fff2893ff184db2fc6eea36877c22081b2ed8f` |
| Accepted game-icon asset index | 521 | `1cf4d2620016b27e94591c1a757401e49a1e195fdc9b5b831d3abf84f71a7da4` |

The mechanically selected item-relevant CR-0 Python overlay is the union
specified in plan section 6.3. It has:

- 182 unique rows/semantic IDs;
- sorted newline semantic-ID hash
  `b28bdc07d4683d1ccd9dce416234daa241c989c8ba59551e8235cb290b6bfb3d`;
- canonical sorted-row JSON hash
  `1c9cedcb50a895f23ca997c3b2bc8d1ab040a6a91e47725d8f635f75ce831e1e`;
- 153 `definition_presentation` rows, 7 `bestiary_wardrobe` rows,
  21 `configured_srd_wardrobe` rows, and one accepted Guardian spatial row.

The current source-path distribution is exact: Field Kit `3`; Acolyte gear
`5`; armor/apparel `39`; consumables `15`; directional environment `2`;
environment content `14`; environment interactions `7`; spell items `11`;
torches `5`; weapons `28`; bestiary content/items `8`; circus items `5`;
configured SRD wardrobe `21`; SRD-roster items `15`; Guardian spell source
`3`; and accepted Guardian spatial source `1`.

The four maintained premade build rows currently resolve 49 complete starter
holding rows. Canonical resolved-row JSON hash:
`b7687f447c836f3373b245fbcc8a1ed70616ba1f05aa50e2e6c072d340209889`.
Their eight explicit premade-owned additional holdings have hash
`4974942a4bf91a7aa29dded99bf90ece5e62bf496de6320d24a841296ddd9f93`:

| Premade | Additional item | Quantity | Slot |
|---|---|---:|---|
| Berserker | `apparel.costume` | 1 | body |
| Berserker | `apparel.leather_boots` | 1 | feet |
| Berserker | `equipment.portable_torch` | 1 | none |
| Spellblade | `apparel.spellblade_crown` | 1 | head |
| Spellblade | `equipment.portable_torch` | 1 | none |
| Shield Fighter | `weapon.longbow` | 1 | ranged main |
| Shield Fighter | `equipment.portable_torch` | 1 | none |
| Draconic Sorcerer | `equipment.portable_torch` | 1 | none |

Every row in this section is `visual_evidence_CR-8` / `preserved_for_CR8`.
CR-I may remove migrated active generic icon-closure rows only as needed to
delete declarations; it must preserve these evidence/source bytes and exact
instance visual values.

## 5. CR-2I item-required behavior closure

The public declarations contain 33 exact item-to-behavior dependency edges,
covering 26 unique action/spell behavior refs. Canonical edge JSON hash:
`f703e142b79ed952d295bf4c3daaa52b148d88374e4700b347fb02cdb2fe947b`.
Seven condition behaviors are constructed by those actions and complete the
family. The resulting 33 unique direct behavior IDs have sorted newline hash
`7886132f4b47c4dc8d95716da233083b3856b77906d9b2a0045d76b913a7313d`.

### 5.1 Exact behavior IDs

```text
action.environment.arcane_device.activate
action.environment.campfire.cook
action.environment.campfire.rest
action.environment.directional_door.close
action.environment.directional_door.open
action.environment.heroes_feast.eat
action.environment.storage_chest.loot_all
action.environment.trap_lever.pull
action.environment.wall_torch.extinguish
action.environment.wall_torch.ignite
action.item.field_kit.deploy
action.item.potion_greater_invisibility.drink
action.item.potion_haste.drink
action.item.potion_healing.drink
action.item.torch.extinguish
action.item.torch.ignite
action.item.weapon_coat.apply
condition.consumable.weapon_coat.concentration_fire
condition.consumable.weapon_coat.fire
condition.consumable.weapon_coat.lightning
condition.consumable.weapon_coat.timed_fire
condition.field_focus
condition.spell.greater_invisibility
condition.spell.haste
spell.acid_flask
spell.burning_hands
spell.fire_bolt
spell.fireball
spell.hold_person
spell.invisibility
spell.mage_armor
spell.magic_missile
spell.spike_growth
```

### 5.1.1 Exact mechanics owners and legacy admission rows

The direct owner is not a new table or resolver. For every row below, the
listed concrete mechanics class remains the owner and carries/produces the
same primitive ID through the existing action/condition/spell source and
Event surfaces. Only the listed legacy declaration/admission and its generic
runtime consumers are removed family-atomically. No class may retain both an
attached legacy declaration identity and its direct identity.

| Direct behavior ID | Concrete mechanics owner | Current legacy declaration/admission | Post-cut owner |
|---|---|---|---|
| `action.environment.arcane_device.activate` | `dnd/items/environment_interactables.py::ActivateDeviceAction` | `dnd/content_system/action_definitions.py::ACTION_BEHAVIOR_DECLARATIONS` | same concrete class/module |
| `action.environment.campfire.cook` | `dnd/items/environment_interactables.py::CookAction` | same action declaration tuple | same concrete class/module |
| `action.environment.campfire.rest` | `dnd/items/environment_interactables.py::RestAction` | same action declaration tuple | same concrete class/module |
| `action.environment.directional_door.close` | `dnd/items/environment.py::CloseDirectionalDoorAction` | same action declaration tuple | same concrete class/module |
| `action.environment.directional_door.open` | `dnd/items/environment.py::OpenDirectionalDoorAction` | same action declaration tuple | same concrete class/module |
| `action.environment.heroes_feast.eat` | `dnd/spells/conjuration.py::EatFromFeast` | same action declaration tuple | same concrete class/module |
| `action.environment.storage_chest.loot_all` | `dnd/items/environment_interactables.py::LootAllAction` | same action declaration tuple | same concrete class/module |
| `action.environment.trap_lever.pull` | `dnd/items/environment_interactables.py::PullLeverAction` | same action declaration tuple | same concrete class/module |
| `action.environment.wall_torch.extinguish` | `dnd/items/torches.py::ExtinguishWallTorchAction` | same action declaration tuple | same concrete class/module |
| `action.environment.wall_torch.ignite` | `dnd/items/torches.py::IgniteWallTorchAction` | same action declaration tuple | same concrete class/module |
| `action.item.field_kit.deploy` | `dnd/extensions/field_focus.py::DeployFieldFocus` | same action declaration tuple | same concrete class/module |
| `action.item.potion_greater_invisibility.drink` | `dnd/items/consumables.py::_DrinkGreaterInvisibilityPotionAction` | same action declaration tuple | same concrete class/module |
| `action.item.potion_haste.drink` | `dnd/items/consumables.py::_DrinkHastePotionAction` | same action declaration tuple | same concrete class/module |
| `action.item.potion_healing.drink` | `dnd/items/consumables.py::_DrinkHealingPotionAction` | same action declaration tuple | same concrete class/module |
| `action.item.torch.extinguish` | `dnd/items/torches.py::ExtinguishTorchAction` | same action declaration tuple | same concrete class/module |
| `action.item.torch.ignite` | `dnd/items/torches.py::IgniteTorchAction` | same action declaration tuple | same concrete class/module |
| `action.item.weapon_coat.apply` | `dnd/items/consumables.py::_ApplyWeaponCoatAction` | same action declaration tuple | same concrete class/module |
| `condition.consumable.weapon_coat.concentration_fire` | `dnd/items/consumables.py::_ConcentrationFireWeaponCoatCondition` | `dnd/content_system/condition_definitions.py::CONDITION_BEHAVIOR_DECLARATIONS` | same concrete class/module |
| `condition.consumable.weapon_coat.fire` | `dnd/items/consumables.py::_FireWeaponCoatCondition` | same condition declaration tuple | same concrete class/module |
| `condition.consumable.weapon_coat.lightning` | `dnd/items/consumables.py::_LightningWeaponCoatCondition` | same condition declaration tuple | same concrete class/module |
| `condition.consumable.weapon_coat.timed_fire` | `dnd/items/consumables.py::_TimedFireWeaponCoatCondition` | same condition declaration tuple | same concrete class/module |
| `condition.field_focus` | `dnd/extensions/field_focus.py::FieldFocus` | same condition declaration tuple | same concrete class/module |
| `condition.spell.greater_invisibility` | `dnd/conditions.py::GreaterInvisibilityEffect` | same condition declaration tuple | same concrete class/module |
| `condition.spell.haste` | `dnd/spells/transmutation.py::HasteEffect` | same condition declaration tuple | same concrete class/module |
| `spell.acid_flask` | `dnd/items/spell_items.py::_AcidFlaskSpell` | `dnd/items/spell_items.py::ACID_FLASK_SPELL_DECLARATION` | same concrete class/module |
| `spell.burning_hands` | `dnd/spells/evocation.py::BurningHands` | `dnd/spells/catalog_content.py::SPELL_CONTENT_DECLARATIONS` | same concrete class/module |
| `spell.fire_bolt` | `dnd/spells/evocation.py::FireBolt` | same spell declaration tuple | same concrete class/module |
| `spell.fireball` | `dnd/spells/evocation.py::Fireball` | same spell declaration tuple | same concrete class/module |
| `spell.hold_person` | `dnd/spells/enchantment.py::HoldPerson` | same spell declaration tuple | same concrete class/module |
| `spell.invisibility` | `dnd/spells/illusion.py::Invisibility` | same spell declaration tuple | same concrete class/module |
| `spell.mage_armor` | `dnd/spells/abjuration.py::MageArmor` | same spell declaration tuple | same concrete class/module |
| `spell.magic_missile` | `dnd/spells/evocation.py::MagicMissile` | same spell declaration tuple | same concrete class/module |
| `spell.spike_growth` | `dnd/spells/transmutation.py::SpikeGrowth` | same spell declaration tuple | same concrete class/module |

The 33 canonical mapping rows above have no duplicate ID or mechanics owner.
Their source symbols are the exact CR-0 `implemented_content.current_owner`
values (line suffixes omitted so edits do not turn evidence into line-number
authority). Their current declaration identities are the corresponding CR-0
`legacy_authorities` `declaration` plus `behavior_identity` rows.

The complete selected-family declaration/admission consumer closure is:

| Consumer owner | Exact selected-family dependency | SHA-256 |
|---|---|---|
| `dnd/items/consumables.py` | action/condition decorators, `get_content_declaration`, condition/action dependency refs, semantic-key validation | `a0bb91a4aad63edb14b311ac87a18907ff2048c4448896c1e6c03cb5ac3a99ca` |
| `dnd/items/torches.py` | action decorators and `GRANTS_ACTION` refs for portable/wall torch behavior | `a3210bd43ca154da099a5d8e532695adaf03c5d632897fd0b74a3922e4511088` |
| `dnd/extensions/field_focus.py` | Field Focus/Deploy decorators and Field Kit action dependency | `d813ac5c296e56a0064dd4457036a674189b5c9980cd53cb930656db1af5a998` |
| `dnd/items/environment_content.py` | selected environment action refs plus Fireball/Magic Missile declaration refs | `10987cbee45421f15d44ce9c34ae96b5fb04aa034883e6f9dd703c7140b9a604` |
| `dnd/items/spell_items.py` | all nine selected spell declarations and item `GRANTS_SPELL` refs | `5bc9089b9c8c2eb3228490c9c0ea3cc151be788c3588e0179b726ba698fc9cc1` |
| `dnd/spells/conjuration.py` | Heroes' Feast action decorator/ref and Guardian spell/object family | `230a357a3578f4604e56199a46d3bd7f4c08cdf0f33aa77eac3b338746e78556` |
| `dnd/classes/sorcerer_progression_definitions.py` | spell/condition declaration maps and `GRANTS_SPELL`/condition dependency refs | `6646f98440e2d8cfbc2831ad18279014a0b94c0200398e574e8cf033031f3462` |
| `dnd/content_system/condition_effect_population.py` | all selected action/condition/spell identity specs, declaration lookup, effect profiles, `APPLIES_CONDITION` refs | `c55647c5917efc7ec445e7a840946783fd1d674f29a0bcc23eb233dfeb57c3e7` |
| `dnd/content_system/action_definitions.py` | selected action declaration/behavior-identity rows and class map | `85179f96d8db3c667771d520e19254b821edbbfa57620b394a527732dfc4d1fe` |
| `dnd/content_system/condition_definitions.py` | selected condition declaration/behavior-identity rows and class map | `5ea05261eb9d15c7bcf6c4c5ac12c3d5c83f1efcee0ddfe00d3fe35700587518` |
| `dnd/spells/catalog_content.py` | eight SRD selected spell declaration rows/maps and Guardian row | `630d74c8f537a1c3fb09df45cd642be01d669b652e24c8fad7d6825cd19e5b03` |
| `dnd/content_system/behavior_bindings.py` | behavior-class/runtime binding admission | `7057855ae08466821d6bc494988774f199c59e46ef0b97bbc1b66d3b542cdf1d` |
| `dnd/core/content/registration.py` | declaration/behavior attachment mechanism | `b9cddc7df5863f2b8928cbacde0929f80803fcfde37fd9a88cdd55c2c75901ee` |
| `dnd/core/content/runtime.py` | installed runtime behavior admission/lookup | `71123f8aec4797d88b3fe197b5143c6d76b0a2bc33455990ca8654a9284d2216` |
| `dnd/content_system/builtin_inventory.py` | selected declarations in builtin runtime inventory | `f619e5d0fbed4274b2f18bc0c91bbb5c83a0afe52cad4e3155d3e66c9eee7644` |
| `dnd/content_system/spell_catalog_composition.py` | native composition rows require `ContentDeclaration` and expose `row.declaration.ref` | `c3e6f814c1c4eb9b2fa9effefab9a57e5384ef3a2a57dca56ab075155e66221c` |

The last row exposes a genuine shared-seam conflict. `SpellCatalogCompositionRow`
requires `declaration: ContentDeclaration`; native rows are built from
`SPELL_CONTENT_DECLARATIONS_BY_CLASS`, and character/origin/scenario holders
consume `row.declaration.ref`. Therefore the nine selected spell behaviors
and Guardian cannot lose their declarations family-locally while unrelated
spells remain wholly legacy unless the implementation adds a forbidden
optional legacy/direct field, per-family switch/resolver, or parallel catalog.
Migrating the shared spell-catalog/holder identity seam would instead broaden
the cut beyond the accepted plan.

Accepted-plan stop condition 2 is active for the selected spell families and
stop condition 11 is active for Guardian's spell side until a human-reviewed
plan amendment chooses the shared spell-catalog/holder cut or another
non-dual owner-preserving route. Slice 1 is **not authorized** by this ledger.

The action/spell dependency mapping is exact:

| Item family/root | Direct behavior(s) after CR-2I |
|---|---|
| Healing potion | `action.item.potion_healing.drink` |
| Greater Invisibility potion | `action.item.potion_greater_invisibility.drink`; `condition.spell.greater_invisibility` |
| Haste potion | `action.item.potion_haste.drink`; `condition.spell.haste` |
| Four weapon coats | `action.item.weapon_coat.apply`; the four exact `condition.consumable.weapon_coat.*` IDs |
| Portable torch | `action.item.torch.ignite`, `action.item.torch.extinguish` |
| Wall torch | `action.environment.wall_torch.ignite`, `action.environment.wall_torch.extinguish` |
| Directional door | `action.environment.directional_door.open`, `action.environment.directional_door.close` |
| Campfire | `action.environment.campfire.rest`, `action.environment.campfire.cook` |
| Arcane device | `action.environment.arcane_device.activate` |
| Trap lever | `action.environment.trap_lever.pull` |
| Storage chest | `action.environment.storage_chest.loot_all` |
| Heroes' Feast object | `action.environment.heroes_feast.eat` |
| Field Kit | `action.item.field_kit.deploy`; `condition.field_focus` |
| Acid Flask | `spell.acid_flask` |
| Scrolls/wands/cannons | `spell.burning_hands`, `spell.fire_bolt`, `spell.fireball`, `spell.hold_person`, `spell.invisibility`, `spell.mage_armor`, `spell.magic_missile`, `spell.spike_growth` according to the exact 33 declaration edges |

The 52 action/spell legacy-authority rows covering the 26 dependency refs have
canonical JSON hash
`f5c30916c63b90247c2c337e9d6e22e92fd94f53c9853c21bf91f427b67a36b7`.
The 14 condition legacy-authority rows covering the seven condition IDs have
hash `a1e9db18542b554ee1687ae4f198ef843c8a43944240658f6feac7e72e832472`.
Each appears twice in CR-0 as its exact declaration and behavior-identity
authority. Slice 1 removes both legacy admissions family-atomically while
retaining one direct behavior owner.

The remaining behavior-bearing item mechanics are concrete ECS hooks, not new
content identities:

| Item family | Frozen current owner/mechanic |
|---|---|
| Assassin's Dagger | `_UnseenStrikeDagger` plus `_unseen_strike_processor`; equip installs and unequip removes its exact damage-result handler |
| Arcane Staff | `_ArcaneStaff`; reversible `+1` spell-attack modifier |
| Spellblade Crown | `SpellbladeCrown`; reversible `+3` Charisma modifier |
| Padded/scale/half-plate/ring-mail/chain-mail/splint/plate | `StealthDisadvantageBodyArmor` and `heavy_armor_strength_penalty`; reversible stealth disadvantage and authored Strength movement penalty |
| Oil Barrel | `OilBarrel`; existing direct Oil/fire material transition on destruction |

Admission/source bytes that govern this slice are frozen at:

| Source | SHA-256 |
|---|---|
| `dnd/content_system/action_definitions.py` | `85179f96d8db3c667771d520e19254b821edbbfa57620b394a527732dfc4d1fe` |
| `dnd/content_system/condition_definitions.py` | `5ea05261eb9d15c7bcf6c4c5ac12c3d5c83f1efcee0ddfe00d3fe35700587518` |
| `dnd/content_system/condition_effect_population.py` | `c55647c5917efc7ec445e7a840946783fd1d674f29a0bcc23eb233dfeb57c3e7` |
| `dnd/content_system/behavior_bindings.py` | `7057855ae08466821d6bc494988774f199c59e46ef0b97bbc1b66d3b542cdf1d` |
| `dnd/core/content/runtime.py` | `71123f8aec4797d88b3fe197b5143c6d76b0a2bc33455990ca8654a9284d2216` |
| `dnd/core/content/registration.py` | `b9cddc7df5863f2b8928cbacde0929f80803fcfde37fd9a88cdd55c2c75901ee` |
| `dnd/spells/catalog_content.py` | `630d74c8f537a1c3fb09df45cd642be01d669b652e24c8fad7d6825cd19e5b03` |

### 5.2 Existing torch regression admitted to Slice 1

`tests/engine/test_spell_families.py::test_eb_15_043_sleet_storm_douses_exposed_flames`
is red at preflight. A carried torch correctly refuses to relight while inside
Sleet Storm, but `WallTorch.light()` bypasses the same active spatial rule and
becomes lit. This is not excluded or relabeled as stale: the final direct
torch proof must make both current torch forms obey the same objective spatial
condition through their existing item/spatial owners.

This authorizes only the smallest repair in the torch behavior family during
CR-2I. If that repair requires redesigning Sleet Storm, adding a second event
path, or migrating another unrelated CR-9 family, Slice 1 stops for amendment.

## 6. Caller, authority, and import closure

### 6.1 Generic construction calls

AST call-site inventory at preflight:

| Scope | Calls | Paths | Normalized call-site hash |
|---|---:|---:|---|
| Production `materialize_item*` calls | 54 | 10 | `529536383811c6ebeb94051f60bb97deeb95310e10d0d2eaa72ef838045d4ab1` |
| Test `materialize_item*` calls | 294 | 59 | `74e542746738bdb48b44710d299cfc09f1827b0d7e169c6a47279e7b69df82fa` |
| Test caller path set | 59 | 59 | `0efa31aa5b28c56378e9331a70cd85642c145e597e7e3dc6a97c73c2171d01fe` |

The ten production caller paths are exact:

```text
dnd/content_system/character_materialization.py
dnd/content_system/creature_possessions.py
dnd/content_system/item_materialization.py
dnd/maps/arena_layout.py
dnd/monsters/bestiary.py
dnd/monsters/circus_fighter.py
dnd/monsters/srd_roster.py
dnd/scenarios/battlefield_catalog.py
dnd/scenarios/encounter_assembler.py
dnd/spells/conjuration.py
```

The test call-site path partition is: 41 otherwise-collectible modules,
9 CR-0 semantic-rescue modules, 6 obsolete-shape modules, 2 deprecated
transport modules, and 1 module blocked by a later content cut. Every retained
feature is represented in the maintained node union in section 10; deprecated
server/transport shape is not revived.

### 6.2 Current import graph

AST import edges from production Python to the current item/recipe/runtime
closure total 167. Their canonical `path:line:import` hash is
`35c01492d3f1db43b211d6b0d7bc5ae3d941852c5e6be104bae02837da847525`.
There are zero function-local imports in this edge set at preflight.

The CR-I disposition is defined by owner, not by a global deletion:

| Disposition | Exact responsibility |
|---|---|
| `behavior_prerequisite_CR-2I` | the 33 IDs and concrete hooks in section 5, their action/condition/spell admission rows, and only their discovery/execution/source consumers |
| `migrate_CR-I` | `BaseItem`/item values/Events; all 147 owners/builders; item bindings/materialization; item holders/loadouts/possessions/containers/world callers; direct durable holdings; specific weapon proficiency; Guardian atomic family |
| `visual_evidence_CR-8` | section 4 artifacts, overlay rows, authored visual literals, asset files, and frozen accepted/current presentation values |
| `unrelated_legacy_domain` | generic registry/pack/recipe infrastructure and creature/character/scenario/spell/spatial declarations after their item rows/callbacks are removed; their own identities remain for later cuts |

The item-runtime text closure currently has 220 occurrences across 13 paths,
hash `deb13f703025a7c1c110c5e3c1ca23609718275ecdf5624d43d7058b839fc20d`.
Its exact path-set hash is
`e3a6708b95f3897f2995ff74c53fe20f4f54739969de73c9841193ebf30704e9`.
All item-runtime rows/callers are `migrate_CR-I`; the generic non-item content
system is `unrelated_legacy_domain` and is not deleted.

The broad recipe/declaration search has 413 occurrences across 44 production
paths (occurrence hash
`a0db612cfc24a6e3fc74f6695f39e477ff54de6c1c341d53f3b999143463c42a`,
path hash `1b14eb69851807ed01131ebf5d0a9445bb266a33cc6fb1c0402a375215efc8ce`).
This broad inventory is deliberately not a deletion allowlist. Only item rows,
item holder recipes, the 205 item presets, and the private Guardian object
belong to CR-I. Class, creature, encounter, spell, spatial, registry, and pack
code survives unless an exact item edge is being replaced.

## 7. Direct durable state, Events, analytics, and proficiency

The Pydantic field snapshot for `BaseItem`, `ItemPresentationState`,
`ItemLocationStateEvent`, `ItemChargeConsumptionEvent`, `EntityCreatedEvent`,
`CharacterItemV1`, `CharacterHoldingsRevision`, `ItemAugmentationRecord`,
`CreatureProficienciesConfig`, and `CreatureProficiencies` has canonical JSON
hash `7feffaed8c3a3725e0593e38202114b80059c74f5e81fc3fbaff3a84a1aedb8e`.

### 7.1 Durable holders

The current direct durable-schema closure has 60 occurrences across eight
paths, occurrence hash
`f4a31079fc290e041f487db4c0a58f9c8a7db01a9c8e2e423601ebc6be8c7e8e`,
path hash `bef6f857eb46291d9736a767da9df393e7e5908c53fd16bd1ac83304a3db1317`:

```text
dnd/classes/content_factories.py
dnd/content_system/background_starting_holdings.py
dnd/content_system/builtin_character_builds.py
dnd/content_system/character_materialization.py
dnd/core/content/character_deployment.py
dnd/core/content/durable_characters.py
dnd/core/content/encounters.py
dnd/scenarios/encounter_assembler.py
```

CR-I atomically replaces `CharacterItemV1` with `CharacterItemV2`, schema 2,
required direct `item_id`, exact quantity/charge/durability/slot state, and the
existing deterministic digests. It deletes recipe payloads,
`ItemAugmentationRecord`, and `durable_augmentations`; it does not add a V1/V2
union or compatibility parser.

### 7.2 Item facts and analytics

The item Event/state closure has 40 occurrences across nine paths, occurrence
hash `632ef657ab799352833e9ea1d1d99f860f11103515bd21eefd42189f09ab2d4a`,
path hash `eb5d9e4d125d345159e02ce816873b29e6737fbc08ae7f70aed75e324e41dab4`.
The exact owner/consumer paths are `dnd/blocks/base_item.py`,
`dnd/core/item_types.py`, `dnd/core/events.py`, `dnd/entity.py`,
`dnd/analytics/game_summary.py`, `dnd/core/base_actions.py`,
`dnd/blocks/equipment.py`, `dnd/items/environment_interactables.py`, and
`dnd/items/torches.py`.

The cut replaces item `content_ref`, item `semantic_key`, and
`item_semantic_key` with one required `item_id`. Generic action, condition,
handler, creature, class, spell, or scenario semantic fields are not renamed.
`GameSummary.item_charges_spent` consumes the new charge-event `item_id`.

### 7.3 Specific weapon proficiency

The exact specific-weapon closure has 22 occurrences across four paths,
occurrence hash `4973939e052af4df5f700df700dcf50da12147ffbe815b679988aad079836177`,
path hash `d1aea3c39e57b26c012cb1656db698f857c486e8c642f3e5712ed2cf08c854ea`:

```text
dnd/blocks/creature_proficiencies.py
dnd/content_system/character_materialization.py
dnd/core/events.py
dnd/entity.py
```

Config, component state, source-owned add/remove APIs, attack consumers, and
`EntityCreatedEvent.weapon_proficiencies` all migrate to direct item-ID strings
without lookup or encoded `ContentRef.identity_key`.

## 8. `environment.door` collision closure

The CR-0-only `environment.door` is a legacy whole-Tile object, not a 148th
public item. The only maintained target is the existing
`environment.directional_door`. The exact semantic mapping is:

| Legacy fact | Direct directional fact |
|---|---|
| `DoorParameters.is_open` | `DirectionalDoor.is_open` unchanged |
| closed `blocks_movement` | owner-Tile boundary `WorldEdgeChannel.MOVEMENT` |
| closed `blocks_vision`/optics | owner-Tile boundary `WorldEdgeChannel.OPTICAL` |
| closed structural propagation | owner-Tile boundary `WorldEdgeChannel.PROPAGATION` |
| `OpenDoorAction` | `OpenDirectionalDoorAction` |
| `CloseDoorAction` | `CloseDirectionalDoorAction` |
| open/close discovery and occupied-open-door close rejection | the existing `DirectionalDoor` mechanics, without a compatibility wrapper |

The old `vision` and `light` input names collapse to the one objective optical
edge channel exactly as the accepted Tile/world-item system requires. No
global scalar blocker or whole-Tile compatibility mode survives.

### 8.1 Already-authored direct production placements

Current production has no active placement of the legacy door. The two direct
placement owners are already authenticated:

| Owner | Placement | Side | Evidence |
|---|---:|---|---|
| `dnd/maps/arena_layout.py` standard barrier | `DOOR_POSITION` | `WEST` | the door occupies the gap in the west-facing barrier strip |
| `dnd/scenarios/battlefield_catalog.py` one/two-barrier builders | `(column, door_y)` | `WEST` | every door occupies the same west-facing barrier authored beside west-facing walls |

These direct owners are preserved and later lose only their legacy
materializer/recipe construction calls.

### 8.2 Maintained legacy test placements

Five maintained semantic placements authenticate their side from actor/path or
paired geometry. One range-only fixture has no geometric semantic source:

| Test owner | Position/context | Authenticated side | CR-I disposition |
|---|---|---|---|
| `tests/engine/test_items_inventory_equipment.py::test_eb_13_009_environment_use_actions_are_stateful_and_spatial` | door `(1, 0)`, actor `(0, 0)` | `WEST` | migrate and preserve use/open/close state proof |
| `tests/manual/test_134_stackable_usable_item_legacy_contract.py::test_override_and_default_door_actions_toggle_spatial_state` | door `(4, 3)`, actor `(3, 3)` | `WEST` | migrate first door |
| same test | door `(3, 4)`, actor `(3, 3)` | `NORTH` | migrate second door |
| `tests/manual/test_legacy_reactive_reaction_coverage.py::test_closed_door_invalidates_prepared_intercept_path_at_trigger_time` | door `(4, 2)` on the horizontal intercept path | `WEST` | migrate and preserve path invalidation |
| `tests/manual/test_legacy_reactive_reaction_coverage.py::test_open_door_is_authoritative_when_dodge_roll_triggers` | door `(5, 2)` between defender `(4, 2)` and escape `(6, 2)` | `WEST` | migrate and preserve traversal recheck |
| `tests/manual/test_134_stackable_usable_item_legacy_contract.py::test_nonusable_and_out_of_range_objects_do_not_surface_use_rows` | far door `(8, 8)`, actor `(1, 1)` | **not authenticated by the test** | human-authored side required before production edits |

The smallest consistent authored decision for the last fixture is `WEST`, the
canonical standard-door orientation used by all production barriers. That is
a recommendation, not an inferred fact; Slice 0 does not silently write it.

The six exact manual door/Guardian anchors added to the maintained union were
run together: **3 failed, 3 passed in 127.47s**. The Guardian lifecycle,
Guardian action-semantics, and far-range exclusion nodes pass. These three
door nodes fail and are retained as real migration/repair obligations:

- `test_override_and_default_door_actions_toggle_spatial_state`: adjacent
  legacy doors produce no discovered object-use rows;
- `test_closed_door_invalidates_prepared_intercept_path_at_trigger_time`:
  closing the door does not mark the interceptor's cached path dirty; and
- `test_open_door_is_authoritative_when_dodge_roll_triggers`: opening the door
  does not allow the expected reactive retreat through it.

The final directional-door proof must re-express these semantics through the
existing boundary structure/event/cache path; none may be deleted as a stale
whole-Tile fixture. If repair needs a second cache/event path or compatibility
door, stop rather than expand the architecture.

MapEditor/server-era `environment.door` references in
`tests/engine/test_encounter_apis.py`,
`tests/manual/test_147_mapeditor_legacy_contract.py`,
`tests/manual/test_180_environment_content_identity.py`,
`tests/manual/test_182_mapeditor_content_recipe_hard_cut.py`, and
`tests/manual/test_19_map_editor_scenario_authoring.py` are respectively
semantic-rescue, later-cut, or deprecated transport/map-authoring evidence.
They do not authorize server/SDK/editor work in CR-I. Their authored map-data
orientation is deferred to the later map-authoring cut; the legacy runtime
door cannot remain merely for those excluded shapes.

### 8.3 Door stop decision

Plan stop condition 10 is active until the coordinator authenticates the far
range-only fixture's side. Production remains forbidden. Once `WEST` (or a
different explicit side) is authorized, every maintained placement is exact
and no additional door abstraction is required.

## 9. Guardian of Faith atomic family

The Guardian is one private direct item species plus its existing spell and
spatial zone. It is not part of the 147-ID public builder map.

| Responsibility | Current owner/evidence | CR-I result |
|---|---|---|
| spell mechanics | `dnd/spells/conjuration.py::GuardianOfFaith` | mechanics class retained; it owns primitive direct ID `spell.guardian_of_faith` after the attached declaration/runtime admission is removed |
| spell cold presentation/rules metadata | Guardian rows in `dnd/spells/catalog_content.py` | exact metadata retained as cold data keyed by the same direct ID; it is not execution admission |
| legacy spell identity/admission | Guardian `SpellContentIdentitySpec`, `SPELL_CONTENT_DECLARATIONS` row/maps, builtin declaration inventory, behavior binding/runtime registration | removed/migrated family-atomically; no Guardian spell `ContentDeclaration` or runtime lookup survives |
| private item species | `GuardianOfFaithObject`, `environment.spell_object.guardian_of_faith` | mechanics class retained and constructed directly as an ordinary `BaseItem` with required private `item_id` |
| legacy item declaration/factory | `GUARDIAN_OF_FAITH_OBJECT_DECLARATION/REF/RECIPE`, `_build_guardian_of_faith_object`, `SRD_SPELL_ENVIRONMENT_OBJECT_DECLARATIONS`, item runtime origin/binding/materializer | deleted atomically when the spell directly constructs the object |
| spatial behavior | `GuardianOfFaithZone`, `GUARDIAN_OF_FAITH_ZONE_CONTENT_REF`, `spatial_effect.spell.guardian_of_faith` | zone mechanics and the existing required spatial-domain identity/Event fact retained unchanged for later CR-9 |
| condition-effect admission | `INDIRECT_CONDITION_EFFECT_SPELL_TYPES` Guardian spell row plus `INTERNAL_ONLY_CONDITION_EFFECT_SOURCE_TYPES` Guardian object-factory row | factory-derived row deleted; spell/source row migrates off `get_content_declaration` to the same direct spell ID without changing effect semantics |
| AI action meaning | `dnd/ai/runtime/action_semantics.py` Guardian spell semantics | retained; it describes the spell, not item construction |

The complete legacy spell consumer closure also includes
`dnd/content_system/builtin_inventory.py`,
`dnd/content_system/spell_catalog_composition.py`,
`dnd/content_system/character_materialization.py`,
`dnd/content_system/builtin_character_builds.py`,
`dnd/content_system/character_origin_definitions.py`,
`dnd/content_system/origin_innate_spellcasting.py`, and
`dnd/scenarios/encounter_assembler.py`. These owners may preserve Guardian's
authored name, level, school, class, and target metadata, but their Guardian
rows must use the concrete class plus direct primitive ID and must not read a
Guardian declaration/ref/runtime binding. This is an exact family consumer
migration, not permission to redesign the global spell catalog or add a
parallel direct catalog.

The complete family further includes the Guardian object dependency in
`_SPELL_OBJECT_DEPENDENCIES_BY_CLASS`, condition-effect ownership, manual
cleric lifecycle proofs, spell identity proofs, environment-object identity
evidence, and action-semantics proof. Its frozen current owner hashes are:

| File | SHA-256 |
|---|---|
| `dnd/spells/conjuration.py` | `230a357a3578f4604e56199a46d3bd7f4c08cdf0f33aa77eac3b338746e78556` |
| `dnd/spells/catalog_content.py` | `630d74c8f537a1c3fb09df45cd642be01d669b652e24c8fad7d6825cd19e5b03` |
| `dnd/content_system/condition_effect_population.py` | `c55647c5917efc7ec445e7a840946783fd1d674f29a0bcc23eb233dfeb57c3e7` |
| `dnd/ai/runtime/action_semantics.py` | `21d22222c79ab66ddecee2c03beb0ff3f17574ea2d13c074e4c22947c79ca5fc` |
| `dnd/content_system/builtin_inventory.py` | `f619e5d0fbed4274b2f18bc0c91bbb5c83a0afe52cad4e3155d3e66c9eee7644` |
| `dnd/content_system/spell_catalog_composition.py` | `c3e6f814c1c4eb9b2fa9effefab9a57e5384ef3a2a57dca56ab075155e66221c` |
| `dnd/content_system/character_materialization.py` | `2f7ca03f8705dcd28cf1547588233358b09203d5f3b59498fe5f3dffc2f99f3c` |
| `dnd/content_system/builtin_character_builds.py` | `6a06763e7c01cb808bca9f4235e17abbda8e9d9068c3784e16fc5d47a58f8f37` |
| `dnd/content_system/character_origin_definitions.py` | `042d4df7d107c48baf70b61b17c4d93d1fbe3a6d89d6b1662acaac758a978a40` |
| `dnd/content_system/origin_innate_spellcasting.py` | `e3225443635f28031cf415e316021741e1ad900a1e8ce9cc6886d2c184e63008` |
| `dnd/scenarios/encounter_assembler.py` | `19a4d6c16e9972b51aa39931b54046b8865b6195dc929447786ab064f9df4c2d` |

The accepted sentence “No Guardian `ContentRef` survives” is scoped by its
immediately preceding “Guardian item fact/Event”: it removes the private
Guardian object's item `ContentRef`. It does **not** migrate the independent
shared spatial-effect seam. `SpatialCondition.content_ref` and
`SpatialEffectChangeEvent.spatial_effect_content_ref` remain required for all
spatial conditions, including `GuardianOfFaithZone`; changing that one zone
would require a forbidden special/optional path, while changing the shared
seam would improperly pull broad CR-9 work.

Slice 2 must preserve faction filtering, save DC, radiant damage, duration,
zone entry behavior, object destruction/cleanup, Event parentage, and the
private/public boundary. It adds no Guardian registry, special construction
path, Event-owned mechanic, or lookup. If that direct substitution pulls an
unrelated spell family, the implementation stops before the BaseItem cut.

The private BaseItem object half has a complete direct route. The spell half
currently reaches the shared required-declaration catalog/holder seam recorded
in section 5.1.1. Consequently the accepted stop is active before Slice 1:
the Guardian family cannot be called complete or implemented until an amended
shared-seam order is accepted. The independent spatial zone identity remains
unchanged and is not the blocker.

## 10. Maintained proof union

Node hashes use sorted node IDs joined by `"\n"` with one final newline.

### 10.1 Current preflight lane

The exact current affected collection is the union of:

1. all nodes collected from these 26 modules, except the one cold server-start
   node named below; and
2. all 105 `maintained_in_process_nodes` frozen by the immutable CR-0 evidence
   manifest; and
3. six exact door/Guardian semantic anchors required by sections 8 and 9.

```text
tests/architecture/test_action_discovery_requirements.py
tests/architecture/test_content_recovery_cr0_evidence.py
tests/architecture/test_no_legacy_character_factory_dependencies.py
tests/architecture/test_spell_catalog_composition.py
tests/engine/test_action_cost_atomicity.py
tests/engine/test_action_discovery.py
tests/engine/test_combat_actions.py
tests/engine/test_condition_lifecycle.py
tests/engine/test_condition_transform_ownership.py
tests/engine/test_content_recovery_behavior_semantics.py
tests/engine/test_content_recovery_item_semantics.py
tests/engine/test_dice_event_semantics.py
tests/engine/test_equipment_domain_ownership.py
tests/engine/test_equipment_replication_facts.py
tests/engine/test_event_lifecycle.py
tests/engine/test_items_inventory_equipment.py
tests/engine/test_monster_presets.py
tests/engine/test_runtime_identity_registries.py
tests/engine/test_runtime_reset.py
tests/engine/test_spatial_conditions.py
tests/engine/test_spell_families.py
tests/engine/test_world_entity_initialization.py
tests/engine/test_world_geometry_contract.py
tests/progression/test_content_recovery_character_semantics.py
tests/progression/test_dwarf_acolyte_authored_content.py
tests/progression/test_schema2_character_materialization.py
```

The six additional anchors are:

```text
tests/manual/test_134_cleric_batch1_legacy_contract.py::test_guardian_placement_ward_and_damage_budget
tests/manual/test_134_stackable_usable_item_legacy_contract.py::test_nonusable_and_out_of_range_objects_do_not_surface_use_rows
tests/manual/test_134_stackable_usable_item_legacy_contract.py::test_override_and_default_door_actions_toggle_spatial_state
tests/manual/test_42_action_semantics.py::test_guardian_of_faith_declares_hostile_only_persistent_effect_scope
tests/manual/test_legacy_reactive_reaction_coverage.py::test_closed_door_invalidates_prepared_intercept_path_at_trigger_time
tests/manual/test_legacy_reactive_reaction_coverage.py::test_open_door_is_authoritative_when_dodge_roll_triggers
```

They are disjoint from the original 403-node union and have normalized hash
`c56e51d5fd581a70dddd8c6cf4d0b1e0e07ca28e7303fe3f909d50caa6fd3d31`.

| Set | Count | Normalized SHA-256 |
|---|---:|---|
| module path set | 26 | `b8f1f6fa9250e17edfdca754655420b0565fa5c392749b30dec35d566a241b79` |
| collected affected nodes after cold-server exclusion | 340 | `0fc9db9ac1e40ad023f3b3758c8cc01d3144bf7963b3753e54cbf25e72c24405` |
| immutable CR-0 maintained nodes | 105 | `f689e92102b7a6e25c832cdc030d88618ab2048cd174e87869d76ed59cdcab33` |
| original deduplicated preflight union | 403 | `c8547f2308ee6f2da74c9946b56c90859358a2da26e109d3dd8bafc2fc4c5af5` |
| exact door/Guardian anchors | 6 | `c56e51d5fd581a70dddd8c6cf4d0b1e0e07ca28e7303fe3f909d50caa6fd3d31` |
| complete current preflight union | 409 | `c4253a3f09c295f1f33e087ac3f36aecd4d455053ba70c7b1adbb6d8c525680a` |

The original 403-node subgroup executed as **1 failed, 402 passed in
223.73s**. Its failure is
`tests/engine/test_spell_families.py::test_eb_15_043_sleet_storm_douses_exposed_flames`:
Sleet Storm correctly douses a carried Torch and a Wall Torch, and correctly
prevents the carried Torch from relighting, but `WallTorch.light()` bypasses
the same exposed-flame suppression and relights inside the active storm.

This is a real maintained behavior regression in the CR-2I torch family, not
a fixture deletion candidate. Slice 1 repairs the existing Wall Torch light
entry so portable and mounted flame items consult the same already-existing
suppression fact. If that repair requires a new event path, spell redesign, or
generic flame framework, stop rather than expand scope.

Exact complete-union execution: **4 failed, 405 passed in 322.10s**. The four
failures are the Sleet Storm/Wall Torch node above plus the three door nodes
in section 8.2. No other node in the complete 409-node lane failed.

The excluded node is
`tests/architecture/test_spell_catalog_composition.py::test_content_bootstrap_and_composed_spell_catalog_cold_start`.
It imports the deprecated server cold-start surface and currently fails on the
removed `dnd.core.senses` module. It is outside the accepted in-process CR-I
boundary and is not hidden inside a passing node count.

### 10.2 Governed CR-0 succession

These six live-source CR-0 gates are intentionally retired, not renamed in
place or retained as stale compatibility tests:

```text
tests/architecture/test_content_recovery_cr0_evidence.py::test_binding_reconciliation_covers_every_authored_row
tests/architecture/test_content_recovery_cr0_evidence.py::test_direct_item_inventory_is_mechanically_reconciled
tests/architecture/test_content_recovery_cr0_evidence.py::test_every_behavior_identity_has_one_exact_concrete_owner
tests/architecture/test_content_recovery_cr0_evidence.py::test_every_current_proof_node_is_collectible
tests/architecture/test_content_recovery_cr0_evidence.py::test_every_materializable_root_has_one_exact_factory_owner
tests/architecture/test_content_recovery_cr0_evidence.py::test_legacy_authority_and_importer_inventories_match_current_python
```

Their six-node normalized hash is
`87e80b8f2f66fa3f0bf5f909e6b9b988efd4d5d7b01075a58309d0a004e4f661`.
The exact successor mapping is the mapping in accepted-plan section 9.1. The
403-node retained current union has normalized hash
`d452549980b0a5ce28adc4c7e561740791276044afcdccc54ccc569ab49f56f8`.

The original CR-0 manifest bytes, source-artifact hashes, historical
manifest-shape/SRD/non-import gates, and every unaffected maintained semantic
proof remain active. Only assertions that claim the old item authority still
equals live post-cut source are succeeded.

### 10.3 Planned successor and feature nodes

The final candidate adds exactly these 25 nodes:

```text
tests/architecture/test_content_recovery_cri_direct_items.py::test_cr0_binding_artifacts_remain_hash_and_row_exact
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_direct_item_visual_values_match_frozen_cr0_rows
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_live_authority_and_importer_delta_is_exact
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_maintained_proof_union_is_collectible_and_hash_exact
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_non_item_visual_overlay_still_matches_current_owners
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_public_item_inventory_is_exact_and_direct
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_remaining_legacy_and_direct_item_construction_owners_are_exact
tests/architecture/test_content_recovery_cri_direct_items.py::test_cri_remaining_legacy_and_migrated_direct_behavior_owners_are_exact
tests/engine/test_direct_item_runtime.py::test_all_maintained_holders_materialize_exact_direct_item_plans
tests/engine/test_direct_item_runtime.py::test_all_public_item_ids_construct_directly_with_independent_state
tests/engine/test_direct_item_runtime.py::test_behavior_bearing_items_preserve_exact_equip_consume_and_use_mechanics
tests/engine/test_direct_item_runtime.py::test_entity_birth_installs_direct_loadout_silently_and_publishes_complete_state
tests/engine/test_direct_item_runtime.py::test_guardian_spell_constructs_private_direct_object_and_preserves_zone_lifecycle
tests/engine/test_direct_item_runtime.py::test_initial_loadout_validation_and_failure_cleanup_leave_no_residue
tests/engine/test_direct_item_runtime.py::test_item_required_behavior_sources_cleanup_symmetrically_and_publish_direct_ids
tests/engine/test_direct_item_runtime.py::test_item_required_behaviors_execute_without_content_runtime_admission
tests/engine/test_direct_item_runtime.py::test_item_state_location_and_charge_events_publish_direct_item_id
tests/engine/test_direct_item_runtime.py::test_legacy_door_collision_migrates_to_explicit_directional_boundary_behavior
tests/engine/test_direct_item_runtime.py::test_oil_barrel_destruction_preserves_direct_material_transition
tests/engine/test_direct_item_runtime.py::test_private_guardian_item_is_direct_but_not_publicly_buildable
tests/engine/test_direct_item_runtime.py::test_runtime_inventory_equipment_and_world_mutations_remain_eventful
tests/engine/test_direct_item_runtime.py::test_stacks_charges_durability_containers_intrinsics_and_world_blockers_are_exact
tests/progression/test_direct_item_durable_and_proficiency.py::test_character_item_v2_rejects_tampering_legacy_recipe_and_augmentations_without_partial_state
tests/progression/test_direct_item_durable_and_proficiency.py::test_character_item_v2_round_trip_authenticates_direct_state
tests/progression/test_direct_item_durable_and_proficiency.py::test_specific_weapon_proficiency_uses_direct_item_ids_in_attacks_sources_and_birth_facts
```

Their normalized hash is
`f5ea8b49e99135bd432bf3bb586324c444637afdc05ae99244f18c6d996993cd`.
The exact planned final union is therefore **403 retained + 25 new = 428
unique nodes**, normalized SHA-256
`9a01f1861ddec6d67b017f963b4ff652a8fe761ebf20774b812a367958913d8e`.

The final count happens to equal the earlier tempting `403 + 25 = 428`, but
the set does not: six missing maintained door/Guardian anchors were added and
the six stale live-source CR-0 assertions were removed. The hashes above bind
that exact substitution and prevent count-only acceptance.

## 11. Slice 0 gate result

| Gate | Result |
|---|---|
| 147 public IDs reconciled | PASS |
| current/accepted builder and value closure | PASS |
| active production and maintained test callers classified | PASS |
| 182 item-relevant visual overlay rows and CR-8 artifacts frozen | PASS |
| item-required behavior/admission closure frozen | PASS |
| selected spell behaviors have a non-dual family-local migration route | **BLOCKED: shared `SpellCatalogCompositionRow.declaration`/holder seam requires amendment** |
| direct durable/Event/analytics/proficiency closure frozen | PASS |
| complete Guardian evidence family frozen | PASS |
| Guardian spell side has a non-dual family-local migration route | **BLOCKED by the same shared spell-catalog/holder seam** |
| maintained current/final node unions frozen | PASS |
| current import edges and no-late-import fact frozen | PASS |
| all door placements have authenticated sides | **BLOCKED: one range-only fixture requires authored side** |
| current maintained lane green | **NO: Sleet Storm/Wall Torch plus three door regressions; 4 failed, 405 passed** |

No production or test file was edited in Slice 0. The Sleet Storm and door
behavior failures are bounded repair obligations inside their existing
families and do not independently require new architecture. The unauthenticated
door side requires an authored human decision. More fundamentally, the shared
spell catalog/holder seam activates accepted-plan stop conditions 2 and 11;
production remains forbidden until a reviewed amendment resolves that order
without compatibility or parallel identity paths.

## 12. Slice 0 review record

The exact blocked Slice 0 candidate at SHA-256
`1d4f7d0ca2d7d728fc486d278b1a9112372b86d6ed48705b3b05723e987f90a7`
received all three required approvals:

| Review | Result | Scope of approval |
|---|---|---|
| correctness/evidence | APPROVE | the 409 current, 403 retained, and 428 planned-final node sets; all four maintained failures; the 33 selected behavior owners; the complete Guardian split; and active stop conditions 2, 10, and 11 are accurate |
| anti-slop | APPROVE | the ledger records the existing shared spell seam without authorizing an optional field, family switch, resolver, parallel catalog, compatibility path, or other new layer |
| anti-OOP/ECS/import boundary | APPROVE | concrete mechanics classes remain direct owners; the item, spell, and spatial Guardian identities remain distinct; the import DAG is preserved; and no manager, service, registry, or special BaseItem/spatial path is proposed |

These approvals accept this evidence freeze and its blocked classification
only. They do not authorize Slice 1 or any production/test edit. Production
remains forbidden until a separately reviewed plan amendment resolves the
shared spell-catalog/holder seam without dual authority and the human authors
the missing door side.

## 13. Accepted amendments and unblocked sequence

The two Slice 0 stops were resolved before production work:

- `DND_CONTENT_RECOVERY_DIRECT_ITEM_CR2I_SCOPE_AMENDMENT_2026-08-31.md`
  authenticated the range-only door placement and kept the collision cut on
  the one directional-door item family; and
- `DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_SEQUENCE_AMENDMENT_2026-08-31.md`
  removed the shared spell/character-holder obstruction by completing the
  prerequisite primitive behavior-fact cut without adding a parallel spell
  catalog, optional declaration field, resolver, or compatibility route.

The prerequisite completion is recorded in
`DND_CONTENT_RECOVERY_PRIMITIVE_BEHAVIOR_FACT_IMPLEMENTATION_LEDGER_2026-08-31.md`.
Those accepted amendments supersede the blocked status in sections 11 and 12;
the historical preflight evidence and its review record remain unchanged.

## 14. Implemented Slices 1-5

The direct-item hard cut is complete:

1. All item-required behavior families use their direct behavior/source IDs;
   no migrated item behavior remains admitted through an item declaration.
2. `BaseItem.item_id` is the required authored species fact. Item location,
   charge, birth, durable, analytics, and proficiency facts use that same ID.
3. The public direct catalog contains exactly 147 IDs: 108 behavior-free and
   39 behavior-bearing/direct-special. The private Guardian of Faith object is
   direct concrete spell construction and is not publicly buildable.
4. Inventory and Equipment retain validation and mutation ownership. Entity
   performs silent unpublished initial composition and publishes the complete
   birth state once; runtime loot/equip/unequip/drop remains eventful.
5. Starting holdings, class/apparel plans, four premades, creature
   possessions, containers, scenarios, spell-created items, durable records,
   and specific weapon proficiency now carry direct item IDs.
6. `environment.door` was cut to the explicit directional-door family with
   authenticated boundary placement. Oil Barrel keeps its direct material
   transition and Guardian keeps its object/zone lifecycle.
7. The item declaration/recipe/preset/binding/materializer closure was deleted.
   Creature and other non-item content authority remains intact.
8. CR-8 evidence was preserved: all eight historical artifact pairs, the
   complete 788-row overlay, its exact 182 item-relevant rows, and every active
   direct item visual value remain checked.
9. Provisional aggregate discard now removes runtime objects and values sourced
   by the entity or any of its owned blocks. This closes the ordered-loadout
   failure case where an earlier equipment hook succeeds before a later hook
   raises, without adding rollback events, callbacks, or a transaction layer.

No item manager, service, runtime, resolver, loader, generic materializer,
compatibility facade, dual identity, callback transaction, OOP definition
hierarchy, late import, reflection dispatch, server/SDK/renderer work, or CR-4+
domain migration was added.

## 15. Exact proof union and certification

The final governed union is exactly:

| Set | Nodes | Normalized SHA-256 | Result |
|---|---:|---|---|
| Retained maintained lane | 908 | `e05020c0f1222c7f2aad71895debe09dbf3326539d4493b82c7c488495418a44` | collected |
| New successor/feature proofs | 25 | `f5ea8b49e99135bd432bf3bb586324c444637afdc05ae99244f18c6d996993cd` | collected |
| Final union | 933 | `969416b9c090911d88eba558d532c92c6eae9614992ba758ea64aac27cbac5d8` | **933 passed in 344.26s** |

Additional certification:

| Gate | Result |
|---|---|
| CR-I successor architecture module | 8 passed in 83.42s |
| complete active maintained collection | 2,405 nodes collected; zero active collection errors |
| failed-loadout/direct cleanup and affected ownership/materialization lanes | 91 passed in 13.97s; focused direct-item/materialization lane 22 passed in 6.65s |
| final formatting-affected Field Kit/Heroes' Feast/architecture group | 38 passed in 87.94s |
| full in-process architecture gates | 67 passed; the same three governed deprecated-server diagnostics remain |
| compileall | PASS |
| fresh imports of BaseItem, direct catalog/builders/loadouts, Entity, and Guardian spell owner | PASS |
| `git diff --check` | PASS; checkout line-ending notices only |
| changed-production function-local import and `TYPE_CHECKING` scan | zero findings |
| engine/item server, AI, SDK, renderer import scan | zero findings |
| exact authority/importer, factory-owner, behavior-owner, public inventory, visual overlay, and CR-0 succession gates | PASS |

The complete architecture directory also reports three already-governed
deprecated-server failures: two `server.world_contracts`/event-server checks
and the server spell-catalog cold start still import the removed
`dnd.core.senses`. They are outside this in-process item cut, were present at
preflight, and were neither hidden nor repaired here. The candidate adds no
server, SDK, renderer, or transport change.

## 16. Frozen candidate manifest

The exact active dirty checkout against checkpoint
`205fd679fde51d5319d332f12ec241d7aecd93a6` is frozen in
`DND_CONTENT_RECOVERY_DIRECT_ITEM_CR1_CR3_IMPLEMENTATION_MANIFEST_2026-08-31.json`.
The manifest intentionally excludes itself and this mutable review ledger.

| Category | Members |
|---|---:|
| production | 92 |
| tests | 84 |
| documents/evidence | 8 |
| total | 184 |

Normalized entry SHA-256:
`11f7c1ba60f90726e3ec76e94268712486e83fcac5f8b3f1041d01b3fcef4f92`.

Manifest file SHA-256:
`f54e15aaa359d33a632027c2bf3d8e1b99c6212530bba3d8a0364f213da9328a`.

No production or test byte may change after this freeze without rerunning the
affected validation, regenerating the manifest, and repeating all three final
reviews.

## 17. Final review checkpoint

The first exact-candidate review found one real cleanup omission: an item-owned
modifier installed by an earlier successful equipment hook survived when a
later initial equipment hook failed. The candidate was unfrozen, the existing
unpublished aggregate-discard boundary was corrected by one ownership edge,
and the regression, affected lanes, exact 933-node union, architecture gates,
compile/import/dependency gates, and manifest were rerun. The earlier approvals
and rejections are superseded by this repaired candidate.

Status: `READY_FOR_INDEPENDENT_REVIEW`.

The frozen candidate now requires the plan-mandated independent reviews:

1. correctness/completeness;
2. anti-slop; and
3. anti-OOP/ECS/import-DAG.

Review results are appended only after all reviewers have inspected the same
manifest and ledger bytes.

## 18. Final independent review record

All three required reviewers approved the repaired exact candidate frozen by
manifest SHA-256
`f54e15aaa359d33a632027c2bf3d8e1b99c6212530bba3d8a0364f213da9328a`:

| Review | Result | Independent challenge |
|---|---|---|
| correctness/completeness | APPROVE | reproduced ordered Arcane Staff/failing-hook cleanup and proved the failed aggregate disappeared while an unrelated entity modifier remained |
| anti-slop | APPROVE | confirmed the repair is one local ownership-set widening at the existing discard seam, with no rollback/event/callback/transaction/manager layer |
| anti-OOP/ECS/import-DAG | APPROVE | reproduced cleanup and sibling isolation; confirmed ECS ownership direction, zero import cycles, zero local/late imports, and no core-to-content inversion |

Each reviewer independently verified all 184 unique manifest members with zero
hash mismatches and reproduced the schema-v1 normalized-entry SHA-256
`11f7c1ba60f90726e3ec76e94268712486e83fcac5f8b3f1041d01b3fcef4f92`.
No reviewer edited the checkout.

Status: `ACCEPTED — DIRECT ITEM CR-1/CR-3 HARD CUT COMPLETE`.
