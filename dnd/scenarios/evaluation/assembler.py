"""Single reset, build, augment, sense, and encounter-start scenario assembler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions_functional import register_spells_by_name
from dnd.classes.barbarian_factory import BarbarianConfig, PrimalPathChoice, create_barbarian
from dnd.classes.fighter_factory import FighterConfig, create_fighter
from dnd.classes.sorcerer_factory import SorcererConfig, create_sorcerer
from dnd.conditions import Blinded, Poisoned
from dnd.controller import Controller, PassController
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.items.test_items import (
    create_acid_flask,
    create_healing_potion,
    create_lightning_weapon_coat,
    create_potion_of_greater_invisibility,
    create_potion_of_haste,
    create_scroll_of_fireball,
    create_scroll_of_hold_person,
    create_scroll_of_magic_missile,
    create_scroll_of_spike_growth,
    create_torch,
    create_wand_of_fire,
    create_wand_of_magic_missiles,
    create_weapon_coat,
    Torch,
)
from dnd.items.weapons import create_club, create_longbow, create_shortsword
from dnd.monsters.bestiary import (
    create_caster,
    create_goblin,
    create_goblin_archer,
    create_skeleton_archer,
    create_skeleton_warlock,
    create_skeleton_warrior,
    register_goblin_nimble_escape,
)
from dnd.monsters.srd_roster import create_srd_monster
from dnd.reactions import add_opportunity_attack_handler
from dnd.scenarios.ai_validation_arenas import (
    ValidationArena,
    ValidationArenaSpec,
    list_ai_validation_arena_specs,
)
from dnd.scenarios.evaluation.battlefield_catalog import BuiltBattlefield, build_battlefield, get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import get_combatant_configuration
from dnd.scenarios.evaluation.compatibility import (
    CompatibilityReport,
    check_built_compatibility,
    check_compatibility,
    resolve_deployment_positions,
)
from dnd.scenarios.evaluation.deployment_catalog import get_deployment
from dnd.scenarios.evaluation.legacy_recipes import get_legacy_recipe
from dnd.scenarios.evaluation.models import (
    ActorAugmentation,
    ActorBlueprint,
    ApparelGrant,
    BarbarianActorBlueprint,
    BestiaryActorBlueprint,
    DamageAffinity,
    EquipmentGrant,
    FighterActorBlueprint,
    ItemGrant,
    ReactionGrant,
    SideConfigurationSpec,
    SorcererActorBlueprint,
    SpellGrant,
    SrdMonsterActorBlueprint,
    StartingCondition,
    StartingDamage,
)
from dnd.scenarios.evaluation.wardrobes import equip_apparel
from dnd.spells.abjuration import register_counterspell_reaction, register_shield_reaction


class ActorBuildContext(BaseModel):
    """Runtime-only actor presentation and placement supplied by assembly."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(description="Stable deployment role for this actor instance.")
    name: str = Field(description="Runtime display name excluded from configuration identity.")
    faction: str = Field(description="Runtime faction excluded from configuration identity.")
    position: tuple[int, int] = Field(description="Runtime spawn position excluded from configuration identity.")


@dataclass(frozen=True)
class AssembledScenario:
    """Arena bundle plus the compatibility evidence used to admit it."""

    arena: ValidationArena
    compatibility: CompatibilityReport
    battlefield: BuiltBattlefield


class IncompatibleScenarioError(ValueError):
    """Raised when a requested composition fails hard compatibility checks."""


def reset_composed_scenario_state(width: int = 15, height: int = 15) -> None:
    """Clear every global engine registry used by scenario construction."""
    reset_engine_runtime(grid_size=(width, height))


