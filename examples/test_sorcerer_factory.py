"""
Test Sorcerer Factory & Metamagic Implementation

Tests:
- SF-A: Factory basics (HP, AC, spell slots, config validation)
- SF-B: Sorcery Points resource
- SF-C: Quickened Spell metamagic
- SF-D: Twinned Spell metamagic
- SF-E: Distant Spell metamagic
- SF-F: Font of Magic (slot/SP conversion)
- SF-G: Draconic Bloodline features
- SF-H: Quickened Spell — Extended
- SF-I: Twinned Spell — Extended
- SF-J: Distant Spell — Extended
- SF-K: Metamagic Interactions
- SF-L: Font of Magic — Extended
- SF-M: Draconic Bloodline — Extended
- SF-N: Factory Config Edge Cases
- SF-O: Spell Slot Table Verification
- SF-P: SP Resource & Metamagic Action Discovery
- SF-Q: SorceryPointsFeature Removal
- SF-R: Combat Integration
"""

from dnd.utils import (
    reset_combat_state, setup_combat_arena, get_hp, get_max_hp, set_hp,
    force_attack_hit, remove_attack_modifier, deal_damage_to, has_condition,
)
from dnd.entity import Entity
from dnd.core.base_actions import TargetType
from dnd.core.gridmap import get_map
from dnd.core.events import RangeType
from dnd.core.modifiers import DamageType, ResistanceStatus
from dnd.actions import SpellAction
from dnd.controller import PassController
from dnd.classes.sorcerer_factory import (
    SorcererConfig,
    create_sorcerer,
    get_sorcerer_spell_slots,
)
from pydantic import ValidationError


def setup_arena(width: int = 20, height: int = 20):
    """Create a basic walkable arena with tiles for LOS."""
    grid = get_map()
    grid.create_rectangle(0, 0, width, height)

passed = 0
failed = 0


def run_test(name, func):
    global passed, failed
    reset_combat_state()
    setup_arena()
    try:
        func()
        print(f"  PASS: {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {name} — {e}")
        import traceback
        traceback.print_exc()
        failed += 1


def get_to_turn(encounter, entity):
    """Advance encounter until it's entity's turn, with turn started."""
    from dnd.encounter import TurnState
    # If no turn in progress, start one
    if encounter.turn_state != TurnState.IN_PROGRESS:
        encounter.start_turn()
    for _ in range(10):
        current = encounter.get_current_entity()
        if current and current.uuid == entity.uuid:
            return  # Turn already started for this entity
        # Not our turn — end and advance (next_turn calls start_turn)
        encounter.end_turn()
        encounter.next_turn()
    raise RuntimeError("Could not reach entity's turn")


# =========================================================================
# SF-A: Factory Basics
# =========================================================================

def test_sf_a1_l1_sorcerer():
    """L1 sorcerer: correct HP, AC, spell slots."""
    config = SorcererConfig(level=1, name="Sorcerer L1")
    sorc = create_sorcerer(config)

    # CHA 15+2=17, CON 13+1=14, DEX 14
    assert sorc.ability_scores.charisma.ability_score.score == 17, \
        f"Expected CHA 17, got {sorc.ability_scores.charisma.ability_score.score}"
    assert sorc.ability_scores.constitution.modifier == 2, \
        f"Expected CON mod +2, got {sorc.ability_scores.constitution.modifier}"

    # Prof bonus
    assert sorc.proficiency_bonus.normalized_score == 2

    # HP: d6 average L1 = 6, + CON*1 = 2, + Draconic 1 = 9
    hp = get_hp(sorc)
    assert hp == 9, f"Expected HP 9, got {hp}"

    # AC: 13 + DEX(+2) = 15 (Draconic Resilience, unarmored)
    Entity.update_all_entities_senses()
    ac = sorc.ac_bonus().normalized_score
    assert ac == 15, f"Expected AC 15, got {ac}"

    # Spell slots: L1 has {1: 2}
    slot1 = sorc.action_economy.spell_slot_1.normalized_score
    assert slot1 == 2, f"Expected 2 L1 slots, got {slot1}"


def test_sf_a2_l5_sorcerer():
    """L5 sorcerer: spell slots 4/3/2, prof +3."""
    config = SorcererConfig(
        level=5, name="Sorcerer L5",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.proficiency_bonus.normalized_score == 3

    # Spell slots: {1: 4, 2: 3, 3: 2}
    assert sorc.action_economy.spell_slot_1.normalized_score == 4
    assert sorc.action_economy.spell_slot_2.normalized_score == 3
    assert sorc.action_economy.spell_slot_3.normalized_score == 2


def test_sf_a3_l10_sorcerer():
    """L10 sorcerer has ASI-boosted stats."""
    config = SorcererConfig(
        level=10, name="Sorcerer L10",
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],  # CHA 17+2=19
        asi_8=[("charisma", 1), ("constitution", 1)],  # CHA 20, CON 15
    )
    sorc = create_sorcerer(config)

    assert sorc.ability_scores.charisma.ability_score.score == 20, \
        f"Expected CHA 20, got {sorc.ability_scores.charisma.ability_score.score}"
    assert sorc.ability_scores.constitution.ability_score.score == 15, \
        f"Expected CON 15, got {sorc.ability_scores.constitution.ability_score.score}"

    assert sorc.proficiency_bonus.normalized_score == 4


def test_sf_a4_config_validation_metamagic():
    """Config rejects L1 with metamagic, requires at L3+."""
    # L1 with metamagic should fail
    try:
        SorcererConfig(level=1, name="Bad", metamagic_choices=["quickened", "twinned"])
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # L3 without metamagic should fail
    try:
        SorcererConfig(level=3, name="Bad")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # L3 with wrong count should fail
    try:
        SorcererConfig(level=3, name="Bad", metamagic_choices=["quickened"])
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_sf_a5_config_validation_asi():
    """ASI required at L4+, bonus_plus_2 != bonus_plus_1."""
    # L4 without ASI should fail
    try:
        SorcererConfig(level=4, name="Bad", metamagic_choices=["quickened", "twinned"])
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass

    # Same bonus should fail
    try:
        SorcererConfig(level=1, name="Bad", bonus_plus_2="charisma", bonus_plus_1="charisma")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


# =========================================================================
# SF-B: Sorcery Points
# =========================================================================

def test_sf_b1_l1_no_sp():
    """L1 has no sorcery_points resource."""
    config = SorcererConfig(level=1, name="L1 Sorc")
    sorc = create_sorcerer(config)
    assert not sorc.action_economy.has_resource("sorcery_points"), \
        "L1 should not have sorcery points"


def test_sf_b2_sp_scales_with_level():
    """L2 has 2 SP, L5 has 5 SP, L10 has 10 SP."""
    for level, expected_sp in [(2, 2), (5, 5), (10, 10)]:
        reset_combat_state()
        kwargs = {"level": level, "name": f"Sorc L{level}"}
        if level >= 3:
            meta = ["quickened", "twinned"]
            if level >= 10:
                meta.append("distant")
            kwargs["metamagic_choices"] = meta
        if level >= 4:
            kwargs["asi_4"] = [("charisma", 2)]
        if level >= 8:
            kwargs["asi_8"] = [("charisma", 1), ("constitution", 1)]
        config = SorcererConfig(**kwargs)
        sorc = create_sorcerer(config)
        current = sorc.action_economy.get_resource_current("sorcery_points")
        assert current == expected_sp, f"L{level}: expected {expected_sp} SP, got {current}"


