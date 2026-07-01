"""
Test suite for alt-field override system on BaseAction and SpellAction.

Tests the infrastructure added in Phases B+C (C1-C4):
- alt_cost_type, alt_extra_costs, alt_target_type, alt_target_count on BaseAction
- alt_range, alt_skip_slot on SpellAction
- effective_* property resolution
- apply_action_overrides / clear_action_overrides helpers
- Bug fixes: get_all_targets() and _validate_target_filter() use effective_target_type

Categories:
  A: Basic alt-field tests (infrastructure)
  B: Target type swap interactions
  C: Concentration + multi-target
  D: Upcasting + alt override interactions
  E: _finalize_aoe interactions
  F: Spell-specific edge cases
  G: Available actions routing
"""

from uuid import uuid4

from dnd.utils import reset_combat_state
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map
from dnd.core.base_actions import TargetType, Cost
from dnd.actions import SpellAction, entity_action_economy_cost_evaluator
from dnd.actions_functional import (
    setup_standard_actions, register_spell,
    apply_action_overrides, clear_action_overrides,
)
from dnd.spells.evocation import (
    FireBolt, Fireball, IceStorm, MagicMissile,
    EldritchBlast, GustOfWind,
)
from dnd.spells.enchantment import HoldPerson
from dnd.spells.conjuration import Web
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.utils import (
    get_hp, has_condition,
    force_spell_attack_hit, remove_spell_attack_modifier,
)
from dnd.core.modifiers import CreatureType

passed = 0
failed = 0
test_names = []

# Large grid/senses distance for range tests (300ft = 60 tiles)
GRID_SIZE = 65
SENSES_DISTANCE = 65


def test(name: str):
    """Decorator to register and run a test."""
    def decorator(fn):
        test_names.append(name)
        global passed, failed
        try:
            fn()
            passed += 1
            print(f"  PASS: {name}")
        except Exception as _e:
            failed += 1
            print(f"  FAIL: {name}")
            import traceback
            traceback.print_exc()
        return fn
    return decorator


# ============================================================================
# Helpers
# ============================================================================

