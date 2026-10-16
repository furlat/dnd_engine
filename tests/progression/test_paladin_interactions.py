"""Native class actions and lifecycle transitions at their gameplay boundaries."""

from dataclasses import replace

from dnd.classes.paladin import (
    SacredWeapon,
    CleansingTouch,
    HolyNimbus,
    DivineSense,
    PaladinAuraBenefit,
    SacredWeaponEffect,
)
from dnd.conditions import Unconscious
from dnd.core.creature_types import CreatureType
from dnd.core.creature_types import DamageType
from dnd.actions import Attack
from dnd.spells.evocation import FireBolt
from dnd.content.characters.builds import create_character
from dnd.content.characters.progression import add_class_level, remove_last_class_level
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.events import (
    EventHandler,
    Trigger,
    EventType,
    EventPhase,
    SavingThrowEvent,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.modifiers import NumericalModifier, AdvantageStatus
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.dice import fixed_dice_faces
from dnd.entity import Entity
from dnd.spells.enchantment import Bless
from dnd.spells.transmutation import Haste, HasteLethargyEffect
from dnd.types.character_progression import CharacterClass, FeatureToggleSelection
from tests.progression.prepared_class_support import prepared_build, prepared_level
from tests.progression.test_paladin_features import paladin, use
from tests.engine.test_roster_support_spells import game as game
from tests.engine.test_bg3_rank_one_two_spells import combatant


def test_sacred_weapon_follows_exact_item_and_current_wielder_then_level_cleanup(game):
    actor = paladin(game, 3)
    ally = combatant(game, "Ally", (3, 2))
    ally.ability_scores.charisma.ability_score.self_static.add_value_modifier(
        NumericalModifier(source_entity_uuid=ally.uuid, value=6)
    )
    mace = build_authored_item("weapon.mace", actor.uuid)
    assert actor.loot_item(mace) and actor.equip_item(mace.uuid, WeaponSlot.MELEE_MAIN)
    result = use(actor, SacredWeapon)
    assert result is not None and not result.canceled
    assert mace.attack_bonus.normalized_score == max(
        1, actor.ability_scores.charisma.modifier
    )
    assert actor.unequip_item(WeaponSlot.MELEE_MAIN) is mace
    assert ally.loot_item(mace) and ally.equip_item(mace.uuid, WeaponSlot.MELEE_MAIN)
    assert mace.attack_bonus.normalized_score == ally.ability_scores.charisma.modifier
    assert any(
        isinstance(c, SacredWeaponEffect)
        for c in mace.active_conditions_by_uuid.values()
    )
    remove_last_class_level(actor)
    assert mace.attack_bonus.normalized_score == 0
    assert not mace.magical_attack_sources


def test_cleansing_removes_only_selected_bless_recipient_and_veto_spends_nothing(game):
    actor = paladin(game, 14)
    caster = combatant(game, "Caster", (2, 3))
    ally = combatant(game, "Ally", (3, 2))
    other = combatant(game, "Other", (4, 2))
    result = Bless(
        semantic_key="spell.bless",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        extra_target_entity_uuids=[other.uuid],
    ).apply()
    assert result is not None and not result.canceled
    chosen = next(
        c
        for c in ally.active_conditions_by_uuid.values()
        if c.effect_origin is not None and c.effect_origin.source_id == "spell.bless"
    )
    other_ids = set(other.active_conditions_by_uuid)

    def reject(event, _):
        return event.cancel(status_message="Keep selected Bless")

    veto = EventHandler(
        source_entity_uuid=ally.uuid,
        name="Veto dispel",
        event_processor=reject,
        validation_only=True,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CONDITION_REMOVAL,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=ally.uuid,
            )
        ],
    )
    ally.add_event_handler(veto)
    charges = actor.action_economy.resources["cleansing_touch"].current
    rejected = use(
        actor, CleansingTouch, target_entity_uuid=ally.uuid, condition_uuid=chosen.uuid
    )
    assert rejected is None or rejected.canceled
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.resources["cleansing_touch"].current == charges
    ally.remove_event_handler(veto)
    result = use(
        actor, CleansingTouch, target_entity_uuid=ally.uuid, condition_uuid=chosen.uuid
    )
    assert result is not None and not result.canceled
    assert chosen.uuid not in ally.active_conditions_by_uuid
    assert set(other.active_conditions_by_uuid) == other_ids


def test_cleansing_haste_keeps_native_ending_penalty(game):
    actor = paladin(game, 14)
    caster = combatant(game, "Caster", (2, 3))
    ally = combatant(game, "Ally", (3, 2))
    result = Haste(
        semantic_key="spell.haste",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
    ).apply()
    assert result is not None and not result.canceled
    chosen = next(
        c
        for c in ally.active_conditions_by_uuid.values()
        if c.effect_origin is not None and c.effect_origin.source_id == "spell.haste"
    )
    result = use(
        actor, CleansingTouch, target_entity_uuid=ally.uuid, condition_uuid=chosen.uuid
    )
    assert result is not None and not result.canceled
    assert any(
        isinstance(c, HasteLethargyEffect)
        for c in ally.active_conditions_by_uuid.values()
    )


