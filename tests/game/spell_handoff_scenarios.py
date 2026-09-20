"""Real discovered spell actions, recorded once for both review perspectives."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import build_directional_door, build_directional_wall
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.conjuration import AcidSplash
from dnd.spells.evocation import EldritchBlast, Fireball, GuidingBolt
from dnd.types.world import CardinalDirection
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


HandoffProgram = Literal["eldritch", "guiding", "acid", "fireball"]
HandoffEnvironment = Literal["open", "wall-east", "wall-north", "closed-door", "open-door"]


def spell_handoff_history(
    *, program: HandoffProgram = "eldritch", level: Literal[5, 11] = 5,
    split: bool = False, miss: bool = False,
    environment: HandoffEnvironment = "open", empty: bool = False, repeat: bool = False,
) -> CapturedHistory:
    """Run actual spell/weapon choices and retain complete native lineages.

    Level, positions, clothing and slot budgets are fixture inputs. Independent
    dice outcomes, mark consumption, area propagation and Ashen membership all
    come from native mechanics; no replay fact or presentation cue is authored.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    battlefield_id = "battlefield.open_floor_bright"
    build_battlefield(battlefield_id)
    game = Game()
    try:
        north = environment == "wall-north"
        if environment != "open":
            direction = CardinalDirection.NORTH if north else CardinalDirection.EAST
            for offset in range(15):
                position = (offset, 7) if north else (7, offset)
                if environment in ("closed-door", "open-door") and offset == 6:
                    barrier = build_directional_door(
                        is_open=environment == "open-door")
                else:
                    barrier = build_directional_wall()
                barrier.place_on_grid(position, boundary_direction=direction)
        if environment != "open":
            placements = {"caster": (2, 6), "perceiver": (3, 5), "first": (6, 5), "second": (8, 6)}
            center = (6, 6)
            if north:
                placements = {role: (y, x) for role, (x, y) in placements.items()}
        else:
            placements = {"caster": (3, 3), "perceiver": (3, 5), "first": (7, 3), "second": (7, 4)}
            center = (7, 3)
        if empty:
            placements = {role: position for role, position in placements.items() if role in ("caster", "perceiver")}
            center = (10, 10)
        spell = {"eldritch": EldritchBlast, "guiding": GuidingBolt, "acid": AcidSplash, "fireball": Fireball}[program]
        actors: dict[str, Entity] = {}
        for role, position in placements.items():
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role in ("caster", "perceiver") else "enemies",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18),
                    charisma=AbilityConfig(ability_score=18), dexterity=AbilityConfig(ability_score=10)),
                action_economy=ActionEconomyConfig(spell_slots={1: 2, 3: 2}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=20, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
                (build_authored_item("weapon.shortbow", actor.uuid), WeaponSlot.RANGED_MAIN),
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
            ))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, spell, caster_level=level)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, perceiver = actors["caster"], actors["perceiver"]
        encounter = Encounter(name="Handed-off spell mechanics", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(*([10] * len(actors))):
            encounter.start_encounter()
        encounter.start_turn()
        while encounter.get_current_entity() is not caster:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Handed-off spell initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield_id)
        before, _ = reduce_interval(None, initial)

        def perform(actor: Entity, behavior: str, *, recipient: Entity | None = None,
                    position: tuple[int, int] | None = None, extras: tuple[Entity, ...] = (),
                    dice: tuple[int, ...], ranged: bool = False, fresh: bool = False) -> Event:
            if fresh:
                encounter.next_turn()
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            available = get_available_actions(actor)
            options = [(action, target) for action in available.all_actions
                if action.behavior_id == behavior and (not ranged or action.weapon_slot == WeaponSlot.RANGED_MAIN.value)
                for target in action.valid_targets if (recipient is None or target.target_uuid == recipient.uuid)
                and (position is None or target.position == position)]
            if not options:
                raise ValueError(f"No discovered {behavior} for {actor.name} toward {position or (recipient.name if recipient else 'self')}")
            action, target = options[0]
            with fixed_dice_faces(*dice):
                event = execute_available_action(actor, action, target,
                    extra_target_uuids=[str(other.uuid) for other in extras])
            assert event is not None and not event.canceled, (behavior, event)
            return event

        if program == "eldritch":
            count = 2 if level == 5 else 3
            recipients = tuple(actors["second"] if split and index % 2 else actors["first"] for index in range(count))
            dice = tuple(face for index in range(count) for face in ((1,) if miss and index == 1 else (15, 4)))
            perform(caster, "spell.eldritch_blast", recipient=recipients[0], extras=recipients[1:], dice=dice)
        elif program == "guiding":
            perform(caster, "spell.guiding_bolt", recipient=actors["first"],
                dice=(1,) if miss else (15, 3, 3, 3, 3))
            if not miss:
                assert "Guiding Bolt" in actors["first"].active_conditions
                perform(perceiver, "action.attack", recipient=actors["first"], ranged=True, dice=(15, 12, 4))
                assert "Guiding Bolt" not in actors["first"].active_conditions
        elif program == "acid":
            perform(caster, "spell.acid_splash", recipient=actors["first"], extras=(actors["second"],),
                dice=(1, *((3,) * (2 if level == 5 else 3)), 20))
        else:
            for index in range(2 if repeat else 1):
                result = perform(caster, "spell.fireball", position=center,
                    dice=tuple([1, *([2] * 8), 20, *([2] * 8)] * len(actors)), fresh=index > 0)
                assert isinstance(result, SpellEvent) and result.resolved_area_positions is not None
                if empty:
                    assert result.total_targets == 0
        history = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "perceiver")))
        primary = history.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, history.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
