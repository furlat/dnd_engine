"""Native Holds, saves, quiet sustain, source clear and independent paralysis."""

import random
from typing import Literal
from uuid import uuid4

from dnd.actions_functional import execute_available_action, get_available_actions, register_spell, setup_standard_actions
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.blocks.spellcasting import SpellcastingConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart
from dnd.core.events import EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spells.enchantment import HoldPerson, HoldMonster
from dnd.spells.transmutation import EnlargeReduceEffect
from dnd.conditions import Paralyzed
from dnd.player.capture import capture_interval, reduce_interval
from dnd.player.recorded import CapturedHistory, ObserverCapture, capture_history


def hold_history(*, program: Literal['hold_person', 'hold_monster'], saved: bool = False,
                 retain_paralysis: bool = False,
                 size_change: Literal['enlarge', 'reduce'] | None = None) -> CapturedHistory:
    random_state = random.getstate()
    reset_engine_runtime()
    battlefield = "battlefield.open_floor_bright"
    build_battlefield(battlefield)
    game = Game()
    try:
        actors = {}
        for role, position in (("caster", (3, 6)), ("recipient", (5, 6)),
                               ("second", (6, 7)), ("bystander", (7, 8))):
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(position=position,
                faction="heroes" if role == "caster" else "monsters",
                ability_scores=AbilityScoresConfig(intelligence=AbilityConfig(ability_score=18)),
                action_economy=ActionEconomyConfig(spell_slots={2: 3, 5: 3}),
                spellcasting=SpellcastingConfig(spellcasting_ability="intelligence"),
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10,
                    hit_dice_count=12, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "caster" else "Head22")))
            actor.install_initial_items(((build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET)))
            setup_standard_actions(actor)
            if role == "caster":
                register_spell(actor, HoldPerson if program == 'hold_person' else HoldMonster, caster_level=17)
            actor.compose_entity()
            game.deploy_entity(actor, position)
            actors[role] = actor
        caster, recipient = actors["caster"], actors["recipient"]
        encounter = Encounter(name="Holds native lifecycle", source_entity_uuid=caster.uuid)
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        with fixed_dice_faces(10, 10, 10, 10):
            encounter.start_encounter()
        encounter.start_turn()
        if size_change is not None:
            event = recipient.add_condition(EnlargeReduceEffect(source_entity_uuid=caster.uuid,
                target_entity_uuid=recipient.uuid, mode=size_change))
            assert event is not None and not event.canceled
            assert "Enlarge/Reduce" in recipient.active_conditions

        def perform(actor: Entity, behavior: str, destination: tuple[int, int]) -> None:
            while encounter.get_current_entity() is not actor:
                with fixed_dice_faces(*([1] * 40)):
                    encounter.next_turn()
            choices = [(action, selection) for action in get_available_actions(actor).all_actions
                if action.behavior_id == behavior for selection in action.valid_targets
                if selection.position == destination]
            assert choices, (behavior, destination)
            with fixed_dice_faces(*([20 if saved and behavior == "spell." + program else 1] * 40)):
                result = execute_available_action(actor, *choices[0])
            assert result is not None and not result.canceled and result.phase is EventPhase.COMPLETION

        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="Holds initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=caster.uuid, battlefield_id=battlefield)
        before, _ = reduce_interval(None, initial)
        perform(caster, 'spell.' + program, recipient.position)
        title = 'Hold Person' if program == 'hold_person' else 'Hold Monster'
        assert (title in recipient.active_conditions) is not saved
        assert ('Paralyzed' in recipient.active_conditions) is not saved
        assert title not in actors['second'].active_conditions
        if not saved:
            assert not any(action.valid_targets for action in get_available_actions(recipient).all_actions)
        perform(caster, 'action.move', (3, 7))
        if not saved:
            if retain_paralysis:
                # Actual native replacement leaves the independent source active;
                # clearing the older Hold tree must not remove this newer UUID.
                event = recipient.add_condition(Paralyzed(source_entity_uuid=actors['second'].uuid,
                    target_entity_uuid=recipient.uuid))
                assert event is not None and not event.canceled
            caster.remove_condition('Concentrating')
            assert title not in recipient.active_conditions
            assert ('Paralyzed' in recipient.active_conditions) is retain_paralysis
            if not retain_paralysis:
                perform(recipient, 'action.move', (5, 8))
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actors[role].uuid, baseline) for role in ("caster", "recipient")))
        primary = captured.views["caster"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(random_state)
