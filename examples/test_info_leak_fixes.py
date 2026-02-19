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

    from cli.prompt_builder import _filter_combat_log, _ANON

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
    result = _filter_combat_log(entries_both_visible, visible_set, controlled)
    test("Both visible: all 1 entry kept", len(result) == 1)
    test("Both visible: no anonymization",
         result[0]["verbose"] == "Hero attacks Visible Enemy")

    # --- Test: Visible source, hidden target → target anonymized ---
    entries_hidden_target = [
        {"source_uuid": visible_enemy_uuid, "target_uuid": hidden_enemy_uuid,
         "source_name": "Goblin", "target_name": "Rogue",
         "verbose": "Goblin attacks Rogue", "sub_entries": []},
    ]
    result = _filter_combat_log(entries_hidden_target, visible_set, controlled)
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
    result = _filter_combat_log(entries_hidden_self, visible_set, controlled)
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
    result = _filter_combat_log(entries_hidden_buff, visible_set, controlled)
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
    result = _filter_combat_log(entries_hidden_attacks_us, visible_set, controlled)
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
    result = _filter_combat_log(all_entries, None, controlled)
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
    result = _filter_combat_log(entries_mixed, visible_set, controlled)
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
    result = _filter_combat_log(entries_with_subs, visible_set, controlled)
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
    result = _filter_combat_log(entries_hidden_aoe, visible_set, controlled)
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
# Run all tests
# =========================================================================
if __name__ == "__main__":
    test_aoe_preview_hidden_entity()
    test_combat_log_anonymization()
    test_aoe_empty_position()

    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
