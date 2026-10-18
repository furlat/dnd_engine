"""Real class inputs and captured book state through worker discovery/commands."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.content.characters.builds import create_character
from dnd.content.items.item_loadouts import ItemLoadoutEntry
from dnd.characters.mastery import SpellMasteryStudy
from dnd.player.commands import CommandRejected
from dnd.content.characters.spellcasting_grants import change_prepared_spells
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.items.spell_items import build_fireball_scroll
from dnd.player.commands import ActionSelection
from dnd.player.facts import PlayerState
from dnd.player.session import close_session
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.character_progression import CharacterClass, PreparedSpellSelection
from server.protocol import (
    CommandRequest,
    ExecuteSelectionIntent,
    PlayerOperation,
    PreviewRequest,
    ChoicesRequest,
    PrepareSpellsIntent,
    StudySpellMasteryIntent,
)
import server.worker as native_worker
from server.worker import needs_advance
from server.worker_protocol import Start, Advance, Command, Preview, Choices
from tests.player.test_compact_choices import request_choices, rows
from tests.player.test_hud_operation_oracle import deliver as oracle_deliver
from tests.progression.prepared_class_support import prepared_build, prepared_level


# The current runtime's seats, as their clients fold every record the worker delivered (each fold
# checked against the live engine by the op-end oracle). One runtime lives at a time.
CLIENTS: dict[int, dict[str, PlayerState]] = {}


def deliver(runtime, records):
    oracle_deliver(runtime, CLIENTS.setdefault(id(runtime), {}), records)


def start(request):
    runtime, reply, records = native_worker.start(request)
    CLIENTS.clear()
    deliver(runtime, records)
    return runtime, reply, records


def dispatch(runtime, request):
    reply, records, response = native_worker.dispatch(runtime, request)
    deliver(runtime, records)
    return reply, records, response


def seat_sheet(runtime, seat, actor_uuid):
    """The sheet in the seat's display: the client fold of the delivered records."""
    return next(row for row in CLIENTS[id(runtime)][seat].hud_snapshot.sheets if row.actor_uuid == actor_uuid)


def worker(build):
    runtime, _, _ = start(
        Start(
            game_id="prepared-caster-proof",
            game_epoch=uuid4(),
            audience_ids={"party": uuid4()},
            encounter_id=None,
            recipe=None,
            assignments=None,
            test_seed=6,
            player_builds=(build,),
        )
    )
    for _ in range(30):
        if not needs_advance(runtime.session):
            break
        dispatch(runtime, Advance())
    seat, publication = next(
        (key, value)
        for key, value in runtime.publications.items()
        if value.boundary.input_actor_uuid is not None
    )
    return runtime, seat, publication


