"""Op-end oracle: after every operation, each seat's displayed HUD equals a fresh evaluation of the live engine.

Boundary: worker start/dispatch -> the delivered records -> the client's fold (`dnd.player.reduction`).
Input: a skirmish played through AI turns, a handler toggle, an unequip and re-equip, a Dodge and an end
of turn. (The scribe, preparation and mastery flows check the same oracle in test_divine_and_wizard_transport.)
Expected: per seat, the sheets it shows (its sheet fold joined with its bodies' name, portrait and HP) and
the initiative it shows equal the live actors' values and the encounter's order filtered by the seat's live
senses, after the initialization and after every operation.
"""

from uuid import UUID, uuid4

from dnd.actor_sheets import evaluate_actor_sheet
from dnd.core.equipment_types import WeaponSlot
from dnd.player.commands import ActionSelection, EquipItem, ToggleHandler, UnequipItem
from dnd.player.facts import PlayerState, PlayerUpdate
from dnd.player.reduction import displayed_initiative, reduce_initialization, reduce_operation
from dnd.player.session import close_session
from dnd.runtime_reset import reset_engine_runtime
from server import worker
from server.protocol import (ChoicesRequest, CommandRequest, EndTurnIntent, EquipIntent, ExecuteSelectionIntent,
    InitializationResponse, PlayerOperation, ToggleHandlerIntent, UnequipIntent)
from server.worker_protocol import Advance, Choices, Command, Start
from tests.player.test_compact_choices import rows


def deliver(runtime, clients: dict[str, PlayerState], records) -> None:
    """Fold the delivered records into each seat's client state, as its client does; at an operation's (or the
    initialization's) end, check every seat against the live engine."""
    seats = {publication.cursor.audience_id: seat for seat, publication in runtime.publications.items()}
    if not any(isinstance(record, (InitializationResponse, PlayerOperation)) for record in records):
        return
    for record in records:
        if isinstance(record, InitializationResponse):
            clients[seats[record.cursor.audience_id]] = reduce_initialization(record.initialization,
                content_additions=record.content_additions)
        elif isinstance(record, PlayerOperation):
            seat = seats[record.cursor.audience_id]
            clients[seat] = reduce_operation(clients[seat], PlayerUpdate(generation=record.generation, observer_uuid=record.observer_uuid,
                lineages=record.lineages, hud=record.hud, combat_log_appends=record.combat_log_appends,
                content_additions=record.content_additions))
    for seat, client in clients.items():
        displayed, expected = shown(client), live(runtime.session, seat)
        assert displayed == expected, (seat, difference(displayed, expected))


FIELDS = ("actor_uuid", "name", "portrait_key", "normal_hp", "maximum_hp", "species", "species_variant", "background",
    "origin", "class_levels", "scribed_spell_ids", "permanent_feature_uses", "prepared_spell_selections", "abilities",
    "skills", "expertise", "saves", "proficiency_bonus", "resources", "compatible_item_slots", "handler_details")


def difference(displayed: tuple, expected: tuple) -> tuple:
    """The first differing sheet's actor and fields (shown, live), or the two initiatives."""
    for left, right in zip(displayed[0], expected[0]):
        if left != right:
            return left[0], tuple((name, a, b) for name, a, b in zip(FIELDS, left, right) if a != b)
    if len(displayed[0]) != len(expected[0]):
        return "sheets", tuple(row[0] for row in displayed[0]), tuple(row[0] for row in expected[0])
    return "initiative", displayed[1], expected[1]


def shown(client: PlayerState) -> tuple:
    """What the seat's client shows: its sheets with their bodies' name, portrait and HP, and the initiative."""
    assert client.hud_snapshot is not None
    sheets = []
    for sheet in client.hud_snapshot.sheets:
        body = client.actors[sheet.actor_uuid]
        sheets.append((sheet.actor_uuid, body.name, body.appearance.portrait_key, body.normal_hp, body.maximum_hp,
            sheet.species, sheet.species_variant, sheet.background, sheet.origin, sheet.class_levels,
            sheet.scribed_spell_ids, sheet.permanent_feature_uses, sheet.prepared_spell_selections,
            sheet.abilities, sheet.skills, sheet.expertise, sheet.saves, sheet.proficiency_bonus, sheet.resources,
            sheet.compatible_item_slots, sheet.handler_details))
    return tuple(sheets), displayed_initiative(client)


