"""One generic assembler for exact encounter recipes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.actions import Disengage, Hide, SpellAction
from dnd.actions_functional import register_spell
from dnd.blocks.base_item import EquippableItem
from dnd.conditions import Blinded, Poisoned
from dnd.content_system.character_materialization import materialize_character
from dnd.content_system.creature_bindings import CREATURE_RUNTIME_BINDINGS
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.controller import Controller, PassController
from dnd.core.content.character_deployment import CharacterDeploymentSnapshot
from dnd.core.content.encounters import (
    AuthoredCreatureRosterSource,
    EncounterCompatibilityReport,
    EncounterRecipe,
    FixedRosterOpeningPolicy,
    OwnedCharacterRosterSource,
    RosterBehaviorGrant,
    RosterDamageAffinity,
    RosterItemGrant,
    RosterItemPlacement,
    RosterSpellGrant,
    RosterStartingCondition,
    RosterStartingDamage,
)
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.registration import get_content_declaration
from dnd.core.gridmap import get_map
from dnd.core.modifiers import ResistanceModifier, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.game import Game
from dnd.items.torches import Torch
from dnd.reactions import add_opportunity_attack_handler
from dnd.scenarios.encounter_compatibility import (
    check_built_encounter_compatibility,
    check_encounter_compatibility,
    resolve_encounter_positions,
)
from dnd.scenarios.battlefield_catalog import (
    BuiltBattlefield,
    build_battlefield,
    get_battlefield,
)
from dnd.spells.abjuration import (
    COUNTERSPELL_REACTION_DECLARATION,
    SHIELD_REACTION_DECLARATION,
    register_counterspell_reaction,
    register_shield_reaction,
)


class IncompatibleEncounterError(ValueError):
    """Raised before runtime actors are committed for an invalid recipe."""


@dataclass(frozen=True, slots=True)
class AssembledEncounter:
    """Engine runtime plus exact recipe-addressed entity bindings."""

    recipe: EncounterRecipe
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
            for roster_slot in self.recipe.roster_slots
            for entity in self.entities_by_roster_slot[
                roster_slot.roster_slot_id
            ]
        )


_SPELL_ROW_BY_REF = {
    row.declaration.ref.identity_key: row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
}
_SHIELD_REACTION_IDENTITY = SHIELD_REACTION_DECLARATION.ref.identity_key
_COUNTERSPELL_REACTION_IDENTITY = (
    COUNTERSPELL_REACTION_DECLARATION.ref.identity_key
)
_HIDE_ACTION_IDENTITY = get_content_declaration(Hide).ref.identity_key
_DISENGAGE_ACTION_IDENTITY = get_content_declaration(
    Disengage,
).ref.identity_key
_SETUP_CONDITION_BY_REF = {
    get_content_declaration(condition_type).ref.identity_key: condition_type
    for condition_type in (Blinded, Poisoned)
}
_RESISTANCE_STATUS_BY_SETUP = {
    "resistance": ResistanceStatus.RESISTANCE,
    "vulnerability": ResistanceStatus.VULNERABILITY,
    "immunity": ResistanceStatus.IMMUNITY,
}


def _display_name(
    recipe_slot,
    member,
) -> str:
    overrides = {
        row.member_id: row.display_name
        for row in recipe_slot.member_presentations
    }
    return overrides.get(member.member_id, member.display_name)


def _materialize_member(
    *,
    recipe_slot,
    member,
    position: tuple[int, int],
    character_deployments: Mapping[UUID, CharacterDeploymentSnapshot],
) -> Entity:
    role = CreatureDeploymentRole(
        role_id=(
            f"encounter.{recipe_slot.roster_slot_id}."
            f"{member.deployment_role}"
        ),
    )
    display_name = _display_name(recipe_slot, member)
    source = member.source
    if isinstance(source, AuthoredCreatureRosterSource):
        return materialize_creature(
            source.recipe,
            runtime_entity_uuid=uuid4(),
            display_name=display_name,
            faction=recipe_slot.faction_id,
            position=position,
            deployment_role=role,
            possession_mode=(
                CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
            ),
        )
    if isinstance(source, OwnedCharacterRosterSource):
        deployment = character_deployments.get(source.character_id)
        if deployment is None:
            raise IncompatibleEncounterError(
                f"Character {source.character_id} was not resolved",
            )
        expected_identity = (
            source.expected_character_row_version,
            source.expected_definition_revision,
            source.expected_definition_digest,
            source.expected_holdings_revision,
            source.expected_holdings_digest,
            source.expected_loadout_revision,
            source.expected_loadout_digest,
            source.expected_ruleset_digest,
        )
        actual_identity = (
            deployment.character_row_version,
            deployment.definition.definition_revision,
            deployment.definition.definition_digest,
            deployment.holdings.holdings_revision,
            deployment.holdings.holdings_digest,
            deployment.loadout.loadout_revision,
            deployment.loadout.loadout_digest,
            deployment.expected_ruleset_digest,
        )
        if actual_identity != expected_identity:
            raise IncompatibleEncounterError(
                f"Character {source.character_id} changed after encounter "
                "normalization",
            )
        return materialize_character(
            definition=deployment.definition,
            holdings=deployment.holdings,
            loadout=deployment.loadout,
            runtime_entity_uuid=None,
            display_name=deployment.display_name,
            faction=recipe_slot.faction_id,
            position=position,
            deployment_role=role,
            expected_ruleset_digest=deployment.expected_ruleset_digest,
            multiclass_slot_rounding_policy=(
                deployment.multiclass_slot_rounding_policy
            ),
            permissive_multiclass_prerequisites=(
                deployment.permissive_multiclass_prerequisites
            ),
        ).entity
    raise TypeError(f"Unsupported roster source: {source!r}")


def _apply_item_grant(entity: Entity, effect: RosterItemGrant) -> None:
    for _ in range(effect.count):
        item = materialize_item(
            effect.recipe,
            entity.uuid,
            origin=ItemRuntimeOrigin.STARTER,
        )
        try:
            if effect.placement is RosterItemPlacement.INVENTORY:
                if not entity.loot_item(item):
                    raise ValueError(
                        f"Inventory rejected "
                        f"{effect.recipe.ref.identity_key!r} "
                        f"for {entity.name!r}",
                    )
            else:
                if not isinstance(item, EquippableItem):
                    raise TypeError(
                        f"Equipped setup recipe "
                        f"{effect.recipe.ref.identity_key!r} is not "
                        "equippable",
                    )
                slot = effect.equipment_slot
                if effect.replace_existing and slot is not None:
                    entity.equipment.unequip(slot)
                if not entity.equipment.equip(item, slot):
                    raise ValueError(
                        f"Equipment rejected "
                        f"{effect.recipe.ref.identity_key!r} for "
                        f"{entity.name!r}",
                    )
            if effect.on_grant == "ignite":
                if not isinstance(item, Torch):
                    raise TypeError("ignite setup effect requires a Torch")
                item.ignite(entity.uuid)
        except BaseException:
            ITEM_RUNTIME_BINDINGS.discard(item.uuid)
            raise


def _apply_spell_grant(entity: Entity, effect: RosterSpellGrant) -> None:
    for spell_ref in effect.spell_refs:
        row = _SPELL_ROW_BY_REF.get(spell_ref.identity_key)
        if row is None or row.spell_type is None:
            raise ValueError(
                f"Spell grant {spell_ref.identity_key!r} has no directly "
                "registered spell action",
            )
        spell_type = row.spell_type
        if not issubclass(spell_type, SpellAction):
            raise TypeError(
                f"Spell grant {spell_ref.identity_key!r} is not a SpellAction",
            )
        register_spell(
            entity,
            spell_type,
            caster_level=effect.caster_level,
        )


def _apply_behavior_grant(
    entity: Entity,
    effect: RosterBehaviorGrant,
) -> None:
    identity = effect.behavior_ref.identity_key
    if identity == _SHIELD_REACTION_IDENTITY:
        register_shield_reaction(entity)
        return
    if identity == _COUNTERSPELL_REACTION_IDENTITY:
        register_counterspell_reaction(entity)
        return
    action_type: type[Hide] | type[Disengage] | None = None
    if identity == _HIDE_ACTION_IDENTITY:
        action_type = Hide
    elif identity == _DISENGAGE_ACTION_IDENTITY:
        action_type = Disengage
    if action_type is not None:
        entity.register_action(
            action_type(
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
            ),
        )
        return
    raise ValueError(
        f"No encounter setup applier owns behavior {identity!r}",
    )


def _apply_immediate_setup_effect(
    entity: Entity,
    effect: object,
) -> None:
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
                value=_RESISTANCE_STATUS_BY_SETUP[effect.status.value],
                damage_type=effect.damage_type,
                name=effect.label,
            ),
        )
        return
    if isinstance(effect, (RosterStartingDamage, RosterStartingCondition)):
        return
    raise TypeError(f"Unsupported immediate encounter setup effect: {effect!r}")


def _discard_provisional_entities(entities: tuple[Entity, ...]) -> None:
    """Release scenario-owned provisional aggregates and runtime bindings."""
    for entity in reversed(entities):
        if entity.creation_committed:
            continue
        item_uuids = {
            *entity.inventory.items,
            *(
                item.uuid
                for item in entity.equipment.get_all_equipped_items()
            ),
        }
        for item_uuid in item_uuids:
            ITEM_RUNTIME_BINDINGS.discard(item_uuid)
        CREATURE_RUNTIME_BINDINGS.discard(entity.uuid)
        if Entity.get(entity.uuid) is entity:
            entity.discard_uncommitted()


def _apply_deferred_setup_effect(
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
            effect_id=(
                f"encounter.starting_damage."
                f"{effect.damage_type.value.casefold()}"
            ),
        )
        target.remove_condition("HasTakenDamage")
        return
    condition_type = _SETUP_CONDITION_BY_REF.get(
        effect.condition_ref.identity_key,
    )
    if condition_type is None:
        raise ValueError(
            f"No encounter setup condition constructor owns "
            f"{effect.condition_ref.identity_key!r}",
        )
    condition = condition_type(
        source_entity_uuid=source.uuid,
        target_entity_uuid=target.uuid,
    )
    target.add_condition(condition)


def _build_runtime_encounter(
    recipe: EncounterRecipe,
    entities_by_roster_slot: Mapping[str, tuple[Entity, ...]],
    *,
    start_encounter: bool,
) -> tuple[Encounter, dict[UUID, Controller]]:
    entities = tuple(
        entity
        for roster_slot in recipe.roster_slots
        for entity in entities_by_roster_slot[
            roster_slot.roster_slot_id
        ]
    )
    for entity in entities:
        add_opportunity_attack_handler(entity)
    Entity.update_all_entities_senses(max_distance=80)
    encounter = Encounter(
        name=recipe.title,
        source_entity_uuid=uuid4(),
    )
    controllers: dict[UUID, Controller] = {}
    for entity in entities:
        controller = PassController(source_entity_uuid=entity.uuid)
        controllers[entity.uuid] = controller
        encounter.add_combatant(entity, controller)
    encounter.roll_initiative()
    if isinstance(recipe.opening_policy, FixedRosterOpeningPolicy):
        opening_entities = entities_by_roster_slot[
            recipe.opening_policy.roster_slot_id
        ]
        opening_ids = {entity.uuid for entity in opening_entities}
        opening_entity_uuid = next(
            entity_uuid
            for entity_uuid in encounter.initiative_order
            if entity_uuid in opening_ids
        )
        encounter.initiative_order = [
            opening_entity_uuid,
            *(
                entity_uuid
                for entity_uuid in encounter.initiative_order
                if entity_uuid != opening_entity_uuid
            ),
        ]
    encounter.current_turn_index = 0
    if start_encounter:
        encounter.start_encounter()
    return encounter, controllers


def assemble_encounter_recipe(
    recipe: EncounterRecipe,
    *,
    game: Game,
    character_deployments: (
        Mapping[UUID, CharacterDeploymentSnapshot] | None
    ) = None,
    start_encounter: bool = True,
) -> AssembledEncounter:
    """Validate and assemble one recipe into the caller-owned empty Game."""
    if game.entities:
        raise ValueError("scenario assembly requires an empty Game")
    if Entity.get_all_entities():
        raise ValueError("scenario assembly requires no registered Entities")
    deployments = character_deployments or {}
    battlefield_spec = get_battlefield(recipe.battlefield_id)
    static_report = check_encounter_compatibility(
        recipe,
        battlefield_spec,
        available_character_ids=frozenset(
            str(character_id) for character_id in deployments
        ),
    )
    if not static_report.admitted:
        raise IncompatibleEncounterError(
            "; ".join(
                issue.message
                for issue in static_report.issues
                if issue.severity.value == "hard"
            ),
        )

    battlefield = build_battlefield(recipe.battlefield_id)
    built_report = check_built_encounter_compatibility(
        static_report,
        recipe,
        get_map(),
    )
    if not built_report.admitted:
        raise IncompatibleEncounterError(
            "; ".join(
                issue.message
                for issue in built_report.issues
                if issue.severity.value == "hard"
            ),
        )

    positions, _ = resolve_encounter_positions(recipe)
    by_roster: dict[str, tuple[Entity, ...]] = {}
    by_address: dict[tuple[str, str], Entity] = {}
    by_role: dict[str, Entity] = {}
    deferred: list[
        tuple[Entity, RosterStartingDamage | RosterStartingCondition]
    ] = []
    immediate: list[
        tuple[
            Entity,
            RosterBehaviorGrant
            | RosterDamageAffinity
            | RosterItemGrant
            | RosterSpellGrant,
        ]
    ] = []
    try:
        for recipe_slot in recipe.roster_slots:
            entities: list[Entity] = []
            for member in recipe_slot.roster.members:
                entity = _materialize_member(
                    recipe_slot=recipe_slot,
                    member=member,
                    position=positions[
                        recipe_slot.roster_slot_id
                    ][member.member_id],
                    character_deployments=deployments,
                )
                entities.append(entity)
                by_address[
                    (recipe_slot.roster_slot_id, member.member_id)
                ] = entity
                by_role[member.deployment_role] = entity
                for effect in member.scenario_setup_effects:
                    if isinstance(
                        effect,
                        (RosterStartingDamage, RosterStartingCondition),
                    ):
                        deferred.append((entity, effect))
                    else:
                        immediate.append((entity, effect))
            by_roster[recipe_slot.roster_slot_id] = tuple(entities)
        for target, effect in immediate:
            _apply_immediate_setup_effect(target, effect)
        for entity in by_address.values():
            entity.validate_initial_composition()
        for entity in by_address.values():
            entity.compose_entity()
    except BaseException:
        _discard_provisional_entities(tuple(by_address.values()))
        raise
    for (roster_slot_id, member_id), entity in by_address.items():
        game.deploy_entity(
            entity,
            positions[roster_slot_id][member_id],
        )
    for target, effect in deferred:
        _apply_deferred_setup_effect(
            target,
            effect,
            entities_by_role=by_role,
        )

    encounter, controllers = _build_runtime_encounter(
        recipe,
        by_roster,
        start_encounter=start_encounter,
    )
    notable_positions = {
        **battlefield.notable_positions,
        **{
            row.label: row.position
            for row in recipe.notable_positions
        },
    }
    return AssembledEncounter(
        recipe=recipe,
        encounter=encounter,
        battlefield=battlefield,
        compatibility=built_report,
        entities_by_roster_slot=by_roster,
        entities_by_member_address=by_address,
        controllers=controllers,
        notable_positions=notable_positions,
    )


def prepare_encounter_recipe(
    recipe: EncounterRecipe,
    *,
    game: Game,
    character_deployments: (
        Mapping[UUID, CharacterDeploymentSnapshot] | None
    ) = None,
) -> AssembledEncounter:
    """Build a validated encounter without crossing its start boundary."""
    return assemble_encounter_recipe(
        recipe,
        game=game,
        character_deployments=character_deployments,
        start_encounter=False,
    )


__all__ = [
    "AssembledEncounter",
    "IncompatibleEncounterError",
    "assemble_encounter_recipe",
    "prepare_encounter_recipe",
]
