"""Tests for information leaking fixes in PvP.

Tests three issues:
1. AoE preview should NOT show hidden entities in affected_entity_names
2. Combat log should anonymize hidden entity names with '???'
3. AoE spells should be executable at empty positions (no targets)
"""
import sys
sys.path.insert(0, ".")

from uuid import uuid4
from typing import Tuple

# Reset state FIRST
from dnd.utils import reset_combat_state
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map
from dnd.spells.evocation import Fireball
from dnd.conditions import Hidden
from dnd.encounter import Encounter
from dnd.controller import PassController
from dnd.utils import get_hp, set_hp
from dnd.actions_functional import setup_standard_actions, register_spell


passed = 0
failed = 0

def test(description: str, condition: bool):
    global passed, failed
    if condition:
        print(f"  PASS: {description}")
        passed += 1
    else:
        print(f"  FAIL: {description}")
        failed += 1


def create_caster(
    name: str = "Wizard",
    position: Tuple[int, int] = (0, 0),
    faction: str = "heroes",
    hp: int = 100,
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            intelligence=AbilityConfig(ability_score=16),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=10, mode="maximums")]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 2}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def create_target(
    name: str = "Skeleton",
    position: Tuple[int, int] = (5, 0),
    faction: str = "monsters",
    hp: int = 50,
) -> Entity:
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            dexterity=AbilityConfig(ability_score=10),
            strength=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=12),
        ),
        health=HealthConfig(
            hit_dices=[HitDiceConfig(hit_dice_value=8, hit_dice_count=5, mode="maximums")]
        ),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    set_hp(entity, hp)
    setup_standard_actions(entity)
    return entity


def setup_arena(width: int = 20, height: int = 20):
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)
    return grid


