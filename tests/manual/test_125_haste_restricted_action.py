"""Haste's restricted action budget and Extra Attack ordering invariants."""

from uuid import UUID, uuid4

import pytest

from dnd.actions import AttackEvent
from dnd.actions_functional import (
    execute_action,
    execute_by_index,
    get_available_actions,
    setup_standard_actions,
    update_weapon_templates,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttackFeature,
)
from dnd.core.base_actions import (
    AvailableActionInfo,
    AvailableActionsResult,
    AvailableTarget,
)
from dnd.core.condition_types import DurationType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, NumericalModifier
from dnd.entity import Entity, EntityConfig
from dnd.items.weapons import DAGGER_RECIPE, GREATSWORD_RECIPE
from dnd.spells.transmutation import HasteEffect
from dnd.spells.transmutation import SlowedEffect
from dnd.utils import reset_combat_state


HASTE_GRANT_SUFFIX = "__grant_haste"
HASTE_ACTION_RESOURCE = "haste_action"


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    """Give every case fresh registries and a visible combat grid."""
    reset_combat_state()
    get_map().create_rectangle(0, 0, 12, 12)


def _create_creature(
    name: str,
    position: tuple[int, int],
    faction: str,
) -> Entity:
    """Create one armed creature with the standard action surface."""
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=18),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=14),
            ),
            health=HealthConfig(
                hit_dices=[
                    HitDiceConfig(
                        hit_dice_value=10,
                        hit_dice_count=20,
                        mode="maximums",
                    )
                ]
            ),
            proficiency_bonus=4,
            position=position,
            faction=faction,
        ),
    )
    entity.equipment.equip(
        materialize_item(
            GREATSWORD_RECIPE,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(entity)
    return entity


def _create_hasted_fighter(
    *,
    extra_attacks: int,
    action_surge: bool = False,
    apply_lethargy: bool = False,
) -> tuple[Entity, Entity]:
    """Create a hasted fighter and one adjacent hostile target."""
    fighter = _create_creature("Hasted Fighter", (3, 3), "heroes")
    target = _create_creature("Target", (4, 3), "monsters")
    fighter.add_condition(
        ExtraAttackFeature(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            extra_attacks=extra_attacks,
        )
    )
    if action_surge:
        fighter.add_condition(
            ActionSurgeFeature(
                source_entity_uuid=fighter.uuid,
                target_entity_uuid=fighter.uuid,
                num_uses=1,
            )
        )
    fighter.add_condition(
        HasteEffect(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            caster_uuid=fighter.uuid,
            apply_lethargy=apply_lethargy,
        )
    )
    fighter.action_economy.resources["extra_attacks"].current = 0
    Entity.update_all_entities_senses()
    return fighter, target


def _find_row(
    available: AvailableActionsResult,
    template_name: str,
) -> AvailableActionInfo:
    """Return one exact legal discovery row."""
    matches = [
        row
        for row in available.all_actions
        if row.template_name == template_name
    ]
    assert len(matches) == 1
    assert matches[0].can_afford
    assert matches[0].valid_targets
    return matches[0]


def _execute(
    actor: Entity,
    template_name: str,
    *,
    target_uuid: UUID | None = None,
) -> Event:
    """Execute one exact row through the public index-based engine path."""
    available = get_available_actions(actor, legal_only=True)
    row = _find_row(available, template_name)
    if target_uuid is None:
        target = row.valid_targets[0]
    else:
        target = next(
            option
            for option in row.valid_targets
            if option.target_uuid == target_uuid
        )
    event = execute_by_index(
        actor,
        row.template_name,
        target.index,
        available=available,
    )
    assert event is not None
    assert not event.canceled
    return event


@pytest.mark.parametrize("extra_attacks", [1, 2, 3])
@pytest.mark.parametrize("haste_attack_first", [False, True])
def test_haste_attack_and_normal_attack_batches_are_order_independent(
    extra_attacks: int,
    haste_attack_first: bool,
) -> None:
    """A Haste Attack neither grants nor destroys a normal Attack batch."""
    fighter, target = _create_hasted_fighter(extra_attacks=extra_attacks)
    regular_attack = "Attack_MELEE_MAIN"
    haste_attack = f"{regular_attack}{HASTE_GRANT_SUFFIX}"

    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 1

    if haste_attack_first:
        _execute(fighter, haste_attack, target_uuid=target.uuid)
        assert fighter.action_economy.resources["extra_attacks"].current == 0
        _execute(fighter, regular_attack, target_uuid=target.uuid)
    else:
        _execute(fighter, regular_attack, target_uuid=target.uuid)
        assert (
            fighter.action_economy.resources["extra_attacks"].current
            == extra_attacks
        )
        _execute(fighter, haste_attack, target_uuid=target.uuid)

    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert (
        fighter.action_economy.resources["extra_attacks"].current
        == extra_attacks
    )

    for remaining in range(extra_attacks - 1, -1, -1):
        _execute(
            fighter,
            "Extra Attack_MELEE_MAIN",
            target_uuid=target.uuid,
        )
        assert fighter.action_economy.resources["extra_attacks"].current == remaining


def test_haste_extra_attack_miss_keeps_weapon_presentation_metadata() -> None:
    """A missed Extra Attack still carries enough metadata to emit an attack cue."""
    fighter, target = _create_hasted_fighter(extra_attacks=1)

    with fixed_dice_faces(10, 4, 4):
        _execute(
            fighter,
            "Attack_MELEE_MAIN",
            target_uuid=target.uuid,
        )

    target.equipment.ac_bonus.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            name="Forced Extra Attack miss",
            value=100,
        )
    )
    with fixed_dice_faces(10):
        event = _execute(
            fighter,
            "Extra Attack_MELEE_MAIN",
            target_uuid=target.uuid,
        )

    assert isinstance(event, AttackEvent)
    assert event.attack_outcome == AttackOutcome.MISS
    assert event.weapon_name == "Greatsword"
    assert event.name == "Extra Attack (Greatsword)"
    assert event.damage_types == [DamageType.SLASHING]