def _build_class_actor(blueprint: ActorBlueprint, context: ActorBuildContext) -> Entity | None:
    """Build one class-factory actor, returning None for other blueprint families."""
    if isinstance(blueprint, BarbarianActorBlueprint):
        return create_barbarian(BarbarianConfig(
            level=blueprint.level,
            name=context.name,
            position=context.position,
            faction=context.faction,
            primal_path=PrimalPathChoice(blueprint.primal_path),
            equipment_preset=blueprint.equipment_preset,
            asi_4=list(blueprint.asi_4) or None,
            asi_8=list(blueprint.asi_8) or None,
        ))
    if isinstance(blueprint, FighterActorBlueprint):
        return create_fighter(FighterConfig(
            level=blueprint.level,
            name=context.name,
            position=context.position,
            faction=context.faction,
            fighting_style=blueprint.fighting_style,
            equipment_preset=blueprint.equipment_preset,
            asi_4=list(blueprint.asi_4) or None,
            asi_6=list(blueprint.asi_6) or None,
            asi_8=list(blueprint.asi_8) or None,
        ))
    if isinstance(blueprint, SorcererActorBlueprint):
        return create_sorcerer(SorcererConfig(
            level=blueprint.level,
            name=context.name,
            position=context.position,
            faction=context.faction,
            metamagic_choices=list(blueprint.metamagic_choices),
            spell_names=list(blueprint.spell_names),
            equipment_preset=blueprint.equipment_preset,
            asi_4=list(blueprint.asi_4) or None,
            asi_8=list(blueprint.asi_8) or None,
        ))
    return None


def _build_bestiary_actor(blueprint: BestiaryActorBlueprint, context: ActorBuildContext) -> Entity:
    """Dispatch one blueprint to the closed set of existing bestiary factories."""
    if blueprint.archetype == "caster":
        return create_caster(name=context.name, position=context.position, faction=context.faction, level=blueprint.level)
    if blueprint.archetype == "goblin":
        return create_goblin(
            name=context.name,
            position=context.position,
            faction=context.faction,
            weight=blueprint.weight or 40,
        )
    if blueprint.archetype == "goblin_archer":
        return create_goblin_archer(
            name=context.name,
            position=context.position,
            faction=context.faction,
            weight=blueprint.weight or 40,
        )
    skeleton_kwargs = {
        "name": context.name,
        "position": context.position,
        "faction": context.faction,
        "weight": blueprint.weight or 120,
        "darkvision": bool(blueprint.darkvision),
    }
    if blueprint.archetype == "skeleton_warrior":
        return create_skeleton_warrior(**skeleton_kwargs)
    if blueprint.archetype == "skeleton_archer":
        return create_skeleton_archer(**skeleton_kwargs)
    if blueprint.archetype == "skeleton_warlock":
        return create_skeleton_warlock(**skeleton_kwargs)
    raise ValueError(f"Unsupported bestiary archetype: {blueprint.archetype}")


def build_actor(blueprint: ActorBlueprint, context: ActorBuildContext) -> Entity:
    """Build one actor through the blueprint's existing engine factory."""
    class_actor = _build_class_actor(blueprint, context)
    if class_actor is not None:
        return class_actor
    if isinstance(blueprint, BestiaryActorBlueprint):
        return _build_bestiary_actor(blueprint, context)
    if isinstance(blueprint, SrdMonsterActorBlueprint):
        return create_srd_monster(
            blueprint.monster_id,
            name=context.name,
            position=context.position,
            faction=context.faction,
        )
    raise ValueError(f"Unsupported actor blueprint: {blueprint}")


