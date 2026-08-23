"""Direct in-process assembly of authored scenarios into one Game."""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.actions.reactions import add_opportunity_attack_handler
from dnd.actions.standard import Disengage, Hide
from dnd.blocks.base_item import EquippableItem
from dnd.conditions import Blinded, Poisoned
from dnd.content.characters.character_builds import create_premade_character
from dnd.content.characters.scenario_character_builds import create_scenario_character
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.monsters.monster_builders import create_monster
from dnd.content.scenarios.battlefield_builders import (
    BuiltBattlefield,
    build_battlefield,
    get_battlefield,
)
from dnd.content.scenarios.scenario_compatibility import (
    check_built_encounter_compatibility,
    check_encounter_compatibility,
    resolve_encounter_positions,
)
from dnd.content.scenarios.scenario_definitions import (
    DamageAffinityStatus,
    EncounterCompatibilityReport,
    EncounterDefinition,
    FixedRosterOpeningPolicy,
    RosterBehaviorGrant,
    RosterDamageAffinity,
    RosterItemGrant,
    RosterItemPlacement,
    RosterResourceState,
    RosterSpellGrant,
    RosterStartingCondition,
    RosterStartingDamage,
)
from dnd.core.modifiers import ResistanceModifier
from dnd.core.gridmap import get_map
from dnd.encounters.controllers import Controller, PassController
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from dnd.game import Game
from dnd.items.torches import Torch
from dnd.spells.spell_builders import (
    REACTION_HANDLER_FACTORIES_BY_SPELL_ID,
    SPELL_ACTION_TYPES_BY_ID,
)
from dnd.types.damage import ResistanceStatus


class IncompatibleScenarioError(ValueError):
    """Raised before entity construction for an invalid authored scenario."""


@dataclass(frozen=True, slots=True)
class AssembledScenario:
    """One in-process Game plus direct authored lookup values."""

    definition: EncounterDefinition
    game: Game
    encounter: Encounter
    battlefield: BuiltBattlefield
    compatibility: EncounterCompatibilityReport
    entities_by_roster_slot: Mapping[str, tuple[Entity, ...]]
    entities_by_member_address: Mapping[tuple[str, str], Entity]
    controllers: Mapping[UUID, Controller]
    notable_positions: Mapping[str, tuple[int, int]]

    @property
    def entities(self) -> tuple[Entity, ...]:
        return tuple(
            entity
            for slot in self.definition.roster_slots
            for entity in self.entities_by_roster_slot[slot.roster_slot_id]
        )


_AFFINITIES = {
    DamageAffinityStatus.RESISTANCE: ResistanceStatus.RESISTANCE,
    DamageAffinityStatus.VULNERABILITY: ResistanceStatus.VULNERABILITY,
    DamageAffinityStatus.IMMUNITY: ResistanceStatus.IMMUNITY,
}
_STARTING_CONDITIONS = {
    "condition.blinded": Blinded,
    "condition.poisoned": Poisoned,
}


def _display_name(slot, member) -> str:
    overrides = {
        row.member_id: row.display_name
        for row in slot.member_presentations
    }
    return overrides.get(member.member_id, member.display_name)


def _optional_int(parameters: Mapping[str, object], key: str) -> int | None:
    value = parameters.get(key)
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"monster parameter {key!r} must be an integer")
    return value


def _optional_bool(parameters: Mapping[str, object], key: str) -> bool | None:
    value = parameters.get(key)
    if value is None:
        return None
    if type(value) is not bool:
        raise TypeError(f"monster parameter {key!r} must be a boolean")
    return value


def _optional_string(parameters: Mapping[str, object], key: str) -> str | None:
    value = parameters.get(key)
    if value is None:
        return None
    if type(value) is not str:
        raise TypeError(f"monster parameter {key!r} must be a string")
    return value


def _create_member(slot, member) -> Entity:
    entity_id = member.source.entity_id
    parameters: Mapping[str, object] = member.source.parameters
    name = _display_name(slot, member)
    if entity_id.startswith("character."):
        return create_scenario_character(
            entity_id,
            uuid4(),
            name=name,
            faction=slot.faction_id,
            parameters=parameters,
        )
    if entity_id.startswith("hero."):
        if parameters:
            raise ValueError("premade character roots do not accept parameters")
        return create_premade_character(
            entity_id,
            uuid4(),
            name=name,
            faction=slot.faction_id,
        )
    allowed = {"caster_level", "darkvision", "wardrobe", "weight"}
    unexpected = set(parameters) - allowed
    if unexpected:
        raise ValueError(
            f"{entity_id} does not accept parameters: "
            + ", ".join(sorted(unexpected)),
        )
    return create_monster(
        entity_id,
        uuid4(),
        name=name,
        faction=slot.faction_id,
        caster_level=_optional_int(parameters, "caster_level") or 5,
        darkvision=_optional_bool(parameters, "darkvision"),
        wardrobe=_optional_string(parameters, "wardrobe"),
        weight=_optional_int(parameters, "weight"),
    )


