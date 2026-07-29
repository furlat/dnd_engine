"""Active regression coverage for temporary action and spell overrides.

The July test rework moved two executable runners out of pytest collection:
``examples/test_action_overrides.py`` (31 cases) and
``examples/test_action_overrides_exec.py`` (20 cases).  The tests below retain
their runtime contracts without retaining their print-driven custom runner.

Legacy-case coverage map:

* range/discovery/execution/scaling: A1, F28, EX-A1, EX-A2
* primary/extra costs and same-turn cleanup: A2, A5-A9, D18-D21,
  F27, EX-B3-EX-B5, EX-G19, EX-G20
* target-type routing and convolution: A3, A4, B10-B15, G29, G30,
  EX-C6-EX-C10, EX-F17
* concentration ownership and partial cleanup: C16, C17, EX-D11-EX-D13
* AoE finalization: E22-E24, EX-E14-EX-E16
* spell-owned multi-target semantics: F25, F25b, F26
* position-AoE event metadata: EX-F18
"""

from typing import cast
from uuid import UUID, uuid4

import pytest

from dnd.actions import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
    entity_resource_cost_evaluator,
)
from dnd.actions_functional import (
    apply_action_overrides,
    clear_action_overrides,
    execute_by_index,
    get_available_actions,
    register_spell,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import (
    ActionEconomyConfig,
    RechargeType,
)
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.core.aoe import Sphere
from dnd.core.base_actions import (
    AvailableActionInfo,
    Cost,
    TargetType,
)
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import AbilityName, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.core.creature_types import CreatureType
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.spells.conjuration import Web
from dnd.spells.enchantment import HoldPerson
from dnd.spells.evocation import (
    EldritchBlast,
    Fireball,
    FireBolt,
    GustOfWind,
    IceStorm,
    MagicMissile,
)
from tests.engine.support import (
    deal_damage_to,
    force_spell_attack_hit,
    remove_spell_attack_modifier,
    reset_combat_state,
)


def reset_override_state(width: int = 12, height: int = 6) -> None:
    """Reset all registries and create the small open grid used by one case."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, width, height)


def create_caster(
    *,
    name: str = "Override Caster",
    position: tuple[int, int] = (0, 0),
    spell_slots: dict[int, int] | None = None,
) -> Entity:
    """Create a durable humanoid spellcaster with ordinary turn resources."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=14),
            constitution=AbilityConfig(ability_score=14),
            intelligence=AbilityConfig(ability_score=14),
            wisdom=AbilityConfig(ability_score=18),
            charisma=AbilityConfig(ability_score=18),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=8,
                    hit_dice_count=10,
                    mode="maximums",
                )
            ]
        ),
        action_economy=ActionEconomyConfig(
            spell_slots=spell_slots
            if spell_slots is not None
            else {1: 4, 2: 3, 3: 3, 4: 2, 5: 1}
        ),
        spellcasting=SpellcastingConfig(spellcasting_ability="wisdom"),
        proficiency_bonus=4,
        position=position,
        faction="heroes",
    )
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    caster.creature_type = CreatureType.HUMANOID
    return caster


def create_target(
    name: str,
    position: tuple[int, int],
    *,
    faction: str = "monsters",
) -> Entity:
    """Create a high-HP humanoid target for deterministic spell assertions."""
    config = EntityConfig(
        ability_scores=AbilityScoresConfig(
            strength=AbilityConfig(ability_score=10),
            dexterity=AbilityConfig(ability_score=10),
            constitution=AbilityConfig(ability_score=10),
            wisdom=AbilityConfig(ability_score=10),
        ),
        health=HealthConfig(
            hit_dices=[
                HitDiceConfig(
                    hit_dice_value=10,
                    hit_dice_count=10,
                    mode="maximums",
                )
            ]
        ),
        action_economy=ActionEconomyConfig(),
        proficiency_bonus=2,
        position=position,
        faction=faction,
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=config,
    )
    target.creature_type = CreatureType.HUMANOID
    return target


def find_spell_template(caster: Entity, name: str) -> SpellAction:
    """Return one exact registered spell template."""
    template = caster.get_action_template(name)
    assert isinstance(template, SpellAction)
    return template


def find_action(
    caster: Entity,
    template_name: str,
) -> AvailableActionInfo:
    """Return one exact current discovery row."""
    available = get_available_actions(caster)
    return next(
        info
        for info in available.all_actions
        if info.template_name == template_name
    )


