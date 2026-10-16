"""Native spell outcomes on rejected effects, source overlap and typed defenses."""

import pytest

from dnd.core.base_conditions import BaseCondition
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Damage, EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.life_types import LifeState
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import ModifiableValue
from dnd.spells.abjuration import ProtectionFromEvilAndGood
from dnd.spells.conjuration import EnsnaringStrike
from dnd.spells.divination import HuntersMark, ReapplyHuntersMark
from dnd.spells.enchantment import (
    AnimalFriendship,
    CharmMonster,
    DissonantWhispers,
    Heroism,
    Hex,
    ReapplyHex,
)
from dnd.spells.evocation import (
    AcidArrow,
    BrandingSmite,
    ChromaticOrb,
    DancingLights,
    Moonbeam,
    MoveDancingLights,
    MoveMoonbeam,
    SearingSmite,
)
from dnd.spells.illusion import PhantasmalForce, PhantasmalKiller
from dnd.spells.necromancy import SpareTheDying
from dnd.spells.transmutation import PlantGrowth
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_bg3_rank_one_two_spells import game as game
from tests.engine.test_bg3_spell_hit_riders import cast, equip
from tests.manual.spell_regression_support import force_save_result


def test_animal_friendship_independent_casters(game):
    first = combatant(game, "First", (2, 2))
    second = combatant(game, "Second", (3, 2))
    beast = combatant(
        game, "Beast", (5, 2), "foes", intelligence=3, creature_type=CreatureType.BEAST
    )
    force_save_result(beast, "wisdom", succeeds=False)
    cast(AnimalFriendship, first, beast)
    cast(AnimalFriendship, second, beast)
    sources = {
        c.source_entity_uuid
        for c in beast.active_conditions_by_uuid.values()
        if c.get_display_name() == "Animal Friendship"
    }
    assert sources == {first.uuid, second.uuid}, sources


@pytest.mark.parametrize("spell", [SearingSmite, BrandingSmite, EnsnaringStrike])
def test_canceled_hybrid_effect_does_not_attack_or_pay_hit_costs(game, spell):
    caster = combatant(game)
    enemy = combatant(game, "Enemy", (3, 2), "foes")
    equip(caster)
    force_save_result(enemy, "strength", succeeds=False)
    caster.add_event_handler(
        EventHandler(
            name="Review veto",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=lambda event, _: event.cancel(status_message="Review veto"),
        )
    )
    before = enemy.get_hp()
    level = spell.model_fields["spell_level"].default
    slot = (
        caster.action_economy.spell_slot_1
        if level == 1
        else caster.action_economy.spell_slot_2
    )
    slots = slot.normalized_score
    with fixed_dice_faces(15, *([2] * 20)):
        result = spell(
            source_entity_uuid=caster.uuid, target_entity_uuid=enemy.uuid
        ).apply()
    assert result is not None and result.canceled
    assert enemy.get_hp() == before, (before, enemy.get_hp())
    assert caster.action_economy.bonus_actions.normalized_score == 1
    assert slot.normalized_score == slots


@pytest.mark.parametrize(
    "spell,repeat,display",
    [(Hex, ReapplyHex, "Hex"), (HuntersMark, ReapplyHuntersMark, "Hunter's Mark")],
)
def test_canceled_reapply_effect_keeps_original_quarry(game, spell, repeat, display):
    caster = combatant(game)
    first = combatant(game, "First", (4, 2), "foes")
    second = combatant(game, "Second", (6, 2), "foes")
    cast(spell, caster, first)
    first.receive_damage(first.get_hp(), DamageType.FORCE, caster.uuid)
    action = next(a for a in caster.registered_actions if isinstance(a, repeat))
    caster.add_event_handler(
        EventHandler(
            name="Review veto reapply",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=lambda event, _: event.cancel(status_message="Review veto"),
        )
    )
    caster.action_economy.reset_all_costs()
    result = action.instantiate(target_entity_uuid=second.uuid).apply()
    assert result is not None and result.canceled
    assert not any(
        c.get_display_name() == display
        for c in second.active_conditions_by_uuid.values()
    )


@pytest.mark.parametrize(
    "spell,repeat,display",
    [
        (DancingLights, MoveDancingLights, "Dancing Lights"),
        (Moonbeam, MoveMoonbeam, "Moonbeam Sustain"),
    ],
)
def test_canceled_move_retains_old_anchor(game, spell, repeat, display):
    caster = combatant(game)
    cast(spell, caster, end_position=(4, 2))
    owner = next(
        c
        for c in caster.active_conditions_by_uuid.values()
        if c.get_display_name() == display
    )
    zone = BaseCondition.get(owner.zone_uuid) if spell is Moonbeam else owner
    action = next(a for a in caster.registered_actions if isinstance(a, repeat))
    caster.add_event_handler(
        EventHandler(
            name="Review veto move",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=lambda event, _: event.cancel(status_message="Review veto"),
        )
    )
    caster.action_economy.reset_all_costs()
    result = action.instantiate(end_position=(6, 2)).apply()
    assert result is not None and result.canceled
    assert zone.position == (4, 2), zone.position


def test_canceled_spare_dying_does_not_stabilize(game):
    caster = combatant(game)
    target = combatant(game, "Dying", (3, 2))
    target.uses_death_saves = True
    target.receive_damage(target.get_hp(), DamageType.FORCE, caster.uuid)
    caster.add_event_handler(
        EventHandler(
            name="Review veto stabilization",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=lambda event, _: event.cancel(status_message="Review veto"),
        )
    )
    result = SpareTheDying(
        source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid
    ).apply()
    assert result is not None and result.canceled
    assert target.health.life_state is LifeState.DYING, target.health.life_state.value


