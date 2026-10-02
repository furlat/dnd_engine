"""Haste's restricted action budget and Extra Attack ordering invariants."""

from uuid import UUID, uuid4
from typing import cast

import pytest

from dnd.actions import Attack, AttackEvent, SpellAction
from dnd.actions_functional import (
    execute_action,
    execute_by_index,
    get_available_actions,
    setup_standard_actions,
    update_weapon_templates,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import (
    RechargeType,
    ResourceCapacityPolicy,
)
from dnd.blocks.equipment import Weapon
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttack,
    ExtraAttackFeature,
)
from dnd.classes.rage import Frenzied, FrenziedStrike, Raging
from dnd.classes.barbarian import Retaliation
from dnd.classes.paladin import create_divine_smite_handler
from dnd.core.base_actions import (
    AvailableActionInfo,
    AvailableActionsResult,
    AvailableTarget,
)
from dnd.core.condition_types import DurationType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import DamageRollResultEvent, Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.modifiers import NumericalModifier
from dnd.core.action_types import HasteActionPolicy
from dnd.entity import Entity, EntityConfig
from dnd.spells.transmutation import HasteEffect
from dnd.spells.transmutation import SlowedEffect
from tests.engine.support import create_test_entity, reset_combat_state


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
    entity = create_test_entity(
        source_id=uuid4(),
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
        cast(Weapon, build_authored_item("weapon.greatsword", entity.uuid)),
        WeaponSlot.MELEE_MAIN,
    )
    setup_standard_actions(entity)
    return entity


def _create_hasted_fighter(
    *,
    extra_attacks: int,
    action_surge: bool = False,
    apply_lethargy: bool = False,
    haste_action_policy: HasteActionPolicy = HasteActionPolicy.BG3_HONOUR,
) -> tuple[Entity, Entity]:
    """Create a hasted fighter and one adjacent hostile target."""
    fighter = _create_creature("Hasted Fighter", (3, 3), "heroes")
    fighter.action_economy.haste_action_policy = haste_action_policy
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