def live(session, seat: str) -> tuple:
    """The same values read fresh from the engine, the initiative filtered by the seat's live senses."""
    audience = session.seats[seat]
    sheets = []
    for identity in session.player_uuids:
        if not audience.controls(identity):
            continue
        actor = session.game.entities[identity]
        groups = evaluate_actor_sheet(actor)
        sheets.append((identity, actor.name, actor.appearance.portrait_key, actor.get_normal_hp(), actor.get_max_hp(),
            actor.character_species, actor.character_species_variant, actor.character_background,
            actor.applied_origin_state, actor.applied_class_levels, actor.scribed_spell_ids,
            actor.permanent_feature_uses, actor.prepared_spell_selections,
            groups.abilities, groups.skills, groups.expertise, groups.saves, groups.proficiency_bonus, groups.resources,
            groups.compatible_item_slots, groups.handler_details))
    seen: set[UUID] = set(audience.controlled)
    for observer in audience.observers:
        seen.update(session.game.entities[observer].senses.entities)
    return tuple(sheets), tuple(identity for identity in session.encounter.initiative_order if identity in seen)


class Table:
    """One played worker session and its seats' client folds, checked after every operation."""

    def __init__(self, start: Start):
        reset_engine_runtime()
        self.runtime, _, records = worker.start(start)
        self.clients: dict[str, PlayerState] = {}
        self.operations = 0
        self.commands = 0
        deliver(self.runtime, self.clients, records)

    def send(self, step: str, request) -> None:
        reply, records, _ = worker.dispatch(self.runtime, request)
        assert reply.rejection is None, step
        deliver(self.runtime, self.clients, records)
        self.operations += sum(isinstance(record, PlayerOperation) for record in records)

    def advance_to_human(self) -> tuple[str, UUID]:
        for index in range(60):
            if not worker.needs_advance(self.runtime.session):
                break
            self.send(f"advance {index}", Advance())
        return next((seat, publication.boundary.input_actor_uuid) for seat, publication in self.runtime.publications.items()
            if publication.boundary.input_actor_uuid is not None)

    def command(self, step: str, seat: str, actor: UUID, intent) -> None:
        self.commands += 1
        self.send(step, Command(seat_id=seat, request=CommandRequest(command_number=self.commands, actor_uuid=actor,
            state_revision=self.runtime.publications[seat].state_revision, intent=intent)))

    def choices(self, seat: str, actor: UUID):
        _, _, response = worker.dispatch(self.runtime, Choices(seat_id=seat, request=ChoicesRequest(actor_uuid=actor,
            state_revision=self.runtime.publications[seat].state_revision, force_attack=False,
            correlation_id=uuid4())))
        return response.choices


def test_skirmish_hud_equals_the_live_engine_after_every_operation():
    table = Table(Start(game_id="hud-oracle", game_epoch=uuid4(), audience_ids={"party": uuid4()},
        encounter_id=None, recipe=None, assignments=None, test_seed=3))
    try:
        seat, actor_uuid = table.advance_to_human()
        actor = table.runtime.session.game.entities[actor_uuid]
        handler = actor.get_player_toggleable_handler_infos()[0]
        choices = table.choices(seat, actor_uuid)
        table.command("toggle", seat, actor_uuid, ToggleHandlerIntent(discovery_generation=choices.discovery_generation,
            handler=ToggleHandler(handler_uuid=handler.uuid, enabled=not handler.enabled)))
        slot, weapon = next((slot, item) for slot in WeaponSlot
            if (item := actor.equipment.get_item_by_slot(slot)) is not None)
        table.command("unequip", seat, actor_uuid, UnequipIntent(item=UnequipItem(slot=slot)))
        table.command("equip", seat, actor_uuid, EquipIntent(item=EquipItem(item_uuid=weapon.uuid, slot=slot)))
        choices = table.choices(seat, actor_uuid)
        dodge = next(row for row in rows(choices) if row.behavior_id == "action.dodge" and row.can_afford)
        table.command("dodge", seat, actor_uuid, ExecuteSelectionIntent(discovery_generation=choices.discovery_generation,
            selection=ActionSelection(dodge.discovery_index, (choices.target_sets[dodge.target_set][0].index,))))
        table.command("end turn", seat, actor_uuid, EndTurnIntent())
        table.advance_to_human()
        assert table.operations >= 8
    finally:
        close_session(table.runtime.session)
