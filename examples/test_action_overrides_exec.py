"""
Deep execution tests for alt-field override system.

Unlike test_action_overrides.py (property-level checks), these tests actually
cast spells end-to-end with overrides and verify game state changes:
damage, saves, concentration cascades, terrain effects, event hierarchy.

Categories:
  EX-A: Range override execution
  EX-B: Cost override execution
  EX-C: Target type swap — full execution
  EX-D: Concentration + multi-target execution
  EX-E: _finalize_aoe gating
  EX-F: Event hierarchy verification
  EX-G: Combined overrides in same turn
"""

from typing import cast as type_cast
from uuid import uuid4, UUID

from dnd.utils import reset_combat_state
reset_combat_state()

from dnd.entity import Entity, EntityConfig
from dnd.blocks.abilities import AbilityScoresConfig, AbilityConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.gridmap import get_map
from dnd.core.base_actions import TargetType, Cost
from dnd.core.events import AbilityName
from dnd.core.modifiers import NumericalModifier, CreatureType
from dnd.actions_functional import setup_standard_actions
from dnd.spells.evocation import (
    FireBolt, Fireball, IceStorm, MagicMissile, GustOfWind,
)
from dnd.spells.enchantment import HoldPerson
from dnd.encounter import Encounter
from dnd.controller import HumanController
from dnd.utils import (
    get_hp, has_condition, deal_damage_to,
    force_spell_attack_hit, remove_spell_attack_modifier,
)

passed = 0
failed = 0
test_names: list = []

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
        except Exception as e:
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
    """Reset all state and create a large grid."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, GRID_SIZE, GRID_SIZE)


def make_caster(name: str, position: tuple, faction: str = "heroes") -> Entity:
    """Create a spellcaster entity with good stats."""
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
    """Create a target with low WIS for easy save failures."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            wisdom=AbilityConfig(ability_score=3),
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


def setup_encounter(*entities: Entity) -> Encounter:
    """Set up encounter with given entities, start it."""
    Entity.update_all_entities_senses(max_distance=SENSES_DISTANCE)
    enc = Encounter(name="Test", source_entity_uuid=uuid4())
    for e in entities:
        enc.add_combatant(e, HumanController(source_entity_uuid=e.uuid))
    enc.roll_initiative()
    enc.start_encounter()
    return enc


def force_save_fail(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add -100 to saving throw to guarantee failure (unless nat 20)."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    mod = NumericalModifier(
        name="Force Fail", value=-100,
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )
    return save.bonus.self_static.add_value_modifier(mod)