def test_aura_recovers_after_unconsciousness_and_expands_on_live_level_eighteen(game):
    actor = paladin(game, 17)
    ally = combatant(game, "Ally", (7, 2))
    assert not any(
        isinstance(c, PaladinAuraBenefit)
        for c in ally.active_conditions_by_uuid.values()
    )
    add_class_level(
        actor, prepared_level(CharacterClass.PALADIN, actor.applied_class_levels)
    )
    assert (
        len(
            [
                c
                for c in ally.active_conditions_by_uuid.values()
                if isinstance(c, PaladinAuraBenefit)
            ]
        )
        == 3
    )
    asleep = Unconscious(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    actor.add_condition(asleep)
    assert not any(
        isinstance(c, PaladinAuraBenefit)
        for c in ally.active_conditions_by_uuid.values()
    )
    actor.remove_condition_by_uuid(asleep.uuid)
    assert (
        len(
            [
                c
                for c in ally.active_conditions_by_uuid.values()
                if isinstance(c, PaladinAuraBenefit)
            ]
        )
        == 3
    )
    remove_last_class_level(actor)
    assert not any(
        isinstance(c, PaladinAuraBenefit)
        for c in ally.active_conditions_by_uuid.values()
    )


def test_holy_nimbus_enemy_start_cadence_and_exact_spell_save_filter(game):
    actor = paladin(game, 20)
    foe = combatant(game, "Fiend", (3, 2), "foes", creature_type=CreatureType.FIEND)
    ally = combatant(game, "Ally", (2, 3))
    hp = foe.get_hp(), ally.get_hp()
    result = use(actor, HolyNimbus)
    assert result is not None and not result.canceled and foe.get_hp() == hp[0]
    foe.on_turn_start()
    ally.on_turn_start()
    assert foe.get_hp() == hp[0] - 10 and ally.get_hp() == hp[1]
    for cause, expected in (
        ("spell.fireball", AdvantageStatus.ADVANTAGE),
        ("class_feature.cleric.turn_undead", AdvantageStatus.NONE),
    ):
        request = SavingThrowEvent(
            source_entity_uuid=foe.uuid,
            target_entity_uuid=actor.uuid,
            ability_name="dexterity",
            dc=10,
            saving_throw_context=SavingThrowContext(
                cause_id=cause, effect_id=cause, is_magical=True
            ),
        )
        with fixed_dice_faces(5, 15):
            _, roll, _ = actor.saving_throw(request)
        assert roll.advantage_status is expected
    remove_last_class_level(actor)
    foe.on_turn_start()
    assert foe.get_hp() == hp[0] - 10


def test_protection_aura_adds_to_actual_death_save(game):
    actor = paladin(game, 6)
    ally = create_character(
        replace(prepared_build(CharacterClass.WIZARD), faction="heroes")
    )
    game.deploy_entity(ally, (3, 2))
    ally.receive_damage(ally.get_hp() + 1, DamageType.FORCE, actor.uuid)
    with fixed_dice_faces(9):
        ally.make_death_save()
    assert ally.death_save_successes == 1 and ally.death_save_failures == 0
    Entity.commit_position_transfers(((actor, (14, 6), None),))
    with fixed_dice_faces(9):
        ally.make_death_save()
    assert ally.death_save_successes == 1 and ally.death_save_failures == 1


def test_improved_smite_applies_on_every_melee_hit_and_doubles_critical_dice(game):
    actor = create_character(
        replace(
            prepared_build(CharacterClass.PALADIN, 11),
            faction="heroes",
            feature_toggles=(
                FeatureToggleSelection("class_feature.paladin.divine_smite", False),
            ),
        )
    )
    game.deploy_entity(actor, (2, 2))
    foe = combatant(game, "Enemy", (3, 2), "foes")
    mace = build_authored_item("weapon.mace", actor.uuid)
    assert actor.loot_item(mace) and actor.equip_item(mace.uuid, WeaponSlot.MELEE_MAIN)
    before = foe.get_hp()
    with fixed_dice_faces(20, 2, 2, 2, 2):
        result = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=foe.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and not result.canceled
    damage = before - foe.get_hp()
    assert damage == 9
    actor.action_economy.reset_all_costs()
    before = foe.get_hp()
    with fixed_dice_faces(10, 2, 2):
        result = Attack(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=foe.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
        ).apply()
    assert result is not None and not result.canceled
    damage = before - foe.get_hp()
    assert damage == 5
    assert actor.action_economy.spell_slot_1.normalized_score == 4


def test_divine_sense_grants_real_spell_attack_advantage_only_against_eligible_types(
    game,
):
    actor = paladin(game, 2)
    fiend = combatant(game, "Fiend", (7, 2), "foes", creature_type=CreatureType.FIEND)
    human = combatant(game, "Humanoid", (7, 4), "foes")
    assert not use(actor, DivineSense).canceled
    with fixed_dice_faces(5, 15, 2):
        result = FireBolt(
            source_entity_uuid=actor.uuid, target_entity_uuid=fiend.uuid
        ).apply()
    assert result is not None and not result.canceled
    assert result.dice_roll.advantage_status is AdvantageStatus.ADVANTAGE
    actor.action_economy.reset_all_costs()
    with fixed_dice_faces(5, 2):
        result = FireBolt(
            source_entity_uuid=actor.uuid, target_entity_uuid=human.uuid
        ).apply()
    assert result is not None and not result.canceled
    assert result.dice_roll.advantage_status is AdvantageStatus.NONE