def _create_hasted_structural_fighter() -> tuple[Entity, Entity]:
    """Create the same matchup through the source-owned Extra Attack family."""
    fighter = _create_creature("Structural Hasted Fighter", (3, 3), "heroes")
    target = _create_creature("Target", (4, 3), "monsters")
    grant_id = uuid4()
    fighter.action_economy.add_attack_multiplicity_grant(
        AttackMultiplicityGrant(
            grant_id=grant_id,
            provider_id="class_feature.extra_attack",
            attacks_per_attack_action=2,
            acquisition_ordinal=5,
        ),
    )
    fighter.action_economy.add_resource_contribution(
        "extra_attacks",
        grant_id,
        maximum=1,
        recharge_type=RechargeType.TURN_START,
        capacity_policy=ResourceCapacityPolicy.MAXIMUM,
    )
    fighter.register_action(
        ExtraAttack(
            source_entity_uuid=fighter.uuid,
            name="Extra Attack",
            template=True,
            discover_equipped_weapon_slots=True,
            semantic_key="action.feature.extra_attack",
            behavior_binding=BehaviorBinding(
                behavior_id="action.feature.extra_attack",
                provided_by_id="class_feature.extra_attack",
                origin_root_id="class.fighter",
                runtime_owner_uuid=fighter.uuid,
            ),
        ),
    )
    fighter.add_condition(
        HasteEffect(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=fighter.uuid,
            caster_uuid=fighter.uuid,
        ),
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


def _condition_parent_lineage(condition_name: str) -> UUID:
    """Return the unique causal parent lineage for one applied condition."""
    matches = [
        event
        for event in EventQueue.get_events_by_type(
            EventType.CONDITION_APPLICATION,
        )
        if getattr(getattr(event, "condition", None), "name", None)
        == condition_name
        and event.phase is EventPhase.DECLARATION
    ]
    assert len(matches) == 1
    parent_event_uuid = matches[0].parent_event
    assert parent_event_uuid is not None
    parent = EventQueue.get_event_by_uuid(parent_event_uuid)
    assert parent is not None
    return parent.lineage_uuid


def test_fighter_internal_markers_remain_in_their_action_lineage() -> None:
    """Action Surge and Extra Attack bookkeeping cannot become root effects."""
    actor, target = _create_hasted_fighter(
        extra_attacks=1,
        action_surge=True,
    )

    surge = ActionSurge(
        source_entity_uuid=actor.uuid,
        template=False,
    ).apply()
    assert surge is not None and not surge.canceled
    assert _condition_parent_lineage("ActionSurging") == surge.lineage_uuid

    attack = _execute(
        actor,
        "Attack_MELEE_MAIN",
        target_uuid=target.uuid,
    )
    assert (
        _condition_parent_lineage("ExtraAttacksGranted")
        == attack.lineage_uuid
    )


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


@pytest.mark.parametrize("haste_attack_first", [False, True])
def test_structural_extra_attack_preserves_haste_ordering(
    haste_attack_first: bool,
) -> None:
    """The source-owned rank uses the same legal Haste/Attack batch semantics."""
    fighter, target = _create_hasted_structural_fighter()
    regular_attack = "Attack_MELEE_MAIN"
    haste_attack = f"{regular_attack}{HASTE_GRANT_SUFFIX}"

    if haste_attack_first:
        _execute(fighter, haste_attack, target_uuid=target.uuid)
        assert fighter.action_economy.resources["extra_attacks"].current == 0
        _execute(fighter, regular_attack, target_uuid=target.uuid)
    else:
        _execute(fighter, regular_attack, target_uuid=target.uuid)
        assert fighter.action_economy.resources["extra_attacks"].current == 1
        _execute(fighter, haste_attack, target_uuid=target.uuid)

    assert fighter.action_economy.resources["extra_attacks"].current == 1
    _execute(
        fighter,
        "Extra Attack_MELEE_MAIN",
        target_uuid=target.uuid,
    )
    assert fighter.action_economy.resources["extra_attacks"].current == 0


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
    weapon = fighter.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert weapon is not None
    assert event.source_item_uuid == weapon.uuid
    assert event.source_item_presentation is not None
    assert event.source_item_presentation.item_uuid == weapon.uuid
    assert event.source_item_presentation.item_id == weapon.item_id


def test_all_equipped_weapon_attack_families_use_the_cold_item_snapshot() -> None:
    """Normal, Extra, and Frenzied attacks share one item-identity boundary."""
    fighter, target = _create_hasted_fighter(extra_attacks=1)
    weapon = fighter.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert weapon is not None

    actions = (
        Attack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ),
        ExtraAttack(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ),
        FrenziedStrike(
            source_entity_uuid=fighter.uuid,
            target_entity_uuid=target.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ),
    )
    for action in actions:
        event = action._create_declaration_event(use_register=False)
        assert isinstance(event, AttackEvent)
        assert event.source_item_uuid == weapon.uuid
        assert event.source_item_presentation is not None
        assert event.source_item_presentation.item_uuid == weapon.uuid
        assert event.source_item_presentation.item_id == weapon.item_id


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


def test_haste_discovery_exposes_every_standard_action_variant() -> None:
    """Honour-mode Haste buys any Action while retaining a separate budget."""
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
        f"Dodge{HASTE_GRANT_SUFFIX}",
    }
    assert expected_haste_rows <= names
    assert f"Extra Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}" not in names

    for registered_template in fighter.registered_actions:
        for variant in registered_template.get_discovery_variants(fighter):
            if variant is not registered_template:
                assert (
                    variant.registered_template_uuid
                    == registered_template.uuid
                )

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


