"""Native aura locality preserves faction, lifecycle and exact source ownership."""

import pytest

from dnd.classes.paladin import PaladinAuraBenefit
from dnd.conditions import Poisoned, Unconscious
from dnd.core.creature_types import DamageType
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture export
from tests.progression.test_paladin_features import paladin

ALL_AURAS = ("courage", "devotion", "protection")


def check_auras(recipient, provider, expected=ALL_AURAS):
    actual = tuple(sorted(
        condition.aura_kind
        for condition in recipient.active_conditions_by_uuid.values()
        if isinstance(condition, PaladinAuraBenefit)
        and condition.source_entity_uuid == provider.uuid
    ))
    assert actual == expected


def test_recipient_faction_change_updates_only_its_aura_memberships(game):
    owner = paladin(game, 10)
    ally = combatant(game, "Ally", (3, 2))
    changed = combatant(game, "Changing allegiance", (4, 2), "foes")
    remote = combatant(game, "Distant", (16, 6), "foes")
    check_auras(ally, owner)
    check_auras(changed, owner, ())
    stable_memberships = frozenset(ally.active_conditions_by_uuid)
    base_save = changed.saving_throw_bonus(None, "wisdom").normalized_score

    changed.set_faction("heroes")
    check_auras(changed, owner)
    protected_save = changed.saving_throw_bonus(None, "wisdom").normalized_score
    assert protected_save == base_save + max(1, owner.ability_scores.charisma.modifier)
    changed.set_faction("foes")
    check_auras(changed, owner, ())
    restored_save = changed.saving_throw_bonus(None, "wisdom").normalized_score
    assert restored_save == base_save

    remote.set_faction("heroes")
    check_auras(remote, owner, ())
    unchanged_memberships = frozenset(ally.active_conditions_by_uuid)
    assert unchanged_memberships == stable_memberships


def test_owner_faction_change_preserves_another_paladins_contributions(game):
    owner = paladin(game, 10)
    other = paladin(game, 10)
    Entity.update_entity_position(other, (3, 3))
    other.ability_scores.charisma.ability_score.self_static.add_value_modifier(
        NumericalModifier(source_entity_uuid=other.uuid, value=4)
    )
    ally = combatant(game, "Ally", (3, 2))
    foe = combatant(game, "Foe", (4, 2), "foes")
    check_auras(ally, owner)
    check_auras(ally, other)
    other_memberships = frozenset(
        condition.uuid for condition in ally.active_conditions_by_uuid.values()
        if isinstance(condition, PaladinAuraBenefit)
        and condition.source_entity_uuid == other.uuid
    )

    owner.set_faction("foes")
    check_auras(ally, owner, ())
    check_auras(ally, other)
    check_auras(foe, owner)
    check_auras(foe, other, ())
    retained = frozenset(ally.active_conditions_by_uuid)
    assert other_memberships <= retained
    bonus = ally.saving_throw_bonus(None, "wisdom").normalized_score
    assert bonus == ally.ability_scores.wisdom.modifier + other.ability_scores.charisma.modifier

    owner.set_faction("heroes")
    check_auras(ally, owner)
    check_auras(ally, other)
    check_auras(foe, owner, ())


@pytest.mark.parametrize("incapacity", ["unconscious", "zero_hp"])
def test_provider_recovery_after_moving_restores_only_current_neighbors(game, incapacity):
    owner = paladin(game, 10)
    old_neighbor = combatant(game, "Old neighbor", (3, 2))
    new_neighbor = combatant(game, "New neighbor", (13, 6))
    check_auras(old_neighbor, owner)
    check_auras(new_neighbor, owner, ())
    if incapacity == "unconscious":
        asleep = Unconscious(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid)
        result = owner.add_condition(asleep)
        assert result is not None
        canceled = result.canceled
        assert not canceled
    else:
        owner.receive_damage(owner.get_hp(), DamageType.FORCE, owner.uuid)
    check_auras(old_neighbor, owner, ())
    Entity.commit_position_transfers(((owner, (14, 6), None),))
    check_auras(new_neighbor, owner, ())
    if incapacity == "unconscious":
        assert owner.remove_condition_by_uuid(asleep.uuid)
    else:
        owner.receive_healing(5, owner.uuid)
    check_auras(old_neighbor, owner, ())
    check_auras(new_neighbor, owner)


def test_undeploy_and_redeploy_rebuilds_only_current_aura_memberships(game):
    owner = paladin(game, 10)
    old_neighbor = combatant(game, "Old neighbor", (3, 2))
    new_neighbor = combatant(game, "New neighbor", (13, 6))
    check_auras(old_neighbor, owner)
    removed = game.remove_entity(owner.uuid)
    assert removed is owner
    check_auras(old_neighbor, owner, ())
    new_neighbor.set_faction("foes")
    game.deploy_entity(owner, (14, 6))
    check_auras(old_neighbor, owner, ())
    check_auras(new_neighbor, owner, ())
    new_neighbor.set_faction("heroes")
    check_auras(new_neighbor, owner)


def test_refresh_retries_exact_retained_membership_after_exit_removal_was_refused(game):
    owner = paladin(game, 10)
    ally = combatant(game, "Ally", (3, 2))
    unrelated = Poisoned(source_entity_uuid=ally.uuid, target_entity_uuid=ally.uuid)
    ally.add_condition(unrelated)
    refusals = []

    def refuse(event, _):
        refusals.append(event.lineage_uuid)
        return event.cancel(status_message="Retain aura lease during exit")

    veto = EventHandler(
        source_entity_uuid=ally.uuid, validation_only=True,
        trigger_conditions=[Trigger(
            event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT,
            event_target_entity_uuid=ally.uuid,
        )],
        event_processor=refuse,
    )
    ally.add_event_handler(veto)
    Entity.commit_position_transfers(((owner, (14, 6), None),))
    assert len(refusals) > 0
    check_auras(ally, owner)
    ally.remove_event_handler(veto)
    owner.add_condition(Poisoned(source_entity_uuid=owner.uuid, target_entity_uuid=owner.uuid))
    check_auras(ally, owner, ())
    retained = frozenset(ally.active_conditions_by_uuid)
    assert unrelated.uuid in retained
