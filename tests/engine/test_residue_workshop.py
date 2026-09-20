"""The selectable workshop composes real bodies, hazards and controls."""

from dnd.actions_functional import execute_by_index, get_available_actions
from dnd.core.creature_types import DamageType
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.encounter_assembler import assemble_encounter_recipe
from dnd.scenarios.encounter_catalog import encounter_recipe


def test_selected_residue_workshop_has_native_bodies_and_usable_trap_lever() -> None:
    reset_engine_runtime()
    game = Game()
    try:
        assembled = assemble_encounter_recipe(encounter_recipe("encounter.residue_workshop"), game=game)
        hero = assembled.entities_by_member_address[("heroes", "fighter")]
        assert hero.equipment.get_all_equipped_items()
        lever_uuid = assembled.battlefield.object_uuids["lever"]
        available = get_available_actions(hero)
        action, target = next(
            (action, target) for action in available.all_actions
            if action.source_item_uuid == lever_uuid
            for target in action.valid_targets
        )
        assert get_map().is_position_hazardous_for(5, 1, hero.uuid)
        result = execute_by_index(hero, action.template_name, target.index, available=available)
        assert result is not None and not result.canceled
        assert not get_map().is_position_hazardous_for(5, 1, hero.uuid)
        assert get_map().is_position_hazardous_for(7, 1, hero.uuid)

        cursor = EventQueue.event_cursor()
        expected = {hero.uuid: "body.blood"}
        for member, release in (("warrior", "body.bone"), ("archer", "body.bone"),
                                ("corrosive", "body.corrosive_blood"), ("dread", "body.dread_blood")):
            creature = assembled.entities_by_member_address[("foes", member)]
            expected[creature.uuid] = release
        for creature in assembled.entities:
            creature.receive_damage(1, DamageType.PIERCING, hero.uuid)
        assert {
            event.target_entity_uuid: event.body_release.release_id
            for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
            and event.body_release is not None
        } == expected
    finally:
        game.close()
        reset_engine_runtime()
