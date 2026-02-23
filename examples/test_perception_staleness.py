#!/usr/bin/env python
"""
Test perception staleness system.

Tests that when an observer's perception capabilities change (via condition),
the senses system automatically detects the change and re-evaluates cached senses.

Tests:
H. Stealth System — Observer Perception Changes
I. Hazard System — Observer Perception Changes
J. Combat Logs for Perception Events
K. Edge Cases
"""

from typing import Any, List, Optional, Tuple
from uuid import UUID, uuid4

from dnd.utils import reset_combat_state
from dnd.core.gridmap import get_map, reset_map
from dnd.core.base_conditions import BaseCondition, ConditionCategory, HazardFilter
from dnd.core.base_block import BaseBlock, SensesType, SenseMode, LightLevel
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.modifiers import NumericalModifier
from dnd.core.combat_log import CombatLogEntryType
from dnd.entity import Entity
from dnd.monsters.bestiary import create_skeleton
from dnd.conditions import Hidden, Invisible
from dnd.encounter import Encounter
from dnd.controller import PassController


passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} {detail}")


def setup_arena(size: int = 15):
    """Set up a simple floor arena."""
    reset_map()
    grid = get_map()
    for x in range(size):
        for y in range(size):
            grid.set_tile(x, y, walkable=True, name="Floor")
    return grid


# =============================================================================
# Test conditions that modify perception
# =============================================================================

class PerceptionBoostCondition(BaseCondition):
    """Test condition that boosts perception skill by a given amount."""
    name: str = "Perception Boost"
    boost_amount: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None
        outs: List[Tuple[UUID, UUID]] = []

        skill = target.skill_set.get_skill("perception")
        mod_uuid = skill.skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Perception Boost",
                value=self.boost_amount
            )
        )
        outs.append((skill.skill_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        return outs, [], [], [], effect_event


class PerceptionDebuffCondition(BaseCondition):
    """Test condition that reduces perception skill by a given amount."""
    name: str = "Perception Debuff"
    debuff_amount: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None
        outs: List[Tuple[UUID, UUID]] = []

        skill = target.skill_set.get_skill("perception")
        mod_uuid = skill.skill_bonus.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=self.source_entity_uuid,
                name="Perception Debuff",
                value=-self.debuff_amount
            )
        )
        outs.append((skill.skill_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        return outs, [], [], [], effect_event


class TruesightCondition(BaseCondition):
    """Test condition that grants Truesight sense mode."""
    name: str = "Truesight"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        target.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=0)
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        return [], [], [], [], effect_event


class DarkvisionCondition(BaseCondition):
    """Test condition that grants Darkvision 60ft."""
    name: str = "Darkvision"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], None

        target.senses.sense_modes.append(
            SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        return [], [], [], [], effect_event


class NoPerceptionEffectCondition(BaseCondition):
    """Test condition that doesn't affect perception at all (e.g. Prone)."""
    name: str = "Test Prone"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        # No modifiers — just a marker condition
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        return [], [], [], [], effect_event


# =============================================================================
# H. Stealth System — Observer Perception Changes
# =============================================================================

def test_h1_wis_buff_reveals_hidden_enemy():
    """WIS buff reveals hidden enemy via perception staleness detection."""
    print("\n=== H1: WIS buff reveals hidden enemy ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    enemy = create_skeleton(name="Hidden Enemy", position=(3, 0), faction="evil")
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    print(f"  Observer base passive perception: {base_pp}")

    # Hide the enemy with a stealth DC above observer's perception
    stealth_dc = base_pp + 5  # Above observer's PP
    hidden = Hidden(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        stealth_result=stealth_dc
    )
    enemy.add_condition(hidden)

    # Re-update senses to pick up the hidden state
    Entity.update_all_entities_senses()

    check("H1a: Enemy not visible before buff",
          enemy.uuid not in observer.senses.entities)

    # Apply perception boost to observer (enough to see hidden enemy)
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)

    new_pp = observer.get_passive_perception()
    print(f"  Observer new passive perception: {new_pp}")

    # The callback should have detected the perception change and refiltered
    check("H1b: Enemy visible after buff (no manual update)",
          enemy.uuid in observer.senses.entities,
          f"entities={list(observer.senses.entities.keys())}")


def test_h2_wis_debuff_hides_previously_visible_enemy():
    """WIS debuff hides a previously visible enemy."""
    print("\n=== H2: WIS debuff hides previously visible enemy ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    enemy = create_skeleton(name="Hidden Enemy", position=(3, 0), faction="evil")
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    print(f"  Observer base passive perception: {base_pp}")

    # First boost observer so they can see the enemy
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)
    Entity.update_all_entities_senses()  # Full update with boosted perception

    boosted_pp = observer.get_passive_perception()
    print(f"  Observer boosted passive perception: {boosted_pp}")

    # Hide the enemy with DC between base_pp and boosted_pp
    stealth_dc = base_pp + 5
    hidden = Hidden(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        stealth_result=stealth_dc
    )
    enemy.add_condition(hidden)
    Entity.update_all_entities_senses()

    check("H2a: Enemy visible with boosted perception",
          enemy.uuid in observer.senses.entities)

    # Remove the boost (simulated by applying a debuff)
    observer.remove_condition("Perception Boost")

    # Apply a debuff to make sure perception drops below stealth DC
    debuff = PerceptionDebuffCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        debuff_amount=5  # Lower than boost so net result is lower than stealth_dc
    )
    observer.add_condition(debuff)

    new_pp = observer.get_passive_perception()
    print(f"  Observer debuffed passive perception: {new_pp}")

    check("H2b: Enemy hidden after debuff (no manual update)",
          enemy.uuid not in observer.senses.entities,
          f"PP={new_pp} vs DC={stealth_dc}")