def fresh_state():
    """Reset all state and create a large grid for range tests."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, GRID_SIZE, GRID_SIZE)


def make_caster(name: str, position: tuple, faction: str = "heroes") -> Entity:
    """Create a spellcaster entity."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=18),
            charisma=AbilityConfig(ability_score=18),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=8, hit_dice_count=10, mode="maximums"
        )]),
        action_economy=ActionEconomyConfig(
            spell_slots={1: 4, 2: 3, 3: 3, 4: 2, 5: 1}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        proficiency_bonus=4,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    entity.creature_type = CreatureType.HUMANOID
    setup_standard_actions(entity)
    return entity


def make_target(name: str, position: tuple, faction: str = "monsters") -> Entity:
    """Create a basic target entity with low WIS for save tests."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=3),  # Very low WIS for Hold Person tests
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=8, hit_dice_count=5, mode="maximums"
        )]),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    entity = Entity.create(source_entity_uuid=uuid4(), name=name, config=config)
    entity.creature_type = CreatureType.HUMANOID
    setup_standard_actions(entity)
    return entity


def find_template(entity: Entity, name: str) -> SpellAction:
    """Find a registered spell action template by name."""
    for t in entity.registered_actions:
        if t.name == name:
            assert isinstance(t, SpellAction), f"Expected SpellAction, got {type(t)}"
            return t
    raise ValueError(f"Template '{name}' not found on {entity.name}")


def setup_encounter(*entities: Entity) -> Encounter:
    """Set up encounter with given entities, start it."""
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)
    enc = Encounter(name="Test", source_entity_uuid=uuid4())
    for e in entities:
        enc.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    enc.roll_initiative()
    enc.start_encounter()
    return enc


# ============================================================================
# Category A: Basic Alt-Field Tests
# ============================================================================

print("\n=== Category A: Basic Alt-Field Tests ===")


@test("A1: Range override extends Fire Bolt reach")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    # Fire Bolt range=120ft → 24 tiles. Put target at 26 tiles (130ft)
    target = make_target("Far Target", (26, 0))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    template = find_template(caster, "Fire Bolt")

    # Default range=120ft, target at 130ft → out of range
    actions = caster.get_available_actions()
    fb_infos = [a for a in actions.entity_actions if a.template_name == "Fire Bolt"]
    found_far = any(
        vt.target_uuid == target.uuid
        for info in fb_infos
        for vt in info.valid_targets
    )
    assert not found_far, "Target at 130ft should NOT be reachable at 120ft range"

    # Set alt_range=300
    template.alt_range = 300
    actions2 = caster.get_available_actions()
    fb_infos2 = [a for a in actions2.entity_actions if a.template_name == "Fire Bolt"]
    found_far2 = any(
        vt.target_uuid == target.uuid
        for info in fb_infos2
        for vt in info.valid_targets
    )
    assert found_far2, "Target at 130ft SHOULD be reachable at 300ft range"

    # Clear → gone again
    template.alt_range = None
    actions3 = caster.get_available_actions()
    fb_infos3 = [a for a in actions3.entity_actions if a.template_name == "Fire Bolt"]
    found_far3 = any(
        vt.target_uuid == target.uuid
        for info in fb_infos3
        for vt in info.valid_targets
    )
    assert not found_far3, "After clearing alt_range, far target unreachable again"


@test("A2: Cost override switches Fire Bolt to bonus action")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (1, 0))
    register_spell(caster, FireBolt, caster_level=5)
    enc = setup_encounter(caster, target)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
        alt_cost_type="bonus_actions",
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    # Bonus action should be consumed (was 1, now 0)
    ba = caster.action_economy.bonus_actions.normalized_score
    assert ba == 0, f"Bonus action should be 0, got {ba}"
    # Standard action should still be 1
    act = caster.action_economy.actions.normalized_score
    assert act == 1, f"Standard action should be 1, got {act}"


@test("A3: Target count override returns from get_multi_target_count")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, FireBolt, caster_level=5)

    template = find_template(caster, "Fire Bolt")
    # Fire Bolt is ENTITY → get_multi_target_count returns None
    assert template.get_multi_target_count() is None

    # Set alt_target_count=3 — base implementation returns it immediately (before target type check)
    template.alt_target_count = 3
    count = template.get_multi_target_count()
    assert count == 3, f"alt_target_count=3 should return 3 regardless of target type, got {count}"

    # With MULTI_ENTITY as well, still returns 3
    template.alt_target_type = TargetType.MULTI_ENTITY
    count2 = template.get_multi_target_count()
    assert count2 == 3, f"Expected 3 with both overrides, got {count2}"


@test("A4: Target type override ENTITY→MULTI_ENTITY appears in available actions")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    make_target("T1", (1, 0))
    make_target("T2", (0, 1))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    template = find_template(caster, "Fire Bolt")
    template.alt_target_type = TargetType.MULTI_ENTITY

    actions = caster.get_available_actions()
    fb_infos = [a for a in actions.entity_actions if a.template_name == "Fire Bolt"]
    assert len(fb_infos) > 0, "Fire Bolt should be in entity_actions with MULTI_ENTITY"
    assert fb_infos[0].target_type == TargetType.MULTI_ENTITY, \
        f"Expected MULTI_ENTITY, got {fb_infos[0].target_type}"


@test("A5: alt_skip_slot removes spell slot cost")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, HoldPerson, caster_level=5)

    template = find_template(caster, "Hold Person")
    # Normal costs include spell slot
    normal_costs = template.effective_costs
    has_slot = any(c.cost_type.startswith("spell_slot") for c in normal_costs)
    assert has_slot, "Hold Person should have spell slot cost"

    # Set alt_skip_slot
    template.alt_skip_slot = True
    skip_costs = template.effective_costs
    has_slot2 = any(c.cost_type.startswith("spell_slot") for c in skip_costs)
    assert not has_slot2, "With alt_skip_slot, no spell slot cost"


@test("A6: Extra costs (resource) affect affordability")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, FireBolt, caster_level=5)

    template = find_template(caster, "Fire Bolt")

    # Add SP extra cost with a resource evaluator that checks a custom attribute
    def sp_evaluator(entity_uuid, resource_name, cost):
        entity = Entity.get(entity_uuid)
        if entity is None:
            return False
        sp = getattr(entity, '_sorcery_points', 0)
        return sp >= cost

    sp_cost = Cost(
        name="Sorcery Points",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=2,
        resource_evaluator=sp_evaluator,
    )
    template.alt_extra_costs = [sp_cost]

    # Without SP, can't afford
    caster._sorcery_points = 0  # type: ignore
    assert not template.check_costs(), "Should be unaffordable with 0 SP"

    # With SP, can afford
    caster._sorcery_points = 5  # type: ignore
    assert template.check_costs(), "Should be affordable with 5 SP"

    # Cleanup
    template.alt_extra_costs = []


@test("A7: Combined overrides work simultaneously")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, FireBolt, caster_level=5)

    template = find_template(caster, "Fire Bolt")
    template.alt_cost_type = "bonus_actions"
    template.alt_range = 500
    template.alt_extra_costs = [Cost(
        name="Extra", cost_type="bonus_actions", cost=0,
        resource_name="test", resource_cost=1,
    )]

    costs = template.effective_costs
    # Should have bonus_actions (from alt_cost_type) + Extra cost
    action_costs = [c for c in costs if c.cost_type == "bonus_actions"]
    assert len(action_costs) >= 1, "Should have bonus_actions cost"

    # Range should be overridden
    assert template.effective_range == 500

    # Extra cost should be appended
    extra = [c for c in costs if c.name == "Extra"]
    assert len(extra) == 1, "Extra cost should be appended"


@test("A8: apply_action_overrides + clear_action_overrides helpers")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, HoldPerson, caster_level=5)

    # Apply overrides only to Fire Bolt
    modified = apply_action_overrides(
        caster,
        filter_fn=lambda a: a.name == "Fire Bolt",
        overrides={"alt_cost_type": "bonus_actions", "alt_range": 300},
    )
    assert len(modified) == 1, "Should have modified 1 template"

    fb = find_template(caster, "Fire Bolt")
    hp = find_template(caster, "Hold Person")
    assert fb.alt_cost_type == "bonus_actions"
    assert fb.alt_range == 300
    assert hp.alt_cost_type is None, "Hold Person should be unaffected"

    # Clear
    clear_action_overrides(caster, modified)
    assert fb.alt_cost_type is None, "alt_cost_type should be cleared"
    assert fb.alt_range is None, "alt_range should be cleared"


@test("A9: Cleanup restores original get_available_actions")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    make_target("Target", (1, 0))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    # Snapshot original
    original_actions = caster.get_available_actions()
    original_fb = [a for a in original_actions.entity_actions if a.template_name == "Fire Bolt"]
    original_count = len(original_fb)
    assert original_count > 0, "Fire Bolt should be in entity_actions initially"

    # Override target type to MULTI_ENTITY (stays in entity_actions but different type)
    modified = apply_action_overrides(
        caster,
        filter_fn=lambda a: a.name == "Fire Bolt",
        overrides={"alt_target_type": TargetType.MULTI_ENTITY},
    )

    mid_actions = caster.get_available_actions()
    fb_mid = [a for a in mid_actions.entity_actions if a.template_name == "Fire Bolt"]
    assert len(fb_mid) > 0, "Fire Bolt with MULTI_ENTITY should still be in entity_actions"
    assert fb_mid[0].target_type == TargetType.MULTI_ENTITY

    # Clear and verify restoration
    clear_action_overrides(caster, modified)
    restored = caster.get_available_actions()
    restored_fb = [a for a in restored.entity_actions if a.template_name == "Fire Bolt"]
    assert len(restored_fb) > 0
    assert restored_fb[0].target_type == TargetType.ENTITY, "Should be back to ENTITY"


# ============================================================================
# Category B: Target Type Swap Interactions
# ============================================================================

print("\n=== Category B: Target Type Swap Interactions ===")


@test("B10: ENTITY→MULTI_ENTITY execution hits 3 targets")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    t3 = make_target("T3", (1, 1))
    enc = setup_encounter(caster, t1, t2, t3)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1_before = get_hp(t1)
    hp2_before = get_hp(t2)
    hp3_before = get_hp(t3)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        extra_target_entity_uuids=[t2.uuid, t3.uuid],
        caster_level=5,
        template=False,
        alt_target_type=TargetType.MULTI_ENTITY,
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp1_after = get_hp(t1)
    hp2_after = get_hp(t2)
    hp3_after = get_hp(t3)
    assert hp1_after < hp1_before, f"T1 should take damage: {hp1_before} → {hp1_after}"
    assert hp2_after < hp2_before, f"T2 should take damage: {hp2_before} → {hp2_after}"
    assert hp3_after < hp3_before, f"T3 should take damage: {hp3_before} → {hp3_after}"


@test("B11: POSITION_AOE→ENTITY (Fireball single-target)")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (2, 0))
    bystander = make_target("Bystander", (2, 1))  # Would be in AoE normally
    enc = setup_encounter(caster, target, bystander)
    enc.start_turn()

    hp_target_before = get_hp(target)
    hp_bystander_before = get_hp(bystander)

    # Fireball as single ENTITY target
    spell = Fireball(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(2, 0),
        cast_at_level=3,
        template=False,
        alt_target_type=TargetType.ENTITY,
    )
    spell.apply()

    hp_target_after = get_hp(target)
    hp_bystander_after = get_hp(bystander)

    assert hp_target_after < hp_target_before, "Target should take damage"
    assert hp_bystander_after == hp_bystander_before, "Bystander should NOT take damage"


@test("B12: POSITION_AOE→MULTI_ENTITY (Fireball pick targets)")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (2, 0))
    t2 = make_target("T2", (2, 1))
    t3 = make_target("T3", (3, 0))  # Not selected
    enc = setup_encounter(caster, t1, t2, t3)
    enc.start_turn()

    hp1_before = get_hp(t1)
    hp2_before = get_hp(t2)
    hp3_before = get_hp(t3)

    spell = Fireball(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        extra_target_entity_uuids=[t2.uuid],
        end_position=(2, 0),
        cast_at_level=3,
        template=False,
        alt_target_type=TargetType.MULTI_ENTITY,
    )
    spell.apply()

    hp1_after = get_hp(t1)
    hp2_after = get_hp(t2)
    hp3_after = get_hp(t3)

    assert hp1_after < hp1_before, "T1 should take damage"
    assert hp2_after < hp2_before, "T2 should take damage"
    assert hp3_after == hp3_before, "T3 should NOT take damage (not selected)"


@test("B13: ENTITY→POSITION_AOE with aoe_shape (bug fix #1)")
def _():
    """Tests the bug fix in get_all_targets(): now uses effective_target_type."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (2, 0))
    t2 = make_target("T2", (2, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    from dnd.core.aoe import Sphere
    hp1_before = get_hp(t1)
    hp2_before = get_hp(t2)

    # Fire Bolt (ENTITY) overridden to POSITION_AOE with a Sphere shape
    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        end_position=(2, 0),
        caster_level=5,
        template=False,
        alt_target_type=TargetType.POSITION_AOE,
        aoe_shape=Sphere(
            source_entity_uuid=caster.uuid,
            target=(2, 0),
            radius_feet=10,
        ),
    )

    hit_mod = force_spell_attack_hit(caster)
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp1_after = get_hp(t1)
    hp2_after = get_hp(t2)

    # Both should take damage via AoE resolution (targets within 10ft sphere at 2,0)
    assert hp1_after < hp1_before, "T1 should take damage from AoE"
    assert hp2_after < hp2_before, "T2 should take damage from AoE"


@test("B14: ENTITY→POSITION_AOE without aoe_shape → 0 targets")
def _():
    """Documents expected behavior: no shape means no targets."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (1, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    hp_before = get_hp(target)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(1, 0),
        caster_level=5,
        template=False,
        alt_target_type=TargetType.POSITION_AOE,
    )
    # Ensure no aoe_shape
    spell.aoe_shape = None
    spell.apply()

    hp_after = get_hp(target)
    assert hp_after == hp_before, "No aoe_shape = 0 targets, no damage"


@test("B15: POSITION zone spell (Web) can't swap to ENTITY")
def _():
    """Documents limitation: Web requires end_position for zone creation."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (2, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    spell = Web(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=None,  # No position
        cast_at_level=2,
        template=False,
        alt_target_type=TargetType.ENTITY,
    )
    result = spell.apply()
    # Should cancel because Web._validate checks for end_position
    assert result is None or result.canceled, "Web without position should fail validation"


# ============================================================================
# Category C: Concentration + Multi-Target
# ============================================================================

print("\n=== Category C: Concentration + Multi-Target ===")


@test("C16: Hold Person + MULTI_ENTITY → one Concentrating, linked to all")
def _():
    """ensure_concentration reuses across convolution loop."""
    for _ in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        # Targets have WIS 3 (from make_target default) → very likely to fail save
        t1 = make_target("T1", (1, 0))
        t2 = make_target("T2", (0, 1))
        t3 = make_target("T3", (1, 1))
        enc = setup_encounter(caster, t1, t2, t3)
        enc.start_turn()

        spell = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=t1.uuid,
            extra_target_entity_uuids=[t2.uuid, t3.uuid],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=3,
        )
        spell.apply()

        # Count how many targets are paralyzed
        held = sum(1 for t in [t1, t2, t3] if has_condition(t, "Paralyzed"))
        if held >= 2:
            # Good — at least 2 targets held
            assert has_condition(caster, "Concentrating"), "Caster should be concentrating"
            # Only ONE Concentrating condition
            conc_count = sum(1 for c in caster.active_conditions.values() if c.name == "Concentrating")
            assert conc_count == 1, f"Should have exactly 1 Concentrating, got {conc_count}"

            # Breaking concentration should remove all
            caster.remove_condition("Concentrating")
            for t in [t1, t2, t3]:
                assert not has_condition(t, "Paralyzed"), f"{t.name} should NOT be paralyzed after conc break"
                assert not has_condition(t, "Hold Person"), f"{t.name} should NOT have Hold Person after conc break"
            return  # Pass

    assert False, "Could not get 2+ Hold Person failures in 20 attempts"