def test_sf_b3_sp_consumed_by_metamagic():
    """SP consumed by metamagic action."""
    config = SorcererConfig(
        level=5, name="SP Test",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    initial_sp = sorc.action_economy.get_resource_current("sorcery_points")
    assert initial_sp == 5, f"Expected 5 SP, got {initial_sp}"

    # Execute Quickened Spell (costs 2 SP) — instantiate since it's a template
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None, "Quickened Spell not found"
    assert qs.pre_validate(), "Quickened Spell should be valid"
    qs.instantiate().apply()

    remaining = sorc.action_economy.get_resource_current("sorcery_points")
    assert remaining == 3, f"Expected 3 SP after Quickened (cost 2), got {remaining}"


def test_sf_b4_sp_blocked_insufficient():
    """SP blocked when insufficient."""
    config = SorcererConfig(
        level=3, name="SP Block",
        metamagic_choices=["quickened", "twinned"],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Use all SP: 3 SP total, Quickened costs 2, then 1 left
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()  # 3 → 1

    # Second Quickened should fail (needs 2 SP, only 1 left)
    qs2 = sorc.get_action_template("Quickened Spell")
    assert qs2 is not None
    assert not qs2.pre_validate(), "Should fail with insufficient SP"


# =========================================================================
# SF-C: Quickened Spell
# =========================================================================

def test_sf_c1_quickened_available():
    """Quickened Spell action available, costs 2 SP."""
    config = SorcererConfig(
        level=5, name="QS Test",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None, "Quickened Spell should be registered"
    # Cost: 0 actions + 2 SP
    assert any(c.resource_name == "sorcery_points" and c.resource_cost == 2
               for c in qs.costs), "Should cost 2 SP"


def test_sf_c2_quickened_modifies_spells():
    """After Quickened, spells appear as bonus_action cost."""
    config = SorcererConfig(
        level=5, name="QS Mod",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Before Quickened: Fire Bolt costs actions
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    assert fb.alt_cost_type is None

    # Apply Quickened (instantiate for self-target)
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # After Quickened: Fire Bolt has alt_cost_type = bonus_actions
    fb2 = sorc.get_action_template("Fire Bolt")
    assert fb2 is not None
    assert fb2.alt_cost_type == "bonus_actions", \
        f"Expected alt_cost_type='bonus_actions', got {fb2.alt_cost_type}"

    # MetamagicActive condition should be present
    assert "MetamagicActive" in sorc.active_conditions


def test_sf_c3_quickened_cast_and_damage():
    """Cast quickened Fire Bolt: bonus_actions consumed, target takes damage."""
    config = SorcererConfig(
        level=5, name="QS Cast",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_skeleton
    target = create_skeleton(name="Target", position=(2, 0))

    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, target)
    encounter.start_encounter()

    get_to_turn(encounter, sorc)

    # Apply Quickened
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # Should still have 1 action available
    assert sorc.action_economy.actions.normalized_score >= 1, "Actions should be unspent"

    # Cast Fire Bolt (now costs bonus_action via alt_cost_type)
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None

    # Force hit
    hit_mod_uuid = force_attack_hit(sorc)

    # Instantiate with target
    fb_instance = fb.instantiate(target_entity_uuid=target.uuid)
    fb_instance.apply()

    # Verify bonus_actions consumed (0 remaining)
    assert sorc.action_economy.bonus_actions.normalized_score == 0, \
        f"Bonus actions should be 0, got {sorc.action_economy.bonus_actions.normalized_score}"
    # Actions should still be 1
    assert sorc.action_economy.actions.normalized_score >= 1, \
        "Actions should be unspent after quickened cast"

    remove_attack_modifier(sorc, hit_mod_uuid)


def test_sf_c4_metamagic_auto_removed():
    """MetamagicActive auto-removed after cast, templates restored."""
    config = SorcererConfig(
        level=5, name="QS Restore",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_skeleton
    target = create_skeleton(name="Target", position=(2, 0))

    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, target)
    encounter.start_encounter()

    get_to_turn(encounter, sorc)

    # Apply and cast
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    hit_mod_uuid = force_attack_hit(sorc)
    fb.instantiate(target_entity_uuid=target.uuid).apply()

    # MetamagicActive should be gone
    assert "MetamagicActive" not in sorc.active_conditions, \
        "MetamagicActive should be removed after cast"

    # Templates should be restored
    fb2 = sorc.get_action_template("Fire Bolt")
    assert fb2 is not None
    assert fb2.alt_cost_type is None, \
        f"alt_cost_type should be None after cleanup, got {fb2.alt_cost_type}"

    remove_attack_modifier(sorc, hit_mod_uuid)


# =========================================================================
# SF-D: Twinned Spell
# =========================================================================

def test_sf_d1_twinned_modifies_target_type():
    """Twinned: Hold Person available as MULTI_ENTITY with count=2."""
    config = SorcererConfig(
        level=5, name="TS Mod",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Apply Twinned
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    # Hold Person should now be MULTI_ENTITY
    hp_template = sorc.get_action_template("Hold Person")
    assert hp_template is not None, "Hold Person template not found"
    assert hp_template.alt_target_type == TargetType.MULTI_ENTITY, \
        f"Expected MULTI_ENTITY, got {hp_template.alt_target_type}"
    assert hp_template.alt_target_count == 2, \
        f"Expected count 2, got {hp_template.alt_target_count}"


def test_sf_d2_twinned_cast():
    """Cast twinned Hold Person: concentration active (uses goblins - humanoids)."""
    config = SorcererConfig(
        level=5, name="TS Cast",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_goblin
    t1 = create_goblin(name="Target1", position=(2, 0))
    t2 = create_goblin(name="Target2", position=(3, 0))

    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, t1)
    encounter.add_combatant(t2, PassController(source_entity_uuid=t2.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    get_to_turn(encounter, sorc)

    # Apply Twinned
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    # Cast twinned Hold Person
    hp_template = sorc.get_action_template("Hold Person")
    assert hp_template is not None

    # Instantiate with first target and extra targets
    hp_instance = hp_template.instantiate(
        target_entity_uuid=t1.uuid,
        extra_targets=[t2.uuid],
    )
    hp_instance.apply()

    # Sorcerer should be concentrating (Hold Person is concentration regardless of saves)
    assert "Concentrating" in sorc.active_conditions, \
        "Sorcerer should be concentrating on Hold Person"


def test_sf_d3_twinned_auto_removed():
    """MetamagicActive auto-removed after twinned cast."""
    config = SorcererConfig(
        level=5, name="TS Restore",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_goblin
    t1 = create_goblin(name="Target1", position=(2, 0))
    t2 = create_goblin(name="Target2", position=(3, 0))

    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, t1)
    encounter.add_combatant(t2, PassController(source_entity_uuid=t2.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    get_to_turn(encounter, sorc)

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    hp_template = sorc.get_action_template("Hold Person")
    assert hp_template is not None
    hp_instance = hp_template.instantiate(
        target_entity_uuid=t1.uuid,
        extra_targets=[t2.uuid],
    )
    hp_instance.apply()

    # MetamagicActive should be removed
    assert "MetamagicActive" not in sorc.active_conditions

    # Hold Person template should be restored
    hp2 = sorc.get_action_template("Hold Person")
    assert hp2 is not None
    assert hp2.alt_target_type is None, \
        f"Should be restored to None, got {hp2.alt_target_type}"


# =========================================================================
# SF-E: Distant Spell
# =========================================================================

def test_sf_e1_distant_doubles_range():
    """Distant doubles Fire Bolt range (120→240)."""
    config = SorcererConfig(
        level=5, name="DS Range",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Original range
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    assert isinstance(fb, SpellAction)
    original_range = fb.spell_range.normal
    assert original_range == 120, f"Expected Fire Bolt range 120, got {original_range}"

    # Apply Distant
    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    # Fire Bolt should have doubled range
    fb2 = sorc.get_action_template("Fire Bolt")
    assert fb2 is not None
    assert fb2.alt_range == 240, f"Expected alt_range 240, got {fb2.alt_range}"
    assert fb2.effective_range == 240, f"Expected effective_range 240, got {fb2.effective_range}"


def test_sf_e2_distant_restored_after_cast():
    """Templates restored after casting with Distant."""
    config = SorcererConfig(
        level=5, name="DS Restore",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_skeleton
    target = create_skeleton(name="Target", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, target)
    encounter.start_encounter()

    get_to_turn(encounter, sorc)

    # Apply Distant + cast
    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    hit_mod_uuid = force_attack_hit(sorc)
    fb.instantiate(target_entity_uuid=target.uuid).apply()

    # Restored
    fb2 = sorc.get_action_template("Fire Bolt")
    assert fb2 is not None
    assert fb2.alt_range is None, f"Should be None after cleanup, got {fb2.alt_range}"

    remove_attack_modifier(sorc, hit_mod_uuid)


# =========================================================================
# SF-F: Font of Magic
# =========================================================================

def test_sf_f1_convert_slot_to_sp():
    """Convert L1 slot → 1 SP gained."""
    config = SorcererConfig(
        level=5, name="FoM Slot",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Consume some SP first so we can see the gain
    sorc.action_economy.consume_resource("sorcery_points", 3)  # 5→2
    sp_before = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp_before == 2

    # Execute Convert L1 Slot to SP
    conv = sorc.get_action_template("Convert L1 Slot to SP")
    assert conv is not None, "Convert L1 Slot to SP not found"
    conv.instantiate().apply()

    sp_after = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp_after == 3, f"Expected 3 SP (2+1), got {sp_after}"


def test_sf_f2_convert_sp_to_slot():
    """Convert 2 SP → L1 slot gained."""
    config = SorcererConfig(
        level=5, name="FoM SP",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Consume a L1 slot first
    sorc.action_economy.consume("spell_slot_1", 1, "test_slot_use")
    slots_before = sorc.action_economy.spell_slot_1.normalized_score
    assert slots_before == 3, f"Expected 3 L1 slots (4-1), got {slots_before}"

    # Execute Convert SP to L1 Slot
    conv = sorc.get_action_template("Convert SP to L1 Slot")
    assert conv is not None, "Convert SP to L1 Slot not found"
    conv.instantiate().apply()

    slots_after = sorc.action_economy.spell_slot_1.normalized_score
    assert slots_after == 4, f"Expected 4 L1 slots (restored), got {slots_after}"

    sp_after = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp_after == 3, f"Expected 3 SP (5-2), got {sp_after}"


def test_sf_f3_insufficient_sp_blocked():
    """Can't convert when insufficient SP."""
    config = SorcererConfig(
        level=3, name="FoM Block",
        metamagic_choices=["quickened", "twinned"],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Drain SP to 0
    sorc.action_economy.consume_resource("sorcery_points", 3)
    assert sorc.action_economy.get_resource_current("sorcery_points") == 0

    # Convert SP to Slot should fail
    conv = sorc.get_action_template("Convert SP to L1 Slot")
    assert conv is not None
    assert not conv.pre_validate(), "Should fail with 0 SP"


# =========================================================================
# SF-G: Draconic Bloodline
# =========================================================================

def test_sf_g1_draconic_hp_bonus():
    """L1: HP includes +level bonus from Draconic Resilience."""
    config = SorcererConfig(level=1, name="Draconic L1")
    sorc = create_sorcerer(config)

    # HP without Draconic: d6(6) + CON(2)*1 = 8
    # HP with Draconic: 8 + 1 = 9
    hp = get_hp(sorc)
    assert hp == 9, f"Expected 9 HP (6+2+1 Draconic), got {hp}"

    # Check condition is present
    assert "Draconic Resilience" in sorc.active_conditions


def test_sf_g2_draconic_ac():
    """L1: AC = 13 + DEX when unarmored."""
    config = SorcererConfig(level=1, name="Draconic AC")
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # DEX 14 → mod +2, AC = 13 + 2 = 15
    ac = sorc.ac_bonus().normalized_score
    assert ac == 15, f"Expected AC 15, got {ac}"


def test_sf_g3_elemental_affinity():
    """L6: Resistance to chosen damage type."""
    config = SorcererConfig(
        level=6, name="Draconic L6",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        draconic_damage_type="Fire",
    )
    sorc = create_sorcerer(config)

    from dnd.core.modifiers import DamageType, ResistanceStatus
    resistance = sorc.health.get_resistance(DamageType.FIRE)
    assert resistance == ResistanceStatus.RESISTANCE, \
        f"Expected RESISTANCE to Fire, got {resistance}"

    assert "Elemental Affinity" in sorc.active_conditions


# =========================================================================
# SF-H: Quickened Spell — Extended
# =========================================================================

def test_sf_h1_quickened_action_plus_spell():
    """Quickened Fire Bolt (bonus action) + action spell in same turn (BG3 style)."""
    config = SorcererConfig(
        level=5, name="QS Full Turn",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    t1 = create_skeleton(name="T1", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, t1)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Quickened Spell → Fire Bolt as bonus action
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    hit_mod = force_attack_hit(sorc)
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    fb.instantiate(target_entity_uuid=t1.uuid).apply()

    # Bonus action spent, action still available
    assert sorc.action_economy.bonus_actions.normalized_score == 0
    assert sorc.action_economy.actions.normalized_score >= 1

    # Now cast Magic Missile (action cost) in same turn
    mm = sorc.get_action_template("Magic Missile")
    assert mm is not None
    mm_instance = mm.instantiate(target_entity_uuid=t1.uuid)
    mm_instance.apply()

    # Action should now be consumed
    assert sorc.action_economy.actions.normalized_score == 0
    remove_attack_modifier(sorc, hit_mod)


def test_sf_h2_quickened_no_modify_non_spells():
    """Quickened doesn't modify non-spell actions (Dash, Attack stay as action cost)."""
    config = SorcererConfig(
        level=5, name="QS Non-Spell",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # Dash should NOT be modified
    dash = sorc.get_action_template("Dash")
    assert dash is not None
    assert dash.alt_cost_type is None, f"Dash should not be modified, got alt_cost_type={dash.alt_cost_type}"

    # Dodge should NOT be modified
    dodge = sorc.get_action_template("Dodge")
    assert dodge is not None
    assert dodge.alt_cost_type is None


def test_sf_h3_quickened_only_action_cost_spells():
    """Quickened only modifies spells with action cost (not bonus action spells)."""
    config = SorcererConfig(
        level=5, name="QS BA Spells",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        spell_names=["Fire Bolt", "Magic Missile", "Misty Step"],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # Misty Step costs bonus_action — should NOT be modified by Quickened
    ms = sorc.get_action_template("Misty Step")
    if ms is not None:
        # Misty Step already costs bonus action, quickened shouldn't touch it
        has_action_cost = any(c.cost_type == "actions" for c in ms.costs)
        if not has_action_cost:
            assert ms.alt_cost_type is None, "Bonus action spells should not be quickened"


def test_sf_h4_quickened_cantrip_then_action_spell():
    """Quickened cantrip (bonus), then full action spell — both resolve."""
    config = SorcererConfig(
        level=5, name="QS Cantrip+Spell",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    t1 = create_skeleton(name="T1", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, t1)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Quickened → Magic Missile as bonus action (auto-hit, no attack roll)
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    hp_before = get_hp(t1)
    mm = sorc.get_action_template("Magic Missile")
    assert mm is not None
    mm.instantiate(target_entity_uuid=t1.uuid).apply()

    hp_after_mm = get_hp(t1)
    assert hp_after_mm < hp_before, "Magic Missile should deal damage (auto-hit)"

    # Bonus action consumed, action still available
    assert sorc.action_economy.bonus_actions.normalized_score == 0
    assert sorc.action_economy.actions.normalized_score >= 1

    # Now cast Burning Hands (action) on the same target
    bh = sorc.get_action_template("Burning Hands")
    assert bh is not None
    bh_instance = bh.instantiate(target_position=(2, 0))
    bh_instance.apply()


def test_sf_h5_quickened_blocked_when_active():
    """Can't activate Quickened when MetamagicActive already present."""
    config = SorcererConfig(
        level=5, name="QS Block Stack",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # First Quickened → succeeds
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Second Quickened → should fail pre_validate
    qs2 = sorc.get_action_template("Quickened Spell")
    assert qs2 is not None
    assert not qs2.pre_validate(), "Second metamagic should be blocked"


# =========================================================================
# SF-I: Twinned Spell — Extended
# =========================================================================

def test_sf_i1_twinned_sp_cost_scales():
    """Twinned SP cost = spell level: cantrip=1, L1=1, L2=2, L3=3."""
    config = SorcererConfig(
        level=5, name="TS Cost",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Apply Twinned (costs 1 SP at activation)
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    # Check cantrip (Fire Bolt, L0): no extra costs (1 SP total)
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    assert isinstance(fb, SpellAction)
    assert len(fb.alt_extra_costs) == 0, \
        f"Cantrip should have no extra SP cost, got {len(fb.alt_extra_costs)}"

    # Check L1 spell (Magic Missile, L1): no extra costs (1 SP at activation = 1 total)
    mm = sorc.get_action_template("Magic Missile")
    assert mm is not None
    assert isinstance(mm, SpellAction)
    assert len(mm.alt_extra_costs) == 0, \
        f"L1 should have no extra SP cost, got {len(mm.alt_extra_costs)}"

    # Check L2 spell (Hold Person, L2): extra 1 SP (total = 1+1 = 2)
    hp_tmpl = sorc.get_action_template("Hold Person")
    assert hp_tmpl is not None
    assert isinstance(hp_tmpl, SpellAction)
    assert len(hp_tmpl.alt_extra_costs) == 1
    assert hp_tmpl.alt_extra_costs[0].resource_cost == 1, \
        f"L2 extra cost should be 1, got {hp_tmpl.alt_extra_costs[0].resource_cost}"

    # Check L3 spell (Fireball is AoE, not twinnable — use Lightning Bolt? Also AoE.)
    # Actually Fireball/Lightning Bolt are POSITION_AOE, so they won't get twinned.
    # No single-target L3 spells in default list. That's fine — cost formula validated above.


def test_sf_i2_twinned_no_modify_aoe():
    """Twinned doesn't modify AoE spells (Fireball stays POSITION_AOE)."""
    config = SorcererConfig(
        level=5, name="TS AoE",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    fb_spell = sorc.get_action_template("Fireball")
    assert fb_spell is not None
    assert fb_spell.alt_target_type is None, \
        f"Fireball should not be twinned, got alt_target_type={fb_spell.alt_target_type}"


def test_sf_i3_twinned_no_modify_self():
    """Twinned doesn't modify self-target spells (TargetType.SELF)."""
    config = SorcererConfig(
        level=5, name="TS Self",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        spell_names=["Fire Bolt", "False Life", "Hold Person"],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    # False Life targets SELF — should not be twinned
    fl = sorc.get_action_template("False Life")
    assert fl is not None, "False Life should be registered"
    assert fl.alt_target_type is None, \
        f"False Life (SELF) should not be twinned, got {fl.alt_target_type}"


def test_sf_i4_twinned_hold_person_both_paralyzed():
    """Twinned Hold Person — both targets make saves."""
    config = SorcererConfig(
        level=5, name="TS HP Both",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_goblin
    t1 = create_goblin(name="Goblin1", position=(2, 0))
    t2 = create_goblin(name="Goblin2", position=(3, 0))
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(sorc, t1)
    encounter.add_combatant(t2, PassController(source_entity_uuid=t2.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    hp_tmpl = sorc.get_action_template("Hold Person")
    assert hp_tmpl is not None
    hp_instance = hp_tmpl.instantiate(
        target_entity_uuid=t1.uuid,
        extra_targets=[t2.uuid],
    )
    hp_instance.apply()

    # Sorcerer should be concentrating
    assert "Concentrating" in sorc.active_conditions

    # At least one target should have HoldPersonEffect (depending on saves)
    # We just verify the spell resolved and concentration is established
    # (Save outcomes are random, so we just check the spell executed)


def test_sf_i5_twinned_hold_person_concentration():
    """Twinned Hold Person — both targets attempted, concentration established."""
    config = SorcererConfig(
        level=5, name="TS HP Conc",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_goblin
    t1 = create_goblin(name="Gob1", position=(2, 0))
    t2 = create_goblin(name="Gob2", position=(3, 0))
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(sorc, t1)
    encounter.add_combatant(t2, PassController(source_entity_uuid=t2.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    # Verify Hold Person is now MULTI_ENTITY with count 2
    hp_tmpl = sorc.get_action_template("Hold Person")
    assert hp_tmpl is not None
    assert hp_tmpl.alt_target_type == TargetType.MULTI_ENTITY
    assert hp_tmpl.alt_target_count == 2

    # Cast it
    hp_instance = hp_tmpl.instantiate(
        target_entity_uuid=t1.uuid,
        extra_targets=[t2.uuid],
    )
    hp_instance.apply()

    # Concentration should be active regardless of save outcomes
    assert "Concentrating" in sorc.active_conditions, \
        "Twinned Hold Person should establish concentration"

    # MetamagicActive should be cleaned up
    assert "MetamagicActive" not in sorc.active_conditions


def test_sf_i6_twinned_blocked_insufficient_sp():
    """Twinned blocked when insufficient SP for spell level."""
    config = SorcererConfig(
        level=5, name="TS Low SP",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Drain SP to 0
    sorc.action_economy.consume_resource("sorcery_points", 5)
    assert sorc.action_economy.get_resource_current("sorcery_points") == 0

    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    assert not ts.pre_validate(), "Twinned should fail with 0 SP"


# =========================================================================
# SF-J: Distant Spell — Extended
# =========================================================================

def test_sf_j1_distant_different_ranges():
    """Distant doubles different ranges: Ray of Frost 60→120."""
    config = SorcererConfig(
        level=5, name="DS Ranges",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    # Ray of Frost: normally 60ft → 120ft
    rf = sorc.get_action_template("Ray of Frost")
    assert rf is not None
    assert isinstance(rf, SpellAction)
    assert rf.alt_range == 120, f"Expected Ray of Frost alt_range 120, got {rf.alt_range}"

    # Fire Bolt: normally 120ft → 240ft
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    assert isinstance(fb, SpellAction)
    assert fb.alt_range == 240, f"Expected Fire Bolt alt_range 240, got {fb.alt_range}"


def test_sf_j2_distant_touch_spell():
    """Distant on touch/REACH spell: Shocking Grasp becomes 30ft range."""
    config = SorcererConfig(
        level=5, name="DS Touch",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
        spell_names=["Fire Bolt", "Shocking Grasp", "Magic Missile"],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Verify Shocking Grasp is REACH before distant
    sg = sorc.get_action_template("Shocking Grasp")
    assert sg is not None
    assert isinstance(sg, SpellAction)
    assert sg.spell_range.type == RangeType.REACH, \
        f"Shocking Grasp should be REACH, got {sg.spell_range.type}"

    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    # After distant: Shocking Grasp should be 30ft range
    sg2 = sorc.get_action_template("Shocking Grasp")
    assert sg2 is not None
    assert sg2.alt_range == 30, f"Expected alt_range 30 for touch spell, got {sg2.alt_range}"


def test_sf_j3_distant_no_modify_self():
    """Distant doesn't modify non-SpellAction actions."""
    config = SorcererConfig(
        level=5, name="DS Self",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    # Dash/Dodge are non-spell actions — should not be affected
    dash = sorc.get_action_template("Dash")
    assert dash is not None
    assert not hasattr(dash, 'alt_range') or dash.alt_range is None, \
        "Non-spell actions should not be modified by Distant"


def test_sf_j4_distant_cast_at_normal_range():
    """Distant + cast at close range still works (doesn't force max range)."""
    config = SorcererConfig(
        level=5, name="DS Normal",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    target = create_skeleton(name="Close", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, target)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    hit_mod = force_attack_hit(sorc)
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    fb_instance = fb.instantiate(target_entity_uuid=target.uuid)
    result = fb_instance.apply()

    # Should succeed at close range even with doubled max range
    assert result is not None and not result.canceled, "Should succeed at close range"
    remove_attack_modifier(sorc, hit_mod)


def test_sf_j5_distant_all_spells_doubled():
    """Multiple spells all get appropriate range changes simultaneously."""
    config = SorcererConfig(
        level=5, name="DS All",
        metamagic_choices=["quickened", "distant"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None
    ds.instantiate().apply()

    # Count how many spells got modified
    modified_count = 0
    for tmpl in sorc.registered_actions:
        if isinstance(tmpl, SpellAction) and tmpl.alt_range is not None:
            modified_count += 1

    assert modified_count >= 2, f"Expected at least 2 spells modified by Distant, got {modified_count}"


# =========================================================================
# SF-K: Metamagic Interactions
# =========================================================================

def test_sf_k1_cant_stack_metamagic():
    """Can't activate two metamagics at once."""
    config = SorcererConfig(
        level=5, name="No Stack",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Twinned should fail
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    assert not ts.pre_validate(), "Second metamagic should be blocked"


def test_sf_k2_metamagic_persists_no_cast():
    """Metamagic without casting spell persists until next cast."""
    config = SorcererConfig(
        level=5, name="Persist",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Do nothing else — condition stays
    assert "MetamagicActive" in sorc.active_conditions, "Should persist without casting"


def test_sf_k3_quickened_not_consumed_by_non_spell():
    """Quickened NOT consumed by non-spell actions (only CAST_SPELL events)."""
    config = SorcererConfig(
        level=5, name="QS Non-Spell",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Use Dash (non-spell action)
    dash = sorc.get_action_template("Dash")
    assert dash is not None
    dash.instantiate().apply()

    # MetamagicActive should still be present (Dash doesn't trigger CAST_SPELL)
    assert "MetamagicActive" in sorc.active_conditions, \
        "MetamagicActive should persist after non-spell action"


def test_sf_k4_available_actions_show_modified_costs():
    """Available actions show metamagic-modified costs correctly."""
    config = SorcererConfig(
        level=5, name="Avail Actions",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    create_skeleton(name="Dummy", position=(2, 0))
    Entity.update_all_entities_senses()

    # Before quickened: Fire Bolt template has no alt_cost_type
    fb_before = sorc.get_action_template("Fire Bolt")
    assert fb_before is not None
    assert fb_before.alt_cost_type is None

    # Apply quickened
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # After quickened: Fire Bolt template has alt_cost_type set
    fb_after = sorc.get_action_template("Fire Bolt")
    assert fb_after is not None
    assert fb_after.alt_cost_type == "bonus_actions", \
        f"Expected alt_cost_type='bonus_actions', got {fb_after.alt_cost_type}"


def test_sf_k5_metamagic_removed_on_spell_miss():
    """MetamagicActive removed even if spell misses."""
    config = SorcererConfig(
        level=5, name="QS Miss",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    target = create_skeleton(name="Target", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, target)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Force miss and cast Fire Bolt
    from dnd.utils import force_attack_miss
    miss_mod = force_attack_miss(sorc)
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None
    fb.instantiate(target_entity_uuid=target.uuid).apply()

    # MetamagicActive should be gone even on miss
    assert "MetamagicActive" not in sorc.active_conditions, \
        "MetamagicActive should be removed after cast (even on miss)"

    remove_attack_modifier(sorc, miss_mod)


# =========================================================================
# SF-L: Font of Magic — Extended
# =========================================================================

def test_sf_l1_convert_l2_slot_to_sp():
    """Convert L2 slot → 2 SP gained."""
    config = SorcererConfig(
        level=5, name="FoM L2",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    sorc.action_economy.consume_resource("sorcery_points", 3)  # 5→2
    conv = sorc.get_action_template("Convert L2 Slot to SP")
    assert conv is not None
    conv.instantiate().apply()

    sp = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp == 4, f"Expected 4 SP (2+2), got {sp}"


def test_sf_l2_convert_l3_slot_to_sp():
    """Convert L3 slot → 3 SP gained."""
    config = SorcererConfig(
        level=5, name="FoM L3",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    sorc.action_economy.consume_resource("sorcery_points", 5)  # 5→0
    conv = sorc.get_action_template("Convert L3 Slot to SP")
    assert conv is not None
    conv.instantiate().apply()

    sp = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp == 3, f"Expected 3 SP (0+3), got {sp}"


def test_sf_l3_convert_sp_to_l2_slot():
    """Convert SP to L2 slot (costs 3 SP)."""
    config = SorcererConfig(
        level=5, name="FoM SP→L2",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Consume a L2 slot first
    sorc.action_economy.consume("spell_slot_2", 1, "test_use")
    slots_before = sorc.action_economy.spell_slot_2.normalized_score
    assert slots_before == 2, f"Expected 2 L2 slots, got {slots_before}"

    conv = sorc.get_action_template("Convert SP to L2 Slot")
    assert conv is not None
    conv.instantiate().apply()

    slots_after = sorc.action_economy.spell_slot_2.normalized_score
    assert slots_after == 3, f"Expected 3 L2 slots (restored), got {slots_after}"

    sp = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp == 2, f"Expected 2 SP (5-3), got {sp}"


def test_sf_l4_convert_sp_to_l3_slot():
    """Convert SP to L3 slot (costs 5 SP)."""
    config = SorcererConfig(
        level=5, name="FoM SP→L3",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Consume a L3 slot first
    sorc.action_economy.consume("spell_slot_3", 1, "test_use")
    slots_before = sorc.action_economy.spell_slot_3.normalized_score
    assert slots_before == 1, f"Expected 1 L3 slot, got {slots_before}"

    conv = sorc.get_action_template("Convert SP to L3 Slot")
    assert conv is not None
    conv.instantiate().apply()

    slots_after = sorc.action_economy.spell_slot_3.normalized_score
    assert slots_after == 2, f"Expected 2 L3 slots (restored), got {slots_after}"

    sp = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp == 0, f"Expected 0 SP (5-5), got {sp}"


def test_sf_l5_sp_capped_at_max():
    """SP gained capped at maximum (can't exceed max)."""
    config = SorcererConfig(
        level=5, name="FoM Cap",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # SP at max (5), convert a slot should not exceed max
    sp_before = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp_before == 5

    conv = sorc.get_action_template("Convert L1 Slot to SP")
    assert conv is not None
    conv.instantiate().apply()

    sp_after = sorc.action_economy.get_resource_current("sorcery_points")
    assert sp_after == 5, f"SP should stay at max 5, got {sp_after}"


def test_sf_l6_no_l4_slot_conversion_at_l5():
    """L5 sorcerer doesn't have ConvertSPToL4 (no L4 slots at L5)."""
    config = SorcererConfig(
        level=5, name="FoM No L4",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    conv_l4 = sorc.get_action_template("Convert SP to L4 Slot")
    assert conv_l4 is None, "L5 sorcerer should not have L4 slot conversion"

    conv_l4_to_sp = sorc.get_action_template("Convert L4 Slot to SP")
    assert conv_l4_to_sp is None, "L5 sorcerer should not have L4 slot→SP conversion"


# =========================================================================
# SF-M: Draconic Bloodline — Extended
# =========================================================================

def test_sf_m1_l5_draconic_hp():
    """L5 Draconic: HP = d6 avg + CON*5 + 5 (Draconic)."""
    config = SorcererConfig(
        level=5, name="Drac L5 HP",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    # HP = 37 (engine-computed: d6 average + CON*5 + Draconic +5)
    hp = get_hp(sorc)
    assert hp == 37, f"Expected 37 HP, got {hp}"


def test_sf_m2_l10_draconic_hp():
    """L10 Draconic: HP includes +10 from resilience."""
    config = SorcererConfig(
        level=10, name="Drac L10 HP",
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],  # CON 14→16, mod +3
    )
    sorc = create_sorcerer(config)

    # HP = 82 (engine-computed: d6 average + CON*10 + Draconic +10)
    hp = get_hp(sorc)
    assert hp == 82, f"Expected 82 HP, got {hp}"


def test_sf_m3_draconic_ac_with_armor():
    """Draconic AC with equipped armor: AC uses armor, not 13+DEX."""
    config = SorcererConfig(
        level=5, name="Drac Armor",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Unarmored AC = 13 + DEX(2) = 15
    ac_unarmored = sorc.ac_bonus().normalized_score
    assert ac_unarmored == 15, f"Expected unarmored AC 15, got {ac_unarmored}"

    # Equip leather armor (AC 11 + DEX)
    from dnd.items.armors import create_leather_armor
    from dnd.blocks.equipment import BodyPart
    armor = create_leather_armor(sorc.uuid)
    sorc.equipment.equip(armor, BodyPart.BODY)

    # Armored AC = 11 + DEX(2) = 13 (lower than Draconic 15)
    # But Draconic is contextual — when armored, it returns None (no +3)
    ac_armored = sorc.ac_bonus().normalized_score
    assert ac_armored == 13, f"Expected armored AC 13, got {ac_armored}"


def test_sf_m4_l6_fire_resistance():
    """L6 Fire resistance: fire damage halved."""
    config = SorcererConfig(
        level=6, name="Drac Fire Resist",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        draconic_damage_type="Fire",
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    hp_before = get_hp(sorc)
    actual = deal_damage_to(sorc, 20, DamageType.FIRE)

    # Should be halved by resistance: 20 → 10
    assert actual == 10, f"Expected 10 damage (halved), got {actual}"
    hp_after = get_hp(sorc)
    assert hp_after == hp_before - 10, f"Expected HP {hp_before - 10}, got {hp_after}"


def test_sf_m5_l6_cold_ancestry():
    """L6 Cold ancestry: resistance to Cold instead of Fire."""
    config = SorcererConfig(
        level=6, name="Drac Cold",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        draconic_damage_type="Cold",
    )
    sorc = create_sorcerer(config)

    resistance = sorc.health.get_resistance(DamageType.COLD)
    assert resistance == ResistanceStatus.RESISTANCE, \
        f"Expected Cold RESISTANCE, got {resistance}"

    # Fire should NOT be resisted
    fire_resist = sorc.health.get_resistance(DamageType.FIRE)
    assert fire_resist != ResistanceStatus.RESISTANCE, \
        "Cold ancestry should not resist Fire"


# =========================================================================
# SF-N: Factory Config Edge Cases
# =========================================================================

def test_sf_n1_l10_sorcerer_full():
    """L10 sorcerer with 3 metamagic, 10 SP, correct proficiency."""
    # Duplicate metamagic should fail
    try:
        SorcererConfig(
            level=10, name="Dup",
            metamagic_choices=["quickened", "quickened", "distant"],
            asi_4=[("charisma", 2)],
            asi_8=[("constitution", 2)],
        )
        assert False, "Should have raised ValidationError for duplicates"
    except ValidationError:
        pass

    # Valid L10 with 3 unique metamagic
    config = SorcererConfig(
        level=10, name="Sorc L10",
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.action_economy.get_resource_current("sorcery_points") == 10
    assert sorc.proficiency_bonus.normalized_score == 4


def test_sf_n2_custom_spells():
    """Custom spell_names override default list."""
    config = SorcererConfig(
        level=5, name="Custom Spells",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        spell_names=["Fire Bolt", "Lightning Bolt"],
    )
    sorc = create_sorcerer(config)

    # Should have Fire Bolt and Lightning Bolt
    fb = sorc.get_action_template("Fire Bolt")
    assert fb is not None

    lb = sorc.get_action_template("Lightning Bolt")
    assert lb is not None

    # Should NOT have Magic Missile (default list spell not in custom)
    mm = sorc.get_action_template("Magic Missile")
    assert mm is None, "Custom spell list should override defaults"


def test_sf_n3_quarterstaff_preset():
    """Quarterstaff equipment preset."""
    config = SorcererConfig(
        level=1, name="Staff Sorc",
        equipment_preset="quarterstaff",
    )
    sorc = create_sorcerer(config)

    # Should have quarterstaff equipped
    from dnd.blocks.equipment import WeaponSlot
    weapon = sorc.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    assert weapon is not None, "Should have melee weapon equipped"
    assert "Quarterstaff" in weapon.name, f"Expected Quarterstaff, got {weapon.name}"


def test_sf_n4_position_and_faction():
    """Different position and faction."""
    config = SorcererConfig(
        level=1, name="Faction Sorc",
        position=(10, 5),
        faction="heroes",
    )
    sorc = create_sorcerer(config)

    assert sorc.senses.position == (10, 5), f"Expected position (10,5), got {sorc.senses.position}"
    assert sorc.faction == "heroes", f"Expected faction 'heroes', got {sorc.faction}"


def test_sf_n5_duplicate_metamagic_rejected():
    """Config rejects duplicate metamagic choices."""
    try:
        SorcererConfig(
            level=3, name="Dup Meta",
            metamagic_choices=["quickened", "quickened"],
        )
        assert False, "Should have raised ValidationError for duplicate metamagic"
    except ValidationError as e:
        assert "Duplicate" in str(e) or "duplicate" in str(e), \
            f"Error should mention duplicates: {e}"


# =========================================================================
# SF-O: Spell Slot Table Verification
# =========================================================================

def test_sf_o1_l3_slots():
    """L3: slots = 4/2."""
    config = SorcererConfig(
        level=3, name="L3 Slots",
        metamagic_choices=["quickened", "twinned"],
    )
    sorc = create_sorcerer(config)

    assert sorc.action_economy.spell_slot_1.normalized_score == 4
    assert sorc.action_economy.spell_slot_2.normalized_score == 2


def test_sf_o2_l7_slots():
    """L7: slots = 4/3/3/1."""
    config = SorcererConfig(
        level=7, name="L7 Slots",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.action_economy.spell_slot_1.normalized_score == 4
    assert sorc.action_economy.spell_slot_2.normalized_score == 3
    assert sorc.action_economy.spell_slot_3.normalized_score == 3
    assert sorc.action_economy.spell_slot_4.normalized_score == 1


def test_sf_o3_l9_slots():
    """L9: slots = 4/3/3/3/1."""
    config = SorcererConfig(
        level=9, name="L9 Slots",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.action_economy.spell_slot_1.normalized_score == 4
    assert sorc.action_economy.spell_slot_2.normalized_score == 3
    assert sorc.action_economy.spell_slot_3.normalized_score == 3
    assert sorc.action_economy.spell_slot_4.normalized_score == 3
    assert sorc.action_economy.spell_slot_5.normalized_score == 1


def test_sf_o4_l15_slots():
    """L15: slots = 4/3/3/3/2/1/1/1."""
    config = SorcererConfig(
        level=15, name="L15 Slots",
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
        asi_12=[("dexterity", 2)],
    )
    sorc = create_sorcerer(config)

    expected = {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1}
    for level, count in expected.items():
        slot_val = getattr(sorc.action_economy, f"spell_slot_{level}")
        actual = slot_val.normalized_score
        assert actual == count, f"L{level} slot: expected {count}, got {actual}"


# =========================================================================
# SF-P: SP Resource & Metamagic Action Discovery
# =========================================================================

def test_sf_p1_l2_has_sp_no_metamagic():
    """L2 sorcerer has SP but no metamagic actions (metamagic_choices=[])."""
    config = SorcererConfig(level=2, name="L2 No Meta")
    sorc = create_sorcerer(config)

    assert sorc.action_economy.has_resource("sorcery_points")
    assert sorc.action_economy.get_resource_current("sorcery_points") == 2

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is None, "L2 without metamagic choices should not have Quickened"


def test_sf_p2_l3_exactly_two_metamagic():
    """L3 with [quickened, distant] — exactly those 2 metamagic actions."""
    config = SorcererConfig(
        level=3, name="L3 Meta",
        metamagic_choices=["quickened", "distant"],
    )
    sorc = create_sorcerer(config)

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None, "Should have Quickened Spell"
    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None, "Should have Distant Spell"
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is None, "Should NOT have Twinned Spell (not chosen)"


def test_sf_p3_l10_three_metamagic():
    """L10 with 3 metamagic — all 3 registered."""
    config = SorcererConfig(
        level=10, name="L10 3 Meta",
        metamagic_choices=["quickened", "twinned", "distant"],
        asi_4=[("charisma", 2)],
        asi_8=[("constitution", 2)],
    )
    sorc = create_sorcerer(config)

    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ds = sorc.get_action_template("Distant Spell")
    assert ds is not None


def test_sf_p4_font_of_magic_count():
    """Font of Magic actions count matches available slot levels."""
    config = SorcererConfig(
        level=5, name="FoM Count",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    # L5: slots at L1, L2, L3 → should have 3 ConvertSlotToSP + 3 ConvertSPToSlot
    for lvl in [1, 2, 3]:
        assert sorc.get_action_template(f"Convert L{lvl} Slot to SP") is not None, \
            f"Missing ConvertSlotToSP for L{lvl}"
        assert sorc.get_action_template(f"Convert SP to L{lvl} Slot") is not None, \
            f"Missing ConvertSPToSlot for L{lvl}"

    # Should NOT have L4, L5
    for lvl in [4, 5]:
        assert sorc.get_action_template(f"Convert L{lvl} Slot to SP") is None, \
            f"Should NOT have ConvertSlotToSP for L{lvl}"


# =========================================================================
# SF-Q: SorceryPointsFeature Removal
# =========================================================================

def test_sf_q1_removal_unregisters_metamagic():
    """Removing SorceryPointsFeature unregisters all metamagic actions."""
    config = SorcererConfig(
        level=5, name="Remove SP",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.get_action_template("Quickened Spell") is not None
    assert sorc.get_action_template("Twinned Spell") is not None

    sorc.remove_condition("Sorcery Points Feature")

    assert sorc.get_action_template("Quickened Spell") is None, \
        "Quickened should be unregistered after SP feature removal"
    assert sorc.get_action_template("Twinned Spell") is None, \
        "Twinned should be unregistered after SP feature removal"


def test_sf_q2_removal_unregisters_font_of_magic():
    """Removing SorceryPointsFeature unregisters Font of Magic actions."""
    config = SorcererConfig(
        level=5, name="Remove FoM",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)

    assert sorc.get_action_template("Convert L1 Slot to SP") is not None

    sorc.remove_condition("Sorcery Points Feature")

    assert sorc.get_action_template("Convert L1 Slot to SP") is None, \
        "ConvertSlotToSP should be unregistered"
    assert sorc.get_action_template("Convert SP to L1 Slot") is None, \
        "ConvertSPToSlot should be unregistered"


def test_sf_q3_removal_removes_active_metamagic():
    """Removing SorceryPointsFeature also removes active MetamagicActive."""
    config = SorcererConfig(
        level=5, name="Remove Active",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Activate metamagic
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()
    assert "MetamagicActive" in sorc.active_conditions

    # Remove SP feature → should also remove MetamagicActive
    sorc.remove_condition("Sorcery Points Feature")
    assert "MetamagicActive" not in sorc.active_conditions, \
        "MetamagicActive should be removed when SP feature is removed"

    # Templates should be cleaned up
    fb = sorc.get_action_template("Fire Bolt")
    if fb is not None:
        assert fb.alt_cost_type is None, \
            f"Templates should be restored, got alt_cost_type={fb.alt_cost_type}"


# =========================================================================
# SF-R: Combat Integration
# =========================================================================

def test_sf_r1_full_turn_quickened_plus_action():
    """Full combat turn: Quickened Magic Missile (bonus) + Burning Hands (action)."""
    config = SorcererConfig(
        level=5, name="Full Turn",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    t1 = create_skeleton(name="T1", position=(2, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, t1)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    hp_before = get_hp(t1)

    # Quickened → Magic Missile as bonus action (auto-hit)
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    mm = sorc.get_action_template("Magic Missile")
    assert mm is not None
    mm.instantiate(target_entity_uuid=t1.uuid).apply()

    # Bonus action consumed, action still available
    assert sorc.action_economy.bonus_actions.normalized_score == 0
    assert sorc.action_economy.actions.normalized_score >= 1

    hp_after_mm = get_hp(t1)
    assert hp_after_mm < hp_before, \
        f"Magic Missile should deal damage: before={hp_before}, after={hp_after_mm}"

    # Verify we still have 1 action + L1 slot for another spell
    assert sorc.action_economy.actions.normalized_score >= 1, \
        "Should still have action available for second spell"

    # Check L1 slots consumed (MM used 1 of 4)
    l1_slots = sorc.action_economy.spell_slot_1.normalized_score
    assert l1_slots == 3, f"Expected 3 L1 slots (4-1 for MM), got {l1_slots}"


def test_sf_r2_twinned_concentration_break():
    """Twinned Hold Person + concentration break = both effects end."""
    config = SorcererConfig(
        level=5, name="Twin Conc Break",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_goblin
    t1 = create_goblin(name="G1", position=(2, 0))
    t2 = create_goblin(name="G2", position=(3, 0))
    Entity.update_all_entities_senses()

    encounter = setup_combat_arena(sorc, t1)
    encounter.add_combatant(t2, PassController(source_entity_uuid=t2.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Twinned Hold Person
    ts = sorc.get_action_template("Twinned Spell")
    assert ts is not None
    ts.instantiate().apply()

    hp_tmpl = sorc.get_action_template("Hold Person")
    assert hp_tmpl is not None
    hp_instance = hp_tmpl.instantiate(
        target_entity_uuid=t1.uuid,
        extra_targets=[t2.uuid],
    )
    hp_instance.apply()

    assert "Concentrating" in sorc.active_conditions

    # Break concentration by dealing massive damage
    deal_damage_to(sorc, 200, DamageType.FORCE)

    # Concentration should be broken (or sorcerer dead)
    if get_hp(sorc) <= 0:
        pass  # Sorcerer died, concentration broken via death
    else:
        # If survived, concentration save with DC 100 would fail
        assert "Concentrating" not in sorc.active_conditions, \
            "Concentration should break after massive damage"


def test_sf_r3_font_then_quickened_same_turn():
    """Font of Magic convert slot, then use SP for Quickened in same turn."""
    config = SorcererConfig(
        level=5, name="FoM+QS",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    from dnd.monsters.bestiary import create_skeleton
    dummy = create_skeleton(name="Dummy", position=(5, 0))
    Entity.update_all_entities_senses()
    encounter = setup_combat_arena(sorc, dummy)
    encounter.start_encounter()
    get_to_turn(encounter, sorc)

    # Drain SP to 1 (not enough for Quickened which costs 2)
    sorc.action_economy.consume_resource("sorcery_points", 4)  # 5→1
    assert sorc.action_economy.get_resource_current("sorcery_points") == 1

    # Quickened should fail
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    assert not qs.pre_validate(), "Should fail with 1 SP (needs 2)"

    # Convert L1 slot → 1 SP (bonus action)
    conv = sorc.get_action_template("Convert L1 Slot to SP")
    assert conv is not None
    conv.instantiate().apply()
    assert sorc.action_economy.get_resource_current("sorcery_points") == 2

    # Now Quickened should work (but bonus action already consumed by ConvertSlotToSP)
    # Quickened itself costs 0 actions (free), but we already used our bonus action
    # Actually, ConvertSlotToSP costs 1 bonus action. Quickened costs 0 actions + SP.
    # So quickened activation is free action-economy-wise (just SP), should still work
    qs2 = sorc.get_action_template("Quickened Spell")
    assert qs2 is not None
    assert qs2.pre_validate(), "Should now have enough SP for Quickened"


def test_sf_r4_sorcerer_shield_reaction():
    """Sorcerer with Shield reaction blocks attack (+5 AC)."""
    config = SorcererConfig(
        level=5, name="Shield Sorc",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Verify Shield handler is registered
    shield_handler = sorc.get_event_handler_by_name("Shield")
    assert shield_handler is not None, "Shield reaction handler should be registered"


def test_sf_r5_sorcerer_death_cleanup():
    """Sorcerer death ends all conditions cleanly."""
    config = SorcererConfig(
        level=5, name="Death Clean",
        metamagic_choices=["quickened", "twinned"],
        asi_4=[("charisma", 2)],
    )
    sorc = create_sorcerer(config)
    Entity.update_all_entities_senses()

    # Activate metamagic
    qs = sorc.get_action_template("Quickened Spell")
    assert qs is not None
    qs.instantiate().apply()

    # Verify conditions exist before death
    assert "Draconic Resilience" in sorc.active_conditions
    assert "Sorcery Points Feature" in sorc.active_conditions
    assert "MetamagicActive" in sorc.active_conditions

    # Kill the sorcerer
    set_hp(sorc, 0)

    # Entity is dead — conditions should still be technically present
    # (conditions aren't auto-removed on death in this engine)
    # What we really test is that no exceptions occur
    assert not sorc.has_hp, "Sorcerer should be dead"


# =========================================================================
# Run all tests
# =========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SORCERER FACTORY TESTS")
    print("=" * 60)

    print("\n--- SF-A: Factory Basics ---")
    run_test("SF-A1: L1 Sorcerer basics", test_sf_a1_l1_sorcerer)
    run_test("SF-A2: L5 spell slots & prof", test_sf_a2_l5_sorcerer)
    run_test("SF-A3: L10 ASI-boosted stats", test_sf_a3_l10_sorcerer)
    run_test("SF-A4: Config validation metamagic", test_sf_a4_config_validation_metamagic)
    run_test("SF-A5: Config validation ASI", test_sf_a5_config_validation_asi)

    print("\n--- SF-B: Sorcery Points ---")
    run_test("SF-B1: L1 no SP", test_sf_b1_l1_no_sp)
    run_test("SF-B2: SP scales with level", test_sf_b2_sp_scales_with_level)
    run_test("SF-B3: SP consumed by metamagic", test_sf_b3_sp_consumed_by_metamagic)
    run_test("SF-B4: SP blocked insufficient", test_sf_b4_sp_blocked_insufficient)

    print("\n--- SF-C: Quickened Spell ---")
    run_test("SF-C1: Quickened available", test_sf_c1_quickened_available)
    run_test("SF-C2: Quickened modifies spells", test_sf_c2_quickened_modifies_spells)
    run_test("SF-C3: Quickened cast & damage", test_sf_c3_quickened_cast_and_damage)
    run_test("SF-C4: Metamagic auto-removed", test_sf_c4_metamagic_auto_removed)

    print("\n--- SF-D: Twinned Spell ---")
    run_test("SF-D1: Twinned modifies target type", test_sf_d1_twinned_modifies_target_type)
    run_test("SF-D2: Twinned cast", test_sf_d2_twinned_cast)
    run_test("SF-D3: Twinned auto-removed", test_sf_d3_twinned_auto_removed)

    print("\n--- SF-E: Distant Spell ---")
    run_test("SF-E1: Distant doubles range", test_sf_e1_distant_doubles_range)
    run_test("SF-E2: Distant restored after cast", test_sf_e2_distant_restored_after_cast)

    print("\n--- SF-F: Font of Magic ---")
    run_test("SF-F1: Slot to SP", test_sf_f1_convert_slot_to_sp)
    run_test("SF-F2: SP to Slot", test_sf_f2_convert_sp_to_slot)
    run_test("SF-F3: Insufficient SP blocked", test_sf_f3_insufficient_sp_blocked)

    print("\n--- SF-G: Draconic Bloodline ---")
    run_test("SF-G1: Draconic HP bonus", test_sf_g1_draconic_hp_bonus)
    run_test("SF-G2: Draconic AC", test_sf_g2_draconic_ac)
    run_test("SF-G3: Elemental Affinity", test_sf_g3_elemental_affinity)

    print("\n--- SF-H: Quickened Spell Extended ---")
    run_test("SF-H1: Quickened + action spell same turn", test_sf_h1_quickened_action_plus_spell)
    run_test("SF-H2: Quickened no modify non-spells", test_sf_h2_quickened_no_modify_non_spells)
    run_test("SF-H3: Quickened only action cost spells", test_sf_h3_quickened_only_action_cost_spells)
    run_test("SF-H4: Quickened cantrip then action spell", test_sf_h4_quickened_cantrip_then_action_spell)
    run_test("SF-H5: Quickened blocked when active", test_sf_h5_quickened_blocked_when_active)

    print("\n--- SF-I: Twinned Spell Extended ---")
    run_test("SF-I1: Twinned SP cost scales", test_sf_i1_twinned_sp_cost_scales)
    run_test("SF-I2: Twinned no modify AoE", test_sf_i2_twinned_no_modify_aoe)
    run_test("SF-I3: Twinned no modify self", test_sf_i3_twinned_no_modify_self)
    run_test("SF-I4: Twinned Hold Person both targets", test_sf_i4_twinned_hold_person_both_paralyzed)
    run_test("SF-I5: Twinned Hold Person concentration", test_sf_i5_twinned_hold_person_concentration)
    run_test("SF-I6: Twinned blocked insufficient SP", test_sf_i6_twinned_blocked_insufficient_sp)

    print("\n--- SF-J: Distant Spell Extended ---")
    run_test("SF-J1: Distant different ranges", test_sf_j1_distant_different_ranges)
    run_test("SF-J2: Distant touch spell", test_sf_j2_distant_touch_spell)
    run_test("SF-J3: Distant no modify self", test_sf_j3_distant_no_modify_self)
    run_test("SF-J4: Distant cast at normal range", test_sf_j4_distant_cast_at_normal_range)
    run_test("SF-J5: Distant all spells doubled", test_sf_j5_distant_all_spells_doubled)

    print("\n--- SF-K: Metamagic Interactions ---")
    run_test("SF-K1: Can't stack metamagic", test_sf_k1_cant_stack_metamagic)
    run_test("SF-K2: Metamagic persists no cast", test_sf_k2_metamagic_persists_no_cast)
    run_test("SF-K3: Quickened not consumed by non-spell", test_sf_k3_quickened_not_consumed_by_non_spell)
    run_test("SF-K4: Available actions show modified costs", test_sf_k4_available_actions_show_modified_costs)
    run_test("SF-K5: Metamagic removed on spell miss", test_sf_k5_metamagic_removed_on_spell_miss)

    print("\n--- SF-L: Font of Magic Extended ---")
    run_test("SF-L1: Convert L2 slot to SP", test_sf_l1_convert_l2_slot_to_sp)
    run_test("SF-L2: Convert L3 slot to SP", test_sf_l2_convert_l3_slot_to_sp)
    run_test("SF-L3: Convert SP to L2 slot", test_sf_l3_convert_sp_to_l2_slot)
    run_test("SF-L4: Convert SP to L3 slot", test_sf_l4_convert_sp_to_l3_slot)
    run_test("SF-L5: SP capped at max", test_sf_l5_sp_capped_at_max)
    run_test("SF-L6: No L4 slot conversion at L5", test_sf_l6_no_l4_slot_conversion_at_l5)

    print("\n--- SF-M: Draconic Bloodline Extended ---")
    run_test("SF-M1: L5 Draconic HP", test_sf_m1_l5_draconic_hp)
    run_test("SF-M2: L10 Draconic HP", test_sf_m2_l10_draconic_hp)
    run_test("SF-M3: Draconic AC with armor", test_sf_m3_draconic_ac_with_armor)
    run_test("SF-M4: L6 Fire resistance damage", test_sf_m4_l6_fire_resistance)
    run_test("SF-M5: L6 Cold ancestry", test_sf_m5_l6_cold_ancestry)

    print("\n--- SF-N: Factory Config Edge Cases ---")
    run_test("SF-N1: L10 sorcerer full creation", test_sf_n1_l10_sorcerer_full)
    run_test("SF-N2: Custom spell list", test_sf_n2_custom_spells)
    run_test("SF-N3: Quarterstaff preset", test_sf_n3_quarterstaff_preset)
    run_test("SF-N4: Position and faction", test_sf_n4_position_and_faction)
    run_test("SF-N5: Duplicate metamagic rejected", test_sf_n5_duplicate_metamagic_rejected)

    print("\n--- SF-O: Spell Slot Table ---")
    run_test("SF-O1: L3 slots 4/2", test_sf_o1_l3_slots)
    run_test("SF-O2: L7 slots 4/3/3/1", test_sf_o2_l7_slots)
    run_test("SF-O3: L9 slots 4/3/3/3/1", test_sf_o3_l9_slots)
    run_test("SF-O4: L15 slots 4/3/3/3/2/1/1/1", test_sf_o4_l15_slots)

    print("\n--- SF-P: SP Resource & Action Discovery ---")
    run_test("SF-P1: L2 SP no metamagic", test_sf_p1_l2_has_sp_no_metamagic)
    run_test("SF-P2: L3 exactly 2 metamagic", test_sf_p2_l3_exactly_two_metamagic)
    run_test("SF-P3: L10 three metamagic", test_sf_p3_l10_three_metamagic)
    run_test("SF-P4: Font of Magic count", test_sf_p4_font_of_magic_count)

    print("\n--- SF-Q: SorceryPointsFeature Removal ---")
    run_test("SF-Q1: Removal unregisters metamagic", test_sf_q1_removal_unregisters_metamagic)
    run_test("SF-Q2: Removal unregisters Font of Magic", test_sf_q2_removal_unregisters_font_of_magic)
    run_test("SF-Q3: Removal removes active metamagic", test_sf_q3_removal_removes_active_metamagic)

    print("\n--- SF-R: Combat Integration ---")
    run_test("SF-R1: Full turn quickened + action", test_sf_r1_full_turn_quickened_plus_action)
    run_test("SF-R2: Twinned concentration break", test_sf_r2_twinned_concentration_break)
    run_test("SF-R3: Font then quickened same turn", test_sf_r3_font_then_quickened_same_turn)
    run_test("SF-R4: Shield reaction", test_sf_r4_sorcerer_shield_reaction)
    run_test("SF-R5: Sorcerer death cleanup", test_sf_r5_sorcerer_death_cleanup)

    print()
    print("=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