def test_captured_scroll_learning_and_preparation_rebuild_then_real_worker_fireball():
    reset_engine_runtime(grid_size=(8, 8))
    build = prepared_build(CharacterClass.WIZARD, 5)
    actor = create_character(build)
    scroll = build_fireball_scroll(actor.uuid)
    actor.inventory.add_item(scroll)
    result = scroll.get_use_actions(actor.uuid)[1].instantiate().apply()
    assert result is not None and not result.canceled
    change_prepared_spells(
        actor, PreparedSpellSelection("class.wizard.spellcasting", ("spell.fireball",))
    )
    captured = replace(
        build,
        scribed_spell_ids=actor.scribed_spell_ids,
        prepared_spells=actor.prepared_spell_selections,
    )
    world = worker(captured)
    runtime, seat, publication = world
    try:
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        choices = request_choices(world).choices
        row = next(
            row
            for row in rows(choices)
            if row.behavior_id == "spell.fireball"
            and row.cast_at_level == 3
            and row.can_afford
        )
        assert (
            row.spellcasting_provider_id == "class.wizard"
            and row.spellcasting_ability == "intelligence"
        )
        binding = next(
            binding
            for binding in choices.target_sets[row.target_set]
            if choices.positions[binding.position]
            in [
                enemy.position
                for enemy in runtime.session.game.entities.values()
                if actor.is_enemy(enemy)
            ]
        )
        selected = ActionSelection(row.discovery_index, (binding.index,))
        cursor = EventQueue.event_cursor()
        _, _, preview = dispatch(
            runtime,
            Preview(
                seat_id=seat,
                request=PreviewRequest(
                    actor_uuid=actor.uuid,
                    state_revision=publication.state_revision,
                    discovery_generation=choices.discovery_generation,
                    correlation_id=uuid4(),
                    selection=selected,
                ),
            ),
        )
        assert preview.preview.can_confirm and EventQueue.event_cursor() == cursor
        with fixed_dice_faces(*([2] * 100)):
            reply, records, _ = dispatch(
                runtime,
                Command(
                    seat_id=seat,
                    request=CommandRequest(
                        command_number=1,
                        actor_uuid=actor.uuid,
                        state_revision=publication.state_revision,
                        intent=ExecuteSelectionIntent(
                            discovery_generation=choices.discovery_generation,
                            selection=selected,
                        ),
                    ),
                ),
            )
        assert reply.rejection is None and records
        assert actor.action_economy.spell_slot_3.normalized_score == 1
        for record in records:
            if isinstance(record, PlayerOperation):
                detached = PlayerOperation.model_validate_json(record.model_dump_json())
                assert detached == record
        sheet = seat_sheet(runtime, seat, actor.uuid)
        assert "spell.fireball" in sheet.scribed_spell_ids
        assert sheet.prepared_spell_selections == actor.prepared_spell_selections
    finally:
        close_session(runtime.session)


@pytest.mark.parametrize("source,expected", [("class.cleric", 7), ("class.paladin", 6)])
def test_worker_duplicate_cure_wounds_uses_selected_wisdom_or_charisma_source(
    source, expected
):
    build = prepared_build(CharacterClass.CLERIC)
    levels = build.class_levels
    for _ in range(2):
        levels = (*levels, prepared_level(CharacterClass.PALADIN, levels))
    build = replace(
        build,
        class_levels=levels,
        prepared_spells=(
            PreparedSpellSelection(
                "class.paladin.spellcasting", ("spell.cure_wounds",)
            ),
        ),
    )
    world = worker(build)
    runtime, seat, publication = world
    try:
        actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
        actor.receive_damage(15, DamageType.FORCE, actor.uuid)
        before = actor.get_hp()
        choices = request_choices(world).choices
        cures = [
            row
            for row in rows(choices)
            if row.behavior_id == "spell.cure_wounds" and row.cast_at_level == 1
        ]
        assert {row.spellcasting_provider_id for row in cures} == {
            "class.cleric",
            "class.paladin",
        }
        row = next(row for row in cures if row.spellcasting_provider_id == source)
        binding = next(
            binding
            for binding in choices.target_sets[row.target_set]
            if binding.kind == "self"
            or binding.kind == "subject"
            and choices.subjects[binding.subject].uuid == actor.uuid
        )
        with fixed_dice_faces(2):
            reply, records, _ = dispatch(
                runtime,
                Command(
                    seat_id=seat,
                    request=CommandRequest(
                        command_number=1,
                        actor_uuid=actor.uuid,
                        state_revision=publication.state_revision,
                        intent=ExecuteSelectionIntent(
                            discovery_generation=choices.discovery_generation,
                            selection=ActionSelection(
                                row.discovery_index, (binding.index,)
                            ),
                        ),
                    ),
                ),
            )
        assert reply.rejection is None and records
        assert actor.get_hp() == before + expected
    finally:
        close_session(runtime.session)