@test("C17: Concentration partial removal — Concentrating survives")
def _():
    """Remove one target's effect, Concentrating survives (policy='last')."""
    for _ in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (1, 0))
        t2 = make_target("T2", (0, 1))
        enc = setup_encounter(caster, t1, t2)
        enc.start_turn()

        spell = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=t1.uuid,
            extra_target_entity_uuids=[t2.uuid],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=2,
        )
        spell.apply()

        held = [t for t in [t1, t2] if has_condition(t, "Paralyzed")]
        if len(held) == 2:
            # Remove one target's effect
            t1.remove_condition("Hold Person")
            assert not has_condition(t1, "Paralyzed"), "T1 should no longer be paralyzed"
            assert has_condition(caster, "Concentrating"), "Concentrating should survive (policy=last)"
            assert has_condition(t2, "Paralyzed"), "T2 should still be paralyzed"

            # Remove second → Concentrating should auto-remove
            t2.remove_condition("Hold Person")
            assert not has_condition(t2, "Paralyzed"), "T2 should no longer be paralyzed"
            assert not has_condition(caster, "Concentrating"), "Concentrating should auto-remove (last child)"
            return

    assert False, "Could not get both Hold Person failures in 20 attempts"


# ============================================================================
# Category D: Upcasting + Alt Override Interactions
# ============================================================================