def test_srd_haste_policy_keeps_the_restricted_action_whitelist() -> None:
    """The optional tabletop policy does not grant Dodge or spell actions."""
    fighter, _target = _create_hasted_fighter(
        extra_attacks=1,
        haste_action_policy=HasteActionPolicy.SRD_5_1,
    )
    spell = SpellAction(
        source_entity_uuid=fighter.uuid,
        name="Strict Policy Probe",
        template=True,
    )
    spell_variant_names = {
        variant.get_discovery_template_name()
        for variant in spell.get_discovery_variants(fighter)
    }
    action_variant_names = {
        variant.get_discovery_template_name()
        for template in fighter.registered_actions
        for variant in template.get_discovery_variants(fighter)
    }

    assert "Strict Policy Probe" in spell_variant_names
    assert f"Strict Policy Probe{HASTE_GRANT_SUFFIX}" not in spell_variant_names
    assert f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}" in action_variant_names
    assert f"Dash{HASTE_GRANT_SUFFIX}" in action_variant_names
    assert f"Disengage{HASTE_GRANT_SUFFIX}" in action_variant_names
    assert f"Hide{HASTE_GRANT_SUFFIX}" in action_variant_names
    assert f"Dodge{HASTE_GRANT_SUFFIX}" not in action_variant_names


def test_haste_does_not_convert_an_off_hand_bonus_action_into_an_action() -> None:
    """Honour-mode Haste adds an Action, not another bonus-action budget."""
    fighter, target = _create_hasted_fighter(extra_attacks=1)
    fighter.equipment.unequip(WeaponSlot.MELEE_MAIN)
    fighter.equipment.equip(
        cast(Weapon, build_authored_item("weapon.dagger", fighter.uuid)),
        WeaponSlot.MELEE_MAIN,
    )
    fighter.equipment.equip(
        cast(Weapon, build_authored_item("weapon.dagger", fighter.uuid)),
        WeaponSlot.MELEE_OFF,
    )
    update_weapon_templates(fighter)

    names = {
        row.template_name
        for row in get_available_actions(fighter, legal_only=True).all_actions
    }
    assert f"Attack_MELEE_OFF{HASTE_GRANT_SUFFIX}" not in names
    assert "Attack_MELEE_OFF" in names

    _execute(fighter, "Attack_MELEE_OFF", target_uuid=target.uuid)

    assert fighter.action_economy.resources[HASTE_ACTION_RESOURCE].current == 1
    assert fighter.action_economy.actions.normalized_score == 1
    assert fighter.action_economy.bonus_actions.normalized_score == 0
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


def _create_grid_actor(
    attacks_per_action: int,
    haste_policy: HasteActionPolicy | None,
    *,
    slow: bool,
    surge: bool,
) -> tuple[Entity, Entity, UUID]:
    """Build one public attack-discovery fixture with real creature and prop targets."""
    actor = _create_creature("Grid fighter", (3, 3), "heroes")
    target = _create_creature("Grid target", (4, 3), "monsters")
    prop = build_authored_item("environment.furniture.anvil", uuid4())
    prop.health = prop.create_item_health(prop.uuid, 1000)
    prop.place_on_grid((3, 4))
    if attacks_per_action > 1:
        actor.add_condition(ExtraAttackFeature(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            extra_attacks=attacks_per_action - 1,
        ))
        actor.action_economy.resources["extra_attacks"].current = 0
    else:
        assert "extra_attacks" not in actor.action_economy.resources
    if surge:
        actor.add_condition(ActionSurgeFeature(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            num_uses=1,
        ))
    if haste_policy is not None:
        actor.action_economy.haste_action_policy = haste_policy
        actor.add_condition(HasteEffect(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            caster_uuid=actor.uuid,
            apply_lethargy=False,
        ))
    if slow:
        actor.add_condition(SlowedEffect(
            source_entity_uuid=target.uuid,
            target_entity_uuid=actor.uuid,
            caster_uuid=target.uuid,
            spell_dc=0,
        ))
    Entity.update_all_entities_senses()
    return actor, target, prop.uuid