def target_index(action: AvailableActionInfo, target_uuid: UUID) -> int:
    """Return the discovery index for one entity target."""
    target = next(
        item
        for item in action.valid_targets
        if item.target_uuid == target_uuid
    )
    return target.index


def assert_completed(event: object) -> SpellEvent:
    """Narrow a successful spell result for subsequent assertions."""
    assert isinstance(event, SpellEvent)
    assert not event.canceled
    assert event.phase is EventPhase.COMPLETION
    return event


def force_save_result(
    entity: Entity,
    ability_name: AbilityName,
    *,
    succeeds: bool,
) -> None:
    """Make a non-natural-1/non-natural-20 save deterministic."""
    saving_throw = entity.saving_throws.get_saving_throw(ability_name)
    saving_throw.bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            name=f"Override test {ability_name} save",
            value=100 if succeeds else -100,
        )
    )


def sorcery_point_cost(amount: int = 2) -> Cost:
    """Create the real named-resource cost used by override tests."""
    return Cost(
        name="Sorcery Points",
        cost_type="actions",
        cost=0,
        resource_name="sorcery_points",
        resource_cost=amount,
        resource_evaluator=entity_resource_cost_evaluator,
    )


def test_range_override_controls_discovery_execution_scaling_and_clear() -> None:
    """A1/F28/EX-A1/EX-A2: one override owns range everywhere."""
    reset_override_state(width=30, height=2)
    caster = create_caster()
    far_target = create_target("Far Target", (26, 0))
    register_spell(caster, FireBolt, caster_level=11)
    Entity.update_all_entities_senses(max_distance=30)

    template = find_spell_template(caster, "Fire Bolt")

    def is_far_target_disclosed() -> bool:
        return any(
            candidate.target_uuid == far_target.uuid
            for info in get_available_actions(caster).entity_actions
            if info.template_name == "Fire Bolt"
            for candidate in info.valid_targets
        )

    assert template.effective_range == 120
    assert not is_far_target_disclosed()

    hp_before = far_target.get_hp()
    ordinary = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=far_target.uuid,
        caster_level=11,
        template=False,
    ).apply()

    assert ordinary is None or ordinary.canceled
    assert far_target.get_hp() == hp_before
    assert caster.action_economy.actions.normalized_score == 1

    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_range": 300},
    )
    assert modified == [template.uuid]
    assert template.effective_range == 300
    assert template.get_range().normal == 300
    assert is_far_target_disclosed()

    available = get_available_actions(caster)
    info = next(
        item for item in available.entity_actions if item.template_name == "Fire Bolt"
    )
    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(2, 2, 2, 2):
        result = execute_by_index(
            caster,
            "Fire Bolt",
            target_index(info, far_target.uuid),
            available=available,
        )
    remove_spell_attack_modifier(caster, hit_modifier)

    event = assert_completed(result)
    assert event.damage_rolls is not None
    assert event.damage_rolls[0].results == [2, 2, 2]
    assert far_target.get_hp() == hp_before - 6

    clear_action_overrides(caster, modified)

    assert template.alt_range is None
    assert template.effective_range == 120
    assert not is_far_target_disclosed()


def test_cost_override_executes_then_clears_within_the_same_turn() -> None:
    """A2/A8/EX-B3/EX-G19: cleanup changes the second same-turn cast."""
    reset_override_state()
    caster = create_caster()
    first_target = create_target("First Target", (1, 0))
    second_target = create_target("Second Target", (0, 1))
    register_spell(caster, FireBolt, caster_level=5)
    register_spell(caster, HoldPerson, caster_level=5)
    Entity.update_all_entities_senses()

    fire_bolt = find_spell_template(caster, "Fire Bolt")
    hold_person = find_spell_template(caster, "Hold Person")
    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_cost_type": "bonus_actions"},
    )

    assert modified == [fire_bolt.uuid]
    assert fire_bolt.alt_cost_type == "bonus_actions"
    assert hold_person.alt_cost_type is None

    hp_first = first_target.get_hp()
    hp_second = second_target.get_hp()
    available = get_available_actions(caster)
    info = next(
        item for item in available.entity_actions if item.template_name == "Fire Bolt"
    )
    assert info.cost_type == "bonus_actions"

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 20)):
        first_result = execute_by_index(
            caster,
            "Fire Bolt",
            target_index(info, first_target.uuid),
            available=available,
        )

    assert_completed(first_result)
    assert caster.action_economy.bonus_actions.normalized_score == 0
    assert caster.action_economy.actions.normalized_score == 1

    clear_action_overrides(caster, modified)
    assert fire_bolt.alt_cost_type is None

    restored = get_available_actions(caster)
    restored_info = next(
        item
        for item in restored.entity_actions
        if item.template_name == "Fire Bolt"
    )
    assert restored_info.cost_type == "actions"

    with fixed_dice_faces(*([2] * 20)):
        second_result = execute_by_index(
            caster,
            "Fire Bolt",
            target_index(restored_info, second_target.uuid),
            available=restored,
        )
    remove_spell_attack_modifier(caster, hit_modifier)

    assert_completed(second_result)
    assert caster.action_economy.actions.normalized_score == 0
    assert first_target.get_hp() < hp_first
    assert second_target.get_hp() < hp_second