def force_save_pass(entity: Entity, ability: str = "wisdom") -> UUID:
    """Add +100 to saving throw to guarantee success (unless nat 1)."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    mod = NumericalModifier(
        name="Force Pass", value=100,
        source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid
    )
    return save.bonus.self_static.add_value_modifier(mod)


def remove_save_modifier(entity: Entity, mod_uuid: UUID, ability: str = "wisdom"):
    """Remove a forced save modifier."""
    save = entity.saving_throws.get_saving_throw(type_cast(AbilityName, ability))
    save.bonus.self_static.remove_modifier(mod_uuid)


# ============================================================================
# Category EX-A: Range Override Execution
# ============================================================================

print("\n=== Category EX-A: Range Override Execution ===")


@test("EX-A1: Fire Bolt at extended range deals damage")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    # 130ft = 26 tiles, beyond default 120ft range
    target = make_target("Far Target", (26, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()
    # Re-expand senses (start_turn resets to max_distance=20 = 100ft)
    caster.update_entity_senses(max_distance=SENSES_DISTANCE)

    hp_before = get_hp(target)

    # Without override, should cancel (out of range)
    spell_no_override = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
    )
    result = spell_no_override.apply()
    assert result is None or result.canceled, "Fire Bolt at 130ft without override should fail"
    assert get_hp(target) == hp_before, "No damage without range override"

    # With alt_range=300, should hit
    hit_mod = force_spell_attack_hit(caster)
    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
        alt_range=300,
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp_after = get_hp(target)
    assert hp_after < hp_before, f"Fire Bolt at 130ft with alt_range=300 should deal damage: {hp_before} → {hp_after}"


@test("EX-A2: Fire Bolt at extended range — cantrip scaling applies")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Far Target", (26, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()
    # Re-expand senses (start_turn resets to max_distance=20 = 100ft)
    caster.update_entity_senses(max_distance=SENSES_DISTANCE)

    hp_before = get_hp(target)

    # caster_level=11 → 3d10 Fire Bolt
    hit_mod = force_spell_attack_hit(caster)
    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=11,
        template=False,
        alt_range=300,
    )
    spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    hp_after = get_hp(target)
    damage_dealt = hp_before - hp_after
    assert damage_dealt >= 3, f"3d10 Fire Bolt should deal ≥3 damage, got {damage_dealt}"


# ============================================================================
# Category EX-B: Cost Override Execution
# ============================================================================

print("\n=== Category EX-B: Cost Override Execution ===")


@test("EX-B3: Fire Bolt as bonus action — actions still available")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)

    # Cast Fire Bolt as bonus action
    spell1 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        caster_level=5,
        template=False,
        alt_cost_type="bonus_actions",
    )
    spell1.apply()

    ba = caster.action_economy.bonus_actions.normalized_score
    act = caster.action_economy.actions.normalized_score
    assert ba == 0, f"Bonus action should be 0, got {ba}"
    assert act == 1, f"Standard action should still be 1, got {act}"

    # Now cast a second Fire Bolt using the standard action
    spell2 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t2.uuid,
        caster_level=5,
        template=False,
    )
    spell2.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    act2 = caster.action_economy.actions.normalized_score
    assert act2 == 0, f"After second cast, actions should be 0, got {act2}"

    # Both targets should have taken damage
    assert get_hp(t1) < 40, "T1 should have taken damage"
    assert get_hp(t2) < 40, "T2 should have taken damage"


@test("EX-B4: Hold Person with alt_skip_slot — slot not consumed, target paralyzed")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        target = make_target("Target", (1, 0))
        enc = setup_encounter(caster, target)
        enc.start_turn()

        l2_before = caster.action_economy.spell_slot_2.normalized_score
        force_save_fail(target, "wisdom")

        spell = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=2,
            template=False,
            alt_skip_slot=True,
        )
        spell.apply()

        if has_condition(target, "Paralyzed"):
            l2_after = caster.action_economy.spell_slot_2.normalized_score
            assert l2_after == l2_before, f"L2 slots should be unchanged: {l2_before} → {l2_after}"
            assert has_condition(target, "Paralyzed"), "Target should be Paralyzed"
            return

    assert False, "Could not get Hold Person save failure in 20 attempts"


@test("EX-B5: alt_extra_costs with resource_evaluator blocks cast when unaffordable")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    target = make_target("Target", (1, 0))
    enc = setup_encounter(caster, target)
    enc.start_turn()

    hp_before = get_hp(target)

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

    # With 0 SP, should fail
    caster._sorcery_points = 0  # type: ignore
    spell1 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
        alt_extra_costs=[sp_cost],
    )
    result1 = spell1.apply()
    assert get_hp(target) == hp_before, "Should not deal damage when SP unaffordable"

    # With 5 SP, should work
    caster._sorcery_points = 5  # type: ignore
    hit_mod = force_spell_attack_hit(caster)
    spell2 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        caster_level=5,
        template=False,
        alt_extra_costs=[sp_cost],
    )
    spell2.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    assert get_hp(target) < hp_before, "Should deal damage when SP affordable"


# ============================================================================
# Category EX-C: Target Type Swap — Full Execution
# ============================================================================

print("\n=== Category EX-C: Target Type Swap — Full Execution ===")


@test("EX-C6: Fire Bolt ENTITY→MULTI_ENTITY — 3 targets take damage")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    t3 = make_target("T3", (1, 1))
    enc = setup_encounter(caster, t1, t2, t3)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1 = get_hp(t1)
    hp2 = get_hp(t2)
    hp3 = get_hp(t3)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        extra_target_entity_uuids=[t2.uuid, t3.uuid],
        caster_level=5,
        template=False,
        alt_target_type=TargetType.MULTI_ENTITY,
    )
    result = spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    assert get_hp(t1) < hp1, "T1 should take damage"
    assert get_hp(t2) < hp2, "T2 should take damage"
    assert get_hp(t3) < hp3, "T3 should take damage"

    # Verify event result has correct target count
    # NOTE: total_damage is 0 because FireBolt._apply() doesn't set it on completion
    # (only AoE spells like Fireball set total_damage for convolution aggregation)
    assert result is not None, "Result should not be None"
    assert result.total_targets == 3, f"total_targets should be 3, got {result.total_targets}"


@test("EX-C7: Fire Bolt ENTITY→POSITION_AOE — AoE splash damage")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (3, 0))
    t2 = make_target("T2", (3, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    from dnd.core.aoe import Sphere
    hit_mod = force_spell_attack_hit(caster)
    hp1 = get_hp(t1)
    hp2 = get_hp(t2)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        end_position=(3, 0),
        caster_level=5,
        template=False,
        alt_target_type=TargetType.POSITION_AOE,
        aoe_shape=Sphere(
            source_entity_uuid=caster.uuid,
            target=(3, 0),
            radius_feet=10,
        ),
    )
    result = spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    assert get_hp(t1) < hp1, "T1 should take damage from AoE"
    assert get_hp(t2) < hp2, "T2 should take damage from AoE"
    assert result is not None
    assert result.total_targets == 2, f"total_targets should be 2, got {result.total_targets}"


@test("EX-C8: Fireball POSITION_AOE→ENTITY — single target, no splash")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        target = make_target("Target", (2, 0))
        bystander = make_target("Bystander", (2, 1))
        enc = setup_encounter(caster, target, bystander)
        enc.start_turn()

        hp_target = get_hp(target)
        hp_bystander = get_hp(bystander)

        force_save_fail(target, "dexterity")

        spell = Fireball(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=(2, 0),
            cast_at_level=3,
            template=False,
            alt_target_type=TargetType.ENTITY,
        )
        spell.apply()

        # Check if target took damage (should have, with -100 save)
        if get_hp(target) < hp_target:
            assert get_hp(bystander) == hp_bystander, "Bystander should NOT take damage with ENTITY override"
            return

    assert False, "Could not get Fireball save failure in 20 attempts"


@test("EX-C9: Fireball POSITION_AOE→MULTI_ENTITY — cherry-pick targets")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (2, 0))
        t2 = make_target("T2", (2, 1))
        t3 = make_target("T3", (3, 0))  # Not selected
        enc = setup_encounter(caster, t1, t2, t3)
        enc.start_turn()

        hp1 = get_hp(t1)
        hp2 = get_hp(t2)
        hp3 = get_hp(t3)

        force_save_fail(t1, "dexterity")
        force_save_fail(t2, "dexterity")

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

        if get_hp(t1) < hp1 and get_hp(t2) < hp2:
            assert get_hp(t3) == hp3, "T3 should NOT take damage (not selected)"
            return

    assert False, "Could not get Fireball save failures in 20 attempts"


@test("EX-C10: Magic Missile as POSITION_AOE — MM override takes precedence")
def _():
    """Documents behavior: MM overrides get_all_targets(), so even with POSITION_AOE
    override, MM's projectile logic takes over. Only the primary target (t1) gets
    all 3 darts; the AoE shape is ignored for target resolution."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (3, 0))
    t2 = make_target("T2", (3, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    from dnd.core.aoe import Sphere
    hp1 = get_hp(t1)
    hp2 = get_hp(t2)

    spell = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        end_position=(3, 0),
        cast_at_level=1,
        template=False,
        alt_target_type=TargetType.POSITION_AOE,
        aoe_shape=Sphere(
            source_entity_uuid=caster.uuid,
            target=(3, 0),
            radius_feet=10,
        ),
    )
    result = spell.apply()

    # MM's get_all_targets() override uses projectile logic (3 darts → all at t1)
    # The POSITION_AOE shape is ignored because MM doesn't call super().get_all_targets()
    assert get_hp(t1) < hp1, "T1 should take damage from 3 darts"
    assert get_hp(t2) == hp2, "T2 should NOT take damage (MM override ignores AoE shape)"
    assert result is not None
    assert result.total_targets == 3, f"total_targets should be 3 (darts), got {result.total_targets}"


# ============================================================================
# Category EX-D: Concentration + Multi-Target Execution
# ============================================================================

print("\n=== Category EX-D: Concentration + Multi-Target Execution ===")


@test("EX-D11: Hold Person MULTI_ENTITY — conc break via damage removes all")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (1, 0))
        t2 = make_target("T2", (0, 1))
        enc = setup_encounter(caster, t1, t2)
        enc.start_turn()

        force_save_fail(t1, "wisdom")
        force_save_fail(t2, "wisdom")

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

        if has_condition(t1, "Paralyzed") and has_condition(t2, "Paralyzed"):
            assert has_condition(caster, "Concentrating")

            # DC=50 CON save — impossible (unless nat 20)
            force_save_fail(caster, "constitution")
            deal_damage_to(caster, 100, source_uuid=t1.uuid)

            if not has_condition(caster, "Concentrating"):
                assert not has_condition(t1, "Paralyzed"), "T1 should be freed"
                assert not has_condition(t2, "Paralyzed"), "T2 should be freed"
                assert not has_condition(t1, "Hold Person"), "T1 Hold Person removed"
                assert not has_condition(t2, "Hold Person"), "T2 Hold Person removed"
                return

    assert False, "Could not get deterministic Hold Person + conc break in 20 attempts"