def _grant_item(entity: Entity, grant: ItemGrant) -> None:
    """Create and loot every item represented by one typed inventory grant."""
    for _ in range(grant.count):
        if grant.item_id == "acid_flask":
            item = create_acid_flask(entity.uuid)
        elif grant.item_id == "healing_potion":
            item = create_healing_potion(entity.uuid, heal_amount=grant.heal_amount or 7)
        elif grant.item_id == "lightning_weapon_coat":
            item = create_lightning_weapon_coat(entity.uuid)
        elif grant.item_id == "potion_greater_invisibility":
            item = create_potion_of_greater_invisibility(entity.uuid)
        elif grant.item_id == "potion_haste":
            item = create_potion_of_haste(entity.uuid)
        elif grant.item_id == "scroll_fireball":
            item = create_scroll_of_fireball(entity.uuid)
        elif grant.item_id == "scroll_hold_person":
            item = create_scroll_of_hold_person(entity.uuid)
        elif grant.item_id == "scroll_magic_missile":
            item = create_scroll_of_magic_missile(entity.uuid)
        elif grant.item_id == "scroll_spike_growth":
            item = create_scroll_of_spike_growth(entity.uuid)
        elif grant.item_id == "torch_lit":
            item = create_torch(entity.uuid)
        elif grant.item_id == "wand_fire":
            item = create_wand_of_fire(entity.uuid, charges=grant.charges or 7)
        elif grant.item_id == "wand_magic_missiles":
            item = create_wand_of_magic_missiles(entity.uuid, charges=grant.charges or 3)
        elif grant.item_id == "weapon_coat":
            item = create_weapon_coat(entity.uuid)
        else:
            raise ValueError(f"Unsupported item grant: {grant.item_id}")
        if not entity.loot_item(item):
            raise ValueError(f"Inventory rejected {grant.item_id!r} for {entity.name!r}.")
        if grant.item_id == "torch_lit":
            if not isinstance(item, Torch):
                raise TypeError("Torch grant factory returned an incompatible item type.")
            item.ignite(entity.uuid)


def _grant_equipment(entity: Entity, grant: EquipmentGrant) -> None:
    """Create and equip one typed weapon grant."""
    slots = {
        "melee_main": WeaponSlot.MELEE_MAIN,
        "melee_off": WeaponSlot.MELEE_OFF,
        "ranged_main": WeaponSlot.RANGED_MAIN,
        "ranged_off": WeaponSlot.RANGED_OFF,
    }
    slot = slots[grant.slot]
    if grant.replace:
        entity.equipment.unequip(slot)
    if grant.item_id == "club":
        item = create_club(entity.uuid)
    elif grant.item_id == "longbow":
        item = create_longbow(entity.uuid)
    elif grant.item_id == "shortsword":
        item = create_shortsword(entity.uuid)
    else:
        raise ValueError(f"Unsupported equipment grant: {grant.item_id}")
    if not entity.equipment.equip(item, slot):
        raise ValueError(f"Equipment rejected {grant.item_id!r} for {entity.name!r}.")


def _apply_immediate_augmentation(entity: Entity, augmentation: ActorAugmentation) -> None:
    """Apply augmentations that do not depend on another composed actor."""
    if isinstance(augmentation, SpellGrant):
        register_spells_by_name(entity, list(augmentation.spell_names), caster_level=augmentation.caster_level)
    elif isinstance(augmentation, ItemGrant):
        _grant_item(entity, augmentation)
    elif isinstance(augmentation, ReactionGrant):
        if augmentation.reaction_id == "counterspell":
            register_counterspell_reaction(entity)
        elif augmentation.reaction_id == "goblin_nimble_escape":
            register_goblin_nimble_escape(entity)
        elif augmentation.reaction_id == "shield":
            register_shield_reaction(entity)
    elif isinstance(augmentation, DamageAffinity):
        statuses = {
            "resistance": ResistanceStatus.RESISTANCE,
            "vulnerability": ResistanceStatus.VULNERABILITY,
            "immunity": ResistanceStatus.IMMUNITY,
        }
        entity.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            value=statuses[augmentation.status],
            damage_type=DamageType(augmentation.damage_type),
            name=augmentation.label,
        ))
    elif isinstance(augmentation, EquipmentGrant):
        _grant_equipment(entity, augmentation)
    elif isinstance(augmentation, ApparelGrant):
        equip_apparel(entity, augmentation)