def test_effective_cost_overrides_compose_without_rewriting_non_action_costs() -> None:
    """A7/F27: override channels compose and only replace action costs."""
    reset_override_state()
    caster = create_caster()
    register_spell(caster, FireBolt, caster_level=5)

    fire_bolt = find_spell_template(caster, "Fire Bolt")
    extra_cost = Cost(
        name="Extra",
        cost_type="bonus_actions",
        cost=0,
        resource_name="test",
        resource_cost=1,
    )
    fire_bolt.alt_cost_type = "bonus_actions"
    fire_bolt.alt_range = 500
    fire_bolt.alt_extra_costs = [extra_cost]

    assert fire_bolt.effective_range == 500
    assert any(
        cost.name == "Cast Spell" and cost.cost_type == "bonus_actions"
        for cost in fire_bolt.effective_costs
    )
    assert [cost for cost in fire_bolt.effective_costs if cost.name == "Extra"] == [
        extra_cost
    ]

    already_bonus = SpellAction(
        source_entity_uuid=caster.uuid,
        template=False,
        costs=[
            Cost(
                name="Bonus Cast",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        alt_cost_type="reactions",
    )

    assert [cost.cost_type for cost in already_bonus.effective_costs] == [
        "bonus_actions"
    ]


def test_target_count_routing_and_cleanup_follow_effective_target_type() -> None:
    """A3/A4/A9/G29/G30: discovery routes the effective target contract."""
    reset_override_state()
    caster = create_caster()
    create_target("First Target", (2, 0))
    create_target("Second Target", (2, 1))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses()

    template = find_spell_template(caster, "Fire Bolt")
    assert template.get_multi_target_count() is None

    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {
            "alt_target_type": TargetType.MULTI_ENTITY,
            "alt_target_count": 3,
        },
    )

    assert template.get_multi_target_count() == 3
    multi = find_action(caster, "Fire Bolt")
    assert multi.target_type is TargetType.MULTI_ENTITY
    assert multi in get_available_actions(caster).entity_actions

    clear_action_overrides(caster, modified)

    restored = find_action(caster, "Fire Bolt")
    assert template.get_multi_target_count() is None
    assert restored.target_type is TargetType.ENTITY

    template.aoe_shape = Sphere(
        source_entity_uuid=caster.uuid,
        target=(2, 0),
        radius_feet=10,
    )
    aoe_modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_target_type": TargetType.POSITION_AOE},
    )
    aoe_actions = get_available_actions(caster)

    assert template in caster.position_actions
    assert template not in caster.entity_actions
    assert not any(
        info.template_name == "Fire Bolt"
        for info in aoe_actions.entity_actions
    )
    assert any(
        info.template_name == "Fire Bolt"
        for info in aoe_actions.position_actions
    )

    clear_action_overrides(caster, aoe_modified)
    assert template.effective_target_type is TargetType.ENTITY