def _extra_credits(actor: Entity) -> int:
    resource = actor.action_economy.resources.get("extra_attacks")
    return resource.current if resource is not None else 0


@pytest.mark.parametrize("slow", [False, True])
@pytest.mark.parametrize("haste_policy", [None, HasteActionPolicy.SRD_5_1, HasteActionPolicy.BG3_HONOUR])
@pytest.mark.parametrize("attacks_per_action", [1, 2, 3, 4])
@pytest.mark.parametrize("surge", [False, True])
@pytest.mark.parametrize("recipients", ["creature", "object", "mixed"])
@pytest.mark.parametrize("offhand_talent", [False, True])
def test_attack_budget_grid_preserves_all_resources_for_creatures_and_objects(
    slow: bool,
    haste_policy: HasteActionPolicy | None,
    attacks_per_action: int,
    surge: bool,
    recipients: str,
    offhand_talent: bool,
) -> None:
    """The 48 budget combinations have the same meaning for either recipient kind."""
    actor, creature, object_uuid = _create_grid_actor(
        attacks_per_action, haste_policy, slow=slow, surge=surge,
    )
    if offhand_talent:
        actor.grant_one_handed_offhand(uuid4())
    targets = {
        "creature": (creature.uuid,),
        "object": (object_uuid,),
        "mixed": (creature.uuid, object_uuid),
    }[recipients]
    attacks = 0

    def attack(name: str) -> Event:
        nonlocal attacks
        with fixed_dice_faces(10, 4, 4):
            result = _execute(actor, name, target_uuid=targets[attacks % len(targets)])
        attacks += 1
        return result

    if haste_policy is not None:
        attack(f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}")
        assert actor.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
        assert actor.action_economy.actions.normalized_score == 1
        assert _extra_credits(actor) == 0
    attack("Attack_MELEE_MAIN")
    credits = 0 if slow else attacks_per_action - 1
    assert actor.action_economy.actions.normalized_score == 0
    assert _extra_credits(actor) == credits
    if credits > 1:
        attack("Extra Attack_MELEE_MAIN")
        credits -= 1
        assert _extra_credits(actor) == credits
    if surge:
        _execute(actor, "Action Surge")
        assert actor.action_economy.resources["action_surge"].current == 0
        assert actor.action_economy.actions.normalized_score == 1
        assert _extra_credits(actor) == credits
        attack("Attack_MELEE_MAIN")
        credits += 0 if slow else attacks_per_action - 1
        assert actor.action_economy.actions.normalized_score == 0
        assert _extra_credits(actor) == credits
    while credits:
        attack("Extra Attack_MELEE_MAIN")
        credits -= 1
        assert _extra_credits(actor) == credits
        assert actor.action_economy.actions.normalized_score == 0
    expected = (1 if slow else attacks_per_action) * (1 + int(surge)) + int(haste_policy is not None)
    assert attacks == expected
    assert actor.action_economy.bonus_actions.normalized_score == (0 if slow else 1)
    assert actor.action_economy.reactions.normalized_score == (0 if slow else 1)
    names = {row.template_name for row in get_available_actions(actor, legal_only=True).all_actions}
    assert "Attack_MELEE_MAIN" not in names
    assert "Extra Attack_MELEE_MAIN" not in names
    assert f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}" not in names