def _apply_deferred_augmentation(
    entity: Entity,
    augmentation: StartingDamage | StartingCondition,
    actors_by_role: Mapping[str, Entity],
) -> None:
    """Apply event-backed setup mutations after every referenced actor exists."""
    source = actors_by_role.get(augmentation.source_role) if augmentation.source_role else entity
    if source is None:
        raise ValueError(f"Starting augmentation references unknown role {augmentation.source_role!r}.")
    if isinstance(augmentation, StartingDamage):
        entity.receive_damage(
            augmentation.amount,
            DamageType(augmentation.damage_type),
            source.uuid,
            effect_id=f"scenario.starting_damage.{augmentation.damage_type.lower()}",
        )
        # Legacy setup damage predates the round-scoped combat tracker. Keep
        # the event lifecycle while restoring the declared starting-condition set.
        entity.remove_condition("HasTakenDamage")
        return
    condition_types = {"Blinded": Blinded, "Poisoned": Poisoned}
    condition = condition_types[augmentation.condition_name](
        source_entity_uuid=source.uuid,
        target_entity_uuid=entity.uuid,
    )
    entity.add_condition(condition)


def _build_side(
    spec: SideConfigurationSpec,
    positions: Mapping[str, tuple[int, int]],
    names: Mapping[str, str],
    faction: str,
) -> tuple[tuple[Entity, ...], dict[str, Entity], list[tuple[Entity, StartingDamage | StartingCondition]]]:
    """Build and immediately augment one complete side."""
    actors: list[Entity] = []
    actors_by_role: dict[str, Entity] = {}
    deferred: list[tuple[Entity, StartingDamage | StartingCondition]] = []
    for blueprint in spec.members:
        role = blueprint.deployment_role or blueprint.actor_id
        context = ActorBuildContext(
            role=role,
            name=names.get(role, blueprint.actor_id),
            faction=faction,
            position=positions[role],
        )
        actor = build_actor(blueprint, context)
        actor.appearance.portrait_key = f"{spec.configuration_id}::{blueprint.actor_id}"
        actors.append(actor)
        actors_by_role[role] = actor
        for augmentation in blueprint.augmentations:
            if isinstance(augmentation, (StartingDamage, StartingCondition)):
                deferred.append((actor, augmentation))
            else:
                _apply_immediate_augmentation(actor, augmentation)
    return tuple(actors), actors_by_role, deferred


def _build_encounter(
    name: str,
    actors: tuple[Entity, ...],
    opening_faction: str | None,
    *,
    start_encounter: bool,
) -> tuple[Encounter, dict[UUID, Controller]]:
    """Build initiative state and optionally cross the encounter-start boundary."""
    for actor in actors:
        add_opportunity_attack_handler(actor)
    Entity.update_all_entities_senses(max_distance=80)

    encounter = Encounter(name=name, source_entity_uuid=uuid4())
    controllers: dict[UUID, Controller] = {}
    for actor in actors:
        controller = PassController(source_entity_uuid=actor.uuid)
        controllers[actor.uuid] = controller
        encounter.add_combatant(actor, controller)

    encounter.roll_initiative()
    if opening_faction is not None:
        opening_candidates = [
            entity_uuid
            for entity_uuid in encounter.initiative_order
            if (entity := Entity.get(entity_uuid)) is not None and entity.faction == opening_faction
        ]
        if not opening_candidates:
            raise ValueError(f"Opening faction {opening_faction!r} has no combatant in {name!r}.")
        opening_entity_uuid = opening_candidates[0]
        encounter.initiative_order = [
            opening_entity_uuid,
            *(entity_uuid for entity_uuid in encounter.initiative_order if entity_uuid != opening_entity_uuid),
        ]
    encounter.current_turn_index = 0
    if start_encounter:
        encounter.start_encounter()
    return encounter, controllers