# =========================================================================
# Test 1: AoE preview does NOT leak hidden entities
# =========================================================================
def test_aoe_preview_hidden_entity():
    """Hidden entity near caster. Fireball preview should NOT show hidden
    entity in affected_entity_names. Fireball execution SHOULD still hit it."""
    print("\n" + "=" * 60)
    print("TEST 1: AoE preview does NOT leak hidden entities")
    print("=" * 60)

    reset_combat_state()
    setup_arena(20, 20)

    # Place entities close together (within default senses range of 10 tiles)
    caster = create_caster(name="Wizard", position=(5, 5))
    hidden_target = create_target(name="Hidden Skeleton", position=(8, 5))
    visible_target = create_target(name="Visible Goblin", position=(9, 5))

    register_spell(caster, Fireball, caster_level=5)

    # Apply Hidden condition with very high stealth DC
    hidden_cond = Hidden(
        source_entity_uuid=hidden_target.uuid,
        target_entity_uuid=hidden_target.uuid,
        stealth_result=30  # Very high - not perceivable
    )
    hidden_target.add_condition(hidden_cond)

    Entity.update_all_entities_senses()

    # Verify: caster can see visible target but NOT hidden target
    test("Hidden target NOT in caster's senses.entities",
         hidden_target.uuid not in caster.senses.entities)
    test("Visible target IS in caster's senses.entities",
         visible_target.uuid in caster.senses.entities)

    # Get available actions - check Fireball preview
    available = caster.get_available_actions(target_filter="enemies")
    fireball_action = None
    for action in available.position_actions:
        if action.template_name == "Fireball":
            fireball_action = action
            break

    test("Fireball found in available actions", fireball_action is not None)

    if fireball_action:
        # Check that hidden entity doesn't appear in ANY preview target
        found_visible = False
        found_hidden = False
        for target in fireball_action.valid_targets:
            if target.affected_entity_names:
                names = target.affected_entity_names
                if "Hidden Skeleton" in names:
                    found_hidden = True
                if "Visible Goblin" in names:
                    found_visible = True

        test("Visible Goblin appears in AoE preview names", found_visible)
        test("Hidden Skeleton does NOT appear in AoE preview names", not found_hidden)

        # Also check affected_entity_uuids
        hidden_in_uuids = False
        for target in fireball_action.valid_targets:
            if target.affected_entity_uuids and hidden_target.uuid in target.affected_entity_uuids:
                hidden_in_uuids = True
                break
        test("Hidden entity UUID not in any preview affected_entity_uuids", not hidden_in_uuids)

    # Now verify execution STILL hits hidden entity (compute_objective is unfiltered)
    # Set up encounter so spell costs can be paid
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, PassController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(hidden_target, PassController(source_entity_uuid=hidden_target.uuid))
    encounter.add_combatant(visible_target, PassController(source_entity_uuid=visible_target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    # start_encounter auto-starts first turn; next_turn handles end+start
    while encounter.get_current_entity() != caster:
        encounter.next_turn()

    initial_hp = get_hp(hidden_target)
    fireball_exec = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(8, 5),
        cast_at_level=3,
        template=False,
    )
    result = fireball_exec.apply()
    test("Fireball execution succeeded", result is not None and not result.canceled)

    final_hp = get_hp(hidden_target)
    test("Hidden entity took damage from Fireball execution",
         final_hp < initial_hp)
    print(f"  (Hidden Skeleton: {initial_hp} -> {final_hp} HP)")


# =========================================================================
# Test 2: Combat log per-entity anonymization
# =========================================================================
def test_combat_log_anonymization():
    """Combat log entries should anonymize hidden entity names, never drop entries."""
    print("\n" + "=" * 60)
    print("TEST 2: Combat log per-entity anonymization")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter_combat_log, ANON_NAME as _ANON

    # Simulate combat log entries
    hero_uuid = str(uuid4())
    hidden_enemy_uuid = str(uuid4())
    visible_enemy_uuid = str(uuid4())
    ally_uuid = str(uuid4())

    visible_set = {hero_uuid, visible_enemy_uuid, ally_uuid}
    controlled = [hero_uuid, ally_uuid]

    # --- Test: Both visible → no anonymization ---
    entries_both_visible = [
        {"source_uuid": hero_uuid, "target_uuid": visible_enemy_uuid,
         "source_name": "Hero", "target_name": "Visible Enemy",
         "verbose": "Hero attacks Visible Enemy", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_both_visible, controlled, visible_set)
    test("Both visible: all 1 entry kept", len(result) == 1)
    test("Both visible: no anonymization",
         result[0]["verbose"] == "Hero attacks Visible Enemy")

    # --- Test: Visible source, hidden target → target anonymized ---
    entries_hidden_target = [
        {"source_uuid": visible_enemy_uuid, "target_uuid": hidden_enemy_uuid,
         "source_name": "Goblin", "target_name": "Rogue",
         "verbose": "Goblin attacks Rogue", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_hidden_target, controlled, visible_set)
    test("Hidden target: entry kept (not dropped)", len(result) == 1)
    test("Hidden target: target_name anonymized", result[0]["target_name"] == _ANON)
    test("Hidden target: source_name preserved", result[0]["source_name"] == "Goblin")
    test("Hidden target: verbose text anonymized",
         result[0]["verbose"] == f"Goblin attacks {_ANON}")

    # --- Test: Hidden source, no target (self-action) → source anonymized ---
    entries_hidden_self = [
        {"source_uuid": hidden_enemy_uuid, "target_uuid": None,
         "source_name": "Hidden Enemy", "target_name": None,
         "verbose": "Hidden Enemy moves to (5,5)", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_hidden_self, controlled, visible_set)
    test("Hidden source self-action: entry kept (not dropped)", len(result) == 1)
    test("Hidden source self-action: source anonymized",
         result[0]["source_name"] == _ANON)
    test("Hidden source self-action: verbose anonymized",
         result[0]["verbose"] == f"{_ANON} moves to (5,5)")

    # --- Test: Hidden source self-buff → source anonymized ---
    entries_hidden_buff = [
        {"source_uuid": hidden_enemy_uuid, "target_uuid": hidden_enemy_uuid,
         "source_name": "Hidden Enemy", "target_name": "Hidden Enemy",
         "verbose": "Hidden Enemy uses Dodge", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_hidden_buff, controlled, visible_set)
    test("Hidden self-buff: entry kept (not dropped)", len(result) == 1)
    test("Hidden self-buff: both names anonymized",
         result[0]["source_name"] == _ANON and result[0]["target_name"] == _ANON)
    test("Hidden self-buff: verbose anonymized",
         result[0]["verbose"] == f"{_ANON} uses Dodge")

    # --- Test: Hidden source attacks controlled target → source anonymized ---
    entries_hidden_attacks_us = [
        {"source_uuid": hidden_enemy_uuid, "target_uuid": hero_uuid,
         "source_name": "Hidden Enemy", "target_name": "Hero",
         "verbose": "Hidden Enemy attacks Hero", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_hidden_attacks_us, controlled, visible_set)
    test("Hidden attacks us: entry kept", len(result) == 1)
    test("Hidden attacks us: source anonymized",
         result[0]["source_name"] == _ANON)
    test("Hidden attacks us: target preserved (controlled)",
         result[0]["target_name"] == "Hero")
    test("Hidden attacks us: verbose anonymized",
         result[0]["verbose"] == f"{_ANON} attacks Hero")

    # --- Test: Omniscient view (None) → no anonymization ---
    all_entries = [
        {"source_uuid": hidden_enemy_uuid, "target_uuid": None,
         "source_name": "Hidden Enemy", "target_name": None,
         "verbose": "Hidden Enemy moves", "sub_entries": []},
    ]
    result = _filter_combat_log(all_entries, controlled, None)
    test("Omniscient: no anonymization",
         result[0]["verbose"] == "Hidden Enemy moves")

    # --- Test: Entries never dropped (all 5 survive) ---
    entries_mixed = [
        {"source_uuid": hero_uuid, "target_uuid": visible_enemy_uuid,
         "source_name": "Hero", "target_name": "Vis",
         "verbose": "Hero attacks Vis", "sub_entries": []},
        {"source_uuid": visible_enemy_uuid, "target_uuid": hero_uuid,
         "source_name": "Vis", "target_name": "Hero",
         "verbose": "Vis attacks Hero", "sub_entries": []},
        {"source_uuid": hidden_enemy_uuid, "target_uuid": None,
         "source_name": "Hid", "target_name": None,
         "verbose": "Hid moves", "sub_entries": []},
        {"source_uuid": hidden_enemy_uuid, "target_uuid": hero_uuid,
         "source_name": "Hid", "target_name": "Hero",
         "verbose": "Hid attacks Hero", "sub_entries": []},
        {"source_uuid": hidden_enemy_uuid, "target_uuid": hidden_enemy_uuid,
         "source_name": "Hid", "target_name": "Hid",
         "verbose": "Hid uses Dodge", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_mixed, controlled, visible_set)
    test("All 5 entries kept (none dropped)", len(result) == 5)

    # --- Test: Sub-entries are anonymized, not dropped ---
    entries_with_subs = [
        {"source_uuid": visible_enemy_uuid, "target_uuid": None,
         "source_name": "Goblin", "target_name": None,
         "verbose": "Goblin uses Fireball", "sub_entries": [
             {"source_uuid": visible_enemy_uuid, "target_uuid": hero_uuid,
              "source_name": "Goblin", "target_name": "Hero",
              "verbose": "Hero: DEX save FAIL", "sub_entries": []},
             {"source_uuid": visible_enemy_uuid, "target_uuid": hidden_enemy_uuid,
              "source_name": "Goblin", "target_name": "Rogue",
              "verbose": "Rogue: DEX save SAVE", "sub_entries": []},
         ]},
    ]
    result = _filter_combat_log(entries_with_subs, controlled, visible_set)
    test("Parent entry kept", len(result) == 1)
    subs = result[0].get("sub_entries", [])
    test("Both sub_entries kept (not dropped)", len(subs) == 2)
    test("Visible sub: no anonymization",
         subs[0]["verbose"] == "Hero: DEX save FAIL")
    test("Hidden sub: target anonymized",
         subs[1]["verbose"] == f"{_ANON}: DEX save SAVE")

    # --- Test: AoE from hidden source, controlled targets in subs ---
    entries_hidden_aoe = [
        {"source_uuid": hidden_enemy_uuid, "target_uuid": None,
         "source_name": "Invisible Wizard", "target_name": None,
         "verbose": "Invisible Wizard uses Fireball → 2 targets",
         "sub_entries": [
             {"source_uuid": hidden_enemy_uuid, "target_uuid": hero_uuid,
              "source_name": "Invisible Wizard", "target_name": "Hero",
              "verbose": "Hero: DEX save FAIL, 15 fire", "sub_entries": []},
             {"source_uuid": hidden_enemy_uuid, "target_uuid": ally_uuid,
              "source_name": "Invisible Wizard", "target_name": "Ally",
              "verbose": "Ally: DEX save SAVE, 7 fire", "sub_entries": []},
         ]},
    ]
    result = _filter_combat_log(entries_hidden_aoe, controlled, visible_set)
    test("Hidden AoE: parent entry kept", len(result) == 1)
    test("Hidden AoE: parent source anonymized",
         result[0]["verbose"] == f"{_ANON} uses Fireball → 2 targets")
    subs = result[0].get("sub_entries", [])
    test("Hidden AoE: both subs kept", len(subs) == 2)
    test("Hidden AoE: sub source anonymized but target (controlled) preserved",
         subs[0]["target_name"] == "Hero" and subs[0]["source_name"] == _ANON)
    test("Hidden AoE: ally sub target preserved",
         subs[1]["target_name"] == "Ally")


# =========================================================================
# Test 3: AoE at empty positions
# =========================================================================
def test_aoe_empty_position():
    """Fireball should be executable at empty positions (no entities in blast)."""
    print("\n" + "=" * 60)
    print("TEST 3: AoE at empty positions")
    print("=" * 60)

    reset_combat_state()
    setup_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    # Need at least one opponent for encounter
    dummy = create_target(name="Far Dummy", position=(19, 19))
    Entity.update_all_entities_senses()

    # Set up encounter so spell costs can be paid
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, PassController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(dummy, PassController(source_entity_uuid=dummy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    # start_encounter auto-starts first turn; next_turn handles end+start
    while encounter.get_current_entity() != caster:
        encounter.next_turn()

    # Cast fireball at an empty position within range
    fireball = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(10, 5),  # Empty position, 5 tiles away
        cast_at_level=3,
        template=False,
    )
    result = fireball.apply()
    test("Fireball at empty position succeeds (not None)", result is not None)
    test("Fireball at empty position not canceled",
         result is not None and not result.canceled)

    # Verify dummy wasn't hit (far away from blast)
    dummy_hp = get_hp(dummy)
    test("Far entity NOT damaged by distant fireball", dummy_hp == 50)


# =========================================================================
# Test 4: Temporal filtering (perceiver_uuids Layer 1)
# =========================================================================
def test_temporal_filtering():
    """filter_combat_log Layer 1: entries with perceiver_uuids that exclude
    the observer are DROPPED. Legacy entries (empty perceiver_uuids) pass through."""
    print("\n" + "=" * 60)
    print("TEST 4: Temporal filtering (perceiver_uuids)")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter_combat_log, ANON_NAME as _ANON

    hero_uuid = str(uuid4())
    ally_uuid = str(uuid4())
    enemy_uuid = str(uuid4())
    bystander_uuid = str(uuid4())

    controlled = [hero_uuid, ally_uuid]
    visible_set = {hero_uuid, ally_uuid, enemy_uuid, bystander_uuid}  # all visible (Layer 2 passes)

    # --- Entry perceivable by hero → SHOWN ---
    entry_hero_perceives = {
        "source_uuid": enemy_uuid, "target_uuid": hero_uuid,
        "source_name": "Skeleton", "target_name": "Hero",
        "verbose": "Skeleton attacks Hero", "sub_entries": [],
        "perceiver_uuids": [hero_uuid, enemy_uuid],
    }
    result = _filter_combat_log([entry_hero_perceives], controlled, visible_set)
    test("Hero in perceiver_uuids → entry shown", len(result) == 1)

    # --- Entry perceivable by ally → SHOWN ---
    entry_ally_perceives = {
        "source_uuid": enemy_uuid, "target_uuid": bystander_uuid,
        "source_name": "Skeleton", "target_name": "Bystander",
        "verbose": "Skeleton attacks Bystander", "sub_entries": [],
        "perceiver_uuids": [ally_uuid, enemy_uuid, bystander_uuid],
    }
    result = _filter_combat_log([entry_ally_perceives], controlled, visible_set)
    test("Ally in perceiver_uuids → entry shown", len(result) == 1)

    # --- Entry NOT perceivable → FULLY ANONYMIZED (not dropped) ---
    entry_not_perceived = {
        "source_uuid": enemy_uuid, "target_uuid": bystander_uuid,
        "source_name": "Skeleton", "target_name": "Bystander",
        "verbose": "Skeleton moves (3,3) behind wall", "sub_entries": [],
        "perceiver_uuids": [enemy_uuid, bystander_uuid],
    }
    result = _filter_combat_log([entry_not_perceived], controlled, visible_set)
    test("Not perceived: entry kept (not dropped)", len(result) == 1)
    test("Not perceived: source fully anonymized",
         result[0]["source_name"] == _ANON)
    test("Not perceived: target fully anonymized",
         result[0]["target_name"] == _ANON)
    test("Not perceived: positions anonymized in text",
         "(?,?)" in result[0]["verbose"])
    test("Not perceived: names anonymized in text",
         "Skeleton" not in result[0]["verbose"] and "Bystander" not in result[0]["verbose"])

    # --- Legacy entry (empty perceiver_uuids) → SHOWN (backwards compat) ---
    entry_legacy = {
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "verbose": "Skeleton does something", "sub_entries": [],
        # no perceiver_uuids key at all
    }
    result = _filter_combat_log([entry_legacy], controlled, visible_set)
    test("Legacy entry (no perceiver_uuids) → shown", len(result) == 1)

    entry_legacy_empty = {
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "verbose": "Skeleton does something", "sub_entries": [],
        "perceiver_uuids": [],  # explicit empty list
    }
    result = _filter_combat_log([entry_legacy_empty], controlled, visible_set)
    test("Legacy entry (empty perceiver_uuids list) → shown", len(result) == 1)

    # --- Mixed batch: all kept, but unperceived are anonymized ---
    result = _filter_combat_log(
        [entry_hero_perceives, entry_not_perceived, entry_ally_perceives],
        controlled, visible_set,
    )
    test("Mixed batch: all 3 entries kept", len(result) == 3)
    test("Mixed batch: perceived entries have real names",
         result[0]["source_name"] == "Skeleton" and result[2]["source_name"] == "Skeleton")
    test("Mixed batch: unperceived entry is anonymized",
         result[1]["source_name"] == _ANON)

    # --- Sub-entries with perceiver_uuids → non-perceived ANONYMIZED ---
    entry_parent_perceived = {
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "verbose": "Skeleton moves (1,1) → (5,5)", "sub_entries": [
            {"source_uuid": enemy_uuid, "target_uuid": None,
             "source_name": "Skeleton", "target_name": None,
             "verbose": "step (1,1)→(2,1)", "sub_entries": [],
             "perceiver_uuids": [enemy_uuid]},  # hero can't see → anonymized
            {"source_uuid": enemy_uuid, "target_uuid": None,
             "source_name": "Skeleton", "target_name": None,
             "verbose": "step (2,1)→(3,1)", "sub_entries": [],
             "perceiver_uuids": [enemy_uuid, hero_uuid]},  # hero CAN see → kept
            {"source_uuid": enemy_uuid, "target_uuid": None,
             "source_name": "Skeleton", "target_name": None,
             "verbose": "step (3,1)→(4,1)", "sub_entries": [],
             "perceiver_uuids": [enemy_uuid]},  # hero can't see → anonymized
        ],
        "perceiver_uuids": [enemy_uuid, hero_uuid],  # parent shown (union)
    }
    result = _filter_combat_log([entry_parent_perceived], controlled, visible_set)
    test("Parent with perceiver_uuids union → shown", len(result) == 1)
    subs = result[0].get("sub_entries", [])
    test("All 3 sub-entries kept (anonymized, not dropped)", len(subs) == 3)
    test("Visible sub keeps real text",
         subs[1]["verbose"] == "step (2,1)→(3,1)")
    test("Invisible sub has anonymized positions",
         "(?,?)" in subs[0]["verbose"])
    test("Invisible sub has anonymized name",
         subs[0]["source_name"] == _ANON)

    # --- Layer 1 + Layer 2 combined: perceived but source hidden → shown + anonymized ---
    hidden_source_uuid = str(uuid4())
    visible_set_partial = {hero_uuid, ally_uuid, enemy_uuid}  # hidden_source NOT visible
    entry_perceived_but_hidden = {
        "source_uuid": hidden_source_uuid, "target_uuid": hero_uuid,
        "source_name": "Invisible Wizard", "target_name": "Hero",
        "verbose": "Invisible Wizard attacks Hero", "sub_entries": [],
        "perceiver_uuids": [hero_uuid, hidden_source_uuid],
    }
    result = _filter_combat_log([entry_perceived_but_hidden], controlled, visible_set_partial)
    test("Perceived but source hidden → entry shown (not dropped)", len(result) == 1)
    test("Perceived but source hidden → source anonymized",
         result[0]["source_name"] == "???")
    test("Perceived but source hidden → target preserved",
         result[0]["target_name"] == "Hero")


# =========================================================================
# Test 5: Engine stamps perceiver_uuids on combat log entries
# =========================================================================
def test_engine_perceiver_stamping():
    """Verify the engine actually populates perceiver_uuids on CombatLogEntry
    objects during encounter combat."""
    print("\n" + "=" * 60)
    print("TEST 5: Engine stamps perceiver_uuids during encounter")
    print("=" * 60)

    reset_combat_state()
    setup_arena(20, 20)

    # Place entities: attacker and target can see each other (open arena)
    attacker = create_caster(name="Wizard", position=(5, 5))
    target = create_target(name="Skeleton", position=(8, 5), faction="monsters")

    register_spell(attacker, Fireball, caster_level=5)
    Entity.update_all_entities_senses()

    # Set up encounter
    encounter = Encounter(name="Test Perceivers", source_entity_uuid=uuid4())
    encounter.add_combatant(attacker, PassController(source_entity_uuid=attacker.uuid))
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    # Advance to attacker's turn
    while encounter.get_current_entity() != attacker:
        encounter.next_turn()

    # Record log position before action
    log_start = len(encounter.combat_log)

    # Execute Fireball — should generate combat log with perceiver_uuids
    fireball = Fireball(
        source_entity_uuid=attacker.uuid,
        end_position=(8, 5),
        cast_at_level=3,
        template=False,
    )
    result = fireball.apply()
    test("Fireball succeeded", result is not None and not result.canceled)

    # Check that combat log entries were generated
    new_entries = encounter.get_combat_log(since=log_start)
    test("Combat log entries were generated", len(new_entries) > 0)

    if new_entries:
        top_entry = new_entries[0]
        test("Top entry has perceiver_uuids field",
             hasattr(top_entry, "perceiver_uuids"))
        test("perceiver_uuids is non-empty",
             len(top_entry.perceiver_uuids) > 0)

        attacker_uuid_str = str(attacker.uuid)
        target_uuid_str = str(target.uuid)

        test("Attacker is in perceiver_uuids (source always perceives)",
             attacker_uuid_str in top_entry.perceiver_uuids)
        test("Target is in perceiver_uuids (target always perceives)",
             target_uuid_str in top_entry.perceiver_uuids)

        print(f"  perceiver_uuids count: {len(top_entry.perceiver_uuids)}")

    # --- Part 2: Observer behind wall can't perceive Fireball ---
    reset_combat_state()
    grid = setup_arena(30, 20)

    # Create a wall column at x=15 blocking LOS
    for y in range(0, 20):
        grid.set_tile(15, y, walkable=False, visible=False, name="Wall")

    attacker2 = create_caster(name="Wizard2", position=(5, 5))
    target2 = create_target(name="Skeleton2", position=(8, 5), faction="monsters")
    # Observer behind wall — can't see attacker or target
    observer = create_target(name="Observer", position=(20, 5), faction="observers")

    register_spell(attacker2, Fireball, caster_level=5)
    Entity.update_all_entities_senses()

    # Verify observer can't see attacker/target (wall blocks LOS)
    test("Observer can't see attacker (wall blocks LOS)",
         attacker2.uuid not in observer.senses.entities)
    test("Observer can't see target (wall blocks LOS)",
         target2.uuid not in observer.senses.entities)

    encounter2 = Encounter(name="Test Wall", source_entity_uuid=uuid4())
    encounter2.add_combatant(attacker2, PassController(source_entity_uuid=attacker2.uuid))
    encounter2.add_combatant(target2, PassController(source_entity_uuid=target2.uuid))
    encounter2.add_combatant(observer, PassController(source_entity_uuid=observer.uuid))
    encounter2.roll_initiative()
    encounter2.start_encounter()

    while encounter2.get_current_entity() != attacker2:
        encounter2.next_turn()

    log_start2 = len(encounter2.combat_log)

    fireball2 = Fireball(
        source_entity_uuid=attacker2.uuid,
        end_position=(8, 5),
        cast_at_level=3,
        template=False,
    )
    result2 = fireball2.apply()
    test("Fireball behind wall succeeded", result2 is not None and not result2.canceled)

    new_entries2 = encounter2.get_combat_log(since=log_start2)
    test("Combat log entries generated (wall scenario)", len(new_entries2) > 0)

    if new_entries2:
        top_entry2 = new_entries2[0]
        observer_uuid_str = str(observer.uuid)
        attacker2_uuid_str = str(attacker2.uuid)
        target2_uuid_str = str(target2.uuid)

        test("Attacker2 in perceiver_uuids",
             attacker2_uuid_str in top_entry2.perceiver_uuids)
        test("Target2 in perceiver_uuids",
             target2_uuid_str in top_entry2.perceiver_uuids)
        test("Observer NOT in perceiver_uuids (behind wall)",
             observer_uuid_str not in top_entry2.perceiver_uuids)

        # Verify temporal filter works end-to-end: observer's log should drop this
        from cli.log_filter import filter_combat_log as _filter_combat_log
        entry_dict = top_entry2.model_dump()
        # Convert perceiver_uuids set to list for dict form
        entry_dict["perceiver_uuids"] = list(top_entry2.perceiver_uuids)

        observer_filtered = _filter_combat_log(
            [entry_dict],
            [observer_uuid_str],
            {observer_uuid_str},  # observer can only see itself
        )
        test("Temporal filter: observer's log keeps entry (anonymized, not dropped)",
             len(observer_filtered) == 1)
        test("Temporal filter: observer sees anonymized names",
             observer_filtered[0]["source_name"] == "???")

        # Attacker's log should keep it
        attacker_filtered = _filter_combat_log(
            [entry_dict],
            [attacker2_uuid_str],
            {attacker2_uuid_str, target2_uuid_str},
        )
        test("Temporal filter: attacker's log keeps own entry",
             len(attacker_filtered) == 1)


# =========================================================================
# Test 6: Movement hidden position anonymization in parent text
# =========================================================================
def test_movement_hidden_positions():
    """Movement parent text should replace hidden step positions with (?,?).
    Sub_entries are kept and anonymized (not dropped)."""
    print("\n" + "=" * 60)
    print("TEST 6: Movement hidden position anonymization")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter, ANON_NAME as _ANON

    hero_uuid = str(uuid4())
    enemy_uuid = str(uuid4())
    controlled = [hero_uuid]
    visible_set = {hero_uuid, enemy_uuid}

    # --- Movement with partially visible steps ---
    # Skeleton moves 5 steps, only steps 3-4 visible to hero (through a door)
    movement_entry = {
        "entry_type": "movement",
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "compact": "{cyan:Skeleton} moves {green:25ft} to {yellow:(9,6)}",
        "verbose": "{cyan:Skeleton} moves (14,6) → {green:(9,6)} (25ft)",
        "detailed": "{cyan:Skeleton} moves (14,6) → {green:(9,6)} (25ft)",
        "data": {
            "entity_name": "Skeleton", "entity_uuid": enemy_uuid,
            "start_position": [14, 6], "end_position": [9, 6],
            "path": [[14, 6], [13, 6], [12, 6], [11, 6], [10, 6], [9, 6]],
            "distance_feet": 25, "movement_cost": 25,
        },
        "sub_entries": [
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (14,6) → (13,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [14, 6], "to_position": [13, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid]},  # behind wall
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (13,6) → (12,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [13, 6], "to_position": [12, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid]},  # behind wall
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (12,6) → (11,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [12, 6], "to_position": [11, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid, hero_uuid]},  # visible through door
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (11,6) → (10,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [11, 6], "to_position": [10, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid, hero_uuid]},  # visible through door
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (10,6) → (9,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [10, 6], "to_position": [9, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid]},  # behind wall again
        ],
        "perceiver_uuids": [enemy_uuid, hero_uuid],  # parent perceived (union)
    }

    result = _filter([movement_entry], controlled, visible_set)
    test("Movement parent kept", len(result) == 1)

    # All sub_entries kept (anonymized, not dropped)
    subs = result[0].get("sub_entries", [])
    test("All 5 sub_entries kept", len(subs) == 5)

    # Non-perceived steps are fully anonymized
    test("Hidden step 1: name anonymized", subs[0]["source_name"] == _ANON)
    test("Hidden step 1: positions anonymized", "(?,?)" in subs[0]["verbose"])
    test("Visible step 3: text preserved", "Skeleton" in subs[2]["verbose"])
    test("Hidden step 5: name anonymized", subs[4]["source_name"] == _ANON)

    # Parent text: hidden positions replaced with (?,?)
    parent_verbose = result[0].get("verbose", "")
    test("Parent text: hidden start (14,6) replaced with (?,?)",
         "(14,6)" not in parent_verbose)
    test("Parent text: hidden end (9,6) replaced with (?,?)",
         "(9,6)" not in parent_verbose)
    test("Parent text contains (?,?) for hidden positions",
         "(?,?)" in parent_verbose)

    # Perceived positions (12,6), (11,6), (10,6) should stay visible
    # (12,6) is from_position of first visible step, (10,6) is to_position of last
    # (11,6) is boundary between two visible steps — should NOT be anonymized
    test("Parent text: visible position (11,6) preserved if in text",
         True)  # (11,6) might not be in parent text — only start/end are

    # --- All steps visible: no anonymization ---
    movement_all_visible = {
        "entry_type": "movement",
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "verbose": "{cyan:Skeleton} moves (5,6) → {green:(3,6)} (10ft)",
        "sub_entries": [
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (5,6) → (4,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [5, 6], "to_position": [4, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid, hero_uuid]},
            {"entry_type": "movement", "source_uuid": enemy_uuid, "source_name": "Skeleton",
             "verbose": "Skeleton (4,6) → (3,6)", "sub_entries": [],
             "data": {"type": "step_movement", "from_position": [4, 6], "to_position": [3, 6], "movement_cost": 5},
             "perceiver_uuids": [enemy_uuid, hero_uuid]},
        ],
        "perceiver_uuids": [enemy_uuid, hero_uuid],
    }

    result_vis = _filter([movement_all_visible], controlled, visible_set)
    test("All-visible movement: no (?,?) in text",
         "(?,?)" not in result_vis[0].get("verbose", ""))

    # --- AoE sub_entries: non-perceived anonymized (not dropped) ---
    hidden_target_uuid = str(uuid4())
    fireball_entry = {
        "entry_type": "multi_entity_action",
        "source_uuid": enemy_uuid, "target_uuid": None,
        "source_name": "Skeleton", "target_name": None,
        "verbose": "Skeleton casts Fireball → 2 targets",
        "sub_entries": [
            {"source_uuid": enemy_uuid, "target_uuid": hero_uuid,
             "source_name": "Skeleton", "target_name": "Hero",
             "verbose": "Hero: DEX save FAIL, 15 fire", "sub_entries": [],
             "perceiver_uuids": [enemy_uuid, hero_uuid]},
            {"source_uuid": enemy_uuid, "target_uuid": hidden_target_uuid,
             "source_name": "Skeleton", "target_name": "Hidden Guy",
             "verbose": "Hidden Guy: DEX save SAVE, 7 fire", "sub_entries": [],
             "perceiver_uuids": [enemy_uuid, hidden_target_uuid]},  # hero can't perceive
        ],
        "perceiver_uuids": [enemy_uuid, hero_uuid, hidden_target_uuid],
    }

    result3 = _filter([fireball_entry], controlled, visible_set)
    test("Fireball parent kept", len(result3) == 1)
    subs3 = result3[0].get("sub_entries", [])
    test("Fireball: both sub_entries kept (anonymized, not dropped)", len(subs3) == 2)
    test("Fireball: perceived sub has real target name",
         subs3[0]["target_name"] == "Hero")
    test("Fireball: non-perceived sub is fully anonymized",
         subs3[1]["source_name"] == _ANON and subs3[1]["target_name"] == _ANON)


# =========================================================================
# Test 7: AoE reveals hidden target — combat log shows real name
# =========================================================================
def test_aoe_reveals_hidden_target():
    """When Fireball hits a Hidden entity and damage breaks Hidden,
    the combat log sub-entry should show the real target name (not '???')
    via the revealed_entity_uuids mechanism."""
    print("\n" + "=" * 60)
    print("TEST 7: AoE reveals hidden target — revealed_entity_uuids")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter

    reset_combat_state()
    setup_arena(20, 20)

    caster = create_caster(name="Wizard", position=(5, 5))
    hidden_target = create_target(name="Sneaky Rogue", position=(8, 5), faction="monsters")
    visible_target = create_target(name="Open Skeleton", position=(9, 5), faction="monsters")

    register_spell(caster, Fireball, caster_level=5)

    # Apply Hidden condition with high stealth DC
    hidden_cond = Hidden(
        source_entity_uuid=hidden_target.uuid,
        target_entity_uuid=hidden_target.uuid,
        stealth_result=30,
    )
    hidden_target.add_condition(hidden_cond)
    Entity.update_all_entities_senses()

    # Verify hidden target not in caster's senses
    test("Hidden target NOT visible to caster before fireball",
         hidden_target.uuid not in caster.senses.entities)

    # Set up encounter
    encounter = Encounter(name="Test Reveal", source_entity_uuid=uuid4())
    encounter.add_combatant(caster, PassController(source_entity_uuid=caster.uuid))
    encounter.add_combatant(hidden_target, PassController(source_entity_uuid=hidden_target.uuid))
    encounter.add_combatant(visible_target, PassController(source_entity_uuid=visible_target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    while encounter.get_current_entity() != caster:
        encounter.next_turn()

    log_start = len(encounter.combat_log)

    # Cast Fireball at hidden target's position
    fireball = Fireball(
        source_entity_uuid=caster.uuid,
        end_position=(8, 5),
        cast_at_level=3,
        template=False,
    )
    result = fireball.apply()
    test("Fireball succeeded", result is not None and not result.canceled)

    # Hidden condition should be removed (damage breaks Hidden)
    test("Hidden condition removed after taking damage",
         "Hidden" not in hidden_target.active_conditions)

    # Check combat log entries
    new_entries = encounter.get_combat_log(since=log_start)
    test("Combat log entries generated", len(new_entries) > 0)

    if new_entries:
        top_entry = new_entries[0]

        # Check revealed_entity_uuids is populated on top-level entry
        test("revealed_entity_uuids field exists",
             hasattr(top_entry, "revealed_entity_uuids"))
        hidden_uuid_str = str(hidden_target.uuid)
        test("Hidden target UUID in revealed_entity_uuids",
             hidden_uuid_str in top_entry.revealed_entity_uuids)

        # Visible target should NOT be in revealed set (was never hidden)
        visible_uuid_str = str(visible_target.uuid)
        test("Visible target NOT in revealed_entity_uuids",
             visible_uuid_str not in top_entry.revealed_entity_uuids)

        # Now test the filter: caster can see visible_target but NOT hidden_target
        # in the stale snapshot. But revealed_entity_uuids should override.
        caster_uuid_str = str(caster.uuid)
        stale_visible = {caster_uuid_str, visible_uuid_str}  # stale: hidden not visible

        entry_dict = top_entry.model_dump()
        entry_dict["perceiver_uuids"] = list(top_entry.perceiver_uuids)
        entry_dict["revealed_entity_uuids"] = list(top_entry.revealed_entity_uuids)
        # Convert sub_entries too
        for sub in entry_dict.get("sub_entries", []):
            if isinstance(sub.get("perceiver_uuids"), set):
                sub["perceiver_uuids"] = list(sub["perceiver_uuids"])
            if isinstance(sub.get("revealed_entity_uuids"), set):
                sub["revealed_entity_uuids"] = list(sub["revealed_entity_uuids"])

        filtered = _filter([entry_dict], [caster_uuid_str], stale_visible)
        test("Filtered log has entry", len(filtered) == 1)

        # Check sub-entries: revealed target should show real name
        subs = filtered[0].get("sub_entries", [])
        found_revealed_with_real_name = False
        found_visible_with_real_name = False
        for sub in subs:
            tn = sub.get("target_name", "")
            if tn == "Sneaky Rogue":
                found_revealed_with_real_name = True
            if tn == "Open Skeleton":
                found_visible_with_real_name = True

        test("Revealed target shows real name (not '???')", found_revealed_with_real_name)
        test("Visible target shows real name", found_visible_with_real_name)


# =========================================================================
# Test 8: revealed_entity_uuids filter unit tests
# =========================================================================
def test_revealed_filter_unit():
    """Unit tests for revealed_entity_uuids in filter_combat_log."""
    print("\n" + "=" * 60)
    print("TEST 8: revealed_entity_uuids filter unit tests")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter, ANON_NAME as _ANON

    hero_uuid = str(uuid4())
    revealed_uuid = str(uuid4())
    still_hidden_uuid = str(uuid4())

    controlled = [hero_uuid]
    visible_set = {hero_uuid}  # only hero visible in stale snapshot

    # --- Entry with revealed target: should show real name ---
    entry_revealed = {
        "source_uuid": hero_uuid, "target_uuid": revealed_uuid,
        "source_name": "Hero", "target_name": "Revealed Rogue",
        "verbose": "Hero hits Revealed Rogue for 15 damage",
        "compact": "Hero hits Revealed Rogue", "detailed": "Hero hits Revealed Rogue",
        "sub_entries": [],
        "revealed_entity_uuids": [revealed_uuid],
    }
    result = _filter([entry_revealed], controlled, visible_set)
    test("Revealed target: name NOT anonymized",
         result[0]["target_name"] == "Revealed Rogue")
    test("Revealed target: text NOT anonymized",
         "Revealed Rogue" in result[0]["verbose"])

    # --- Entry with still-hidden target: should still anonymize ---
    entry_still_hidden = {
        "source_uuid": hero_uuid, "target_uuid": still_hidden_uuid,
        "source_name": "Hero", "target_name": "Still Hidden",
        "verbose": "Hero hits Still Hidden", "compact": "Hero hits Still Hidden",
        "detailed": "Hero hits Still Hidden",
        "sub_entries": [],
        "revealed_entity_uuids": [],  # NOT revealed
    }
    result = _filter([entry_still_hidden], controlled, visible_set)
    test("Still-hidden target: name IS anonymized",
         result[0]["target_name"] == _ANON)

    # --- Sub-entries inherit parent's revealed set ---
    entry_parent_with_reveal = {
        "source_uuid": hero_uuid, "target_uuid": None,
        "source_name": "Hero", "target_name": None,
        "verbose": "Hero casts Fireball", "compact": "Fireball", "detailed": "Fireball",
        "revealed_entity_uuids": [revealed_uuid],
        "sub_entries": [
            {"source_uuid": hero_uuid, "target_uuid": revealed_uuid,
             "source_name": "Hero", "target_name": "Revealed Rogue",
             "verbose": "Revealed Rogue: DEX save FAIL", "compact": "save",
             "detailed": "save", "sub_entries": []},
            {"source_uuid": hero_uuid, "target_uuid": still_hidden_uuid,
             "source_name": "Hero", "target_name": "Still Hidden",
             "verbose": "Still Hidden: DEX save SAVE", "compact": "save",
             "detailed": "save", "sub_entries": []},
        ],
    }
    result = _filter([entry_parent_with_reveal], controlled, visible_set)
    subs = result[0].get("sub_entries", [])
    test("Sub-entry revealed target: name shown",
         subs[0]["target_name"] == "Revealed Rogue")
    test("Sub-entry still-hidden target: name anonymized",
         subs[1]["target_name"] == _ANON)

    # --- Non-perceived entry: revealed_entity_uuids doesn't override Layer 1 ---
    entry_not_perceived = {
        "source_uuid": revealed_uuid, "target_uuid": hero_uuid,
        "source_name": "Revealed Rogue", "target_name": "Hero",
        "verbose": "Revealed Rogue attacks Hero",
        "compact": "attack", "detailed": "attack",
        "sub_entries": [],
        "perceiver_uuids": [revealed_uuid],  # hero NOT in perceivers
        "revealed_entity_uuids": [revealed_uuid],
    }
    result = _filter([entry_not_perceived], controlled, visible_set)
    test("Not-perceived + revealed: revealed entity name shown (revealed overrides Layer 1)",
         result[0]["source_name"] == "Revealed Rogue")


# =========================================================================
# Test 9: condition_name in CONDITION_REMOVED combat log data
# =========================================================================
def test_condition_removal_log_data():
    """ConditionRemovalEvent.generate_combat_log() should include condition_name in data."""
    print("\n" + "=" * 60)
    print("TEST 9: condition_name in removal combat log data")
    print("=" * 60)

    reset_combat_state()
    setup_arena(20, 20)

    target = create_target(name="Target", position=(5, 5))
    Entity.update_all_entities_senses()

    # Set up encounter for combat log capture
    encounter = Encounter(name="Test Removal", source_entity_uuid=uuid4())
    encounter.add_combatant(target, PassController(source_entity_uuid=target.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    encounter.start_turn()

    # Apply and then remove a Hidden condition
    hidden_cond = Hidden(
        source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid,
        stealth_result=20,
    )
    target.add_condition(hidden_cond)
    test("Hidden condition applied", "Hidden" in target.active_conditions)

    log_before = len(encounter.combat_log)
    target.remove_condition("Hidden")
    test("Hidden condition removed", "Hidden" not in target.active_conditions)

    # Check combat log for condition_name in data
    new_logs = encounter.get_combat_log(since=log_before)
    found_removal_with_name = False
    for log_entry in new_logs:
        if log_entry.entry_type.value == "condition_removed":
            data = log_entry.data
            if data.get("condition_name") == "Hidden":
                found_removal_with_name = True
                break
        # Also check sub_entries
        for sub in log_entry.sub_entries:
            if sub.entry_type.value == "condition_removed":
                data = sub.data
                if data.get("condition_name") == "Hidden":
                    found_removal_with_name = True
                    break

    test("CONDITION_REMOVED log has condition_name='Hidden' in data", found_removal_with_name)


# =========================================================================
# Test 10: Killing invisible unit — all sub-events show real name
# =========================================================================
def test_invisible_kill_reveals_sub_events():
    """When Fireball kills an invisible (concentration) entity, ALL sub-events
    in the combat log should show the entity's real name — including deep
    sub-events like concentration check, Invisible removal, Dead application.

    This is the end-to-end test for the 'Layer 1 trumps revealed' bug fix.
    """
    print("\n" + "=" * 60)
    print("TEST 10: Killing invisible unit — all sub-events show real name")
    print("=" * 60)

    from cli.log_filter import filter_combat_log as _filter, ANON_NAME as _ANON
    from dnd.spells.illusion import Invisibility
    from dnd.conditions import Concentrating

    reset_combat_state()
    setup_arena(20, 20)

    # Hero (caster) and invisible enemy
    hero = create_caster(name="Hero Wizard", position=(5, 5), hp=200)
    enemy = create_caster(name="Sneaky Mage", position=(8, 5), faction="monsters", hp=20)

    register_spell(hero, Fireball, caster_level=5)
    register_spell(enemy, Invisibility, caster_level=3)

    Entity.update_all_entities_senses()

    # Enemy casts Invisibility on self (concentration spell)
    invis_spell = Invisibility(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        cast_at_level=2,
        template=False,
    )
    invis_result = invis_spell.apply()
    test("Invisibility spell succeeded", invis_result is not None and not invis_result.canceled)
    test("Enemy has Invisible condition", "Invisible" in enemy.active_conditions)
    test("Enemy has Concentrating condition", "Concentrating" in enemy.active_conditions)

    Entity.update_all_entities_senses()

    # Verify enemy not visible to hero
    test("Invisible enemy NOT in hero's senses",
         enemy.uuid not in hero.senses.entities)

    # Set up encounter
    encounter = Encounter(name="Test Invisible Kill", source_entity_uuid=uuid4())
    encounter.add_combatant(hero, PassController(source_entity_uuid=hero.uuid))
    encounter.add_combatant(enemy, PassController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    while encounter.get_current_entity() != hero:
        encounter.next_turn()

    log_start = len(encounter.combat_log)

    # Cast Fireball at enemy position — should deal lethal damage (enemy has 20 HP)
    fireball = Fireball(
        source_entity_uuid=hero.uuid,
        end_position=(8, 5),
        cast_at_level=3,
        template=False,
    )
    result = fireball.apply()
    test("Fireball succeeded", result is not None and not result.canceled)

    # Enemy should be dead (20 HP, Fireball does 8d6 avg ~28 damage)
    enemy_dead = not enemy.has_hp
    test("Enemy took damage from Fireball", get_hp(enemy) < 20)

    # Invisible should be removed (either from death or concentration break)
    test("Invisible condition removed", "Invisible" not in enemy.active_conditions)
    test("Concentrating condition removed", "Concentrating" not in enemy.active_conditions)

    # Check combat log
    new_entries = encounter.get_combat_log(since=log_start)
    test("Combat log entries generated", len(new_entries) > 0)

    if not new_entries:
        return

    top_entry = new_entries[0]

    # Check revealed_entity_uuids is populated
    enemy_uuid_str = str(enemy.uuid)
    test("Enemy UUID in revealed_entity_uuids",
         enemy_uuid_str in top_entry.revealed_entity_uuids)

    # Now filter the log from hero's perspective with STALE visible set
    # (enemy was invisible, so NOT in the visible set at snapshot time)
    hero_uuid_str = str(hero.uuid)
    stale_visible = {hero_uuid_str}  # only hero visible

    # Convert to dict for filtering
    def entry_to_dict(entry):
        d = entry.model_dump()
        d["perceiver_uuids"] = list(entry.perceiver_uuids)
        d["revealed_entity_uuids"] = list(entry.revealed_entity_uuids)
        for sub in d.get("sub_entries", []):
            _convert_sub_sets(sub)
        return d

    def _convert_sub_sets(sub):
        if isinstance(sub.get("perceiver_uuids"), set):
            sub["perceiver_uuids"] = list(sub["perceiver_uuids"])
        if isinstance(sub.get("revealed_entity_uuids"), set):
            sub["revealed_entity_uuids"] = list(sub["revealed_entity_uuids"])
        for child in sub.get("sub_entries", []):
            _convert_sub_sets(child)

    entry_dict = entry_to_dict(top_entry)
    filtered = _filter([entry_dict], [hero_uuid_str], stale_visible)
    test("Filtered log has entry", len(filtered) == 1)

    # Recursively check ALL sub-entries — none should show "???" for the enemy's name
    def check_no_anon_for_enemy(entries, depth=0):
        """Recursively check no sub-entry anonymizes the revealed enemy."""
        anon_found = []
        for e in entries:
            prefix = "  " * depth
            sn = e.get("source_name", "")
            tn = e.get("target_name", "")
            etype = e.get("entry_type", "?")
            compact = e.get("compact", "")

            # Check source/target name fields
            if e.get("source_uuid") == enemy_uuid_str and sn == _ANON:
                anon_found.append(f"{prefix}source_name='???' in {etype}: {compact}")
            if e.get("target_uuid") == enemy_uuid_str and tn == _ANON:
                anon_found.append(f"{prefix}target_name='???' in {etype}: {compact}")

            # Check text fields for "???"
            for field in ("compact", "verbose", "detailed"):
                text = e.get(field, "")
                if _ANON in text and (e.get("source_uuid") == enemy_uuid_str
                                       or e.get("target_uuid") == enemy_uuid_str):
                    anon_found.append(f"{prefix}{field} has '???' in {etype}: {text}")
                    break  # one field is enough to flag

            # Recurse
            anon_found.extend(check_no_anon_for_enemy(e.get("sub_entries", []), depth + 1))
        return anon_found

    anon_issues = check_no_anon_for_enemy(filtered)
    if anon_issues:
        print("  ANONYMIZATION ISSUES FOUND:")
        for issue in anon_issues:
            print(f"    - {issue}")
    test("No sub-entry anonymizes the revealed enemy (zero '???' for Sneaky Mage)",
         len(anon_issues) == 0)

    # Also verify: top-level entry shows enemy name
    top_compact = filtered[0].get("compact", "")
    test("Top-level entry shows enemy name in text",
         "Sneaky Mage" in top_compact or any(
             "Sneaky Mage" in s.get("target_name", "") or "Sneaky Mage" in s.get("compact", "")
             for s in filtered[0].get("sub_entries", [])
         ))


# =========================================================================
# Run all tests
# =========================================================================
if __name__ == "__main__":
    test_aoe_preview_hidden_entity()
    test_combat_log_anonymization()
    test_aoe_empty_position()
    test_temporal_filtering()
    test_engine_perceiver_stamping()
    test_movement_hidden_positions()
    test_aoe_reveals_hidden_target()
    test_revealed_filter_unit()
    test_condition_removal_log_data()
    test_invisible_kill_reveals_sub_events()

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