@test("EX-D12: Hold Person MULTI_ENTITY — partial save, then damage break")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (1, 0))
        t2 = make_target("T2", (0, 1))
        t3 = make_target("T3", (1, 1))
        enc = setup_encounter(caster, t1, t2, t3)
        enc.start_turn()

        force_save_fail(t1, "wisdom")
        force_save_fail(t2, "wisdom")
        force_save_pass(t3, "wisdom")

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

        t1_held = has_condition(t1, "Paralyzed")
        t2_held = has_condition(t2, "Paralyzed")
        t3_held = has_condition(t3, "Paralyzed")

        if t1_held and t2_held and not t3_held:
            assert has_condition(caster, "Concentrating")

            # Break concentration
            force_save_fail(caster, "constitution")
            deal_damage_to(caster, 100, source_uuid=t1.uuid)

            if not has_condition(caster, "Concentrating"):
                assert not has_condition(t1, "Paralyzed"), "T1 freed after conc break"
                assert not has_condition(t2, "Paralyzed"), "T2 freed after conc break"
                return

    assert False, "Could not get partial save + conc break in 20 attempts"


@test("EX-D13: Hold Person MULTI_ENTITY — one target freed, conc survives, then break")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (1, 0))
        t2 = make_target("T2", (0, 1))
        enc = setup_encounter(caster, t1, t2)
        enc.start_turn()

        force_save_fail(t1, "wisdom")
        force_save_fail(t2, "wisdom")

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

        if has_condition(t1, "Paralyzed") and has_condition(t2, "Paralyzed"):
            # Remove Hold Person from T1 manually
            t1.remove_condition("Hold Person")
            assert not has_condition(t1, "Paralyzed"), "T1 should be freed"
            assert has_condition(caster, "Concentrating"), "Conc should survive (policy=last)"
            assert has_condition(t2, "Paralyzed"), "T2 should still be paralyzed"

            # Now break concentration via damage
            force_save_fail(caster, "constitution")
            deal_damage_to(caster, 100, source_uuid=t1.uuid)

            if not has_condition(caster, "Concentrating"):
                assert not has_condition(t2, "Paralyzed"), "T2 freed after conc break"
                return

    assert False, "Could not get deterministic Hold Person + partial removal in 20 attempts"