def _default_validation_spec(
    hero: SideConfigurationSpec,
    monsters: SideConfigurationSpec,
    battlefield_id: str,
) -> ValidationArenaSpec:
    """Create report metadata for a non-legacy composition."""
    arena_id = f"composed:{hero.configuration_id}:{monsters.configuration_id}:{battlefield_id}"
    return ValidationArenaSpec(
        arena_id=arena_id,
        title=f"{hero.title} vs {monsters.title}",
        hero_role=hero.title,
        tags=("composed", "evaluation"),
        expected_pressure=("general configuration-strength evaluation",),
        map_notes=(battlefield_id,),
    )


def _default_side_duel_spec(
    side_a: SideConfigurationSpec,
    side_b: SideConfigurationSpec,
    battlefield_id: str,
) -> ValidationArenaSpec:
    """Create report metadata for one neutral composed duel."""
    arena_id = f"side-duel:{side_a.configuration_id}:{side_b.configuration_id}:{battlefield_id}"
    return ValidationArenaSpec(
        arena_id=arena_id,
        title=f"{side_a.title} vs {side_b.title}",
        hero_role=side_a.title,
        tags=("composed", "evaluation", "side-duel"),
        expected_pressure=("generic side-versus-side configuration evaluation",),
        map_notes=(battlefield_id,),
    )


def _positions_from_slots(
    spec: SideConfigurationSpec,
    slots: tuple[tuple[int, int], ...],
    side_name: str,
) -> dict[str, tuple[int, int]]:
    """Bind ordered neutral deployment slots to one configuration's actor roles."""
    if len(slots) < len(spec.members):
        raise IncompatibleScenarioError(
            f"{side_name} provides {len(slots)} slots for {len(spec.members)} actors."
        )
    return {
        member.deployment_role or member.actor_id: slots[index]
        for index, member in enumerate(spec.members)
    }


def _validate_generic_positions(
    side_a: SideConfigurationSpec,
    side_b: SideConfigurationSpec,
    battlefield_id: str,
    side_a_positions: Mapping[str, tuple[int, int]],
    side_b_positions: Mapping[str, tuple[int, int]],
) -> None:
    """Reject invalid neutral spawns and incompatible battlefield requirements."""
    battlefield = get_battlefield(battlefield_id)
    capabilities = set(battlefield.capabilities)
    errors: list[str] = []
    for side in (side_a, side_b):
        for capability in sorted(set(side.required_battlefield_capabilities) - capabilities):
            errors.append(f"{side.configuration_id!r} requires absent capability {capability!r}.")
        for capability in sorted(set(side.forbidden_battlefield_capabilities) & capabilities):
            errors.append(f"{side.configuration_id!r} forbids battlefield capability {capability!r}.")

    active_positions = [
        (f"side_a:{role}", position) for role, position in side_a_positions.items()
    ]
    active_positions.extend(
        (f"side_b:{role}", position) for role, position in side_b_positions.items()
    )
    positions_only = [position for _, position in active_positions]
    if len(positions_only) != len(set(positions_only)):
        errors.append("Two neutral combatants resolve to the same spawn coordinate.")
    for role, (x, y) in active_positions:
        if not (0 <= x < battlefield.width and 0 <= y < battlefield.height):
            errors.append(f"Role {role!r} resolves outside the battlefield bounds.")
    if errors:
        raise IncompatibleScenarioError("; ".join(errors))


def _validate_built_generic_positions(
    side_a_positions: Mapping[str, tuple[int, int]],
    side_b_positions: Mapping[str, tuple[int, int]],
) -> None:
    """Validate neutral spawns against constructed terrain and connectivity."""
    grid = get_map()
    active_positions = [
        (f"side_a:{role}", position) for role, position in side_a_positions.items()
    ]
    active_positions.extend(
        (f"side_b:{role}", position) for role, position in side_b_positions.items()
    )
    errors: list[str] = []
    for role, position in active_positions:
        if not grid.is_walkable_for(*position):
            errors.append(f"Role {role!r} resolves to a blocked spawn coordinate.")
        if grid.get_entities_at(position):
            errors.append(f"Role {role!r} resolves to an occupied spawn coordinate.")
    if side_a_positions and side_b_positions and not any(
        grid.get_path(side_a_position, side_b_position) is not None
        for side_a_position in side_a_positions.values()
        for side_b_position in side_b_positions.values()
    ):
        errors.append("No traversable relationship exists between side-A and side-B spawn zones.")
    if errors:
        raise IncompatibleScenarioError("; ".join(errors))