def test_h3_varying_stealth_dc():
    """Multiple hidden enemies with different stealth DCs."""
    print("\n=== H3: Varying stealth DCs with changing perception ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    enemy_a = create_skeleton(name="Enemy A", position=(3, 0), faction="evil")
    enemy_b = create_skeleton(name="Enemy B", position=(0, 3), faction="evil")
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    print(f"  Observer base passive perception: {base_pp}")

    # Enemy A: easy to spot (DC = base_pp - 3)
    hidden_a = Hidden(
        source_entity_uuid=enemy_a.uuid,
        target_entity_uuid=enemy_a.uuid,
        stealth_result=max(1, base_pp - 3)
    )
    enemy_a.add_condition(hidden_a)

    # Enemy B: hard to spot (DC = base_pp + 10)
    hidden_b = Hidden(
        source_entity_uuid=enemy_b.uuid,
        target_entity_uuid=enemy_b.uuid,
        stealth_result=base_pp + 10
    )
    enemy_b.add_condition(hidden_b)

    Entity.update_all_entities_senses()

    check("H3a: Enemy A visible (low stealth DC)", enemy_a.uuid in observer.senses.entities)
    check("H3b: Enemy B hidden (high stealth DC)", enemy_b.uuid not in observer.senses.entities)

    # Buff perception by +15 → should see both
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=15
    )
    observer.add_condition(boost)

    check("H3c: Both visible after buff",
          enemy_a.uuid in observer.senses.entities and enemy_b.uuid in observer.senses.entities)

    # Debuff heavily → should see neither
    observer.remove_condition("Perception Boost")
    debuff = PerceptionDebuffCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        debuff_amount=15  # Drop perception way below both DCs
    )
    observer.add_condition(debuff)

    new_pp = observer.get_passive_perception()
    print(f"  Observer debuffed passive perception: {new_pp}")

    check("H3d: Neither visible after heavy debuff",
          enemy_a.uuid not in observer.senses.entities and enemy_b.uuid not in observer.senses.entities,
          f"PP={new_pp}")


def test_h4_truesight_reveals_invisible():
    """Truesight sense mode reveals invisible entity."""
    print("\n=== H4: Truesight reveals invisible entity ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    enemy = create_skeleton(name="Invisible Enemy", position=(3, 0), faction="evil")
    Entity.update_all_entities_senses()

    # Make enemy invisible
    invis = Invisible(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
    )
    enemy.add_condition(invis)
    Entity.update_all_entities_senses()

    check("H4a: Invisible enemy not visible", enemy.uuid not in observer.senses.entities)

    # Grant Truesight to observer
    truesight = TruesightCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
    )
    observer.add_condition(truesight)

    # Sense modes changed → full visibility recompute (update_visibility_func called)
    check("H4b: Invisible enemy visible with Truesight",
          enemy.uuid in observer.senses.entities,
          f"entities={list(observer.senses.entities.keys())}")


# =============================================================================
# I. Hazard System — Observer Perception Changes
# =============================================================================