def test_worker_item_cast_and_learn_are_distinct_and_captured_book_rebuilds():
    build = replace(
        prepared_build(CharacterClass.WIZARD, 5),
        item_loadout=(
            ItemLoadoutEntry("spell_item.scroll_fireball"),
            ItemLoadoutEntry("spell_item.scroll_magic_missile"),
        ),
    )
    runtime, seat, publication = worker(build)
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    try:
        choices = request_choices((runtime, seat, publication)).choices
        learn = next(
            row
            for row in rows(choices)
            if row.behavior_id == "action.wizard.learn_scroll"
        )
        fireball = next(
            row
            for row in rows(choices)
            if row.behavior_id == "spell.fireball" and row.source_item_uuid is not None
        )
        assert learn.source_item_uuid == fireball.source_item_uuid
        cursor = EventQueue.event_cursor()
        selection = ActionSelection(
            learn.discovery_index, (choices.target_sets[learn.target_set][0].index,)
        )
        _, _, preview = dispatch(
            runtime,
            Preview(
                seat_id=seat,
                request=PreviewRequest(
                    actor_uuid=actor.uuid,
                    state_revision=publication.state_revision,
                    discovery_generation=choices.discovery_generation,
                    correlation_id=uuid4(),
                    selection=selection,
                ),
            ),
        )
        assert preview.preview.can_confirm and EventQueue.event_cursor() == cursor
        reply, records, _ = dispatch(
            runtime,
            Command(
                seat_id=seat,
                request=CommandRequest(
                    command_number=1,
                    actor_uuid=actor.uuid,
                    state_revision=publication.state_revision,
                    intent=ExecuteSelectionIntent(
                        discovery_generation=choices.discovery_generation,
                        selection=selection,
                    ),
                ),
            ),
        )
        assert reply.rejection is None
        packet = next(
            record for record in records if isinstance(record, PlayerOperation)
        )
        assert PlayerOperation.model_validate_json(packet.model_dump_json()) == packet
        sheet = seat_sheet(runtime, seat, actor.uuid)
        assert "spell.fireball" in sheet.scribed_spell_ids
        assert learn.source_item_uuid not in actor.inventory.items
        rebuilt = create_character(
            replace(
                build,
                item_loadout=(),
                scribed_spell_ids=sheet.scribed_spell_ids,
                class_levels=sheet.class_levels,
                prepared_spells=sheet.prepared_spell_selections,
            )
        )
        assert rebuilt.scribed_spell_ids == actor.scribed_spell_ids
        publication = runtime.publications[seat]
        choices = request_choices((runtime, seat, publication)).choices
        cast_row = next(
            row
            for row in rows(choices)
            if row.behavior_id == "spell.magic_missile"
            and row.source_item_uuid is not None
        )
        target = next(
            binding
            for binding in choices.target_sets[cast_row.target_set]
            if binding.kind == "subject"
            and actor.is_enemy(
                runtime.session.game.entities[choices.subjects[binding.subject].uuid]
            )
        )
        slots = actor.action_economy.spell_slot_1.normalized_score
        with fixed_dice_faces(*([2] * 20)):
            reply, _, _ = dispatch(
                runtime,
                Command(
                    seat_id=seat,
                    request=CommandRequest(
                        command_number=2,
                        actor_uuid=actor.uuid,
                        state_revision=publication.state_revision,
                        intent=ExecuteSelectionIntent(
                            discovery_generation=choices.discovery_generation,
                            selection=ActionSelection(
                                cast_row.discovery_index, (target.index,)
                            ),
                        ),
                    ),
                ),
            )
        assert (
            reply.rejection is None
            and actor.action_economy.spell_slot_1.normalized_score == slots
        )
        assert cast_row.source_item_uuid not in actor.inventory.items
    finally:
        close_session(runtime.session)


