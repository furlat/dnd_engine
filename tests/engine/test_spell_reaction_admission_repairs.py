"""A reaction must admit its own event/effect before changing the triggering action."""
import pytest

from dnd.actions import Attack
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.spells.abjuration import ShieldBuff
from dnd.spells.evocation import FireBolt
from dnd.types.character_progression import Species
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_spell_catalog_audit_gameplay_regressions import wizard
from tests.engine.test_roster_support_spells import game as game
from tests.manual.spell_regression_support import force_save_result


def deny(actor, event_type, phase, condition_type=None):
    def refuse(event, _):
        if condition_type is not None and (
                not isinstance(event, ConditionApplicationEvent) or not isinstance(event.condition, condition_type)):
            return None
        return event.cancel(status_message="Reaction admission denied")
    actor.add_event_handler(EventHandler(name="Reaction admission ward", source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(event_type=event_type, event_phase=phase,
            **({"event_target_entity_uuid": actor.uuid} if condition_type else {"event_source_entity_uuid": actor.uuid}))],
        event_processor=refuse))


def test_shield_does_not_intercept_when_its_buff_is_denied(game):
    actor = wizard(game, ("spell.shield",))
    enemy = combatant(game, "Attacker", (3, 2), "foes")
    deny(actor, EventType.CONDITION_APPLICATION, EventPhase.EFFECT, ShieldBuff)
    before = actor.get_hp()
    with fixed_dice_faces(10, *([2] * 20)):
        result = Attack(source_entity_uuid=enemy.uuid, target_entity_uuid=actor.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN).apply()
    outcome = result.attack_outcome
    assert outcome is AttackOutcome.HIT
    hp = actor.get_hp()
    assert hp < before
    conditions = set(actor.active_conditions)
    assert "Shield" not in conditions
    reactions = actor.action_economy.reactions.normalized_score
    assert reactions == 1


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_counterspell_honors_its_own_canceled_reaction(game, phase):
    actor = wizard(game, ("spell.counterspell",))
    enemy = combatant(game, "Caster", (8, 2), "foes")
    target = combatant(game, "Ally", (10, 2))
    deny(actor, EventType.TRIGGER_EVENT, phase)
    before = target.get_hp()
    with fixed_dice_faces(15, *([2] * 20)):
        result = FireBolt(source_entity_uuid=enemy.uuid, target_entity_uuid=target.uuid).apply()
    canceled = result.canceled
    assert not canceled
    hp = target.get_hp()
    assert hp < before
    reactions = actor.action_economy.reactions.normalized_score
    assert reactions == (1 if phase is EventPhase.DECLARATION else 0)


@pytest.mark.parametrize("phase", [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT])
def test_innate_rebuke_honors_its_own_canceled_reaction(game, phase):
    actor = wizard(game, species=Species.TIEFLING)
    enemy = combatant(game, "Damage source", (8, 2), "foes")
    force_save_result(enemy, "dexterity", succeeds=False)
    deny(actor, EventType.BASE_ACTION, phase)
    before = enemy.get_hp()
    with fixed_dice_faces(5, *([2] * 20)):
        actor.receive_damage(1, DamageType.FORCE, enemy.uuid)
    hp = enemy.get_hp()
    assert hp == before
    reactions = actor.action_economy.reactions.normalized_score
    assert reactions == (1 if phase is EventPhase.DECLARATION else 0)