@pytest.mark.parametrize("haste_policy", list(HasteActionPolicy))
@pytest.mark.parametrize("haste_order", ["before", "during", "after"])
@pytest.mark.parametrize("surge_order", ["before", "during", "after"])
def test_haste_and_surge_order_cannot_replace_pending_attack_credits(
    haste_policy: HasteActionPolicy,
    haste_order: str,
    surge_order: str,
) -> None:
    """Interleaving either additional budget preserves an N=4 partially used batch."""
    actor, target, object_uuid = _create_grid_actor(4, haste_policy, slow=False, surge=True)
    count = 0

    def attack(name: str) -> None:
        nonlocal count
        with fixed_dice_faces(10, 4, 4):
            _execute(actor, name, target_uuid=target.uuid if count % 2 == 0 else object_uuid)
        count += 1

    if surge_order == "before":
        _execute(actor, "Action Surge")
    if haste_order == "before":
        attack(f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}")
    attack("Attack_MELEE_MAIN")
    attack("Extra Attack_MELEE_MAIN")
    assert _extra_credits(actor) == 2
    if haste_order == "during":
        attack(f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}")
        assert _extra_credits(actor) == 2
    if surge_order == "during":
        _execute(actor, "Action Surge")
    if surge_order != "after":
        attack("Attack_MELEE_MAIN")
        assert _extra_credits(actor) == 5
    while _extra_credits(actor):
        attack("Extra Attack_MELEE_MAIN")
    if surge_order == "after":
        _execute(actor, "Action Surge")
        attack("Attack_MELEE_MAIN")
        assert _extra_credits(actor) == 3
        while _extra_credits(actor):
            attack("Extra Attack_MELEE_MAIN")
    if haste_order == "after":
        attack(f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}")
    assert count == 9
    assert actor.action_economy.actions.normalized_score == 0
    assert actor.action_economy.resources[HASTE_ACTION_RESOURCE].current == 0
    assert _extra_credits(actor) == 0


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION])
@pytest.mark.parametrize("cancel_before_feature", [False, True])
def test_canceled_attack_batch_depends_on_commitment_not_handler_registration(
    phase: EventPhase,
    cancel_before_feature: bool,
) -> None:
    actor, target, _ = _create_grid_actor(1, None, slow=False, surge=False)

    def cancel_attack(event: Event, _source: UUID) -> Event | None:
        if event.source_entity_uuid == actor.uuid:
            return event.cancel(status_message="Attack interrupted by reaction")
        return None

    cancel = EventHandler(
        name="Blocking reaction",
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=phase)],
        event_processor=cancel_attack,
    )
    if cancel_before_feature:
        actor.add_event_handler(cancel)
    actor.add_condition(ExtraAttackFeature(
        source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, extra_attacks=3,
    ))
    actor.action_economy.resources["extra_attacks"].current = 0
    if not cancel_before_feature:
        actor.add_event_handler(cancel)
    original_hp = target.get_hp()
    result = execute_action(actor, "Attack_MELEE_MAIN", AvailableTarget(index=0, target_uuid=target.uuid))
    assert result is not None and result.canceled
    committed = phase is EventPhase.EXECUTION
    assert actor.action_economy.actions.normalized_score == (0 if committed else 1)
    assert _extra_credits(actor) == (3 if committed else 0)
    assert target.get_hp() == original_hp


@pytest.mark.parametrize("first", ["haste", "bonus"])
@pytest.mark.parametrize("haste_policy", list(HasteActionPolicy))
def test_slow_action_bonus_exclusion_uses_action_semantics_with_haste_funding(
    first: str,
    haste_policy: HasteActionPolicy,
) -> None:
    actor, target, _ = _create_grid_actor(2, haste_policy, slow=True, surge=False)
    actor.equipment.unequip(WeaponSlot.MELEE_MAIN)
    for slot in (WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF):
        actor.equipment.equip(cast(Weapon, build_authored_item("weapon.dagger", actor.uuid)), slot)
    update_weapon_templates(actor)
    haste = f"Attack_MELEE_MAIN{HASTE_GRANT_SUFFIX}"
    first_name, forbidden = (haste, "Attack_MELEE_OFF") if first == "haste" else ("Attack_MELEE_OFF", haste)
    _execute(actor, first_name, target_uuid=target.uuid)
    state = (
        actor.action_economy.actions.normalized_score,
        actor.action_economy.bonus_actions.normalized_score,
        actor.action_economy.resources[HASTE_ACTION_RESOURCE].current,
    )
    assert state == ((1, 0, 0) if first == "haste" else (0, 0, 1))
    legal_names = {row.template_name for row in get_available_actions(actor, legal_only=True).all_actions}
    assert forbidden not in legal_names
    blocked = execute_action(actor, forbidden, AvailableTarget(index=0, target_uuid=target.uuid))
    assert blocked is None or blocked.canceled
    assert state == (
        actor.action_economy.actions.normalized_score,
        actor.action_economy.bonus_actions.normalized_score,
        actor.action_economy.resources[HASTE_ACTION_RESOURCE].current,
    )
    assert _extra_credits(actor) == 0


