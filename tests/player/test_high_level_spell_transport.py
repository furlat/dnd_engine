"""High-level action shapes through real worker choices, preview and commands."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import register_spell
from dnd.conditions import Charmed, Prone
from dnd.core.content.registration import get_content_declaration
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue
from dnd.core.geometry import grid_distance_feet
from dnd.core.gridmap import get_map
from dnd.player.commands import ActionSelection, ToggleHandler
from dnd.player.reduction import reduce_operation
from dnd.reactions import add_stand_when_healed_handler
from dnd.spells.abjuration import DispelEvilAndGood
from dnd.spells.enchantment import CharmMonster
from dnd.spells.evocation import (
    ArcaneSword,
    DelayedBlastFireball,
    FreezingSphere,
    PowerWordHeal,
)
from dnd.spells.summoning import ConjureElemental, PlanarAlly, SummonDragon
from dnd.spells.wall_constructions import Forcecage
from server.protocol import (
    CommandRequest,
    ExecuteSelectionIntent,
    PlayerOperation,
    PreviewRequest,
    ToggleHandlerIntent,
)
from server.worker import dispatch
from server.worker_protocol import Command, Preview
from tests.engine.test_high_level_spell_controls import high_actor
from tests.player.test_compact_choices import request_choices, rows, world


@pytest.mark.parametrize(
    "spell,facets",
    [
        (CharmMonster, ()),
        (DispelEvilAndGood, ()),
        (ArcaneSword, ()),
        (FreezingSphere, (("form", "launch"),)),
        (FreezingSphere, (("form", "portable"),)),
        (DelayedBlastFireball, ()),
        (Forcecage, (("form", "cage"),)),
        (Forcecage, (("form", "box"),)),
        (ConjureElemental, (("form", "earth_myrmidon"),)),
        (PlanarAlly, (("form", "deva"),)),
        (SummonDragon, (("damage_type", "Cold"), ("resistance", "Poison"))),
    ],
)
def test_high_level_shape_discover_preview_submit_without_preview_side_effects(
    world, spell, facets
):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    actor.action_economy.set_normal_spell_slot_capacity(
        uuid4(), {rank: 3 for rank in range(1, 10)}
    )
    actor.action_economy.reset_spell_slot_costs()
    if spell is DispelEvilAndGood:
        point = next(
            position
            for position in actor.senses.visible
            if grid_distance_feet(actor.position, position) <= 10
            and get_map().is_walkable_for(*position, requesting_entity_uuid=actor.uuid)
            and not get_map().get_entities_at(position)
        )
        fiend = high_actor(
            runtime.session.game,
            "Charm source",
            point,
            "fiends",
            creature_type=CreatureType.FIEND,
        )
        effect = actor.add_condition(
            Charmed(
                source_entity_uuid=fiend.uuid,
                target_entity_uuid=actor.uuid,
                source_creature_type=CreatureType.FIEND,
            )
        )
        assert effect is not None and not effect.canceled
    register_spell(actor, spell, caster_level=17)
    choices = request_choices(world).choices
    # Stable identity comes from the authored declaration, never Python naming.
    behavior = get_content_declaration(spell).ref.content_id
    candidates = [
        row
        for row in rows(choices)
        if row.behavior_id == behavior
        and row.can_afford
        and (spell is not CharmMonster or 5 in row.cast_levels)
        and choices.target_sets[row.target_set]
        and all(
            any(
                facet.key == key and facet.value == value
                for facet in row.variant_facets
            )
            for key, value in facets
        )
    ]
    assert candidates, (
        behavior,
        [
            (
                row.template_name,
                row.can_afford,
                len(choices.target_sets[row.target_set]),
            )
            for row in rows(choices)
            if row.behavior_id == behavior
        ],
    )
    row = candidates[0]
    bindings = choices.target_sets[row.target_set]
    cursor = EventQueue.event_cursor()
    births = set(runtime.session.game.entities)
    # Charm Monster is cast at level 5 (two targets): the selection names the level (plan D17).
    level = 5 if spell is CharmMonster else row.cast_at_level
    costs = (
        actor.action_economy.actions.normalized_score,
        actor.action_economy.spell_slot_value(level).normalized_score,
    )
    selected = None
    for binding in bindings:
        selection = ActionSelection(
            action_index=row.discovery_index,
            cast_at_level=level if level != row.cast_at_level else None,
            target_indices=(
                binding.index,
                next(other.index for other in bindings if other.index != binding.index),
            )
            if spell is CharmMonster
            else (binding.index,),
        )
        _, _, response = dispatch(
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
        if response.preview.next_positions:
            destination = response.preview.positions[response.preview.next_positions[0]]
            selection = replace(selection, extra_target_positions=(destination,))
            _, _, response = dispatch(
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
        if response.preview.can_confirm:
            selected = selection
            break
    assert selected is not None, behavior
    assert (
        EventQueue.event_cursor() == cursor
        and set(runtime.session.game.entities) == births
    )
    assert costs == (
        actor.action_economy.actions.normalized_score,
        actor.action_economy.spell_slot_value(level).normalized_score,
    )
    before_public = deepcopy(runtime.audiences[seat].latest)
    with fixed_dice_faces(15, *([2] * 400)):
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
    assert reply.rejection is None and records, behavior
    assert actor.action_economy.actions.normalized_score == costs[0] - 1, (
        costs,
        actor.action_economy.actions.normalized_score,
        [
            (event.phase, event.canceled, event.status_message)
            for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpellEvent) and event.behavior_id == behavior
        ],
    )

    if spell is SummonDragon:
        actor_ids = set(runtime.session.game.entities)
        native_cursor = EventQueue.event_cursor()
        dragon = next(
            entity
            for entity in runtime.session.game.entities.values()
            if entity.name == "Draconic Spirit"
        )
        record = next(
            record
            for record in records
            if record.cursor.audience_id
            == runtime.publications[seat].cursor.audience_id
        )
        detached = PlayerOperation.model_validate_json(record.model_dump_json())
        replayed = reduce_operation(before_public, detached)
        assert replayed == replace(
            runtime.audiences[seat].latest,
            combat_log_appends=before_public.combat_log_appends
            + detached.combat_log_appends,
        )
        assert dragon.uuid in replayed.actors
        assert (
            set(runtime.session.game.entities) == actor_ids
            and EventQueue.event_cursor() == native_cursor
        )

    followup = (
        "action.spell.arcane_sword.strike"
        if spell is ArcaneSword
        else "action.spell.payload.throw"
        if spell is FreezingSphere and ("form", "portable") in facets
        else "action.spell.dispel_evil_and_good.break_enchantment"
        if spell is DispelEvilAndGood
        else None
    )
    if followup is not None:
        # This boundary case starts the next affordable action with native turn costs recovered.
        actor.action_economy.reset_all_costs()
        publication = runtime.publications[seat]
        choices = request_choices((runtime, seat, publication)).choices
        options = [
            candidate
            for candidate in rows(choices)
            if candidate.behavior_id == followup
            and candidate.can_afford
            and choices.target_sets[candidate.target_set]
        ]
        assert options, followup
        candidate = options[0]
        selection = None
        cursor = EventQueue.event_cursor()
        for binding in choices.target_sets[candidate.target_set]:
            proposed = ActionSelection(
                action_index=candidate.discovery_index, target_indices=(binding.index,)
            )
            _, _, response = dispatch(
                runtime,
                Preview(
                    seat_id=seat,
                    request=PreviewRequest(
                        actor_uuid=actor.uuid,
                        state_revision=publication.state_revision,
                        discovery_generation=choices.discovery_generation,
                        correlation_id=uuid4(),
                        selection=proposed,
                    ),
                ),
            )
            if response.preview.next_positions:
                proposed = replace(
                    proposed,
                    extra_target_positions=(
                        response.preview.positions[response.preview.next_positions[0]],
                    ),
                )
                _, _, response = dispatch(
                    runtime,
                    Preview(
                        seat_id=seat,
                        request=PreviewRequest(
                            actor_uuid=actor.uuid,
                            state_revision=publication.state_revision,
                            discovery_generation=choices.discovery_generation,
                            correlation_id=uuid4(),
                            selection=proposed,
                        ),
                    ),
                )
            if response.preview.can_confirm:
                selection = proposed
                break
        assert selection is not None and EventQueue.event_cursor() == cursor
        with fixed_dice_faces(15, *([2] * 400)):
            reply, records, _ = dispatch(
                runtime,
                Command(
                    seat_id=seat,
                    request=CommandRequest(
                        command_number=2,
                        actor_uuid=actor.uuid,
                        state_revision=publication.state_revision,
                        intent=ExecuteSelectionIntent(
                            discovery_generation=choices.discovery_generation,
                            selection=selection,
                        ),
                    ),
                ),
            )
        assert reply.rejection is None and records, followup
        if spell is ArcaneSword:
            assert actor.action_economy.bonus_actions.normalized_score == 0
        else:
            assert actor.action_economy.actions.normalized_score == 0


def test_power_word_heal_uses_recipient_preference_from_real_toggle_command(world):
    runtime, seat, publication = world
    actor = runtime.session.game.entities[publication.boundary.input_actor_uuid]
    actor.action_economy.set_normal_spell_slot_capacity(uuid4(), {9: 1})
    actor.action_economy.reset_spell_slot_costs()
    register_spell(actor, PowerWordHeal, caster_level=17)
    add_stand_when_healed_handler(actor)
    prone = Prone(source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid)
    prone.suppress_immediate_stand_for_application()
    application = actor.add_condition(prone)
    assert application is not None and not application.canceled, (
        application.status_message if application else "No Prone application"
    )
    assert "Prone" in actor.active_conditions
    handler = next(
        handler
        for handler in actor.event_handlers.values()
        if handler.semantic_key == "reaction.stand_when_healed"
    )
    choices = request_choices(world).choices
    reply, _, _ = dispatch(
        runtime,
        Command(
            seat_id=seat,
            request=CommandRequest(
                command_number=1,
                actor_uuid=actor.uuid,
                state_revision=publication.state_revision,
                intent=ToggleHandlerIntent(
                    discovery_generation=choices.discovery_generation,
                    handler=ToggleHandler(handler_uuid=handler.uuid, enabled=False),
                ),
            ),
        ),
    )
    assert reply.rejection is None
    publication = runtime.publications[seat]
    choices = request_choices((runtime, seat, publication)).choices
    row = next(
        row
        for row in rows(choices)
        if row.behavior_id == "spell.power_word_heal" and row.can_afford
    )
    binding = next(
        binding
        for binding in choices.target_sets[row.target_set]
        if choices.subjects[binding.subject].uuid == actor.uuid
    )
    selection = ActionSelection(
        action_index=row.discovery_index, target_indices=(binding.index,)
    )
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
                    selection=selection,
                ),
            ),
        ),
    )
    assert reply.rejection is None
    assert (
        "Prone" in actor.active_conditions
        and actor.action_economy.reactions.normalized_score == 1
    ), (
        list(actor.active_conditions),
        actor.action_economy.reactions.normalized_score,
        handler.enabled,
    )