def _side_actor_names(
    spec: SideConfigurationSpec,
    actor_names: Mapping[str, str],
    namespace: str,
) -> dict[str, str]:
    """Resolve namespaced presentation names with legacy role-name fallback."""
    names: dict[str, str] = {}
    for member in spec.members:
        role = member.deployment_role or member.actor_id
        namespaced_name = actor_names.get(f"{namespace}:{role}")
        fallback_name = actor_names.get(role)
        if namespaced_name is not None:
            names[role] = namespaced_name
        elif fallback_name is not None:
            names[role] = fallback_name
    return names


def _apply_generic_deferred_augmentations(
    side_a: tuple[Entity, ...],
    side_a_by_role: Mapping[str, Entity],
    side_a_deferred: list[tuple[Entity, StartingDamage | StartingCondition]],
    side_b_by_role: Mapping[str, Entity],
    side_b_deferred: list[tuple[Entity, StartingDamage | StartingCondition]],
) -> None:
    """Resolve deferred actor references without merging mirrored raw role names."""
    namespaced_roles = {
        **{f"side_a:{role}": actor for role, actor in side_a_by_role.items()},
        **{f"side_b:{role}": actor for role, actor in side_b_by_role.items()},
    }
    side_a_references = {**namespaced_roles, **side_a_by_role}
    side_b_references = {**namespaced_roles, **side_b_by_role}
    side_a_references.setdefault("hero", side_a[0])
    side_b_references.setdefault("hero", side_a[0])
    for actor, augmentation in side_a_deferred:
        _apply_deferred_augmentation(actor, augmentation, side_a_references)
    for actor, augmentation in side_b_deferred:
        _apply_deferred_augmentation(actor, augmentation, side_b_references)


def assemble_generic_side_duel(
    side_a_configuration_id: str,
    side_b_configuration_id: str,
    battlefield_id: str,
    *,
    side_a_slots: tuple[tuple[int, int], ...],
    side_b_slots: tuple[tuple[int, int], ...],
    encounter_name: str | None = None,
    actor_names: Mapping[str, str] | None = None,
    notable_positions: Mapping[str, tuple[int, int]] | None = None,
    opening_faction: str | None = None,
    validation_spec: ValidationArenaSpec | None = None,
) -> ValidationArena:
    """Assemble any two catalog configurations as neutral side A and side B."""
    if opening_faction not in {None, "side_a", "side_b"}:
        raise ValueError("opening_faction must be 'side_a', 'side_b', or None.")
    side_a_spec = get_combatant_configuration(side_a_configuration_id)
    side_b_spec = get_combatant_configuration(side_b_configuration_id)
    battlefield_spec = get_battlefield(battlefield_id)
    side_a_positions = _positions_from_slots(side_a_spec, side_a_slots, "side_a")
    side_b_positions = _positions_from_slots(side_b_spec, side_b_slots, "side_b")
    _validate_generic_positions(
        side_a_spec,
        side_b_spec,
        battlefield_id,
        side_a_positions,
        side_b_positions,
    )

    reset_composed_scenario_state(battlefield_spec.width, battlefield_spec.height)
    built_battlefield = build_battlefield(battlefield_id)
    _validate_built_generic_positions(side_a_positions, side_b_positions)

    names = actor_names or {}
    side_a_actors, side_a_by_role, side_a_deferred = _build_side(
        side_a_spec,
        side_a_positions,
        _side_actor_names(side_a_spec, names, "side_a"),
        "side_a",
    )
    side_b_actors, side_b_by_role, side_b_deferred = _build_side(
        side_b_spec,
        side_b_positions,
        _side_actor_names(side_b_spec, names, "side_b"),
        "side_b",
    )
    _apply_generic_deferred_augmentations(
        side_a_actors,
        side_a_by_role,
        side_a_deferred,
        side_b_by_role,
        side_b_deferred,
    )

    resolved_name = encounter_name or f"Evaluation: {side_a_spec.title} vs {side_b_spec.title}"
    encounter, controllers = _build_encounter(
        resolved_name,
        (*side_a_actors, *side_b_actors),
        opening_faction,
        start_encounter=True,
    )
    positions = (
        dict(notable_positions)
        if notable_positions is not None
        else dict(built_battlefield.notable_positions)
    )
    positions.setdefault("side_a_start", side_a_actors[0].position)
    positions.setdefault("side_b_start", side_b_actors[0].position)
    positions.setdefault("hero_start", side_a_actors[0].position)
    spec = validation_spec or _default_side_duel_spec(side_a_spec, side_b_spec, battlefield_id)
    return ValidationArena(
        spec=spec,
        encounter=encounter,
        hero=side_a_actors[0],
        monsters=side_b_actors,
        controllers=controllers,
        notable_positions=positions,
        environment=built_battlefield.environment,
        side_a=side_a_actors,
        side_b=side_b_actors,
    )