def test_extra_resource_cost_gates_discovery_execution_and_is_consumed() -> None:
    """A6/D20/EX-B5: an extra named resource is a real executable cost."""
    reset_override_state()
    caster = create_caster()
    target = create_target("Resource Target", (1, 0))
    register_spell(caster, FireBolt, caster_level=5)
    Entity.update_all_entities_senses()

    template = find_spell_template(caster, "Fire Bolt")
    extra_cost = sorcery_point_cost()
    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Fire Bolt",
        {"alt_extra_costs": [extra_cost]},
    )

    assert not template.check_costs()
    assert len(template.generate_variants(caster)) == 1
    assert [
        cost.name
        for cost in template.generate_variants(caster)[0].effective_costs
        if cost.resource_name == "sorcery_points"
    ] == ["Sorcery Points"]
    unaffordable = find_action(caster, "Fire Bolt")
    assert unaffordable.can_afford is False
    assert unaffordable.valid_targets == []
    assert not any(
        info.template_name == "Fire Bolt"
        for info in get_available_actions(caster, legal_only=True).all_actions
    )

    hp_before = target.get_hp()
    unavailable_result = template.instantiate(
        target_entity_uuid=target.uuid
    ).apply()
    assert unavailable_result is None
    assert target.get_hp() == hp_before

    caster.action_economy.add_resource(
        "sorcery_points",
        maximum=2,
        recharge_type=RechargeType.LONG_REST,
    )
    assert template.check_costs()
    assert find_action(caster, "Fire Bolt").can_afford

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 20)):
        result = template.instantiate(target_entity_uuid=target.uuid).apply()
    remove_spell_attack_modifier(caster, hit_modifier)

    assert_completed(result)
    assert target.get_hp() < hp_before
    assert caster.action_economy.get_resource_current("sorcery_points") == 0
    assert caster.action_economy.actions.normalized_score == 0

    clear_action_overrides(caster, modified)
    assert template.alt_extra_costs == []


def test_generated_upcast_variant_checks_and_consumes_extra_resource_once() -> None:
    """D20/EX-B5: generated spell rows normalize each extra cost once."""
    reset_override_state()
    caster = create_caster(spell_slots={1: 1})
    target = create_target("Missile Resource Target", (2, 0))
    register_spell(caster, MagicMissile, caster_level=5)
    Entity.update_all_entities_senses()

    template = find_spell_template(caster, "Magic Missile")
    modified = apply_action_overrides(
        caster,
        lambda action: action.name == "Magic Missile",
        {"alt_extra_costs": [sorcery_point_cost()]},
    )
    caster.action_economy.add_resource(
        "sorcery_points",
        maximum=1,
        recharge_type=RechargeType.LONG_REST,
    )

    unaffordable_variant = template.generate_variants(caster)[0]
    assert not unaffordable_variant.check_costs()
    assert len(
        [
            cost
            for cost in unaffordable_variant.effective_costs
            if cost.resource_name == "sorcery_points"
        ]
    ) == 1
    unavailable = find_action(caster, "Magic Missile__slot_1")
    assert unavailable.can_afford is False
    assert unavailable.valid_targets == []
    assert not any(
        info.template_name == "Magic Missile__slot_1"
        for info in get_available_actions(caster, legal_only=True).all_actions
    )

    caster.action_economy.add_resource(
        "sorcery_points",
        maximum=2,
        recharge_type=RechargeType.LONG_REST,
    )
    available = get_available_actions(caster)
    affordable = next(
        info
        for info in available.entity_actions
        if info.template_name == "Magic Missile__slot_1"
    )

    assert affordable.can_afford
    assert len(
        [
            cost
            for cost in affordable.costs
            if cost.resource_name == "sorcery_points"
        ]
    ) == 1

    hp_before = target.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        result = execute_by_index(
            caster,
            affordable.template_name,
            target_index(affordable, target.uuid),
            available=available,
        )

    event = assert_completed(result)
    assert event.total_targets == 3
    assert target.get_hp() == hp_before - 9
    assert caster.action_economy.get_resource_current("sorcery_points") == 0
    assert caster.action_economy.spell_slot_1.normalized_score == 0

    clear_action_overrides(caster, modified)


def test_upcast_variants_preserve_cost_swap_and_skip_slot_overrides() -> None:
    """A5/D18/D19: all generated levels use one effective cost policy."""
    reset_override_state()
    caster = create_caster(spell_slots={2: 2, 3: 2, 4: 1})
    register_spell(caster, HoldPerson, caster_level=7)

    template = find_spell_template(caster, "Hold Person")
    assert any(
        cost.cost_type.startswith("spell_slot_")
        for cost in template.effective_costs
    )

    template.alt_cost_type = "bonus_actions"
    variants = template.generate_variants(caster)

    assert [variant.cast_at_level for variant in variants] == [2, 3, 4]
    for variant in variants:
        assert any(
            cost.cost_type == "bonus_actions" and cost.cost == 1
            for cost in variant.effective_costs
        )
        assert any(
            cost.cost_type == f"spell_slot_{variant.cast_at_level}"
            for cost in variant.effective_costs
        )

    template.alt_skip_slot = True
    slotless_variants = template.generate_variants(caster)

    assert [variant.cast_at_level for variant in slotless_variants] == [2, 3, 4]
    assert all(
        not any(
            cost.cost_type.startswith("spell_slot_")
            for cost in variant.effective_costs
        )
        for variant in slotless_variants
    )
    assert not any(
        cost.cost_type.startswith("spell_slot_")
        for cost in template.effective_costs
    )


