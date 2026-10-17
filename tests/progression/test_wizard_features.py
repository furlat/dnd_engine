"""Real Wizard builds exercise packet ownership, recovery and free cast costs."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import SpellAction
from dnd.actions_functional import get_available_actions, preview_available_selection
from dnd.spells.evocation import MagicMissile
from dnd.characters.mastery import study_spell_mastery, SpellMasteryStudy
from dnd.classes.wizard import ArcaneRecovery
from dnd.content.characters.builds import create_character
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventType
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.entity import Entity
from dnd.spells.enchantment import ViciousMockery, MockedEffect
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_roster_support_spells import game as game
from tests.manual.spell_regression_support import force_save_result
from tests.progression.prepared_class_support import prepared_build


def wizard(game, level, *, scribed=(), prepared=()):
    actor = create_character(
        replace(
            prepared_build(CharacterClass.WIZARD, level),
            faction="heroes",
            scribed_spell_ids=scribed,
            prepared_spells=(
                PreparedSpellSelection("class.wizard.spellcasting", prepared),
            ),
        )
    )
    game.deploy_entity(actor, (2, 2))
    Entity.update_all_entities_senses()
    return actor


def cast(actor, spell_id, target=None, *, rank=1, free=False, **kw):
    template = next(
        action
        for action in actor.registered_actions
        if isinstance(action, SpellAction) and action.semantic_key == spell_id
    )
    variant = next(
        variant
        for variant in template.discovery_forms(actor.action_scan(subjective=True))
        if variant.cast_at_level == rank
        and (variant.cast_cost_grant_id is not None) == free
    )
    return variant.model_copy(
        deep=True,
        update={
            "uuid": uuid4(),
            "template": False,
            "use_register": False,
            "target_entity_uuid": target.uuid if target is not None else None,
            **kw,
        },
    ).apply()


def test_empowered_evocation_adds_int_to_every_missile_dart_before_affinity(game):
    actor = wizard(game, 10, prepared=("spell.magic_missile",))
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    before = enemy.get_hp()
    bonus = actor.ability_scores.intelligence.modifier
    with fixed_dice_faces(2, 2, 2):
        result = cast(actor, "spell.magic_missile", enemy)
    assert result is not None and not result.canceled
    assert enemy.get_hp() == before - 3 * (3 + bonus)


def test_sculpt_fireball_excludes_allied_save_and_damage_but_enemy_is_normal(game):
    actor = wizard(game, 5, scribed=("spell.fireball",), prepared=("spell.fireball",))
    ally = combatant(game, "Ally", (4, 2))
    enemy = combatant(game, "Enemy", (6, 2), "foes")
    force_save_result(enemy, "dexterity", succeeds=False)
    before = {target.uuid: target.get_hp() for target in (actor, ally, enemy)}
    row = next(
        row
        for row in get_available_actions(actor).all_actions
        if row.behavior_id == "spell.fireball"
        and row.execution_template.cast_at_level == 3
    )
    target = next(
        target for target in row.valid_targets if target.position == enemy.position
    )
    preview_cursor = EventQueue.event_cursor()
    preview = preview_available_selection(actor, row, (target,))
    assert preview.can_confirm and set(preview.affected_entity_uuids) == {enemy.uuid}
    assert EventQueue.event_cursor() == preview_cursor
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 50)):
        result = cast(actor, "spell.fireball", rank=3, end_position=enemy.position)
    assert result is not None and not result.canceled
    assert actor.get_hp() == before[actor.uuid] and ally.get_hp() == before[ally.uuid]
    assert enemy.get_hp() == before[enemy.uuid] - 16
    assert not [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SAVING_THROW
        and event.target_entity_uuid in (actor.uuid, ally.uuid)
    ]


def test_potent_successful_cantrip_half_preserves_success_and_no_mockery_rider(game):
    actor = wizard(game, 6)
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    force_save_result(enemy, "dexterity", succeeds=True)
    before = enemy.get_hp()
    with fixed_dice_faces(20, 3, 4):
        result = cast(actor, "spell.acid_splash", enemy, rank=0)
    assert result is not None and not result.canceled
    assert enemy.get_hp() == before - 3
    force_save_result(enemy, "wisdom", succeeds=True)
    actor.action_economy.reset_all_costs()
    before = enemy.get_hp()
    with fixed_dice_faces(20, 3, 4):
        result = ViciousMockery(
            source_entity_uuid=actor.uuid, target_entity_uuid=enemy.uuid, caster_level=6
        ).apply()
    assert result is not None and not result.canceled and result.save_success
    assert enemy.get_hp() == before - 3
    assert not any(
        isinstance(condition, MockedEffect)
        for condition in enemy.active_conditions_by_uuid.values()
    )


def test_arcane_recovery_recovers_existing_shared_debits_and_preserves_budget_until_long_rest(
    game,
):
    actor = wizard(game, 5)
    actor.action_economy.consume("spell_slot_2", 1)
    actor.action_economy.consume("spell_slot_1", 1)
    action = next(
        action
        for action in actor.registered_actions
        if isinstance(action, ArcaneRecovery)
    )
    result = action.instantiate(slot_rank=2).apply()
    assert result is not None and not result.canceled
    assert actor.action_economy.spell_slot_2.normalized_score == 3
    assert actor.action_economy.resources["arcane_recovery"].current == 1
    actor.action_economy.reset_all_costs()
    result = action.instantiate(slot_rank=1).apply()
    assert result is not None and not result.canceled
    assert actor.action_economy.resources["arcane_recovery"].current == 0
    actor.on_short_rest()
    assert actor.action_economy.resources["arcane_recovery"].current == 0
    assert actor.on_long_rest()
    assert actor.action_economy.resources["arcane_recovery"].current == 3
    slots = actor.action_economy.get_normal_spell_slot_capacities()
    rejected = action.instantiate(slot_rank=2).apply()
    assert rejected is not None and rejected.canceled
    assert actor.action_economy.actions.normalized_score == 1
    assert actor.action_economy.get_normal_spell_slot_capacities() == slots


def test_overchannel_counts_once_per_cast_and_recoil_ignores_immunity_then_real_rest_resets(
    game,
):
    actor = wizard(game, 14, prepared=("spell.magic_missile",))
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    handler = next(
        handler
        for handler in actor.event_handlers.values()
        if handler.semantic_key == "class_feature.wizard.overchannel"
    )
    assert actor.set_handler_enabled_by_uuid(handler.uuid, True)
    actor.health.damage_reduction.self_static.add_resistance_modifier(
        ResistanceModifier(
            source_entity_uuid=actor.uuid,
            damage_type=DamageType.NECROTIC,
            value=ResistanceStatus.IMMUNITY,
        )
    )
    before_enemy, before_self = enemy.get_hp(), actor.get_hp()
    bonus = actor.ability_scores.intelligence.modifier
    with fixed_dice_faces(1, 1, 1):
        result = cast(actor, "spell.magic_missile", enemy)
    assert result is not None and not result.canceled
    assert enemy.get_hp() == before_enemy - 3 * (5 + bonus)
    assert actor.get_hp() == before_self and actor.spellcasting.overchannel_uses == 1
    actor.action_economy.reset_all_costs()
    with fixed_dice_faces(*([1] * 20)):
        result = cast(actor, "spell.magic_missile", enemy)
    assert result is not None and not result.canceled
    assert (
        actor.get_hp() == before_self - 2 and actor.spellcasting.overchannel_uses == 2
    )
    actor.on_short_rest()
    assert actor.spellcasting.overchannel_uses == 2
    assert actor.on_long_rest()
    assert actor.spellcasting.overchannel_uses == 0


def test_mastery_free_base_rank_survives_zero_slots_and_upcast_stays_paid(game):
    build = prepared_build(CharacterClass.WIZARD, 18)
    row = build.class_levels[-1]
    choices = tuple(
        replace(choice, values=("spell.magic_missile",))
        if choice.choice_id.endswith(".mastery_1")
        else choice
        for choice in row.choices
    )
    build = replace(
        build,
        class_levels=(*build.class_levels[:-1], replace(row, choices=choices)),
        faction="heroes",
        prepared_spells=(
            PreparedSpellSelection(
                "class.wizard.spellcasting", ("spell.magic_missile",)
            ),
        ),
    )
    actor = create_character(build)
    game.deploy_entity(actor, (2, 2))
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    actor.action_economy.consume("spell_slot_1", 4)
    with fixed_dice_faces(1, 1, 1):
        result = cast(actor, "spell.magic_missile", enemy, free=True)
    assert result is not None and not result.canceled
    assert actor.action_economy.spell_slot_1.normalized_score == 0
    actor.action_economy.reset_all_costs()
    with fixed_dice_faces(1, 1, 1, 1):
        result = cast(actor, "spell.magic_missile", enemy, rank=2)
    assert result is not None and not result.canceled
    assert actor.action_economy.spell_slot_2.normalized_score == 2


def test_mastery_shield_spends_reaction_without_any_slot(game):
    build = prepared_build(CharacterClass.WIZARD, 18)
    row = build.class_levels[-1]
    choices = tuple(
        replace(choice, values=("spell.shield",))
        if choice.choice_id.endswith(".mastery_1")
        else choice
        for choice in row.choices
    )
    actor = create_character(
        replace(
            build,
            class_levels=(*build.class_levels[:-1], replace(row, choices=choices)),
            faction="heroes",
            scribed_spell_ids=("spell.shield",),
            prepared_spells=(
                PreparedSpellSelection("class.wizard.spellcasting", ("spell.shield",)),
            ),
        )
    )
    game.deploy_entity(actor, (2, 2))
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    for (
        rank,
        capacity,
    ) in actor.action_economy.get_normal_spell_slot_capacities().items():
        actor.action_economy.consume(f"spell_slot_{rank}", capacity)
    before = actor.get_hp()
    with fixed_dice_faces(2, 2, 2):
        result = MagicMissile(
            source_entity_uuid=enemy.uuid, target_entity_uuid=actor.uuid
        ).apply()
    assert result is not None and not result.canceled
    assert (
        actor.get_hp() == before
        and actor.action_economy.reactions.normalized_score == 0
    )
    assert all(
        actor.action_economy.spell_slot_value(rank).normalized_score == 0
        for rank in range(1, 10)
    )


def test_signature_counterspell_uses_own_charge_without_slot_and_short_rest_restores_it(
    game,
):
    build = prepared_build(CharacterClass.WIZARD, 20)
    row = build.class_levels[-1]
    choices = tuple(
        replace(choice, values=("spell.counterspell", "spell.fireball"))
        if choice.choice_id.endswith(".signature")
        else choice
        for choice in row.choices
    )
    actor = create_character(
        replace(
            build,
            class_levels=(*build.class_levels[:-1], replace(row, choices=choices)),
            faction="heroes",
            scribed_spell_ids=("spell.counterspell", "spell.fireball"),
        )
    )
    game.deploy_entity(actor, (2, 2))
    enemy = combatant(game, "Enemy", (5, 2), "foes")
    for (
        rank,
        capacity,
    ) in actor.action_economy.get_normal_spell_slot_capacities().items():
        actor.action_economy.consume(f"spell_slot_{rank}", capacity)
    before = actor.get_hp()
    with fixed_dice_faces(2, 2, 2):
        result = MagicMissile(
            source_entity_uuid=enemy.uuid, target_entity_uuid=actor.uuid
        ).apply()
    assert result is not None and result.canceled
    assert (
        actor.get_hp() == before
        and actor.action_economy.reactions.normalized_score == 0
    )
    assert (
        actor.action_economy.resources["signature_spell.spell.counterspell"].current
        == 0
    )
    assert actor.action_economy.resources["signature_spell.spell.fireball"].current == 1
    actor.on_short_rest()
    assert (
        actor.action_economy.resources["signature_spell.spell.counterspell"].current
        == 1
    )


def test_mastery_eight_hour_study_changes_only_free_choices_and_rebuilds(game):
    actor = wizard(game, 18, scribed=("spell.shield", "spell.mirror_image"))
    old_slots = actor.action_economy.get_normal_spell_slot_capacities()
    with pytest.raises(ValueError, match="eight-hour"):
        study_spell_mastery(
            actor, SpellMasteryStudy("spell.shield", "spell.mirror_image", hours=1)
        )
    result = study_spell_mastery(
        actor, SpellMasteryStudy("spell.shield", "spell.mirror_image")
    )
    assert result.hours == 8
    grants = [
        grant
        for grant in actor.spellcasting.free_cast_grants.values()
        if grant.provider_id == "class_feature.wizard.spell_mastery"
    ]
    assert {grant.spell_id for grant in grants} == {
        "spell.shield",
        "spell.mirror_image",
    }
    assert actor.action_economy.get_normal_spell_slot_capacities() == old_slots
    rebuilt = create_character(
        replace(
            prepared_build(CharacterClass.WIZARD, 18),
            class_levels=result.applied_class_levels,
            scribed_spell_ids=actor.scribed_spell_ids,
        )
    )
    assert {
        grant.spell_id
        for grant in rebuilt.spellcasting.free_cast_grants.values()
        if grant.provider_id == "class_feature.wizard.spell_mastery"
    } == {"spell.shield", "spell.mirror_image"}


def test_retained_wall_sculpt_stops_allied_save_and_later_contact(game):
    actor = wizard(
        game, 7, scribed=("spell.wall_of_fire",), prepared=("spell.wall_of_fire",)
    )
    ally = combatant(game, "Ally", (6, 4))
    enemy = combatant(game, "Enemy", (8, 4), "foes")
    force_save_result(enemy, "dexterity", succeeds=False)
    before = ally.get_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 40)):
        result = cast(
            actor,
            "spell.wall_of_fire",
            rank=4,
            end_position=(5, 4),
            extra_target_positions=[(10, 4)],
        )
        ally.on_turn_end()
    assert result is not None and not result.canceled
    assert ally.get_hp() == before
    assert not [
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SAVING_THROW
        and event.target_entity_uuid == ally.uuid
    ]