def assemble_composed_scenario(
    hero_configuration_id: str,
    monster_configuration_id: str,
    battlefield_id: str,
    deployment_id: str,
    *,
    encounter_name: str | None = None,
    actor_names: Mapping[str, str] | None = None,
    notable_positions: Mapping[str, tuple[int, int]] | None = None,
    opening_faction: str | None = None,
    validation_spec: ValidationArenaSpec | None = None,
    start_encounter: bool = True,
) -> AssembledScenario:
    """Reset and assemble one compatible scenario through existing engine factories.

    Server composition passes ``start_encounter=False`` so final controllers,
    replication, and replay capture can be installed before the one canonical
    encounter-start boundary. Evaluation helpers retain the historical
    immediate-start behavior.
    """
    hero_spec = get_combatant_configuration(hero_configuration_id)
    monster_spec = get_combatant_configuration(monster_configuration_id)
    battlefield_spec = get_battlefield(battlefield_id)
    deployment = get_deployment(deployment_id)
    static_report = check_compatibility(hero_spec, monster_spec, battlefield_spec, deployment)
    if not static_report.admitted:
        raise IncompatibleScenarioError("; ".join(issue.message for issue in static_report.issues if issue.severity == "hard"))

    reset_composed_scenario_state(battlefield_spec.width, battlefield_spec.height)
    built_battlefield = build_battlefield(battlefield_id)
    built_report = check_built_compatibility(
        static_report,
        hero_spec,
        monster_spec,
        deployment,
        get_map(),
    )
    if not built_report.admitted:
        raise IncompatibleScenarioError("; ".join(issue.message for issue in built_report.issues if issue.severity == "hard"))

    hero_positions, monster_positions = resolve_deployment_positions(hero_spec, monster_spec, deployment)
    names = actor_names or {}
    hero_actors, hero_by_role, hero_deferred = _build_side(hero_spec, hero_positions, names, "heroes")
    monster_actors, monsters_by_role, monster_deferred = _build_side(
        monster_spec,
        monster_positions,
        names,
        "monsters",
    )
    actors_by_role = {**hero_by_role, **monsters_by_role}
    for actor, augmentation in (*hero_deferred, *monster_deferred):
        _apply_deferred_augmentation(actor, augmentation, actors_by_role)

    hero = hero_actors[0]
    resolved_encounter_name = encounter_name or f"Evaluation: {hero_spec.title} vs {monster_spec.title}"
    encounter, controllers = _build_encounter(
        resolved_encounter_name,
        (hero, *monster_actors),
        opening_faction,
        start_encounter=start_encounter,
    )
    positions = (
        dict(notable_positions)
        if notable_positions is not None
        else dict(built_battlefield.notable_positions)
    )
    positions.setdefault("hero_start", hero.position)
    spec = validation_spec or _default_validation_spec(hero_spec, monster_spec, battlefield_id)
    arena = ValidationArena(
        spec=spec,
        encounter=encounter,
        hero=hero,
        monsters=monster_actors,
        controllers=controllers,
        notable_positions=positions,
        environment=built_battlefield.environment,
    )
    return AssembledScenario(arena=arena, compatibility=built_report, battlefield=built_battlefield)