# ============================================================================
# Category EX-E: _finalize_aoe Gating
# ============================================================================

print("\n=== Category EX-E: _finalize_aoe Gating ===")


@test("EX-E14: IceStorm normal — terrain created (control)")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        target = make_target("Target", (4, 0))
        enc = setup_encounter(caster, target)
        enc.start_turn()

        force_save_fail(target, "dexterity")

        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=(4, 0),
            cast_at_level=4,
            template=False,
        )
        spell.apply()

        if get_hp(target) < 40:
            # Terrain should exist on caster (IceStormTerrain is tracked as caster condition)
            assert has_condition(caster, "Ice Storm Terrain"), "Normal IceStorm SHOULD create terrain"
            return

    assert False, "Could not get IceStorm save failure in 20 attempts"


@test("EX-E15: IceStorm→ENTITY — no terrain, damage still dealt")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        target = make_target("Target", (2, 0))
        enc = setup_encounter(caster, target)
        enc.start_turn()

        hp_before = get_hp(target)
        force_save_fail(target, "dexterity")

        spell = IceStorm(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=(2, 0),
            cast_at_level=4,
            template=False,
            alt_target_type=TargetType.ENTITY,
        )
        spell.apply()

        if get_hp(target) < hp_before:
            assert not has_condition(caster, "Ice Storm Terrain"), "No terrain with ENTITY override"
            return

    assert False, "Could not get IceStorm save failure in 20 attempts"