def _apply_item_grant(entity: Entity, effect: RosterItemGrant) -> None:
    for _index in range(effect.count):
        item = build_authored_item(
            effect.item_id,
            entity.uuid,
            parameters=effect.parameters,
        )
        if not entity.loot_item(item):
            raise ValueError(
                f"inventory rejected {effect.item_id!r} for {entity.name!r}",
            )
        if effect.placement is not RosterItemPlacement.INVENTORY:
            if not isinstance(item, EquippableItem):
                raise TypeError(f"{effect.item_id!r} is not equippable")
            if effect.replace_existing and effect.equipment_slot is not None:
                entity.unequip_item(effect.equipment_slot)
            slot = (
                effect.equipment_slot
                if effect.placement is RosterItemPlacement.EQUIPPED
                else None
            )
            if not entity.equip_item(item.uuid, slot):
                raise ValueError(
                    f"equipment rejected {effect.item_id!r} for {entity.name!r}",
                )
        if effect.on_grant == "ignite":
            if not isinstance(item, Torch):
                raise TypeError("ignite setup requires a portable torch")
            item.ignite(entity.uuid)


def _apply_spell_grant(entity: Entity, effect: RosterSpellGrant) -> None:
    for spell_id in effect.spell_ids:
        try:
            spell_type = SPELL_ACTION_TYPES_BY_ID[spell_id]
        except KeyError as exc:
            raise KeyError(f"unknown scenario spell {spell_id!r}") from exc
        entity.register_action(spell_type(
            source_entity_uuid=entity.uuid,
            caster_level=effect.caster_level,
            template=True,
            semantic_key=spell_id,
            behavior_id=spell_id,
            provided_by_id=spell_id,
            origin_root_id=spell_id,
        ))


def _apply_behavior_grant(entity: Entity, effect: RosterBehaviorGrant) -> None:
    if effect.behavior_id in {"reaction.spell.shield", "reaction.spell.counterspell"}:
        spell_id = effect.behavior_id.removeprefix("reaction.")
        handler = REACTION_HANDLER_FACTORIES_BY_SPELL_ID[spell_id](entity.uuid)
        handler.semantic_key = effect.behavior_id
        handler.behavior_id = effect.behavior_id
        handler.provided_by_id = effect.behavior_id
        handler.origin_root_id = effect.behavior_id
        handler.bind_behavior_owner()
        entity.add_event_handler(handler)
        return
    action_type = {
        "action.hide": Hide,
        "action.disengage": Disengage,
    }.get(effect.behavior_id)
    if action_type is None:
        raise ValueError(f"unknown scenario behavior {effect.behavior_id!r}")
    entity.register_action(action_type(
        source_entity_uuid=entity.uuid,
        template=True,
        name=(
            effect.configured_display_name
            or ("Hide" if action_type is Hide else "Disengage")
        ),
        alt_cost_type=(
            "bonus_actions"
            if effect.action_cost_variant == "bonus_action"
            else None
        ),
        semantic_key=effect.behavior_id,
        behavior_id=effect.behavior_id,
        provided_by_id=effect.behavior_id,
        origin_root_id=effect.behavior_id,
    ))


def _apply_immediate_effect(entity: Entity, effect: object) -> None:
    if isinstance(effect, RosterItemGrant):
        _apply_item_grant(entity, effect)
        return
    if isinstance(effect, RosterSpellGrant):
        _apply_spell_grant(entity, effect)
        return
    if isinstance(effect, RosterBehaviorGrant):
        _apply_behavior_grant(entity, effect)
        return
    if isinstance(effect, RosterDamageAffinity):
        entity.health.damage_reduction.self_static.add_resistance_modifier(
            ResistanceModifier(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
                value=_AFFINITIES[effect.status],
                damage_type=effect.damage_type,
                name=effect.label,
            ),
        )
        return
    if isinstance(effect, RosterResourceState):
        resource = entity.action_economy.resources.get(effect.resource_id)
        if resource is None:
            raise ValueError(f"unknown scenario resource {effect.resource_id!r}")
        if type(effect.value) is not int:
            raise TypeError("scenario resource state must be an integer")
        if not 0 <= effect.value <= resource.maximum:
            raise ValueError("scenario resource state is outside its capacity")
        resource.current = effect.value
        return
    if isinstance(effect, (RosterStartingDamage, RosterStartingCondition)):
        return
    raise TypeError(f"unsupported scenario setup effect {effect!r}")


def _apply_deferred_effect(
    target: Entity,
    effect: RosterStartingDamage | RosterStartingCondition,
    *,
    entities_by_role: Mapping[str, Entity],
) -> None:
    source = (
        entities_by_role[effect.source_member_role]
        if effect.source_member_role is not None
        else target
    )
    if isinstance(effect, RosterStartingDamage):
        target.receive_damage(
            effect.amount,
            effect.damage_type,
            source.uuid,
            effect_id=f"scenario.starting_damage.{effect.damage_type.value.casefold()}",
        )
        target.remove_condition("HasTakenDamage")
        return
    try:
        condition_type = _STARTING_CONDITIONS[effect.condition_id]
    except KeyError as exc:
        raise KeyError(f"unknown scenario condition {effect.condition_id!r}") from exc
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
        semantic_key=effect.condition_id,
        behavior_id=effect.condition_id,
        provided_by_id=effect.condition_id,
        origin_root_id=effect.condition_id,
    )
    condition.bind_behavior_owner(origin_root_id=effect.condition_id)
    target.add_condition(condition)


