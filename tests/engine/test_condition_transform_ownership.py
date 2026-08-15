"""Ownership checks for condition-applied neutral entity transforms."""

from __future__ import annotations

import pytest

from dnd.actions.standard import (
    Disengage,
    Move,
    entity_action_economy_cost_evaluator,
)
from dnd.core.base_actions import (
    BaseAction,
    Cost,
)
from dnd.core.events.events_registry import (
    EventQueue,
    EventType,
)
from dnd.types.damage import DamageType
from dnd.entity import Entity
from dnd.conditions import Blinded, Incapacitated, Paralyzed, Stunned, Unconscious
from dnd.monsters.bestiary import create_skeleton
from dnd.actions.reactions import add_opportunity_attack_handler
from dnd.spells.abjuration import (
    BanishedCondition,
)
from dnd.spells.enchantment import SleepEffect
from dnd.spells.illusion import HypnoticPatternEffect
from dnd.spells.necromancy import EyebiteAsleepEffect
from dnd.spells.transmutation import HasteLethargyEffect
from tests.engine.support import force_attack_hit, remove_attack_modifier
from tests.engine.test_combat_actions import (
    reset_core_action_state,
    strong_entity,
)


def _apply_condition(condition_type, source: Entity, target: Entity):
    """Apply one concrete condition and return its exact owner instance."""
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    result = target.add_condition(condition)

    assert result is not None
    assert result.canceled is False
    assert target.active_conditions_by_uuid[condition.uuid] is condition
    return condition


def _cost_free_action(
    source: Entity,
    *,
    allow_while_incapacitated: bool = False,
) -> BaseAction:
    """Build a zero-cost probe whose only gate is permission to act."""
    return BaseAction(
        name="Cost-Free Permission Probe",
        source_entity_uuid=source.uuid,
        costs=[],
        allow_while_incapacitated=allow_while_incapacitated,
        use_register=False,
    )