def test_weapon_attack_metadata_snapshot_is_typed_and_handles_unarmed_slots() -> None:
    """Equipment owns the immutable metadata used by every weapon constructor."""
    fighter, _target = _create_hasted_fighter(extra_attacks=1)

    assert fighter.equipment.snapshot_attack_event_metadata(
        WeaponSlot.MELEE_MAIN,
    ) == (
        "Greatsword",
        (DamageType.SLASHING,),
    )
    assert fighter.equipment.snapshot_attack_event_metadata(
        WeaponSlot.MELEE_OFF,
    ) == (
        "Unarmed",
        (DamageType.BLUDGEONING,),
    )


def test_haste_discovery_exposes_only_its_rules_legal_action_variants() -> None:
    """The restricted budget cannot buy arbitrary ordinary actions."""
    fighter, _target = _create_hasted_fighter(extra_attacks=1)
    variants = {
        variant.get_discovery_template_name(): variant
        for template in fighter.registered_actions
        for variant in template.get_discovery_variants(fighter)
    }
    names = set(variants)

    expected_haste_rows = {
        f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}",
        f"Dash{HASTE_GRANT_SUFFIX}",
        f"Disengage{HASTE_GRANT_SUFFIX}",
        f"Hide{HASTE_GRANT_SUFFIX}",
    }
    assert expected_haste_rows <= names
    assert f"Dodge{HASTE_GRANT_SUFFIX}" not in names
    assert f"Extra Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}" not in names

    for template_name in expected_haste_rows:
        costs = variants[template_name].effective_costs
        assert len(costs) == 1
        assert any(
            cost.resource_name == HASTE_ACTION_RESOURCE
            and cost.resource_cost == 1
            for cost in costs
        )
        assert all(
            cost.cost == 0
            for cost in costs
            if cost.cost_type == "actions"
        )


