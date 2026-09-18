"""Real environment actions, recorded once from both participants' viewpoints."""

import random
from typing import Literal
from uuid import UUID, uuid4

from dnd.actions_functional import execute_by_index, get_available_actions, setup_standard_actions
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.controller import HumanController
from dnd.core.base_block import BaseBlock
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import BodyPart, WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.items.environment_interactables import TrapLever
from dnd.items.torches import WallTorch
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.types.senses import SenseMode, SensesType
from game.presentation import capture_interval, reduce_interval
from game.replay import CapturedHistory, ObserverCapture, capture_history


def environment_history(
    *, program: Literal["lights", "lever"] = "lights",
    fixture_kind: Literal["standing", "wall"] = "standing",
    observer_darkvision: bool = False, second_light: bool = False,
) -> CapturedHistory:
    """Use native turns/discovery; no animation waits or visibility overrides.

    The fixture tiles have dim ambient light so the operator can find the
    extinguished fixture. Neighboring actor cells are dark. Walking while it
    is off gives playback actual movement to show before the relighting action.
    """
    previous_random = random.getstate()
    reset_engine_runtime()
    built = build_battlefield("battlefield.environment_workshop")
    game = Game()
    try:
        selected = BaseBlock.get(built.object_uuids[f"{fixture_kind}_torch"])
        assert isinstance(selected, WallTorch) and selected.position is not None
        for key in ("standing_torch", "wall_torch", "second_torch"):
            fixture = BaseBlock.get(built.object_uuids[key])
            assert isinstance(fixture, WallTorch)
            if program == "lever" or (
                fixture is not selected and not (key == "second_torch" and second_light)
            ):
                fixture.put_out()
        lever = BaseBlock.get(built.object_uuids["lever"])
        assert isinstance(lever, TrapLever)
        linked_uuid = lever.to_item_presentation_state().linked_spatial_condition_uuid
        assert linked_uuid is not None
        linked = SpikeTrap.get(linked_uuid)
        other = SpikeTrap.get(built.spike_traps[1][0])
        assert isinstance(linked, SpikeTrap) and isinstance(other, SpikeTrap)
        assert linked.applied and other.applied
        x, y = selected.position
        placements = (("operator", (x - 1, y)), ("witness", (x + 2, y)))
        if program == "lever":
            placements = (("operator", (2, 1)), ("witness", (4, 1)))
        actors: dict[str, Entity] = {}
        for role, position in placements:
            actor = Entity.create(uuid4(), role.title(), config=EntityConfig(
                position=position, faction="heroes" if role == "operator" else "enemies",
                health=HealthConfig(hit_dices=[HitDiceConfig(hit_dice_value=10, hit_dice_count=8, mode="maximums")]),
                appearance=AppearanceConfig(body_category="NakedBody", has_beard=False,
                    head_category="Head10" if role == "operator" else "Head22"),
            ))
            actor.install_initial_items((
                (build_authored_item("weapon.shortsword", actor.uuid), WeaponSlot.MELEE_MAIN),
                (build_authored_item("apparel.robes.red_mage", actor.uuid), BodyPart.BODY),
                (build_authored_item("apparel.cloth_shoes.red", actor.uuid), BodyPart.FEET),
            ))
            if role == "operator" or observer_darkvision:
                actor.senses.add_sense_mode_source(actor.uuid,
                    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60))
            setup_standard_actions(actor)
            actor.compose_entity()
            actors[role] = actor
        for actor in actors.values():
            game.deploy_entity(actor, actor.position)
        operator, witness = actors["operator"], actors["witness"]
        encounter = Encounter(name="Paired environment experiment", source_entity_uuid=uuid4())
        for actor in actors.values():
            encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        random.seed(0)
        encounter.start_encounter()
        encounter.start_turn()

        def perform(
            actor: Entity, *, item_uuid: UUID | None = None,
            destination: tuple[int, int] | None = None,
        ) -> Event:
            while encounter.get_current_entity() is not actor:
                encounter.next_turn()
            available = get_available_actions(actor)
            choices = [
                (row, target) for row in available.all_actions
                if (row.source_item_uuid == item_uuid if item_uuid is not None else row.behavior_id == "action.move")
                for target in row.valid_targets
                if destination is None or target.position == destination
            ]
            if not choices:
                raise ValueError(f"{actor.name} has no discovered action for {item_uuid or destination}")
            row, target = choices[0]
            result = execute_by_index(actor, row.template_name, target.index, available=available)
            assert result is not None and result.phase is EventPhase.COMPLETION and not result.canceled
            return result

        first = witness if program == "lever" else operator
        while encounter.get_current_entity() is not first:
            encounter.next_turn()
        baseline = EventQueue.event_cursor()
        initial = capture_interval(name="environment initialization", start_cursor=0, end_cursor=baseline,
            observer_uuid=operator.uuid, battlefield_id=built.definition.battlefield_id)
        before, _ = reduce_interval(None, initial)
        if program == "lights":
            assert selected.is_lit and operator.uuid in witness.senses.entities
            perform(operator, item_uuid=selected.uuid)
            assert not selected.is_lit
            assert (operator.uuid in witness.senses.entities) == (observer_darkvision or second_light)
            perform(operator, destination=(x - 1, y + 1))
            perform(operator, destination=(x - 1, y))
            perform(witness, destination=(x + 3, y))
            perform(witness, destination=(x + 2, y))
            perform(operator, item_uuid=selected.uuid)
            assert selected.is_lit and operator.uuid in witness.senses.entities
        else:
            hp_before = witness.get_hp()
            with fixed_dice_faces(2, 2):
                perform(witness, destination=(5, 1))
            assert witness.get_hp() < hp_before
            perform(witness, destination=(4, 1))
            perform(operator, item_uuid=lever.uuid)
            assert not linked.applied and other.applied and lever.charges == 0
            hp_after = witness.get_hp()
            perform(witness, destination=(5, 1))
            assert witness.get_hp() == hp_after
            with fixed_dice_faces(2, 2):
                perform(witness, destination=(7, 1))
            assert witness.get_hp() < hp_after and other.applied
        captured = capture_history(before, (), observers=tuple(
            ObserverCapture(role, actor.uuid, baseline) for role, actor in actors.items()))
        primary = captured.views["operator"]
        return CapturedHistory(primary.initialization, before, primary.lineages, captured.views)
    finally:
        game.close()
        reset_engine_runtime()
        random.setstate(previous_random)