@test("EX-E16: GustOfWind→ENTITY — no zone, no concentration")
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

    assert not has_condition(caster, "Gust of Wind Zone"), "No zone with ENTITY override"
    assert not has_condition(caster, "Concentrating"), "No concentration when _finalize_aoe skipped"


# ============================================================================
# Category EX-F: Event Hierarchy Verification
# ============================================================================

print("\n=== Category EX-F: Event Hierarchy Verification ===")


@test("EX-F17: MULTI_ENTITY Fire Bolt — result has total_targets, HP drops verified")
def _():
    """FireBolt doesn't set total_damage on completion events (it's a single-target
    spell by design), so convolution aggregates 0. We verify HP drops directly."""
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    t3 = make_target("T3", (1, 1))
    enc = setup_encounter(caster, t1, t2, t3)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1 = get_hp(t1)
    hp2 = get_hp(t2)
    hp3 = get_hp(t3)

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        extra_target_entity_uuids=[t2.uuid, t3.uuid],
        caster_level=5,
        template=False,
        alt_target_type=TargetType.MULTI_ENTITY,
    )
    result = spell.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    assert result is not None, "Result should not be None"
    assert result.total_targets == 3, f"total_targets should be 3, got {result.total_targets}"

    # Verify all 3 targets took damage
    actual_damage = (hp1 - get_hp(t1)) + (hp2 - get_hp(t2)) + (hp3 - get_hp(t3))
    assert actual_damage > 0, f"Sum of HP drops should be > 0, got {actual_damage}"
    assert get_hp(t1) < hp1, "T1 should take damage"
    assert get_hp(t2) < hp2, "T2 should take damage"
    assert get_hp(t3) < hp3, "T3 should take damage"


@test("EX-F18: POSITION_AOE Fireball — result has total_targets and aoe_position")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        t1 = make_target("T1", (4, 0))
        enc = setup_encounter(caster, t1)
        enc.start_turn()

        force_save_fail(t1, "dexterity")

        spell = Fireball(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=t1.uuid,
            end_position=(4, 0),
            cast_at_level=3,
            template=False,
        )
        result = spell.apply()

        if result is not None and not result.canceled:
            assert result.total_targets >= 1, f"total_targets should be ≥1, got {result.total_targets}"
            assert result.aoe_position == (4, 0), f"aoe_position should be (4,0), got {result.aoe_position}"
            return

    assert False, "Could not get valid Fireball result in 20 attempts"


# ============================================================================
# Category EX-G: Combined Overrides in Same Turn
# ============================================================================

print("\n=== Category EX-G: Combined Overrides in Same Turn ===")


@test("EX-G19: Two spells in one turn via cost override")
def _():
    fresh_state()
    caster = make_caster("Mage", (0, 0))
    t1 = make_target("T1", (1, 0))
    t2 = make_target("T2", (0, 1))
    enc = setup_encounter(caster, t1, t2)
    enc.start_turn()

    hit_mod = force_spell_attack_hit(caster)
    hp1 = get_hp(t1)
    hp2 = get_hp(t2)

    # First: Fire Bolt as bonus action
    spell1 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t1.uuid,
        caster_level=5,
        template=False,
        alt_cost_type="bonus_actions",
    )
    spell1.apply()

    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert caster.action_economy.actions.normalized_score == 1

    # Second: normal Fire Bolt
    spell2 = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=t2.uuid,
        caster_level=5,
        template=False,
    )
    spell2.apply()
    remove_spell_attack_modifier(caster, hit_mod)

    assert caster.action_economy.actions.normalized_score == 0
    assert get_hp(t1) < hp1, "T1 should take damage"
    assert get_hp(t2) < hp2, "T2 should take damage"


@test("EX-G20: Upcast Hold Person L3 + alt_skip_slot — 0 slots used, still works")
def _():
    for attempt in range(20):
        fresh_state()
        caster = make_caster("Mage", (0, 0))
        target = make_target("Target", (1, 0))
        enc = setup_encounter(caster, target)
        enc.start_turn()

        l3_before = caster.action_economy.spell_slot_3.normalized_score
        force_save_fail(target, "wisdom")

        spell = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=3,
            template=False,
            alt_skip_slot=True,
        )
        spell.apply()

        if has_condition(target, "Paralyzed"):
            l3_after = caster.action_economy.spell_slot_3.normalized_score
            assert l3_after == l3_before, f"L3 slots should be unchanged: {l3_before} → {l3_after}"
            return

    assert False, "Could not get Hold Person save failure in 20 attempts"


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