@pytest.mark.parametrize("slow_before_feature", [False, True])
def test_slow_suppresses_batch_independently_of_feature_installation_order(slow_before_feature: bool) -> None:
    actor, target, _ = _create_grid_actor(1, None, slow=False, surge=False)
    slowed = SlowedEffect(source_entity_uuid=target.uuid, target_entity_uuid=actor.uuid)
    if slow_before_feature:
        actor.add_condition(slowed)
    actor.add_condition(ExtraAttackFeature(
        source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid, extra_attacks=3,
    ))
    if not slow_before_feature:
        actor.add_condition(slowed)
    _execute(actor, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    assert actor.action_economy.actions.normalized_score == 0
    assert _extra_credits(actor) == 0
    assert not any(row.template_name.startswith("Extra Attack") for row in get_available_actions(actor, legal_only=True).all_actions)


def test_slow_discards_pending_batch_and_removal_requires_a_new_paid_attack() -> None:
    actor, target, _ = _create_grid_actor(4, None, slow=False, surge=True)
    _execute(actor, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    _execute(actor, "Extra Attack_MELEE_MAIN", target_uuid=target.uuid)
    assert _extra_credits(actor) == 2
    actor.add_condition(SlowedEffect(source_entity_uuid=target.uuid, target_entity_uuid=actor.uuid))
    assert _extra_credits(actor) == 0
    assert actor.action_economy.bonus_actions.normalized_score == 0
    assert not any(row.template_name.startswith("Extra Attack") for row in get_available_actions(actor, legal_only=True).all_actions)
    actor.remove_condition("Slowed")
    assert _extra_credits(actor) == 0
    assert actor.action_economy.bonus_actions.normalized_score == 1
    _execute(actor, "Action Surge")
    _execute(actor, "Attack_MELEE_MAIN", target_uuid=target.uuid)
    assert _extra_credits(actor) == 3


@pytest.mark.parametrize("variant", ["ordinary-offhand", "extra-offhand", "frenzy-offhand"])
def test_object_offhand_variants_preserve_their_original_payment(variant: str) -> None:
    actor, _, prop_uuid = _create_grid_actor(2, None, slow=False, surge=False)
    actor.equipment.unequip(WeaponSlot.MELEE_MAIN)
    actor.equipment.equip(cast(Weapon, build_authored_item("weapon.dagger", actor.uuid)), WeaponSlot.MELEE_MAIN)
    actor.equipment.equip(cast(Weapon, build_authored_item("weapon.dagger", actor.uuid)), WeaponSlot.MELEE_OFF)
    update_weapon_templates(actor)
    if variant == "extra-offhand":
        _execute(actor, "Attack_MELEE_MAIN", target_uuid=prop_uuid)
        attack_type = ExtraAttack
    elif variant == "frenzy-offhand":
        actor.add_condition(Frenzied(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
        attack_type = FrenziedStrike
    else:
        attack_type = Attack
    with fixed_dice_faces(18, 4):
        event = attack_type(source_entity_uuid=actor.uuid, target_entity_uuid=prop_uuid,
                            weapon_slot=WeaponSlot.MELEE_OFF).apply()
    assert event is not None and not event.canceled
    assert actor.action_economy.actions.normalized_score == (0 if variant == "extra-offhand" else 1)
    assert actor.action_economy.bonus_actions.normalized_score == (1 if variant == "extra-offhand" else 0)
    assert _extra_credits(actor) == 0


def test_frenzied_strike_disappears_when_its_condition_ends() -> None:
    actor, _, prop_uuid = _create_grid_actor(2, None, slow=False, surge=False)
    actor.add_condition(Frenzied(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid,
        behavior_binding=BehaviorBinding(behavior_id="action.class.barbarian.frenzy",
            provided_by_id="class_feature.barbarian.frenzy", origin_root_id="class.barbarian",
            runtime_owner_uuid=actor.uuid)))
    assert any(row.template_name == "Frenzied Strike" and
               any(target.target_uuid == prop_uuid for target in row.valid_targets)
               for row in get_available_actions(actor, legal_only=True).all_actions)
    actor.remove_condition("Frenzied")
    assert not any(row.template_name.startswith("Frenzied Strike")
                   for row in get_available_actions(actor).all_actions)


@pytest.mark.parametrize("cancel_phase", [EventPhase.DECLARATION, EventPhase.EXECUTION])
def test_retaliation_pays_reaction_at_commitment_even_when_later_canceled(cancel_phase: EventPhase) -> None:
    actor, target, _ = _create_grid_actor(2, None, slow=False, surge=False)
    actor.add_condition(Retaliation(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
    def stop_reaction(event: Event, _source: UUID | None) -> Event:
        return event.cancel(status_message="Interrupted retaliation")
    EventQueue.add_event_handler(EventHandler(name="Interrupt retaliation", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.ATTACK, event_phase=cancel_phase,
                                    event_source_entity_uuid=actor.uuid)],
        event_processor=stop_reaction))
    target_hp = target.get_hp()
    actor.receive_damage(1, DamageType.FORCE, source_entity_uuid=target.uuid)
    assert target.get_hp() == target_hp
    assert actor.action_economy.reactions.normalized_score == (1 if cancel_phase is EventPhase.DECLARATION else 0)
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.bonus_actions.normalized_score == 1
    assert _extra_credits(actor) == 0


@pytest.mark.parametrize("recipient", ["hostile-creature", "friendly-creature", "object"])
def test_rage_maintenance_requires_a_hostile_creature_attack(recipient: str) -> None:
    actor, target, prop_uuid = _create_grid_actor(1, None, slow=False, surge=False)
    if recipient == "friendly-creature":
        target.faction = actor.faction
    actor.add_condition(Raging(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
    with fixed_dice_faces(18, 4, 4):
        event = Attack(source_entity_uuid=actor.uuid,
                       target_entity_uuid=prop_uuid if recipient == "object" else target.uuid,
                       weapon_slot=WeaponSlot.MELEE_MAIN, valid_target_filter="all").apply()
    assert event is not None and not event.canceled
    actor.on_turn_start()
    assert ("Raging" in actor.active_conditions) is (recipient == "hostile-creature")


def test_divine_smite_keeps_slot_when_attacking_an_object() -> None:
    actor, _, prop_uuid = _create_grid_actor(1, None, slow=False, surge=False)
    base = actor.action_economy.spell_slot_1.get_base_modifier()
    assert base is not None
    base.value = 1
    actor.add_event_handler(create_divine_smite_handler(actor.uuid, 1))
    with fixed_dice_faces(18, 4, 4):
        result = _execute(actor, "Attack_MELEE_MAIN", target_uuid=prop_uuid)
    assert actor.action_economy.spell_slot_1.normalized_score == 1
    assert isinstance(result, AttackEvent) and result.damage_rolls
    damage = next(event for event in EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT)
                  if isinstance(event, DamageRollResultEvent) and event.phase is EventPhase.COMPLETION)
    assert all(packet.damage.damage_type is not DamageType.RADIANT for packet in damage.damage_packets)
