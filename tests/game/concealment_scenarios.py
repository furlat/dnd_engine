"""Native concealment experiments; both views come from one causal history."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.conditions import Hidden
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_block import LightLevel
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.divination import SeeInvisibility, TrueSeeing
from dnd.spells.evocation import FireBolt
from dnd.spells.illusion import GreaterInvisibility, Invisibility
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


ConcealmentProgram = Literal["invisibility", "greater-invisibility", "see-invisibility", "sight-expiry", "doorway", "hide-bright", "hide-dim", "stacked"]
SightGrant = Literal["none", "spell", "potion"]
RevealOperation = Literal["none", "drop-concentration", "attack", "cast"]


def concealment_history(
    *, program: ConcealmentProgram = "invisibility", allied: bool = False,
    sight_grant: SightGrant = "none", stealth_face: int = 18,
    reveal: RevealOperation = "drop-concentration",
) -> CapturedHistory:
    """Run a small selected native program, without setting perception flags.

    Spell slots, equipment, factions and light are setup data. Cast, drink,
    Hide, movement, voluntary concentration removal and expiry all use their
    existing mechanical owners. The renderer receives only the recorded views.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = ("battlefield.visibility_doorway_open" if program == "doorway"
                      else "battlefield.open_floor_bright")
    built = build_battlefield(battlefield_id)
    if program in ("hide-dim", "stacked"):
        for position in ((7, 3), (8, 3), (9, 3)):
            get_map().set_tile_base_light(position, LightLevel.DIM_LIGHT)
    game = Game()
    try:
        placements = ((("perceiver", (5, 7)), ("subject", (8, 7))) if program == "doorway"
                      else (("perceiver", (3, 3)), ("subject", (7, 3))))
        actors: dict[str, Entity] = {}
        for role, position in placements:
            actor = Entity.create(uuid4(), "Perceiver" if role == "perceiver" else "Subject", config=EntityConfig(
                position=position, faction="heroes" if role == "perceiver" or allied else "enemies",
                action_economy=ActionEconomyConfig(spell_slots={2: 1, 4: 1, 6: 1}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "perceiver" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("weapon.shortbow", actor.uuid), WeaponSlot.RANGED_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            if role == "perceiver" and sight_grant == "potion":
                actor.install_initial_items(((build_authored_item("consumable.potion_true_seeing", actor.uuid), None),))
            setup_standard_actions(actor)
            for spell in (Invisibility, GreaterInvisibility, SeeInvisibility, TrueSeeing, FireBolt):
                register_spell(actor, spell, caster_level=1)
            actor.compose_entity()
            actors[role] = actor
        for actor in actors.values():
            game.deploy_entity(actor, actor.position)
        perceiver, subject = actors["perceiver"], actors["subject"]
        encounter = Encounter(name="Paired concealment experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def turn(actor: Entity, *, fresh: bool = False) -> None:
            if fresh:
                encounter.next_turn()
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()

        def perform(
            actor: Entity, behavior: str, *, target: Entity | None = None,
            destination: tuple[int, int] | None = None, weapon_slot: WeaponSlot | None = None,
        ) -> Event:
            turn(actor)
            for attempt in range(2):
                available = get_available_actions(actor)
                options = [(row, option) for row in available.all_actions if row.behavior_id == behavior
                           and (weapon_slot is None or row.weapon_slot == weapon_slot.value)
                           for option in row.valid_targets
                           if (destination is None or option.position == destination)
                           and (target is None or option.target_uuid == target.uuid)]
                if options:
                    break
                if attempt == 0:
                    turn(actor, fresh=True)
            if not options:
                raise ValueError(f"{actor.name} has no discovered {behavior} to {destination or (target.name if target else 'self')}")
            row, option = options[0]
            actions_before = actor.action_economy.actions.normalized_score
            bonus_before = actor.action_economy.bonus_actions.normalized_score
            result = execute_by_index(actor, row.template_name, option.index, available=available)
            assert result is not None and result.phase in (EventPhase.COMPLETION, EventPhase.CANCEL)
            assert not result.canceled, (behavior, result.status_message)
            if behavior == "action.hide":
                assert actor.action_economy.actions.normalized_score == actions_before - 1
            if behavior == "action.item.potion_true_seeing.drink":
                assert actor.action_economy.bonus_actions.normalized_score == bonus_before - 1
            return result

        def grant_sight() -> None:
            if program == "see-invisibility":
                perform(perceiver, "spell.see_invisibility")
            elif sight_grant == "spell":
                perform(perceiver, "spell.true_seeing", target=perceiver)
            elif sight_grant == "potion":
                perform(perceiver, "action.item.potion_true_seeing.drink")

        def reveal_subject() -> None:
            if reveal == "drop-concentration":
                perform(subject, "action.drop_concentration")
            elif reveal == "attack":
                random.seed(0)
                perform(subject, "action.attack", target=perceiver, weapon_slot=WeaponSlot.RANGED_MAIN)
            elif reveal == "cast":
                random.seed(0)
                perform(subject, "spell.fire_bolt", target=perceiver)

        baseline_cursor = EventQueue.event_cursor()
        startup = capture_interval(name="concealment initialization", start_cursor=0, end_cursor=baseline_cursor,
            observer_uuid=perceiver.uuid, battlefield_id=battlefield_id, door_uuid=built.object_uuids.get("door"))
        before, _ = reduce_interval(None, startup)
        if program == "sight-expiry":
            perform(subject, "spell.invisibility", target=subject)
            assert subject.uuid not in perceiver.senses.entities
            grant_sight()
            assert subject.uuid in perceiver.senses.entities
            perform(subject, "action.move", destination=(9, 3))
            # Real turns advance the spell's existing ten-round duration.
            for _ in range(24):
                if "True Seeing" not in perceiver.active_conditions:
                    break
                encounter.next_turn()
            assert "True Seeing" not in perceiver.active_conditions
            assert subject.uuid not in perceiver.senses.entities
            assert subject.is_invisible
        elif program in ("invisibility", "greater-invisibility", "see-invisibility", "doorway"):
            grant_sight()
            perform(subject, "spell.greater_invisibility" if program == "greater-invisibility"
                    else "spell.invisibility", target=subject)
            assert subject.is_invisible
            if program == "doorway":
                perform(subject, "action.move", destination=(8, 4))
                perform(subject, "action.move", destination=(8, 10))
            else:
                perform(subject, "action.move", destination=(9, 3))
                if program == "greater-invisibility":
                    # Advantage attack, weapon damage, then the existing
                    # Greater Invisibility persistence check (DC 15).
                    with fixed_dice_faces(15, 14, 4, 15):
                        perform(subject, "action.attack", target=perceiver, weapon_slot=WeaponSlot.RANGED_MAIN)
                    assert subject.is_invisible
                reveal_subject()
                if reveal != "none":
                    assert not subject.is_invisible
        else:
            grant_sight()
            if program == "stacked":
                perform(subject, "spell.invisibility", target=subject)
                turn(subject, fresh=True)
            blocked = program == "hide-bright" and not allied
            if blocked:
                turn(subject)
                actions_before = subject.action_economy.actions.normalized_score
                available = get_available_actions(subject)
                assert not any(row.behavior_id == "action.hide" and row.valid_targets for row in available.all_actions)
                assert "Hidden" not in subject.active_conditions
                assert subject.action_economy.actions.normalized_score == actions_before
            else:
                with fixed_dice_faces(stealth_face):
                    perform(subject, "action.hide")
                condition = subject.active_conditions.get("Hidden")
                assert isinstance(condition, Hidden)
                assert condition.stealth_result == stealth_face
                if program in ("hide-dim", "stacked"):
                    perform(subject, "action.move", destination=(9, 3))
                reveal_subject()
                if reveal in ("attack", "cast"):
                    assert "Hidden" not in subject.active_conditions
                    assert not subject.is_invisible
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline_cursor) for role, actor in actors.items()))
        primary = captured.views["perceiver"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