def test_i1_wis_buff_reveals_hidden_trap():
    """WIS buff makes hidden hazard detectable, marking paths dirty."""
    print("\n=== I1: WIS buff reveals hidden trap ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    print(f"  Observer base passive perception: {base_pp}")

    # Place hidden hazard on tile (DC above observer's PP)
    tile = grid.get_tile(5, 5)
    assert tile is not None
    hazard = BaseCondition(
        name="HiddenTrap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=base_pp + 5,
    )
    tile.add_condition(hazard)

    # Before buff: tile not hazardous for observer
    check("I1a: Hidden trap not hazardous before buff",
          not tile.is_hazardous_for(observer.uuid))

    # Buff perception
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)

    new_pp = observer.get_passive_perception()
    print(f"  Observer new passive perception: {new_pp}")

    # Now the tile should be hazardous (perception is live, checked each call)
    check("I1b: Hidden trap hazardous after buff",
          tile.is_hazardous_for(observer.uuid))

    # Paths should be marked dirty (will be recomputed at next turn start)
    check("I1c: Paths marked dirty", observer.senses._paths_dirty)


def test_i2_wis_debuff_hides_visible_trap():
    """WIS debuff makes previously visible hazard undetectable."""
    print("\n=== I2: WIS debuff hides previously visible trap ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))

    # First boost observer
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)
    Entity.update_all_entities_senses()

    boosted_pp = observer.get_passive_perception()
    base_pp = boosted_pp - 10
    print(f"  Observer boosted passive perception: {boosted_pp}")

    # Place hazard with DC between base and boosted
    trap_dc = base_pp + 5
    tile = grid.get_tile(5, 5)
    assert tile is not None
    hazard = BaseCondition(
        name="HiddenTrap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=trap_dc,
    )
    tile.add_condition(hazard)

    check("I2a: Trap hazardous with boosted perception",
          tile.is_hazardous_for(observer.uuid))

    # Remove boost
    observer.remove_condition("Perception Boost")

    debuffed_pp = observer.get_passive_perception()
    print(f"  Observer debuffed passive perception: {debuffed_pp}")

    check("I2b: Trap not hazardous after debuff",
          not tile.is_hazardous_for(observer.uuid))

    # Paths marked dirty
    check("I2c: Paths marked dirty", observer.senses._paths_dirty)


def test_i3_varying_trap_stealth_dc():
    """Multiple hidden traps with different DCs."""
    print("\n=== I3: Varying trap stealth DCs ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    print(f"  Observer base passive perception: {base_pp}")

    # Trap A: easy to spot (DC = base_pp - 3)
    tile_a = grid.get_tile(5, 5)
    assert tile_a is not None
    hazard_a = BaseCondition(
        name="EasyTrap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=tile_a.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=max(1, base_pp - 3),
    )
    tile_a.add_condition(hazard_a)

    # Trap B: hard to spot (DC = base_pp + 10)
    tile_b = grid.get_tile(7, 7)
    assert tile_b is not None
    hazard_b = BaseCondition(
        name="HardTrap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=tile_b.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=base_pp + 10,
    )
    tile_b.add_condition(hazard_b)

    check("I3a: Easy trap hazardous", tile_a.is_hazardous_for(observer.uuid))
    check("I3b: Hard trap not hazardous", not tile_b.is_hazardous_for(observer.uuid))

    # Buff to see both
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=15
    )
    observer.add_condition(boost)

    check("I3c: Both hazardous after buff",
          tile_a.is_hazardous_for(observer.uuid) and tile_b.is_hazardous_for(observer.uuid))

    # Debuff to see neither
    observer.remove_condition("Perception Boost")
    debuff = PerceptionDebuffCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        debuff_amount=15
    )
    observer.add_condition(debuff)

    new_pp = observer.get_passive_perception()
    print(f"  Observer debuffed passive perception: {new_pp}")

    check("I3d: Neither hazardous after heavy debuff",
          not tile_a.is_hazardous_for(observer.uuid) and not tile_b.is_hazardous_for(observer.uuid))


# =============================================================================
# J. Combat Logs for Perception Events
# =============================================================================