def test_worker_outside_combat_recovery_ritual_preparation_and_mastery_study():
    build = replace(
        prepared_build(CharacterClass.WIZARD, 18),
        scribed_spell_ids=("spell.shield", "spell.mirror_image", "spell.longstrider"),
    )
    runtime, seat, publication = worker(build)
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    try:
        actor.action_economy.consume("actions", 1)
        actor.action_economy.consume("spell_slot_1", 1)
        runtime.session.encounter.end_encounter()
        turn_actions = actor.action_economy.actions.normalized_score
        assert turn_actions == 1

        def choices_for_actor():
            _, _, response = dispatch(
                runtime,
                Choices(
                    seat_id=seat,
                    request=ChoicesRequest(
                        actor_uuid=actor.uuid,
                        state_revision=runtime.publications[seat].state_revision,
                        force_attack=False,
                        correlation_id=uuid4(),
                    ),
                ),
            )
            return response.choices

        choices = choices_for_actor()
        recovery = next(
            row
            for row in rows(choices)
            if row.behavior_id == "action.class.wizard.arcane_recovery"
            and row.can_afford
            and "Level 1" in row.display_name
        )
        selection = ActionSelection(
            recovery.discovery_index,
            (choices.target_sets[recovery.target_set][0].index,),
        )
        reply, _, _ = dispatch(
            runtime,
            Command(
                seat_id=seat,
                request=CommandRequest(
                    command_number=1,
                    actor_uuid=actor.uuid,
                    state_revision=runtime.publications[seat].state_revision,
                    intent=ExecuteSelectionIntent(
                        discovery_generation=choices.discovery_generation,
                        selection=selection,
                    ),
                ),
            ),
        )
        assert (
            reply.rejection is None
            and actor.action_economy.spell_slot_1.normalized_score == 4
        )
        old = runtime.publications[seat].state_revision
        intent = PrepareSpellsIntent(
            selection=PreparedSpellSelection(
                "class.wizard.spellcasting", ("spell.longstrider",)
            )
        )
        dispatch(
            runtime,
            Command(
                seat_id=seat,
                request=CommandRequest(
                    command_number=2,
                    actor_uuid=actor.uuid,
                    state_revision=old,
                    intent=intent,
                ),
            ),
        )
        with pytest.raises(CommandRejected):
            dispatch(
                runtime,
                Command(
                    seat_id=seat,
                    request=CommandRequest(
                        command_number=3,
                        actor_uuid=actor.uuid,
                        state_revision=old,
                        intent=intent,
                    ),
                ),
            )
        choices = choices_for_actor()
        ritual = next(
            row
            for row in rows(choices)
            if row.behavior_id == "spell.longstrider"
            and row.can_afford
            and not any(
                cost.cost_type.startswith("spell_slot_") and cost.cost
                for cost in row.costs
            )
        )
        own = next(
            binding
            for binding in choices.target_sets[ritual.target_set]
            if binding.kind == "self"
            or binding.kind == "subject"
            and choices.subjects[binding.subject].uuid == actor.uuid
        )
        slots = actor.action_economy.spell_slot_1.normalized_score
        dispatch(
            runtime,
            Command(
                seat_id=seat,
                request=CommandRequest(
                    command_number=4,
                    actor_uuid=actor.uuid,
                    state_revision=runtime.publications[seat].state_revision,
                    intent=ExecuteSelectionIntent(
                        discovery_generation=choices.discovery_generation,
                        selection=ActionSelection(ritual.discovery_index, (own.index,)),
                    ),
                ),
            ),
        )
        assert actor.action_economy.spell_slot_1.normalized_score == slots
        intent = StudySpellMasteryIntent(
            selection=SpellMasteryStudy("spell.shield", "spell.mirror_image")
        )
        _, records, _ = dispatch(
            runtime,
            Command(
                seat_id=seat,
                request=CommandRequest(
                    command_number=5,
                    actor_uuid=actor.uuid,
                    state_revision=runtime.publications[seat].state_revision,
                    intent=intent,
                ),
            ),
        )
        packet = next(
            record for record in records if isinstance(record, PlayerOperation)
        )
        assert PlayerOperation.model_validate_json(packet.model_dump_json()) == packet
        sheet = seat_sheet(runtime, seat, actor.uuid)
        rebuilt = create_character(
            replace(
                build,
                class_levels=sheet.class_levels,
                scribed_spell_ids=sheet.scribed_spell_ids,
                prepared_spells=sheet.prepared_spell_selections,
            )
        )
        assert {
            grant.spell_id
            for grant in rebuilt.spellcasting.free_cast_grants.values()
            if grant.provider_id == "class_feature.wizard.spell_mastery"
        } == {"spell.shield", "spell.mirror_image"}
    finally:
        close_session(runtime.session)