def assemble_composed_arena(
    hero_configuration_id: str,
    monster_configuration_id: str,
    battlefield_id: str,
    deployment_id: str,
    *,
    opening_faction: str | None = None,
) -> ValidationArena:
    """Return only the arena bundle for a general composed scenario."""
    return assemble_composed_scenario(
        hero_configuration_id,
        monster_configuration_id,
        battlefield_id,
        deployment_id,
        opening_faction=opening_faction,
    ).arena


def prepare_composed_scenario(
    hero_configuration_id: str,
    monster_configuration_id: str,
    battlefield_id: str,
    deployment_id: str,
    *,
    encounter_name: str | None = None,
    actor_names: Mapping[str, str] | None = None,
    notable_positions: Mapping[str, tuple[int, int]] | None = None,
    opening_faction: str | None = None,
    validation_spec: ValidationArenaSpec | None = None,
) -> AssembledScenario:
    """Assemble a server-owned scenario without starting its encounter."""
    return assemble_composed_scenario(
        hero_configuration_id,
        monster_configuration_id,
        battlefield_id,
        deployment_id,
        encounter_name=encounter_name,
        actor_names=actor_names,
        notable_positions=notable_positions,
        opening_faction=opening_faction,
        validation_spec=validation_spec,
        start_encounter=False,
    )


_LEGACY_VALIDATION_SPECS = {
    spec.arena_id: spec for spec in list_ai_validation_arena_specs()
}


def assemble_legacy_scenario(arena_id: str, *, opening_faction: str | None = None) -> ValidationArena:
    """Reconstruct one historical arena from canonical catalogs and recipe metadata."""
    recipe = get_legacy_recipe(arena_id)
    actor_names = {presentation.role: presentation.name for presentation in recipe.actor_presentations}
    notable_positions = {position.label: position.position for position in recipe.notable_positions}
    return assemble_composed_scenario(
        recipe.hero_configuration_id,
        recipe.monster_configuration_id,
        recipe.battlefield_id,
        recipe.deployment_id,
        encounter_name=recipe.encounter_name,
        actor_names=actor_names,
        notable_positions=notable_positions,
        opening_faction=opening_faction,
        validation_spec=_LEGACY_VALIDATION_SPECS[arena_id],
    ).arena


def prepare_legacy_scenario(arena_id: str, *, opening_faction: str | None = None) -> ValidationArena:
    """Reconstruct a historical arena without crossing encounter start."""
    recipe = get_legacy_recipe(arena_id)
    actor_names = {presentation.role: presentation.name for presentation in recipe.actor_presentations}
    notable_positions = {position.label: position.position for position in recipe.notable_positions}
    return prepare_composed_scenario(
        recipe.hero_configuration_id,
        recipe.monster_configuration_id,
        recipe.battlefield_id,
        recipe.deployment_id,
        encounter_name=recipe.encounter_name,
        actor_names=actor_names,
        notable_positions=notable_positions,
        opening_faction=opening_faction,
        validation_spec=_LEGACY_VALIDATION_SPECS[arena_id],
    ).arena