@pytest.mark.parametrize("cast_at_level", [2, 3])
def test_skip_slot_execution_applies_upcast_effect_without_consuming_slot(
    cast_at_level: int,
) -> None:
    """D21/EX-B4/EX-G20: slotless level-2 and level-3 casts both execute."""
    reset_override_state()
    caster = create_caster(spell_slots={2: 2, 3: 2})
    target = create_target("Held Target", (1, 0))
    Entity.update_all_entities_senses()
    force_save_result(target, "wisdom", succeeds=False)

    slot = (
        caster.action_economy.spell_slot_2
        if cast_at_level == 2
        else caster.action_economy.spell_slot_3
    )
    slot_before = slot.normalized_score

    with fixed_dice_faces(2):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            cast_at_level=cast_at_level,
            template=False,
            alt_skip_slot=True,
        ).apply()

    assert_completed(result)
    assert "Paralyzed" in target.active_conditions
    assert slot.normalized_score == slot_before
    assert caster.action_economy.actions.normalized_score == 0


def test_entity_to_multi_entity_convolves_and_registers_child_applications() -> None:
    """B10/EX-C6/EX-F17: each selected entity owns one child lineage."""
    reset_override_state()
    caster = create_caster()
    targets = [
        create_target("Target One", (1, 0)),
        create_target("Target Two", (0, 1)),
        create_target("Target Three", (1, 1)),
    ]
    Entity.update_all_entities_senses()
    hp_before = {target.uuid: target.get_hp() for target in targets}

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 20)):
        result = FireBolt(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=targets[0].uuid,
            extra_target_entity_uuids=[
                targets[1].uuid,
                targets[2].uuid,
            ],
            caster_level=5,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
        ).apply()
    remove_spell_attack_modifier(caster, hit_modifier)

    event = assert_completed(result)
    assert event.total_targets == 3
    assert all(target.get_hp() < hp_before[target.uuid] for target in targets)

    application_completions = [
        candidate
        for candidate in EventQueue.get_events_by_phase(EventPhase.COMPLETION)
        if isinstance(candidate, SpellEvent)
        and candidate.name == "Fire Bolt"
        and candidate.application_id is not None
    ]
    assert len(application_completions) == 3
    assert {
        candidate.target_entity_uuid
        for candidate in application_completions
    } == {target.uuid for target in targets}
    assert sorted(
        cast(int, candidate.application_index)
        for candidate in application_completions
    ) == [0, 1, 2]
    assert len(
        {candidate.lineage_uuid for candidate in application_completions}
    ) == 3
    assert all(
        candidate.parent_event is not None
        for candidate in application_completions
    )


def test_position_aoe_to_entity_affects_only_the_explicit_target() -> None:
    """B11/EX-C8: replacing POSITION_AOE with ENTITY disables splash."""
    reset_override_state()
    caster = create_caster()
    target = create_target("Explicit Target", (4, 0))
    bystander = create_target("Bystander", (4, 1))
    Entity.update_all_entities_senses()
    force_save_result(target, "dexterity", succeeds=False)
    hp_target = target.get_hp()
    hp_bystander = bystander.get_hp()

    with fixed_dice_faces(*([2] * 9)):
        result = Fireball(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=target.position,
            cast_at_level=3,
            template=False,
            alt_target_type=TargetType.ENTITY,
        ).apply()

    assert_completed(result)
    assert target.get_hp() < hp_target
    assert bystander.get_hp() == hp_bystander


def test_position_aoe_to_multi_entity_affects_only_selected_targets() -> None:
    """B12/EX-C9: replacing POSITION_AOE with MULTI_ENTITY cherry-picks."""
    reset_override_state()
    caster = create_caster()
    selected = [
        create_target("Selected One", (4, 0)),
        create_target("Selected Two", (4, 1)),
    ]
    unselected = create_target("Unselected", (5, 0))
    Entity.update_all_entities_senses()
    for target in selected:
        force_save_result(target, "dexterity", succeeds=False)
    hp_before = {
        target.uuid: target.get_hp()
        for target in [*selected, unselected]
    }

    with fixed_dice_faces(*([2] * 18)):
        result = Fireball(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=selected[0].uuid,
            extra_target_entity_uuids=[selected[1].uuid],
            end_position=selected[0].position,
            cast_at_level=3,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
        ).apply()

    event = assert_completed(result)
    assert event.total_targets == 2
    assert all(
        target.get_hp() < hp_before[target.uuid]
        for target in selected
    )
    assert unselected.get_hp() == hp_before[unselected.uuid]