def _reaction_action(source: Entity) -> BaseAction:
    """Build one pure reaction-cost action governed by the reaction channel."""
    return BaseAction(
        name="Reaction Permission Probe",
        source_entity_uuid=source.uuid,
        costs=[
            Cost(
                name="Reaction Permission Cost",
                cost_type="reactions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            )
        ],
        use_register=False,
    )


@pytest.mark.parametrize("removed_first", ["Blinded", "Unconscious"])
def test_visual_access_remains_denied_until_every_owner_is_removed(
    removed_first: str,
) -> None:
    """Blinded and Unconscious own independent visual-access constraints."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    assert target.senses.visual_access.normalized_score == 1
    assert target.can_see_visual_effects() is True

    owners = {
        "Blinded": _apply_condition(Blinded, source, target),
        "Unconscious": _apply_condition(Unconscious, source, target),
    }

    assert target.senses.visual_access.normalized_score == 0
    assert target.can_see_visual_effects() is False

    target.remove_condition_by_uuid(owners[removed_first].uuid)

    remaining = "Unconscious" if removed_first == "Blinded" else "Blinded"
    assert owners[remaining].uuid in target.active_conditions_by_uuid
    assert target.senses.visual_access.normalized_score == 0
    assert target.can_see_visual_effects() is False

    target.remove_condition_by_uuid(owners[remaining].uuid)

    assert target.senses.visual_access.normalized_score == 1
    assert target.can_see_visual_effects() is True


@pytest.mark.parametrize("removed_first", ["Unconscious", "Paralyzed"])
def test_severe_conditions_own_independent_action_and_movement_denials(
    removed_first: str,
) -> None:
    """Removing one severe condition cannot release another owner's denial."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    owners = {
        "Unconscious": _apply_condition(Unconscious, source, target),
        "Paralyzed": _apply_condition(Paralyzed, source, target),
    }

    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert _cost_free_action(target).check_costs() is False

    target.remove_condition_by_uuid(owners[removed_first].uuid)

    remaining = "Paralyzed" if removed_first == "Unconscious" else "Unconscious"
    assert owners[remaining].uuid in target.active_conditions_by_uuid
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.bonus_actions.normalized_score == 0
    assert target.action_economy.reactions.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert _cost_free_action(target).check_costs() is False

    target.remove_condition_by_uuid(owners[remaining].uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.actions.normalized_score == 1
    assert target.action_economy.bonus_actions.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert _cost_free_action(target).check_costs() is True


@pytest.mark.parametrize("condition_type", [Incapacitated, Stunned])
def test_action_permission_blocks_zero_cost_and_reaction_actions_when_capped(
    condition_type,
) -> None:
    """Severe denials close both the neutral gate and reaction resource."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    incapacitated = _apply_condition(condition_type, source, target)
    ordinary = _cost_free_action(target)
    reaction = _reaction_action(target)
    permitted_exception = _cost_free_action(
        target,
        allow_while_incapacitated=True,
    )

    assert ordinary.effective_costs == []
    assert permitted_exception.effective_costs == []
    assert target.action_economy.action_permission.normalized_score == 0
    assert ordinary.check_costs() is False
    assert target.action_economy.reactions.normalized_score == 0
    assert reaction.check_costs() is False
    assert permitted_exception.check_costs() is True

    target.remove_condition_by_uuid(incapacitated.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.reactions.normalized_score == 1
    assert ordinary.check_costs() is True
    assert reaction.check_costs() is True


def test_disengaging_owns_opportunity_attack_provocation_constraint() -> None:
    """Disengaging toggles provenance and the opportunity-attack outcome together."""
    reset_core_action_state()
    watcher = create_skeleton(
        name="Watcher",
        position=(5, 5),
        faction="monsters",
    )
    mover = strong_entity("Mover", (5, 6), "heroes")
    add_opportunity_attack_handler(watcher)
    Entity.update_all_entities_senses(max_distance=20)

    assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 1

    disengage_event = Disengage(source_entity_uuid=mover.uuid).apply()
    disengaging = mover.active_conditions.get("Disengaging")

    assert disengage_event is not None
    assert disengaging is not None
    assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 0

    hp_before = mover.get_hp()
    hit_modifier = force_attack_hit(watcher)
    try:
        protected_move = Move(
            source_entity_uuid=mover.uuid,
            end_position=(5, 10),
        ).apply()

        assert protected_move is not None
        assert mover.get_hp() == hp_before
        assert watcher.action_economy.reactions.normalized_score == 1
        assert not any(
            event.name == "Opportunity Attack"
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
        )

        mover.remove_condition_by_uuid(disengaging.uuid)
        assert mover.action_economy.provokes_opportunity_attacks.normalized_score == 1

        Entity.update_entity_position(mover, (5, 6))
        mover.action_economy.reset_all_costs()
        Entity.update_all_entities_senses(max_distance=20)
        unprotected_move = Move(
            source_entity_uuid=mover.uuid,
            end_position=(5, 10),
        ).apply()

        assert unprotected_move is not None
        assert mover.get_hp() < hp_before
        assert watcher.action_economy.reactions.normalized_score == 0
        assert any(
            event.name == "Opportunity Attack"
            for event in EventQueue.get_events_by_type(EventType.ATTACK)
        )
    finally:
        remove_attack_modifier(watcher, hit_modifier)


def test_magical_sleep_remains_after_healing_removes_life_state_transform() -> None:
    """Sleep remains after healing removes only life-state-owned modifiers."""
    reset_core_action_state()
    source = create_skeleton(
        name="Source",
        position=(1, 1),
        faction="monsters",
    )
    target = strong_entity(
        "Death-Save Target",
        (2, 1),
        "heroes",
        uses_death_saves=True,
    )

    damage = target.receive_damage(
        amount=target.get_normal_hp(),
        damage_type=DamageType.SLASHING,
        source_entity_uuid=source.uuid,
    )
    assert damage > 0
    assert target.health.life_state.value == "dying"
    assert "Dying" not in target.active_conditions
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.can_see_visual_effects() is False

    sleep = _apply_condition(SleepEffect, source, target)
    assert target.active_conditions_by_uuid[sleep.uuid] is sleep
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0

    healed = target.receive_healing(1, source_entity_uuid=target.uuid)

    assert healed == 1
    assert target.health.life_state.value == "alive"
    assert target.active_conditions_by_uuid[sleep.uuid] is sleep
    assert target.senses.visual_access.normalized_score == 0
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.can_see_visual_effects() is False
    assert _cost_free_action(target).check_costs() is False
    assert _reaction_action(target).check_costs() is False

    target.remove_condition_by_uuid(sleep.uuid)

    assert target.senses.visual_access.normalized_score == 1
    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert target.can_see_visual_effects() is True
    assert _cost_free_action(target).check_costs() is True


@pytest.mark.parametrize(
    ("effect_type", "denies_visual_access"),
    [
        (SleepEffect, True),
        (EyebiteAsleepEffect, True),
        (HasteLethargyEffect, False),
    ],
)
def test_spell_local_control_effects_own_transforms_without_global_children(
    effect_type,
    denies_visual_access: bool,
) -> None:
    """Spell-local controls clean only their own directly installed gates."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    effect = _apply_condition(effect_type, source, target)

    assert effect.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert "Unconscious" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target.action_economy.movement.normalized_score == 0
    assert target.senses.visual_access.normalized_score == (
        0 if denies_visual_access else 1
    )

    target.remove_condition_by_uuid(effect.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target.action_economy.movement.normalized_score == 30
    assert target.senses.visual_access.normalized_score == 1


def test_hypnotic_pattern_keeps_only_its_real_charmed_child() -> None:
    """Hypnotic Pattern owns denial directly while retaining Charmed linkage."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")

    effect = _apply_condition(HypnoticPatternEffect, source, target)

    assert "Hypnotic Pattern" in target.active_conditions
    assert "Charmed" in target.active_conditions
    assert "Incapacitated" not in target.active_conditions
    assert len(effect.sub_conditions) == 1
    assert target.active_conditions["Charmed"].uuid == effect.sub_conditions[0]
    assert target.action_economy.action_permission.normalized_score == 0

    target.remove_condition_by_uuid(effect.uuid)

    assert "Charmed" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 1


def test_banishment_owns_denial_and_restores_spatial_registration() -> None:
    """Banishment's direct transform and spatial removal share one owner."""
    reset_core_action_state()
    source = strong_entity("Source", (1, 1), "heroes")
    target = strong_entity("Target", (2, 1), "monsters")
    original_position = target.position

    effect = _apply_condition(BanishedCondition, source, target)

    assert effect.sub_conditions == []
    assert "Incapacitated" not in target.active_conditions
    assert target.action_economy.action_permission.normalized_score == 0
    assert target not in Entity._entity_by_position[original_position]

    target.remove_condition_by_uuid(effect.uuid)

    assert target.action_economy.action_permission.normalized_score == 1
    assert target in Entity._entity_by_position[original_position]