print("\n=== Category D: Upcasting + Alt Override Interactions ===")


@test("D18: Upcast + alt_cost_type — all variants have bonus_action cost")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, HoldPerson, caster_level=5)

    template = find_template(caster, "Hold Person")
    template.alt_cost_type = "bonus_actions"

    variants = template.generate_variants(caster)
    assert len(variants) >= 2, f"Should have multiple variants, got {len(variants)}"

    for v in variants:
        has_ba = any(c.cost_type == "bonus_actions" for c in v.costs)
        assert has_ba, f"Variant at L{v.cast_at_level} should have bonus_actions cost"
        has_slot = any(c.cost_type == f"spell_slot_{v.cast_at_level}" for c in v.costs)
        assert has_slot, f"Variant at L{v.cast_at_level} should have spell slot L{v.cast_at_level}"


@test("D19: Upcast + alt_skip_slot — no spell slot cost at any level")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, HoldPerson, caster_level=5)

    template = find_template(caster, "Hold Person")
    template.alt_skip_slot = True

    variants = template.generate_variants(caster)
    for v in variants:
        has_slot = any(c.cost_type.startswith("spell_slot") for c in v.costs)
        assert not has_slot, f"Variant at L{v.cast_at_level} should have NO spell slot cost"


@test("D20: Cantrip + alt_extra_costs — single variant with extra cost")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    register_spell(caster, FireBolt, caster_level=5)

    template = find_template(caster, "Fire Bolt")
    sp_cost = Cost(
        name="SP Cost", cost_type="actions", cost=0,
        resource_name="sorcery_points", resource_cost=2,
    )
    template.alt_extra_costs = [sp_cost]

    variants = template.generate_variants(caster)
    assert len(variants) == 1, "Cantrip should have 1 variant"
    v = variants[0]
    extra = [c for c in v.costs if c.name == "SP Cost"]
    assert len(extra) == 1, "Extra SP cost should be in variant costs"