@pytest.mark.parametrize("with_shape", [True, False])
def test_entity_to_position_aoe_uses_shape_for_convolution(
    with_shape: bool,
) -> None:
    """B13/B14/EX-C7: a promoted entity spell uses only explicit AoE geometry."""
    reset_override_state()
    caster = create_caster()
    targets = [
        create_target("Area One", (3, 0)),
        create_target("Area Two", (3, 1)),
    ]
    Entity.update_all_entities_senses()
    hp_before = {target.uuid: target.get_hp() for target in targets}

    spell = FireBolt(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=targets[0].uuid,
        end_position=(3, 0),
        caster_level=5,
        template=False,
        alt_target_type=TargetType.POSITION_AOE,
        aoe_shape=(
            Sphere(
                source_entity_uuid=caster.uuid,
                target=(3, 0),
                radius_feet=10,
            )
            if with_shape
            else None
        ),
    )

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 6)):
        result = spell.apply()
    remove_spell_attack_modifier(caster, hit_modifier)

    event = assert_completed(result)
    if with_shape:
        assert event.total_targets == 2
        assert event.aoe_position == (3, 0)
        assert all(
            target.get_hp() < hp_before[target.uuid]
            for target in targets
        )
    else:
        assert event.total_targets == 0
        assert all(
            target.get_hp() == hp_before[target.uuid]
            for target in targets
        )


def test_position_zone_spell_still_requires_position_when_retargeted() -> None:
    """B15: a target-type override cannot replace a spell-owned prerequisite."""
    reset_override_state()
    caster = create_caster()
    target = create_target("Web Target", (2, 0))
    Entity.update_all_entities_senses()
    actions_before = caster.action_economy.actions.normalized_score
    slots_before = caster.action_economy.spell_slot_2.normalized_score

    result = Web(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid,
        end_position=None,
        cast_at_level=2,
        template=False,
        alt_target_type=TargetType.ENTITY,
    ).apply()

    assert result is not None
    assert result.canceled
    assert caster.action_economy.actions.normalized_score == actions_before
    assert caster.action_economy.spell_slot_2.normalized_score == slots_before


def test_multitarget_concentration_has_one_owner_and_manual_break_cleans_all() -> None:
    """C16: convolution reuses one concentration condition for every target."""
    reset_override_state()
    caster = create_caster()
    targets = [
        create_target("Held One", (1, 0)),
        create_target("Held Two", (0, 1)),
        create_target("Held Three", (1, 1)),
    ]
    Entity.update_all_entities_senses()
    for target in targets:
        force_save_result(target, "wisdom", succeeds=False)

    with fixed_dice_faces(*([2] * 20)):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=targets[0].uuid,
            extra_target_entity_uuids=[
                targets[1].uuid,
                targets[2].uuid,
            ],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=3,
        ).apply()

    assert_completed(result)
    assert list(caster.active_conditions).count("Concentrating") == 1
    assert all("Paralyzed" in target.active_conditions for target in targets)

    caster.remove_condition("Concentrating")

    assert "Concentrating" not in caster.active_conditions
    assert all("Hold Person" not in target.active_conditions for target in targets)
    assert all("Paralyzed" not in target.active_conditions for target in targets)


def test_multitarget_concentration_survives_until_its_last_child_is_removed() -> None:
    """C17: policy=last preserves siblings and then removes the owner."""
    reset_override_state()
    caster = create_caster()
    first = create_target("Held One", (1, 0))
    second = create_target("Held Two", (0, 1))
    Entity.update_all_entities_senses()
    force_save_result(first, "wisdom", succeeds=False)
    force_save_result(second, "wisdom", succeeds=False)

    with fixed_dice_faces(2, 2):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=first.uuid,
            extra_target_entity_uuids=[second.uuid],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=2,
        ).apply()

    assert_completed(result)
    first.remove_condition("Hold Person")

    assert "Paralyzed" not in first.active_conditions
    assert "Concentrating" in caster.active_conditions
    assert "Paralyzed" in second.active_conditions

    second.remove_condition("Hold Person")

    assert "Paralyzed" not in second.active_conditions
    assert "Concentrating" not in caster.active_conditions