def test_j1_entity_spotted_on_perception_buff():
    """ENTITY_SPOTTED combat log generated when buff reveals hidden enemy."""
    print("\n=== J1: ENTITY_SPOTTED on perception buff ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0), faction="good")
    enemy = create_skeleton(name="Hidden Rogue", position=(3, 0), faction="evil")

    # Set up encounter for combat logs
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(observer, PassController(source_entity_uuid=observer.uuid))
    encounter.add_combatant(enemy, PassController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    stealth_dc = base_pp + 5

    # Hide the enemy
    hidden = Hidden(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        stealth_result=stealth_dc
    )
    enemy.add_condition(hidden)
    Entity.update_all_entities_senses()

    check("J1a: Enemy hidden before buff", enemy.uuid not in observer.senses.entities)

    # Record log position
    log_start = len(encounter.combat_log)

    # Buff perception to reveal the enemy
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)

    # Check for ENTITY_SPOTTED log
    new_logs = encounter.combat_log[log_start:]
    spotted_logs = [l for l in new_logs if l.entry_type == CombatLogEntryType.ENTITY_SPOTTED]
    check("J1b: ENTITY_SPOTTED log generated", len(spotted_logs) > 0,
          f"logs={[l.entry_type for l in new_logs]}")

    encounter.end_encounter()


def test_j2_hazard_detected_on_perception_buff():
    """HAZARD_DETECTED combat log generated when buff reveals hidden trap."""
    print("\n=== J2: HAZARD_DETECTED on perception buff ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0), faction="good")
    dummy = create_skeleton(name="Dummy", position=(10, 0), faction="evil")

    # Set up encounter for combat logs
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(observer, PassController(source_entity_uuid=observer.uuid))
    encounter.add_combatant(dummy, PassController(source_entity_uuid=dummy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    trap_dc = base_pp + 5

    # Place hidden hazard
    tile = grid.get_tile(3, 3)
    assert tile is not None
    hazard = BaseCondition(
        name="Hidden Spike Trap",
        source_entity_uuid=uuid4(),
        target_entity_uuid=tile.uuid,
        condition_category=ConditionCategory.CONDITION,
        hazard_filter=HazardFilter.ALL,
        condition_stealth_dc=trap_dc,
    )
    tile.add_condition(hazard)

    # Record log position
    log_start = len(encounter.combat_log)

    # Buff perception to detect the trap
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=10
    )
    observer.add_condition(boost)

    # Check for HAZARD_DETECTED log
    new_logs = encounter.combat_log[log_start:]
    hazard_logs = [l for l in new_logs if l.entry_type == CombatLogEntryType.HAZARD_DETECTED]
    check("J2a: HAZARD_DETECTED log generated", len(hazard_logs) > 0,
          f"logs={[l.entry_type for l in new_logs]}")

    if hazard_logs:
        log = hazard_logs[0]
        check("J2b: Log has correct source", log.source_name == "Observer")
        data = log.data
        check("J2c: Log has hazard_name", data.get("hazard_name") == "Hidden Spike Trap")
        check("J2d: Log has correct position", tuple(data.get("position", ())) == (3, 3))
        check("J2e: Log has passive_perception", data.get("passive_perception") == observer.get_passive_perception())
        check("J2f: Log has stealth_dc", data.get("stealth_dc") == trap_dc)

    encounter.end_encounter()


def test_j3_no_false_positives():
    """Condition that doesn't affect perception produces no perception logs."""
    print("\n=== J3: No false positives ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0), faction="good")
    enemy = create_skeleton(name="Hidden Enemy", position=(3, 0), faction="evil")

    # Set up encounter
    encounter = Encounter(name="Test", source_entity_uuid=uuid4())
    encounter.add_combatant(observer, PassController(source_entity_uuid=observer.uuid))
    encounter.add_combatant(enemy, PassController(source_entity_uuid=enemy.uuid))
    encounter.roll_initiative()
    encounter.start_encounter()

    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    stealth_dc = base_pp + 5

    # Hide enemy
    hidden = Hidden(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        stealth_result=stealth_dc
    )
    enemy.add_condition(hidden)
    Entity.update_all_entities_senses()

    entities_before = dict(observer.senses.entities)
    log_start = len(encounter.combat_log)

    # Apply a condition that doesn't affect perception
    no_effect = NoPerceptionEffectCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
    )
    observer.add_condition(no_effect)

    # No perception-related logs
    new_logs = encounter.combat_log[log_start:]
    spotted_logs = [l for l in new_logs if l.entry_type in (
        CombatLogEntryType.ENTITY_SPOTTED, CombatLogEntryType.HAZARD_DETECTED
    )]
    check("J3a: No perception logs from non-perception condition", len(spotted_logs) == 0,
          f"logs={[l.entry_type for l in spotted_logs]}")

    # Senses entities unchanged
    check("J3b: senses.entities unchanged",
          observer.senses.entities == entities_before)

    encounter.end_encounter()


# =============================================================================
# K. Edge Cases
# =============================================================================

def test_k1_snapshot_initialized_correctly():
    """After first update_all_entities_senses, snapshot matches actual perception."""
    print("\n=== K1: Snapshot initialized correctly ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    Entity.update_all_entities_senses()

    pp = observer.get_passive_perception()
    snapshot_pp = observer.senses._last_passive_perception
    snapshot_hash = observer.senses._last_sense_modes_hash
    computed_hash = observer.senses.compute_sense_modes_hash()

    check("K1a: Snapshot PP matches actual PP",
          snapshot_pp == pp,
          f"snapshot={snapshot_pp}, actual={pp}")

    check("K1b: Snapshot sense modes hash matches computed",
          snapshot_hash == computed_hash,
          f"snapshot={snapshot_hash}, computed={computed_hash}")


def test_k2_multiple_conditions_in_sequence():
    """Multiple condition changes settle to final state correctly."""
    print("\n=== K2: Multiple condition changes in sequence ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    enemy = create_skeleton(name="Hidden Enemy", position=(3, 0), faction="evil")
    Entity.update_all_entities_senses()

    base_pp = observer.get_passive_perception()
    stealth_dc = base_pp + 3

    hidden = Hidden(
        source_entity_uuid=enemy.uuid,
        target_entity_uuid=enemy.uuid,
        stealth_result=stealth_dc
    )
    enemy.add_condition(hidden)
    Entity.update_all_entities_senses()

    check("K2a: Enemy hidden at start", enemy.uuid not in observer.senses.entities)

    # First: boost by +5 → should reveal (base_pp + 5 > stealth_dc = base_pp + 3)
    boost = PerceptionBoostCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        boost_amount=5
    )
    observer.add_condition(boost)

    check("K2b: Enemy visible after +5 boost", enemy.uuid in observer.senses.entities)

    # Second: debuff by -10 → net is base_pp - 5, below stealth_dc
    observer.remove_condition("Perception Boost")
    debuff = PerceptionDebuffCondition(
        source_entity_uuid=observer.uuid,
        target_entity_uuid=observer.uuid,
        debuff_amount=10
    )
    observer.add_condition(debuff)

    final_pp = observer.get_passive_perception()
    print(f"  Final PP: {final_pp} (base={base_pp}, stealth_dc={stealth_dc})")

    check("K2c: Enemy hidden after net debuff",
          enemy.uuid not in observer.senses.entities,
          f"PP={final_pp} vs DC={stealth_dc}")


def test_k3_condition_on_other_entity_no_self_recheck():
    """Condition on another entity doesn't trigger observer's perception recheck."""
    print("\n=== K3: Condition on other entity doesn't trigger self-recheck ===")
    reset_combat_state()
    grid = setup_arena()

    observer = create_skeleton(name="Observer", position=(0, 0))
    other = create_skeleton(name="Other", position=(3, 0))
    Entity.update_all_entities_senses()

    pp_before = observer.senses._last_passive_perception
    hash_before = observer.senses._last_sense_modes_hash

    # Apply condition to OTHER entity
    boost = PerceptionBoostCondition(
        source_entity_uuid=other.uuid,
        target_entity_uuid=other.uuid,
        boost_amount=10
    )
    other.add_condition(boost)

    # Observer's snapshot should be unchanged
    check("K3a: Observer PP snapshot unchanged",
          observer.senses._last_passive_perception == pp_before)
    check("K3b: Observer sense modes hash unchanged",
          observer.senses._last_sense_modes_hash == hash_before)


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    # H. Stealth System
    test_h1_wis_buff_reveals_hidden_enemy()
    test_h2_wis_debuff_hides_previously_visible_enemy()
    test_h3_varying_stealth_dc()
    test_h4_truesight_reveals_invisible()

    # I. Hazard System
    test_i1_wis_buff_reveals_hidden_trap()
    test_i2_wis_debuff_hides_visible_trap()
    test_i3_varying_trap_stealth_dc()

    # J. Combat Logs
    test_j1_entity_spotted_on_perception_buff()
    test_j2_hazard_detected_on_perception_buff()
    test_j3_no_false_positives()

    # K. Edge Cases
    test_k1_snapshot_initialized_correctly()
    test_k2_multiple_conditions_in_sequence()
    test_k3_condition_on_other_entity_no_self_recheck()

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"FAILURES: {failed}")