def _runtime_encounter(
    definition: EncounterDefinition,
    entities_by_roster_slot: Mapping[str, tuple[Entity, ...]],
    *,
    start_encounter: bool,
) -> tuple[Encounter, dict[UUID, Controller]]:
    entities = tuple(
        entity
        for slot in definition.roster_slots
        for entity in entities_by_roster_slot[slot.roster_slot_id]
    )
    for entity in entities:
        add_opportunity_attack_handler(entity)
    Entity.materialize_all_navigation(max_distance=80)
    encounter = Encounter(name=definition.title, source_entity_uuid=uuid4())
    controllers: dict[UUID, Controller] = {}
    for entity in entities:
        controller = PassController(source_entity_uuid=entity.uuid)
        controllers[entity.uuid] = controller
        encounter.add_combatant(entity, controller)
    encounter.roll_initiative()
    if isinstance(definition.opening_policy, FixedRosterOpeningPolicy):
        opening_ids = {
            entity.uuid
            for entity in entities_by_roster_slot[
                definition.opening_policy.roster_slot_id
            ]
        }
        opening_uuid = next(
            entity_uuid
            for entity_uuid in encounter.initiative_order
            if entity_uuid in opening_ids
        )
        encounter.initiative_order = [
            opening_uuid,
            *(
                entity_uuid
                for entity_uuid in encounter.initiative_order
                if entity_uuid != opening_uuid
            ),
        ]
    encounter.current_turn_index = 0
    if start_encounter:
        encounter.start_encounter()
    return encounter, controllers


def assemble_scenario(
    game: Game,
    definition: EncounterDefinition,
    *,
    start_encounter: bool = True,
) -> AssembledScenario:
    """Build and deploy one scenario without resetting process-global state."""
    if game.entities:
        raise ValueError("scenario assembly requires an empty Game")
    battlefield_definition = get_battlefield(definition.battlefield_id)
    static_report = check_encounter_compatibility(
        definition,
        battlefield_definition,
    )
    if not static_report.admitted:
        raise IncompatibleScenarioError(
            "; ".join(issue.message for issue in static_report.issues),
        )
    battlefield = build_battlefield(definition.battlefield_id)
    built_report = check_built_encounter_compatibility(
        static_report,
        definition,
        get_map(),
    )
    if not built_report.admitted:
        raise IncompatibleScenarioError(
            "; ".join(issue.message for issue in built_report.issues),
        )

    positions, position_issues = resolve_encounter_positions(definition)
    if position_issues:
        raise IncompatibleScenarioError(
            "; ".join(issue.message for issue in position_issues),
        )
    by_roster: dict[str, tuple[Entity, ...]] = {}
    by_address: dict[tuple[str, str], Entity] = {}
    by_role: dict[str, Entity] = {}
    deferred: list[
        tuple[Entity, RosterStartingDamage | RosterStartingCondition]
    ] = []

    for slot in definition.roster_slots:
        members: list[Entity] = []
        for member in slot.roster.members:
            entity = _create_member(slot, member)
            members.append(entity)
            by_address[(slot.roster_slot_id, member.member_id)] = entity
            by_role[member.deployment_role] = entity
        by_roster[slot.roster_slot_id] = tuple(members)

    for slot in definition.roster_slots:
        for member, entity in zip(
            slot.roster.members,
            by_roster[slot.roster_slot_id],
            strict=True,
        ):
            game.deploy_entity(
                entity,
                positions[slot.roster_slot_id][member.member_id],
            )
            for effect in member.scenario_setup_effects:
                if isinstance(effect, (RosterStartingDamage, RosterStartingCondition)):
                    deferred.append((entity, effect))
                else:
                    _apply_immediate_effect(entity, effect)
    for target, effect in deferred:
        _apply_deferred_effect(target, effect, entities_by_role=by_role)

    encounter, controllers = _runtime_encounter(
        definition,
        by_roster,
        start_encounter=start_encounter,
    )
    notable_positions = {
        **battlefield.notable_positions,
        **{row.label: row.position for row in definition.notable_positions},
    }
    return AssembledScenario(
        definition=definition,
        game=game,
        encounter=encounter,
        battlefield=battlefield,
        compatibility=built_report,
        entities_by_roster_slot=by_roster,
        entities_by_member_address=by_address,
        controllers=controllers,
        notable_positions=notable_positions,
    )


def prepare_scenario(
    game: Game,
    definition: EncounterDefinition,
) -> AssembledScenario:
    """Build and deploy a scenario without crossing Encounter start."""
    return assemble_scenario(game, definition, start_encounter=False)


__all__ = [
    "AssembledScenario",
    "IncompatibleScenarioError",
    "assemble_scenario",
    "prepare_scenario",
]
