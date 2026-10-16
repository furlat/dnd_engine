"""A refused native spell effect must leave no recipient effect behind.

These cases exercise real paid casts and native admission handlers. They do not
mock spell collaborators or prescribe how an admitted effect is implemented.
"""

import pytest

from dnd.conditions import Poisoned
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.spells.abjuration import (
    AntilifeShell,
    DeathWard,
    FreedomOfMovement,
    GlobeOfInvulnerability,
    GreaterRestoration,
    LesserRestoration,
    ProtectionFromEnergy,
    ProtectionFromPoison,
    RemoveCurse,
    Sanctuary,
    ShieldOfFaith,
    Stoneskin,
)
from dnd.spells.conjuration import PoisonSpray
from dnd.spells.divination import Guidance, SeeInvisibility, TrueSeeing
from dnd.spells.enchantment import Bless, CharmPerson, PowerWordStun
from dnd.spells.evocation import (
    CureWounds,
    HealingWord,
    HealSpell,
    Light,
    MagicMissile,
    SacredFlame,
)
from dnd.spells.illusion import Blur, GreaterInvisibility, Invisibility, MirrorImage
from dnd.spells.necromancy import BestowCurse, FalseLife
from dnd.spells.transmutation import (
    DarkvisionSpell,
    EnhanceAbility,
    EnlargeReduce,
    ExpeditiousRetreat,
    Haste,
    JumpSpell,
    Longstrider,
    Regenerate,
)
from tests.engine.test_high_level_spell_controls import high_actor
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture re-export
from tests.manual.spell_regression_support import force_save_result


def recipient_effect_state(actor):
    return {
        "hp": actor.get_hp(),
        "temporary_hp": actor.health.temporary_hit_points.normalized_score,
        "speed": actor.action_economy.current_speed(),
        "ac": actor.ac_bonus().normalized_score,
        "size": actor.size,
        "areas": frozenset(
            (zone.name, frozenset(zone.affected_positions))
            for zone in get_map().get_spatial_conditions()
        ),
        "conditions": frozenset(
            condition.get_display_name()
            for condition in actor.active_conditions_by_uuid.values()
            if condition.name != "Concentrating"
        ),
    }


REFUSED_EFFECT_BUG = pytest.mark.xfail(
    strict=True, reason="SC-09: spell mutates its recipient after effect refusal"
)


@pytest.mark.parametrize(
    "spell_type,self_target,faction",
    [
        pytest.param(FalseLife, True, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(SeeInvisibility, True, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(DarkvisionSpell, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Haste, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Blur, True, "heroes", marks=REFUSED_EFFECT_BUG),
        (CharmPerson, False, "foes"),
        pytest.param(BestowCurse, False, "foes", marks=REFUSED_EFFECT_BUG),
        (Bless, False, "heroes"),
        (MagicMissile, False, "foes"),
        (Longstrider, False, "heroes"),
        pytest.param(Guidance, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Light, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(ExpeditiousRetreat, True, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(JumpSpell, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Sanctuary, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(ShieldOfFaith, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(EnhanceAbility, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(EnlargeReduce, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Invisibility, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(MirrorImage, True, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(ProtectionFromPoison, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(ProtectionFromEnergy, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(DeathWard, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(FreedomOfMovement, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(GreaterInvisibility, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Stoneskin, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(TrueSeeing, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(CureWounds, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(HealingWord, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(HealSpell, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(Regenerate, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(PoisonSpray, False, "foes", marks=REFUSED_EFFECT_BUG),
        pytest.param(SacredFlame, False, "foes", marks=REFUSED_EFFECT_BUG),
        pytest.param(PowerWordStun, False, "foes", marks=REFUSED_EFFECT_BUG),
        pytest.param(LesserRestoration, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(GreaterRestoration, False, "heroes", marks=REFUSED_EFFECT_BUG),
        pytest.param(RemoveCurse, False, "heroes", marks=REFUSED_EFFECT_BUG),
        (AntilifeShell, True, "heroes"),
        pytest.param(GlobeOfInvulnerability, True, "heroes", marks=REFUSED_EFFECT_BUG),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
def test_refused_spell_effect_has_no_recipient_mutation(game, spell_type, self_target, faction):
    caster = high_actor(game)
    recipient = caster if self_target else high_actor(game, "Recipient", (3, 2), faction)
    if spell_type in (CureWounds, HealingWord, HealSpell, Regenerate):
        recipient.receive_damage(20, DamageType.FORCE, caster.uuid)
    if spell_type is PowerWordStun:
        recipient.receive_damage(80, DamageType.FORCE, caster.uuid)
    if spell_type in (LesserRestoration, GreaterRestoration):
        recipient.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=recipient.uuid))
    if spell_type is RemoveCurse:
        recipient.add_condition(BaseCondition(name="Audit curse", source_entity_uuid=caster.uuid,
            target_entity_uuid=recipient.uuid, tags={ConditionTag.CURSE}))
    for ability in ("wisdom", "constitution", "dexterity"):
        force_save_result(recipient, ability, succeeds=False)
    refused_lineages = set()

    def refuse(event, _):
        refused_lineages.add(event.lineage_uuid)
        return event.cancel(status_message="Spell effect refused by audit ward")

    caster.add_event_handler(EventHandler(
        name="Audit spell effect admission refusal",
        source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.CAST_SPELL,
            event_phase=EventPhase.EFFECT,
            event_source_entity_uuid=caster.uuid,
        )],
        event_processor=refuse,
    ))
    before = recipient_effect_state(recipient)
    with fixed_dice_faces(*([2] * 25)):
        result = spell_type(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=recipient.uuid,
        ).apply()
    assert result is not None
    observed_refusals = len(refused_lineages)
    assert observed_refusals > 0, "Scenario must reach the actual effect-admission boundary"
    canceled = result.canceled
    assert canceled
    after = recipient_effect_state(recipient)
    assert after == before