def test_damage_breaks_multitarget_concentration_and_all_linked_effects() -> None:
    """EX-D11: failed damage concentration save removes all held targets."""
    reset_override_state()
    caster = create_caster()
    targets = [
        create_target("Held One", (1, 0)),
        create_target("Held Two", (0, 1)),
    ]
    Entity.update_all_entities_senses()
    for target in targets:
        force_save_result(target, "wisdom", succeeds=False)

    with fixed_dice_faces(2, 2):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=targets[0].uuid,
            extra_target_entity_uuids=[targets[1].uuid],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=2,
        ).apply()
    assert_completed(result)
    assert all("Paralyzed" in target.active_conditions for target in targets)

    force_save_result(caster, "constitution", succeeds=False)
    with fixed_dice_faces(2):
        deal_damage_to(caster, 10, source_uuid=targets[0].uuid)

    assert "Concentrating" not in caster.active_conditions
    assert all("Hold Person" not in target.active_conditions for target in targets)
    assert all("Paralyzed" not in target.active_conditions for target in targets)


def test_partial_save_then_damage_break_cleans_only_applied_children() -> None:
    """EX-D12: a successful target save does not corrupt later cleanup."""
    reset_override_state()
    caster = create_caster()
    failed_targets = [
        create_target("Failed One", (1, 0)),
        create_target("Failed Two", (0, 1)),
    ]
    successful_target = create_target("Successful Save", (1, 1))
    Entity.update_all_entities_senses()
    for target in failed_targets:
        force_save_result(target, "wisdom", succeeds=False)
    force_save_result(successful_target, "wisdom", succeeds=True)

    with fixed_dice_faces(2, 2, 2):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=failed_targets[0].uuid,
            extra_target_entity_uuids=[
                failed_targets[1].uuid,
                successful_target.uuid,
            ],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=3,
        ).apply()

    assert_completed(result)
    assert all(
        "Paralyzed" in target.active_conditions
        for target in failed_targets
    )
    assert "Paralyzed" not in successful_target.active_conditions
    assert "Concentrating" in caster.active_conditions

    force_save_result(caster, "constitution", succeeds=False)
    with fixed_dice_faces(2):
        deal_damage_to(caster, 10, source_uuid=failed_targets[0].uuid)

    assert "Concentrating" not in caster.active_conditions
    assert all(
        "Paralyzed" not in target.active_conditions
        for target in failed_targets
    )


def test_partial_manual_cleanup_then_damage_break_removes_remaining_child() -> None:
    """EX-D13: damage cleanup remains correct after one child leaves early."""
    reset_override_state()
    caster = create_caster()
    first = create_target("Held One", (1, 0))
    second = create_target("Held Two", (0, 1))
    Entity.update_all_entities_senses()
    force_save_result(first, "wisdom", succeeds=False)
    force_save_result(second, "wisdom", succeeds=False)

    with fixed_dice_faces(2, 2):
        result = HoldPerson(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=first.uuid,
            extra_target_entity_uuids=[second.uuid],
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=2,
        ).apply()
    assert_completed(result)

    first.remove_condition("Hold Person")
    assert "Concentrating" in caster.active_conditions
    assert "Paralyzed" in second.active_conditions

    force_save_result(caster, "constitution", succeeds=False)
    with fixed_dice_faces(2):
        deal_damage_to(caster, 10, source_uuid=first.uuid)

    assert "Concentrating" not in caster.active_conditions
    assert "Paralyzed" not in second.active_conditions


@pytest.mark.parametrize("override_to_entity", [False, True])
def test_ice_storm_finalization_follows_effective_target_type(
    override_to_entity: bool,
) -> None:
    """E22/E24/EX-E14/EX-E15: terrain is gated by effective POSITION_AOE."""
    reset_override_state()
    caster = create_caster()
    target = create_target("Ice Target", (5, 0))
    Entity.update_all_entities_senses()
    force_save_result(target, "dexterity", succeeds=False)
    hp_before = target.get_hp()

    with fixed_dice_faces(*([2] * 20)):
        result = IceStorm(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=target.position,
            cast_at_level=4,
            template=False,
            alt_target_type=(
                TargetType.ENTITY if override_to_entity else None
            ),
        ).apply()

    assert_completed(result)
    assert target.get_hp() < hp_before
    assert (
        "Ice Storm Terrain" in caster.active_conditions
    ) is (not override_to_entity)