@pytest.mark.parametrize(
    "spell,kwargs",
    [
        (PlantGrowth, {}),
        (AcidArrow, {"target_mode": "ground"}),
        (ChromaticOrb, {"target_mode": "ground", "element": "acid"}),
    ],
)
def test_canceled_ground_effect_creates_no_field(game, spell, kwargs):
    caster = combatant(game)
    caster.add_event_handler(
        EventHandler(
            name="Review veto ground",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=lambda event, _: event.cancel(status_message="Review veto"),
        )
    )
    result = spell(
        source_entity_uuid=caster.uuid, end_position=(5, 2), **kwargs
    ).apply()
    assert result is not None and result.canceled
    assert not get_map().get_spatial_conditions()


def test_phantasmal_force_selects_largest_component_after_flat_defense(game):
    caster = combatant(game)
    target = combatant(game, "Enemy", (5, 2), "foes")
    force_save_result(target, "intelligence", succeeds=False)
    cast(PhantasmalForce, caster, target)
    target.health.damage_reduction.self_static.add_value_modifier(
        NumericalModifier(
            name="Native flat defense",
            value=10,
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
        )
    )
    damages = [
        Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=4,
            dice_numbers=0,
            damage_type=kind,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=caster.uuid, base_value=amount
            ),
        )
        for kind, amount in ((DamageType.BLUDGEONING, 10), (DamageType.FIRE, 6))
    ]
    hp = target.get_hp()
    target.receive_damage(
        16,
        DamageType.BLUDGEONING,
        caster.uuid,
        damages=damages,
        component_amounts=(10, 6),
        independent_resolution=True,
    )
    assert target.get_hp() == hp - 6
    effect = next(
        c
        for c in target.active_conditions_by_uuid.values()
        if c.get_display_name() == "Phantasmal Force"
    )
    assert effect.damage_type is DamageType.FIRE, effect.damage_type.value


def test_heroism_clears_new_killer_and_prevents_new_fear(game):
    helper = combatant(game)
    target = combatant(game, "Ally", (3, 2))
    enemy = combatant(game, "Enemy", (6, 2), "foes", slots={1: 4, 4: 3})
    force_save_result(target, "wisdom", succeeds=False)
    cast(PhantasmalKiller, enemy, target)
    assert any(
        c.get_display_name() == "Phantasmal Killer"
        for c in target.active_conditions_by_uuid.values()
    )
    cast(Heroism, helper, target)
    assert not any(
        c.get_display_name() == "Phantasmal Killer"
        for c in target.active_conditions_by_uuid.values()
    )
    with fixed_dice_faces(8, 3, 3, 3):
        cast(DissonantWhispers, enemy, target)
    assert not any(
        c.get_display_name() == "Dissonant Whispers Fear"
        for c in target.active_conditions_by_uuid.values()
    )
    assert target.action_economy.current_speed() > 0


def test_protection_cures_only_eligible_new_charm_source(game):
    helper = combatant(game)
    target = combatant(game, "Ally", (3, 2))
    fiend = combatant(
        game, "Fiend", (6, 2), "foes", creature_type=CreatureType.FIEND, slots={4: 3}
    )
    human = combatant(game, "Human", (6, 3), "foes", slots={4: 3})
    force_save_result(target, "wisdom", succeeds=False)
    cast(CharmMonster, fiend, target)
    cast(CharmMonster, human, target)
    cast(ProtectionFromEvilAndGood, helper, target)
    sources = {
        c.source_entity_uuid
        for c in target.active_conditions_by_uuid.values()
        if c.get_display_name() == "Charm Monster"
    }
    assert sources == {human.uuid}, sources


def test_dissonant_deadline_expires_through_native_turns(game):
    caster = combatant(game)
    target = combatant(game, "Enemy", (5, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(DissonantWhispers, caster, target)
    assert target.action_economy.current_speed() == 0
    target.on_turn_start()
    target.on_turn_end()
    target.on_turn_start()
    target.on_turn_end()
    assert not any(
        c.get_display_name() == "Dissonant Whispers Fear"
        for c in target.active_conditions_by_uuid.values()
    )


@pytest.mark.parametrize(
    "spell,repeat,display",
    [(Hex, ReapplyHex, "Hex"), (HuntersMark, ReapplyHuntersMark, "Hunter's Mark")],
)
def test_reapply_does_not_publish_orphan_quarry_after_effect_ends_concentration(
    game, spell, repeat, display
):
    caster = combatant(game)
    first = combatant(game, "First", (4, 2), "foes")
    second = combatant(game, "Second", (6, 2), "foes")
    cast(spell, caster, first)
    first.receive_damage(first.get_hp(), DamageType.FORCE, caster.uuid)
    action = next(a for a in caster.registered_actions if isinstance(a, repeat))

    def end_concentration(event, _):
        caster.remove_condition("Concentrating", parent_event=event)
        return None

    caster.add_event_handler(
        EventHandler(
            name="Lose sustain at effect",
            source_entity_uuid=caster.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.BASE_ACTION,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=caster.uuid,
                )
            ],
            event_processor=end_concentration,
        )
    )
    caster.action_economy.reset_all_costs()
    action.instantiate(target_entity_uuid=second.uuid).apply()
    assert "Concentrating" not in caster.active_conditions
    assert not any(
        c.get_display_name() == display
        for c in second.active_conditions_by_uuid.values()
    )