def test_haste_weapon_attack_can_use_an_equipped_off_hand_weapon() -> None:
    """The restricted Attack may choose either hand without spending a bonus action."""
    fighter, target = _create_hasted_fighter(extra_attacks=1)
    fighter.equipment.unequip(WeaponSlot.MELEE_MAIN)
    fighter.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_MAIN,
    )
    fighter.equipment.equip(
        materialize_item(
            DAGGER_RECIPE,
            fighter.uuid,
            origin=ItemRuntimeOrigin.STARTER,
            expected_type=Weapon,
        ),
        WeaponSlot.MELEE_OFF,
    )
    update_weapon_templates(fighter)

    haste_attack = f"Attack_MELEE_OFF{HASTE_GRANT_SUFFIX}"
    row = _find_row(
        get_available_actions(fighter, legal_only=True),
        haste_attack,
    )
    assert len(row.costs) == 1
    assert row.costs[0].cost_type == "bonus_actions"
    assert row.costs[0].cost == 0
    assert row.costs[0].resource_name == HASTE_ACTION_RESOURCE
    assert row.costs[0].resource_cost == 1

    _execute(fighter, haste_attack, target_uuid=target.uuid)

    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.bonus_actions.normalized_score == 1
    assert fighter.action_economy.resources["extra_attacks"].current == 0


def test_haste_dash_does_not_poison_later_action_surge_attack_batch() -> None:
    """Spending Haste on Dash cannot suppress a later surged Attack."""
    fighter, target = _create_hasted_fighter(
        extra_attacks=1,
        action_surge=True,
    )

    _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    _execute(
        fighter,
        "Extra Attack_MELEE_MAIN",
        target_uuid=target.uuid,
    )
    assert fighter.action_economy.resources["extra_attacks"].current == 0

    _execute(fighter, f"Dash{HASTE_GRANT_SUFFIX}")
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert fighter.action_economy.actions.normalized_score == 0

    surge = ActionSurge(source_entity_uuid=fighter.uuid, template=False).apply()
    assert surge is not None
    assert not surge.canceled
    assert fighter.action_economy.actions.normalized_score == 1

    _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    assert fighter.action_economy.resources["extra_attacks"].current == 1


@pytest.mark.parametrize("surge_first", [False, True])
def test_haste_and_action_surge_preserve_both_extra_attack_batches(
    surge_first: bool,
) -> None:
    """Two ordinary Attack actions and one Haste attack yield five swings."""
    fighter, target = _create_hasted_fighter(
        extra_attacks=1,
        action_surge=True,
    )

    if surge_first:
        surge = ActionSurge(
            source_entity_uuid=fighter.uuid,
            template=False,
        ).apply()
        assert surge is not None
        assert not surge.canceled

    _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    _execute(fighter, "Extra Attack_MELEE_MAIN", target_uuid=target.uuid)

    if surge_first:
        _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
        _execute(
            fighter,
            "Extra Attack_MELEE_MAIN",
            target_uuid=target.uuid,
        )
        _execute(
            fighter,
            f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}",
            target_uuid=target.uuid,
        )
    else:
        _execute(
            fighter,
            f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}",
            target_uuid=target.uuid,
        )
        surge = ActionSurge(
            source_entity_uuid=fighter.uuid,
            template=False,
        ).apply()
        assert surge is not None
        assert not surge.canceled
        _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
        _execute(
            fighter,
            "Extra Attack_MELEE_MAIN",
            target_uuid=target.uuid,
        )

    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert fighter.action_economy.resources["extra_attacks"].current == 0


def test_wire_template_name_resolves_haste_variant_without_cached_row() -> None:
    """Serialized commands can resolve the generated Haste variant by name."""
    fighter, target = _create_hasted_fighter(extra_attacks=1)

    event = execute_action(
        fighter,
        f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}",
        AvailableTarget(
            index=0,
            target_uuid=target.uuid,
        ),
    )

    assert event is not None
    assert not event.canceled
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.resources["extra_attacks"].current == 0