@test("D21: Upcast + alt_skip_slot execution — no slot consumed")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (1, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    l2_before = caster.action_economy.spell_slot_2.normalized_score

    spell = HoldPerson(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=2,
        template=False,
        alt_skip_slot=True,
    )
    spell.apply()

    l2_after = caster.action_economy.spell_slot_2.normalized_score
    assert l2_after == l2_before, f"L2 slots should be unchanged: {l2_before} → {l2_after}"


# ============================================================================
# Category E: _finalize_aoe Interactions
# ============================================================================

print("\n=== Category E: _finalize_aoe Interactions ===")


@test("E22: IceStorm→ENTITY: no terrain created")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (2, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    hp_before = get_hp(target)

    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(2, 0),
        cast_at_level=4,
        template=False,
        alt_target_type=TargetType.ENTITY,
    )
    spell.apply()

    hp_after = get_hp(target)
    assert hp_after < hp_before, "Target should take damage"

    has_terrain = has_condition(caster, "Ice Storm Terrain")
    assert not has_terrain, "No terrain should be created when overriding to ENTITY"


@test("E23: GustOfWind→ENTITY: no zone, no concentration")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (2, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    spell = GustOfWind(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(5, 0),
        cast_at_level=2,
        template=False,
        alt_target_type=TargetType.ENTITY,
    )
    spell.apply()

    has_zone = has_condition(caster, "Gust of Wind Zone")
    assert not has_zone, "No zone should be created when overriding to ENTITY"

    has_conc = has_condition(caster, "Concentrating")
    assert not has_conc, "No concentration when _finalize_aoe is skipped"


@test("E24: IceStorm normal: terrain created (control)")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (3, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    spell = IceStorm(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=(3, 0),
        cast_at_level=4,
        template=False,
    )
    spell.apply()

    has_terrain = has_condition(caster, "Ice Storm Terrain")
    assert has_terrain, "Normal IceStorm SHOULD create terrain"


# ============================================================================
# Category F: Spell-Specific Edge Cases
# ============================================================================

print("\n=== Category F: Spell-Specific Edge Cases ===")


@test("F25: EldritchBlast: alt_target_count without MULTI_ENTITY → 1 target")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1_before = get_hp(t1)
    hp2_before = get_hp(t2)

    # alt_target_count=3 but NO alt_target_type → still ENTITY, single target flow
    spell = EldritchBlast(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        caster_level=5,
        template=False,
        alt_target_count=3,
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp1_after = get_hp(t1)
    hp2_after = get_hp(t2)
    assert hp1_after < hp1_before, "T1 should take damage (single target)"
    assert hp2_after == hp2_before, "T2 should NOT take damage (alt_target_count without MULTI_ENTITY)"


@test("F25b: EldritchBlast: MULTI_ENTITY + alt_target_count=3 → 3 targets")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    t3 = make_target("T3", (1, 1))
    enc = setup_encounter(caster, t1, t2, t3)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1_before = get_hp(t1)
    hp2_before = get_hp(t2)
    hp3_before = get_hp(t3)

    spell = EldritchBlast(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        extra_target_entity_uuids=[t2.uuid, t3.uuid],
        caster_level=5,
        template=False,
        alt_target_type=TargetType.MULTI_ENTITY,
        alt_target_count=3,
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp1_after = get_hp(t1)
    hp2_after = get_hp(t2)
    hp3_after = get_hp(t3)
    assert hp1_after < hp1_before, "T1 should take damage"
    assert hp2_after < hp2_before, "T2 should take damage"
    assert hp3_after < hp3_before, "T3 should take damage"


@test("F26: MagicMissile overrides get_multi_target_count (ignores alt_target_count)")
def _():
    """Documents limitation: MM overrides get_multi_target_count, alt_target_count ignored."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (1, 0))
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        cast_at_level=1,
        template=False,
        alt_target_count=5,
    )

    # MM overrides get_multi_target_count → returns get_num_projectiles() = 3
    count = spell.get_multi_target_count()
    assert count == 3, f"MM's override should return 3 (ignoring alt_target_count), got {count}"

    # get_all_targets also uses its own logic
    targets = spell.get_all_targets()
    assert len(targets) == 3, f"MM should fire 3 darts at L1, got {len(targets)}"


@test("F27: alt_cost_type on bonus_action spell (Misty Step pattern)")
def _():
    """Documents limitation: alt_cost_type only replaces 'actions' cost type."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))

    class FakeBASpell(SpellAction):
        name: str = "Fake BA Spell"
        spell_level: int = 0
        costs: list = [Cost(name="Cast", cost_type="bonus_actions", cost=1,
                            evaluator=entity_action_economy_cost_evaluator)]

    spell = FakeBASpell(
        source_entity_uuid=caster.uuid,
        template=False,
        alt_cost_type="reactions",
    )

    costs = spell.effective_costs
    has_ba = any(c.cost_type == "bonus_actions" for c in costs)
    has_reaction = any(c.cost_type == "reactions" for c in costs)
    assert has_ba, "bonus_actions cost should remain (not replaced)"
    assert not has_reaction, "reactions should NOT appear (alt_cost_type only replaces 'actions')"


@test("F28: Range override on Fire Bolt (120→300)")
def _():
    """Validates effective_range propagates through _validate on ENTITY spells."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    # Place target at 130ft (26 tiles) — beyond 120ft default, within 300ft override
    target = make_target("Far Target", (26, 0))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    template = find_template(caster, "Fire Bolt")

    # Default range=120ft → target at 130ft unreachable
    actions = caster.get_available_actions()
    fb_infos = [a for a in actions.entity_actions if a.template_name == "Fire Bolt"]
    found_far = any(
        vt.target_uuid == target.uuid
        for info in fb_infos
        for vt in info.valid_targets
    )
    assert not found_far, "130ft target should NOT be reachable at 120ft range"

    # Override range to 300
    template.alt_range = 300
    actions2 = caster.get_available_actions()
    fb_infos2 = [a for a in actions2.entity_actions if a.template_name == "Fire Bolt"]
    found_far2 = any(
        vt.target_uuid == target.uuid
        for info in fb_infos2
        for vt in info.valid_targets
    )
    assert found_far2, "130ft target SHOULD be reachable at 300ft range"


# ============================================================================
# Category G: Available Actions Routing
# ============================================================================

print("\n=== Category G: Available Actions Routing ===")


@test("G29: ENTITY→POSITION_AOE routing — appears in position_actions")
def _():
    """ENTITY spell with POSITION_AOE override routes to position_actions output
    via get_valid_positions() which now uses effective_target_type (bug #4 fix).
    """
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    make_target("Target", (1, 0))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    template = find_template(caster, "Fire Bolt")

    # Original: should be in entity_actions
    actions = caster.get_available_actions()
    fb_entity = [a for a in actions.entity_actions if a.template_name == "Fire Bolt"]
    assert len(fb_entity) > 0, "Fire Bolt should be in entity_actions initially"

    # Override to POSITION_AOE with shape
    from dnd.core.aoe import Sphere
    template.alt_target_type = TargetType.POSITION_AOE
    template.aoe_shape = Sphere(
        source_entity_uuid=caster.uuid,
        target=(0, 0),
        radius_feet=10,
    )

    # Property routing works correctly
    assert template.effective_target_type == TargetType.POSITION_AOE
    assert template in caster.position_actions, "Template should be in position_actions property"
    assert template not in caster.entity_actions, "Template should NOT be in entity_actions property"

    # With bug #4 fixed, get_valid_positions() now returns positions for overridden spells
    actions2 = caster.get_available_actions()
    fb_entity2 = [a for a in actions2.entity_actions if a.template_name == "Fire Bolt"]
    fb_pos2 = [a for a in actions2.position_actions if a.template_name == "Fire Bolt"]
    assert len(fb_entity2) == 0, "Fire Bolt should NOT be in entity_actions with AOE override"
    assert len(fb_pos2) > 0, "Fire Bolt should appear in position_actions with AOE override"


@test("G30: ENTITY→MULTI_ENTITY stays in entity_actions")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    make_target("T1", (1, 0))
    make_target("T2", (0, 1))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)

    template = find_template(caster, "Fire Bolt")
    template.alt_target_type = TargetType.MULTI_ENTITY

    actions = caster.get_available_actions()
    fb_infos = [a for a in actions.entity_actions if a.template_name == "Fire Bolt"]
    assert len(fb_infos) > 0, "Fire Bolt with MULTI_ENTITY should be in entity_actions"
    assert fb_infos[0].target_type == TargetType.MULTI_ENTITY


# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
print(f"{'='*60}")

if failed > 0:
    print("\nFAILED TESTS:")
    exit(1)
else:
    print("\nAll tests passed!")