def test_gust_of_wind_entity_override_skips_zone_and_concentration() -> None:
    """E23/EX-E16: non-AoE Gust does not run its AoE finalizer."""
    reset_override_state(width=10, height=4)
    caster = create_caster()
    target = create_target("Wind Target", (2, 0))
    Entity.update_all_entities_senses()
    force_save_result(target, "strength", succeeds=False)

    with fixed_dice_faces(2):
        result = GustOfWind(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            end_position=(5, 0),
            cast_at_level=2,
            template=False,
            alt_target_type=TargetType.ENTITY,
        ).apply()

    assert_completed(result)
    assert "Gust of Wind Zone" not in caster.active_conditions
    assert "Concentrating" not in caster.active_conditions


def test_eldritch_blast_target_count_only_convolves_when_multi_entity() -> None:
    """F25/F25b: count metadata alone does not change target dispatch."""
    reset_override_state()
    caster = create_caster()
    first = create_target("Blast One", (1, 0))
    second = create_target("Blast Two", (0, 1))
    Entity.update_all_entities_senses()
    hp_first = first.get_hp()
    hp_second = second.get_hp()

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 20)):
        single_result = EldritchBlast(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=first.uuid,
            caster_level=5,
            template=False,
            alt_target_count=3,
        ).apply()
    remove_spell_attack_modifier(caster, hit_modifier)

    assert_completed(single_result)
    assert first.get_hp() < hp_first
    assert second.get_hp() == hp_second

    reset_override_state()
    caster = create_caster()
    targets = [
        create_target("Blast One", (1, 0)),
        create_target("Blast Two", (0, 1)),
        create_target("Blast Three", (1, 1)),
    ]
    Entity.update_all_entities_senses()
    hp_before = {target.uuid: target.get_hp() for target in targets}

    hit_modifier = force_spell_attack_hit(caster)
    with fixed_dice_faces(*([2] * 20)):
        multi_result = EldritchBlast(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=targets[0].uuid,
            extra_target_entity_uuids=[
                targets[1].uuid,
                targets[2].uuid,
            ],
            caster_level=5,
            template=False,
            alt_target_type=TargetType.MULTI_ENTITY,
            alt_target_count=3,
        ).apply()
    remove_spell_attack_modifier(caster, hit_modifier)

    event = assert_completed(multi_result)
    assert event.total_targets == 3
    assert all(target.get_hp() < hp_before[target.uuid] for target in targets)


def test_magic_missile_owns_projectile_count_and_target_resolution() -> None:
    """F26/EX-C10: spell-owned dart allocation takes precedence over alts."""
    reset_override_state()
    caster = create_caster()
    primary = create_target("Missile Target", (3, 0))
    bystander = create_target("Missile Bystander", (3, 1))
    Entity.update_all_entities_senses()

    count_probe = MagicMissile(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=primary.uuid,
        cast_at_level=1,
        template=False,
        alt_target_count=5,
    )
    assert count_probe.get_multi_target_count() == 3
    assert count_probe.get_all_targets() == [primary.uuid, primary.uuid, primary.uuid]

    hp_primary = primary.get_hp()
    hp_bystander = bystander.get_hp()
    with fixed_dice_faces(2, 2, 2):
        result = MagicMissile(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=primary.uuid,
            end_position=primary.position,
            cast_at_level=1,
            template=False,
            alt_target_type=TargetType.POSITION_AOE,
            aoe_shape=Sphere(
                source_entity_uuid=caster.uuid,
                target=primary.position,
                radius_feet=10,
            ),
        ).apply()

    event = assert_completed(result)
    assert event.total_targets == 3
    assert primary.get_hp() == hp_primary - 9
    assert bystander.get_hp() == hp_bystander


def test_fireball_position_aoe_event_reports_target_count_and_position() -> None:
    """EX-F18: the aggregate event retains area geometry and target count."""
    reset_override_state(width=12, height=4)
    caster = create_caster()
    target = create_target("Area Target", (6, 0))
    Entity.update_all_entities_senses()
    force_save_result(target, "dexterity", succeeds=False)

    with fixed_dice_faces(*([2] * 9)):
        result = Fireball(
            source_entity_uuid=caster.uuid,
            end_position=target.position,
            cast_at_level=3,
            template=False,
        ).apply()

    event = assert_completed(result)
    assert event.total_targets == 1
    assert event.aoe_position == target.position
    assert event.total_damage > 0