def test_haste_budget_recharges_and_is_removed_with_its_condition() -> None:
    """The restricted budget has turn and condition ownership."""
    fighter, _target = _create_hasted_fighter(extra_attacks=1)

    _execute(fighter, f"Dash{HASTE_GRANT_SUFFIX}")
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0

    fighter.action_economy.on_turn_start()
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 1

    fighter.remove_condition("Haste")
    assert HASTE_ACTION_RESOURCE not in fighter.action_economy.resources
    names = {
        row.template_name
        for row in get_available_actions(fighter).all_actions
    }
    assert not any(name.endswith(HASTE_GRANT_SUFFIX) for name in names)


@pytest.mark.parametrize("cleanup_path", ["direct_removal", "duration_expiry"])
def test_haste_cleanup_paths_remove_the_budget_and_apply_owned_lethargy(
    cleanup_path: str,
) -> None:
    """Dispel-like removal and duration expiry share the complete cleanup path."""
    fighter, _target = _create_hasted_fighter(
        extra_attacks=1,
        apply_lethargy=True,
    )
    haste = fighter.active_conditions["Haste"]

    if cleanup_path == "direct_removal":
        fighter.remove_condition("Haste")
    else:
        haste.duration.duration_type = DurationType.ROUNDS
        haste.duration.duration = 1
        assert fighter.advance_duration("Haste")

    assert "Haste" not in fighter.active_conditions
    assert HASTE_ACTION_RESOURCE not in fighter.action_economy.resources
    assert fighter.action_economy.get_restricted_action_grants() == ()
    assert "Haste Lethargy" in fighter.active_conditions
    assert fighter.action_economy.action_permission.normalized_score == 0
    assert fighter.action_economy.movement.normalized_score == 0


def test_replacing_haste_preserves_the_new_conditions_owned_budget() -> None:
    """Old-condition cleanup cannot remove a replacement condition's grant."""
    fighter, _target = _create_hasted_fighter(extra_attacks=1)
    first = fighter.active_conditions["Haste"]
    replacement = HasteEffect(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        caster_uuid=fighter.uuid,
        apply_lethargy=False,
    )

    fighter.add_condition(replacement)

    assert fighter.active_conditions["Haste"].uuid == replacement.uuid
    assert fighter.active_conditions["Haste"].uuid != first.uuid
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 1
    grants = fighter.action_economy.get_restricted_action_grants()
    assert len(grants) == 1
    assert grants[0].owner_uuid == replacement.uuid


@pytest.mark.parametrize("action_surge", [False, True])
def test_slow_keeps_haste_and_surge_actions_but_suppresses_extra_attacks(
    action_surge: bool,
) -> None:
    """Restore the archived Haste/Slow interaction as an active invariant."""
    fighter, target = _create_hasted_fighter(
        extra_attacks=1,
        action_surge=action_surge,
    )
    fighter.add_condition(
        SlowedEffect(
            source_entity_uuid=target.uuid,
            target_entity_uuid=fighter.uuid,
            caster_uuid=target.uuid,
            spell_dc=0,
        )
    )
    if action_surge:
        surge = ActionSurge(
            source_entity_uuid=fighter.uuid,
            template=False,
        ).apply()
        assert surge is not None
        assert not surge.canceled

    expected_normal_actions = 2 if action_surge else 1
    assert (
        fighter.action_economy.actions.normalized_score
        == expected_normal_actions
    )
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 1

    _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    assert fighter.action_economy.resources["extra_attacks"].current == 0
    _execute(
        fighter,
        f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}",
        target_uuid=target.uuid,
    )
    assert fighter.action_economy.resources["extra_attacks"].current == 0

    if action_surge:
        _execute(fighter, "Attack_MELEE_MAIN", target_uuid=target.uuid)
        assert fighter.action_economy.resources["extra_attacks"].current == 0

    assert fighter.action_economy.actions.normalized_score == 0
    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    legal_names = {
        row.template_name
        for row in get_available_actions(fighter, legal_only=True).all_actions
    }
    assert "Extra Attack_MELEE_MAIN" not in legal_names
