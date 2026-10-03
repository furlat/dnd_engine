"""Explicit world binding for temporary creatures using native composition owners."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.actions import PreparedSpellConcentration, SpellAction, SpellEvent
from dnd.ai.runtime.controller import NativeAIController
from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.content_system.installed_creature_materialization import materialize_installed_creature
from dnd.core.base_block import BaseBlock, ConditionRemovalReceipt, PreparedInitialConditions
from dnd.core.base_conditions import ConditionRemovalEvent, Duration
from dnd.core.condition_types import DurationType, InvoluntarySustainLoss
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import CreatureType
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, SummonAdmissionEvent, Trigger
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter, EncounterState, PreparedCombatantJoin
from dnd.entity import Entity, PreparedBirth
from dnd.game import Game, PreparedDeployment, PreparedRetirement
from dnd.summoning.conditions import SummonControl, Summoned
from dnd.summoning.forms import SPELL_SPECIFICATIONS, selected_form
from dnd.types.summoning import SummonDepartureCause, SummonManifestation, SummonOrigin, SummonRules, SummonSelection, SummonSustain, TerminalOwnerRelease


@dataclass(slots=True)
class SummonMembership:
    entity: Entity
    existence: Summoned
    control: SummonControl | None
    controller: NativeAIController


@dataclass(slots=True)
class PreparedSummon:
    membership: SummonMembership
    initial: PreparedInitialConditions
    birth: PreparedBirth
    deployment: PreparedDeployment
    join: PreparedCombatantJoin
    concentration: PreparedSpellConcentration | None
    committed: bool = False


class SummoningSystem:
    """One explicit game/encounter owner; creatures themselves remain ordinary data."""

    def __init__(self, game: Game, encounter: Encounter) -> None:
        self.uuid = uuid4()
        self.game = game
        self.encounter = encounter
        self.memberships: dict[UUID, SummonMembership] = {}
        self._committed_casts: set[UUID] = set()
        self._closed = False
        self._retirements: dict[UUID, PreparedRetirement] = {}
        self._preparing_retirement: set[UUID] = set()
        self._condition_members: dict[UUID, SummonMembership] = {}
        self._system_name = f"summoning:{id(game)}"
        if self._system_name in EventQueue._pre_completion_systems:
            raise ValueError("Summoning is already bound to this game")
        self._handlers = (
            EventHandler(source_entity_uuid=self.uuid, content_kind=RuntimeBehaviorKind.SYSTEM, name="Summon admission", validation_only=True,
                trigger_conditions=[Trigger(event_type=EventType.SUMMON_ADMISSION,
                                            event_phase=EventPhase.DECLARATION)],
                event_processor=self._admit),
            EventHandler(uuid=self.uuid, source_entity_uuid=self.uuid, content_kind=RuntimeBehaviorKind.SYSTEM, name="Summon creation",
                event_processor=self._cast),
        )
        for handler in self._handlers:
            EventQueue.add_event_handler(handler)
        self._removal_participant = BaseBlock.register_condition_removal_participant(self)
        self._settled_hook = BaseBlock.register_condition_graph_settled_hook(self._settled)
        EventQueue.add_pre_completion_system(self._system_name, self,
            {EventType.CONDITION_REMOVAL, EventType.DAMAGE_APPLIED, EventType.DEATH, EventType.INSTANT_DEATH})
        game.add_close_callback(self.close)

    def placement_error(self, caster_uuid: UUID, selection: SummonSelection, *, subjective: bool) -> str | None:
        """Validate the chosen creature and its one destination without allocating it."""
        try:
            selected_form(selection)
        except ValueError as error:
            return str(error)
        caster = self.game.get_entity(caster_uuid)
        if (self._closed or self.encounter.state is not EncounterState.ACTIVE
                or caster is None or caster_uuid not in self.encounter.combatants
                or not caster.has_runtime_agency() or not caster.is_deployed):
            return "Summoning requires a present caster in the bound active encounter"
        if not caster.faction:
            return "Summoning requires the caster to have an allegiance"
        position = selection.target_position
        specification = SPELL_SPECIFICATIONS[selection.family]
        if (not caster.senses.visible.get(position, False)
                or caster.senses.get_feet_distance(position) > specification.placement_range_feet):
            return "Choose a visible destination within summoning range"
        if subjective:
            if (not caster._is_subjectively_walkable_position(position)
                    or position == caster.position
                    or any(contact.position == position for contact in caster.senses.entities.values())):
                return "Choose an unoccupied walkable destination"
        elif not get_map().is_walkable_for(*position):
            return "Summon destination is unavailable"
        return None

    def _admit(self, event: Event, source_uuid: UUID) -> Event | None:
        del source_uuid
        if not isinstance(event, SummonAdmissionEvent) or event.source_entity_uuid not in self.game.entities:
            return None
        error = self.placement_error(event.source_entity_uuid, event.selection, subjective=event.subjective)
        return event.cancel(status_message=error) if error else event.model_copy(update={"binding_uuid": self.uuid})

    def _cast(self, event: Event, source_uuid: UUID) -> Event | None:
        del source_uuid
        if not isinstance(event, SpellEvent) or event.summon_application is None:
            return None
        application = event.summon_application
        if application.binding_uuid != self.uuid:
            return None
        if event.lineage_uuid in self._committed_casts:
            return event
        action = SpellAction.get(application.action_uuid)
        if not isinstance(action, SpellAction) or action.source_entity_uuid != event.source_entity_uuid:
            raise RuntimeError("Summon effect has no exact live executable spell")
        error = self.placement_error(event.source_entity_uuid, application.selection, subjective=False)
        if error:
            return event.cancel(status_message=error)
        if not self.create_summon(application.selection, parent_event=event,
                rules=SPELL_SPECIFICATIONS[application.selection.family].rules, concentration_action=action):
            return event.cancel(status_message="Summon composition was rejected")
        return event

    def create_summon(self, selection: SummonSelection, *, parent_event: Event,
                      rules: SummonRules, concentration_action: SpellAction | None = None) -> bool:
        """Create from trusted authored rules after the caller's native costs.

        Player spell input never supplies these rules. The three spell adapters
        resolve their immutable specification; an authored independent effect can
        supply NONE sustain while sharing the same existence and retirement path.
        """
        if parent_event.lineage_uuid in self._committed_casts:
            return True
        if rules.sustain is not SummonSustain.NONE and (
            concentration_action is None or not concentration_action.concentration
        ):
            raise ValueError("Authored sustain requires a concentration-capable action")
        if concentration_action is not None and concentration_action.source_entity_uuid != parent_event.source_entity_uuid:
            raise ValueError("Sustainer action must belong to the creating source")
        if self.placement_error(parent_event.source_entity_uuid, selection, subjective=False):
            return False
        prepared = self._prepare(selection, concentration_action, parent_event, rules)
        if prepared is None:
            return False
        self._commit(prepared, concentration_action, parent_event)
        return True

    def _prepare(self, selection: SummonSelection, action: SpellAction | None,
                 event: Event, rules: SummonRules) -> PreparedSummon | None:
        form = selected_form(selection)
        caster = self.game.get_entity(event.source_entity_uuid)
        if caster is None:
            return None
        entity = materialize_installed_creature(form.recipe, runtime_entity_uuid=uuid4(),
            display_name=form.display_name, faction=caster.faction, position=selection.target_position,
            deployment_role=CreatureDeploymentRole(role_id="summoning.creature"),
            possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY)
        controller: NativeAIController | None = None
        initial: PreparedInitialConditions | None = None
        join: PreparedCombatantJoin | None = None
        concentration: PreparedSpellConcentration | None = None
        try:
            if form.manifestation is SummonManifestation.FEY_SPIRIT:
                entity.creature_type = CreatureType.FEY
            existence_uuid = uuid4()
            control_uuid = uuid4() if rules.sustain is SummonSustain.CONTROL else None
            origin = SummonOrigin(summoner_uuid=caster.uuid, cast_lineage_uuid=event.lineage_uuid,
                recipe=form.recipe, form_id=form.form_id, manifestation=form.manifestation,
                existence_condition_uuid=existence_uuid, control_condition_uuid=control_uuid)
            existence = Summoned(uuid=existence_uuid, source_entity_uuid=caster.uuid,
                target_entity_uuid=entity.uuid, origin=origin,
                duration=Duration(duration=rules.duration_rounds, duration_type=DurationType.ROUNDS),
                last_progressed_interval=(self.encounter.uuid, self.encounter.round_number))
            control = SummonControl(uuid=control_uuid, source_entity_uuid=caster.uuid,
                target_entity_uuid=entity.uuid, original_controller_uuid=caster.uuid) if control_uuid else None
            conditions = [existence, control] if control is not None else [existence]
            initial = entity.prepare_initial_conditions(conditions, parent_event=event)
            if control is not None:
                existence.sub_conditions.append(control.uuid)
            controller = NativeAIController.create(source_entity_uuid=entity.uuid,
                game_id=str(self.uuid), assignment_id=str(entity.uuid), controlled_entity_uuids=(entity.uuid,))
            deployment = self.game.prepare_deployment(entity, selection.target_position, parent_event=event)
            join = self.encounter.prepare_combatant_join(entity, controller, after_uuid=caster.uuid)
            if rules.sustain is not SummonSustain.NONE:
                assert action is not None
                admitted = action.prepare_concentration(event)
                if not isinstance(admitted, PreparedSpellConcentration):
                    raise ValueError("Summon concentration was rejected")
                concentration = admitted
            birth = entity.prepare_birth(initial_conditions=initial, parent_event=event, summon_origin=origin)
            error = self.placement_error(caster.uuid, selection, subjective=False)
            if error:
                raise ValueError(error)
            self.game.validate_prepared_deployment(deployment)
            self.encounter.validate_combatant_join(join)
            if concentration is not None and not concentration.condition.validate_prepared_removal():
                raise ValueError("Concentration replacement no longer has valid destinations")
            if concentration is not None and selection.target_position in concentration.condition.prepared_removal_occupancies():
                raise ValueError("Summon destination conflicts with concentration cleanup")
            return PreparedSummon(SummonMembership(entity, existence, control, controller),
                initial, birth, deployment, join, concentration)
        except BaseException as error:
            errors: list[BaseException] = []
            if concentration is not None and concentration.application is not None:
                try:
                    concentration.owner.cancel_condition_application(concentration.application, "Summon admission canceled")
                except BaseException as cleanup_error:
                    errors.append(cleanup_error)
            if join is not None:
                try:
                    self.encounter.cancel_combatant_join(join)
                except BaseException as cleanup_error:
                    errors.append(cleanup_error)
            if controller is not None:
                try:
                    controller.close()
                except BaseException as cleanup_error:
                    errors.append(cleanup_error)
                finally:
                    controller.remove_from_register()
            if initial is not None:
                for application in reversed(initial.applications):
                    try:
                        entity.cancel_condition_application(application, "Summon admission canceled")
                    except BaseException as cleanup_error:
                        errors.append(cleanup_error)
            CREATURE_RUNTIME_BINDINGS.discard(entity.uuid)
            try:
                entity.discard_uncommitted()
            except BaseException as cleanup_error:
                errors.append(cleanup_error)
            if errors:
                raise BaseExceptionGroup("Summon admission and cleanup failed", [error, *errors]) from None
            if isinstance(error, ValueError):
                return None
            raise

    def _commit(self, prepared: PreparedSummon, action: SpellAction | None, event: Event) -> None:
        member = prepared.membership
        errors: list[BaseException] = []
        try:
            with BaseBlock.condition_removal_scope():
                if prepared.concentration is not None:
                    assert action is not None
                    action.commit_prepared_concentration(prepared.concentration, member.entity,
                        member.control if member.control is not None else member.existence)
                member.entity.commit_initial_conditions(prepared.initial)
                member.entity.commit_birth(prepared.birth)
                self.game.commit_deployment(prepared.deployment)
                self.encounter.commit_combatant_join(prepared.join)
                self.memberships[member.entity.uuid] = member
                self._condition_members[member.existence.uuid] = member
                if member.control is not None:
                    self._condition_members[member.control.uuid] = member
                self._committed_casts.add(event.lineage_uuid)
                prepared.committed = True
                try:
                    member.entity.publish_birth(prepared.birth)
                except BaseException as error:
                    errors.append(error)
                try:
                    member.entity.publish_initial_conditions(prepared.initial)
                except BaseException as error:
                    errors.append(error)
                try:
                    self.game.publish_deployment(prepared.deployment)
                except BaseException as error:
                    errors.append(error)
                if prepared.concentration is not None:
                    assert action is not None
                    try:
                        action.publish_prepared_concentration(prepared.concentration)
                    except BaseException as error:
                        errors.append(error)
        except BaseException as error:
            errors.append(error)
        if prepared.committed and member.entity.uuid in self.memberships and member.entity.has_runtime_agency():
            try:
                member.controller.start([member.entity])
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Summon birth publication failed after commitment", errors)

    def prepare_condition_removal(self, owner_uuid: UUID | None, condition_uuid: UUID,
                                  event: Event, terminal_release: TerminalOwnerRelease | None,
                                  involuntary_loss: InvoluntarySustainLoss | None) -> bool:
        del involuntary_loss
        member = self._condition_members.get(condition_uuid)
        if member is None or condition_uuid != member.existence.uuid:
            return True
        if owner_uuid != member.entity.uuid:
            raise RuntimeError("Summon existence has changed native owner")
        if condition_uuid in self._retirements or condition_uuid in self._preparing_retirement:
            return True
        cause = terminal_release or member.existence.terminal_release(SummonDepartureCause.DISMISSED, event.uuid)
        self._preparing_retirement.add(condition_uuid)
        try:
            prepared = self.game.prepare_entity_retirement(member.entity.uuid, cause=cause, parent_event=event)
            if prepared is None:
                return False
            self._retirements[condition_uuid] = prepared
            return True
        finally:
            self._preparing_retirement.discard(condition_uuid)

    def validate_condition_removal(self, condition_uuid: UUID) -> bool:
        prepared = self._retirements.get(condition_uuid)
        return prepared is None or prepared.entity.entity.validate_prepared_retirement(prepared.entity)

    def cancel_condition_removal(self, condition_uuid: UUID, reason: str) -> None:
        del reason
        prepared = self._retirements.pop(condition_uuid, None)
        if prepared is not None:
            prepared.entity.entity.cancel_retirement(prepared.entity)

    def commit_condition_removal(self, owner_uuid: UUID, condition_uuid: UUID) -> None:
        member = self._condition_members.get(condition_uuid)
        if member is not None and condition_uuid == member.existence.uuid:
            if owner_uuid != member.entity.uuid:
                raise RuntimeError("Committed summon existence changed native owner")
            member.entity.revoke_runtime_agency()

    def __call__(self, event: Event) -> None:
        if isinstance(event, ConditionRemovalEvent):
            member = self._condition_members.get(event.condition.uuid)
            if member is not None and event.condition.uuid == member.existence.uuid and not member.existence.applied:
                member.entity.revoke_runtime_agency()
            return
        target_uuid = event.target_entity_uuid or event.source_entity_uuid
        member = self.memberships.get(target_uuid)
        if member is not None and member.existence.applied and (
            member.entity.get_hp() <= 0 or event.event_type in {EventType.DEATH, EventType.INSTANT_DEATH}
        ):
            self._depart(member, SummonDepartureCause.DEFEATED, event)

    def _settled(self, receipts: tuple[ConditionRemovalReceipt, ...]) -> None:
        errors: list[BaseException] = []
        ending = {receipt.condition_uuid for receipt in receipts if receipt.condition_uuid in self._retirements}
        for receipt in receipts:
            try:
                member = self._condition_members.get(receipt.condition_uuid)
                if member is None:
                    continue
                parent = EventQueue.get_event_by_uuid(receipt.removal_event_uuid)
                if receipt.condition_uuid == member.existence.uuid:
                    prepared = self._retirements.pop(receipt.condition_uuid, None)
                    if prepared is None:
                        raise RuntimeError("Committed summon departure lacks admitted native retirement")
                    member.entity.revoke_runtime_agency()
                    self.encounter.request_combatant_leave(member.entity.uuid, parent_event=parent)
                    try:
                        self.game.commit_entity_retirement(prepared)
                    except BaseException as error:
                        errors.append(error)
                    finally:
                        if prepared.entity.committed:
                            try:
                                member.controller.close()
                            except BaseException as error:
                                errors.append(error)
                            member.controller.remove_from_register()
                            CREATURE_RUNTIME_BINDINGS.discard(member.entity.uuid)
                            self.memberships.pop(member.entity.uuid, None)
                            self._condition_members.pop(member.existence.uuid, None)
                            if member.control is not None:
                                self._condition_members.pop(member.control.uuid, None)
                    self.encounter.finish_combatant_leaves()
                elif (member.control is not None and receipt.condition_uuid == member.control.uuid
                      and member.existence.uuid not in ending and member.existence.applied):
                    member.entity.set_faction(f"uncontrolled_summon:{member.entity.uuid}", parent_event=parent)
                    if self.encounter.state is EncounterState.ACTIVE:
                        self.encounter._check_encounter_end()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Committed summon departures failed to publish", errors)

    def _depart(self, member: SummonMembership, cause: SummonDepartureCause,
                parent_event: Event | None = None) -> bool:
        release = member.existence.terminal_release(cause, parent_event.uuid if parent_event is not None else None)
        return member.entity.remove_condition_by_uuid(member.existence.uuid,
            parent_event=parent_event, terminal_release=release)

    def rebind_encounter(self, encounter: Encounter) -> None:
        """Join a later active encounter without recreating surviving creatures."""
        if self._closed or self.encounter.state is EncounterState.ACTIVE:
            raise ValueError("Rebind requires the previous encounter to have ended")
        if encounter.state is not EncounterState.ACTIVE:
            raise ValueError("Rebind requires an already-composed active encounter")
        if encounter is self.encounter:
            return
        joins: list[tuple[SummonMembership, NativeAIController, PreparedCombatantJoin]] = []
        try:
            for member in self.memberships.values():
                controlled = member.control is None or member.control.applied
                anchor = member.existence.origin.summoner_uuid if controlled else None
                if controlled and anchor not in encounter.combatants:
                    raise ValueError("Controlled survivor requires its summoner in the new encounter")
                controller = NativeAIController.create(source_entity_uuid=member.entity.uuid,
                    game_id=str(self.uuid), assignment_id=str(member.entity.uuid),
                    controlled_entity_uuids=(member.entity.uuid,))
                try:
                    join = encounter.prepare_combatant_join(member.entity, controller, after_uuid=anchor)
                except BaseException:
                    controller.close()
                    controller.remove_from_register()
                    raise
                joins.append((member, controller, join))
            for _, _, join in joins:
                encounter.validate_combatant_join(join)
        except BaseException:
            for _, controller, join in joins:
                encounter.cancel_combatant_join(join)
                controller.close()
                controller.remove_from_register()
            raise
        for member, controller, join in joins:
            self.encounter.release_inactive_combatant(member.entity.uuid)
            member.controller.close()
            member.controller.remove_from_register()
            encounter.commit_combatant_join(join)
            member.controller = controller
        self.encounter = encounter
        for member, controller, _ in joins:
            controller.start([member.entity])

    def close(self, parent_event: Event | None = None) -> None:
        if self._closed:
            return
        errors: list[BaseException] = []
        for member in tuple(self.memberships.values()):
            try:
                self._depart(member, SummonDepartureCause.CLOSED, parent_event)
            except BaseException as error:
                errors.append(error)
        if not self.memberships:
            self.reset()
        if errors:
            raise BaseExceptionGroup("Summon close failed", errors)

    def reset(self) -> None:
        """Drop this binding silently when the existing runtime generation resets."""
        if self._closed:
            return
        self._closed = True
        for member in tuple(self.memberships.values()):
            member.controller.close()
        for handler in self._handlers:
            handler.remove()
            handler.remove_from_register()
        BaseBlock.remove_condition_removal_participant(self._removal_participant)
        BaseBlock.remove_condition_graph_settled_hook(self._settled_hook)
        EventQueue.remove_pre_completion_system(self._system_name)
        self.game.remove_close_callback(self.close)
        self.memberships.clear()
        self._condition_members.clear()
        self._retirements.clear()
        self._committed_casts.clear()


def bind_summoning(game: Game, encounter: Encounter) -> SummoningSystem:
    """Bind only after native world, content and encounter composition."""
    return SummoningSystem(game, encounter)
