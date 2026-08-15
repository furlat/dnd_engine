"""Engine-facing producers for the dependency-neutral world contracts.

All registry access and concrete engine inspection for shared world DTOs lives
here.  Contract consumers must import :mod:`server.world_contracts` directly;
they never need Entity, GridMap, Encounter, or concrete item classes.
"""

from collections.abc import Iterable
from typing import Optional, cast
from uuid import UUID

from dnd.blocks.appearance import Appearance
from dnd.blocks.base_item import BaseItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeBinding,
)
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import Tile
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.content.descriptors import (
    ContentPresentation,
    compute_safe_content_presentation_hash,
)
from dnd.core.gridmap import GridMap
from dnd.core.item_types import ItemPresentationKind, ItemPresentationState
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.spatial_effects import SpatialEffect
from server.world_contracts import (
    APIAppearance,
    APICombatant,
    APIContentRefSnapshot,
    APIConditionSummary,
    APIDirectionalBlockMap,
    DirectionalStructuralEdgeMap,
    APIEncounter,
    APIEntitySummary,
    APIEquipmentOverview,
    APIEquipmentSlot,
    APIGrid,
    APITraversalConnector,
    APITraversalConnectorEndpoint,
    APIItemRuntimeRecipeRefSnapshot,
    APIItemSummary,
    APIRecipePresetRefSnapshot,
    APISpatialEffectPresentation,
    APISpatialEffectSummary,
    APITile,
    SafeContentPresentationRef,
    StructuralEdgeAppearance,
    StructuralEdgeKind,
)


_EQUIPMENT_SLOT_ROWS = (
    ("weapon_melee_main", "weapon", "weapon_melee_main"),
    ("weapon_melee_off", "weapon", "weapon_melee_off"),
    ("weapon_ranged_main", "weapon", "weapon_ranged_main"),
    ("weapon_ranged_off", "weapon", "weapon_ranged_off"),
    ("helmet", "armor", "helmet"),
    ("body_armor", "armor", "body_armor"),
    ("gauntlets", "armor", "gauntlets"),
    ("greaves", "armor", "greaves"),
    ("boots", "armor", "boots"),
    ("amulet", "armor", "amulet"),
    ("cloak", "armor", "cloak"),
    ("ring_left", "ring", "ring_left"),
    ("ring_right", "ring", "ring_right"),
)

_CARDINAL_DIRECTION_DELTAS: dict[str, tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
}
_OPPOSITE_DIRECTION: dict[str, str] = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}


def _resolve_bound_item_presentation(
    item: BaseItem,
) -> tuple[ItemPresentationState, ItemRuntimeBinding, ContentPresentation]:
    """Resolve one runtime item to its exact authenticated safe presentation."""
    state = item.to_item_presentation_state()
    binding = ITEM_RUNTIME_BINDINGS.require(item.uuid)
    if state.content_ref is None:
        raise ValueError(
            f"Player-visible item {item.uuid} has no authored content reference",
        )
    if state.content_ref.model_dump(mode="json") != binding.recipe.ref.model_dump(
        mode="json",
    ):
        raise ValueError(
            f"Player-visible item {item.uuid} content reference disagrees with "
            "its runtime binding",
        )
    loaded = SERVER_CONTENT_SYSTEM_RUNTIME.require()
    if binding.content_set_digest != loaded.content_set_digest:
        raise ValueError(
            f"Player-visible item {item.uuid} belongs to a different content set",
        )
    if binding.recipe_preset_ref is not None:
        preset = loaded.registry.resolve_recipe_preset(
            binding.recipe_preset_ref,
        )
        if preset.recipe != binding.recipe:
            raise ValueError(
                f"Player-visible item {item.uuid} preset disagrees with its "
                "runtime recipe",
            )
        presentation = preset.descriptor.presentation
    else:
        declaration = loaded.registry.resolve_definition(binding.recipe.ref)
        presentation = declaration.descriptor.presentation
    return state, binding, presentation


def project_safe_item_presentation_ref(
    item: BaseItem,
) -> SafeContentPresentationRef:
    """Project only the mechanics-free catalog identity for one visible item."""
    _, _, presentation = _resolve_bound_item_presentation(item)
    return SafeContentPresentationRef(
        presentation_contract_hash=compute_safe_content_presentation_hash(
            presentation,
        ),
    )


def project_item_summary(item: BaseItem) -> APIItemSummary:
    """Project one controlled item with exact reconstruction identity."""
    state, binding, presentation = _resolve_bound_item_presentation(item)
    content_ref = APIContentRefSnapshot.model_validate(
        binding.recipe.ref.model_dump(mode="python"),
    )
    is_usable = state.item_kind is ItemPresentationKind.USABLE
    return APIItemSummary(
        uuid=str(state.item_uuid),
        content_ref=content_ref,
        recipe_ref=APIItemRuntimeRecipeRefSnapshot(
            recipe_digest=binding.recipe.recipe_digest,
            preset_ref=(
                APIRecipePresetRefSnapshot.model_validate(
                    binding.recipe_preset_ref.model_dump(mode="python"),
                )
                if binding.recipe_preset_ref is not None
                else None
            ),
        ),
        safe_presentation_ref=SafeContentPresentationRef(
            presentation_contract_hash=compute_safe_content_presentation_hash(
                presentation,
            ),
        ),
        name=state.name,
        description=state.description,
        item_type=state.item_kind.value,
        rarity=state.rarity.value,
        weight=state.weight,
        is_equipped=item.is_equipped,
        equipped_slot=item.equipped_slot,
        visual_item_name=state.visual_item_name,
        visual_variant_id=state.visual_variant_id,
        equipped_visual_policy=state.equipped_visual_policy.value,
        damage_dice=state.damage_dice,
        damage_type=state.damage_type,
        weapon_properties=list(state.weapon_properties),
        armor_type=state.armor_type,
        armor_ac=state.armor_ac,
        shield_ac_bonus=state.shield_ac_bonus,
        charges=state.charges if is_usable else None,
        max_charges=state.max_charges if is_usable else None,
        stack_count=state.stack_count if is_usable else None,
        is_consumable=state.is_consumable,
    )


def project_equipment_overview(entity: Entity) -> APIEquipmentOverview:
    """Project one entity's complete controlled-equipment reducer seed."""
    slots: list[APIEquipmentSlot] = []
    for slot_name, default_type, attribute_name in _EQUIPMENT_SLOT_ROWS:
        item = getattr(entity.equipment, attribute_name)
        item_summary = project_item_summary(item) if item is not None else None
        slot_type = default_type
        if (
            item_summary is not None
            and item_summary.item_type in {"shield", "weapon"}
        ):
            slot_type = item_summary.item_type
        slots.append(
            APIEquipmentSlot(
                slot=slot_name,
                slot_type=slot_type,
                item=item_summary,
            )
        )
    return APIEquipmentOverview(
        slots=slots,
        active_weapon_set=entity.equipment.active_weapon_set,
        ac=entity.ac_bonus().normalized_score,
        inventory=[
            project_item_summary(item)
            for item in entity.inventory.items.values()
        ],
    )


def project_appearance(appearance: Appearance) -> APIAppearance:
    """Project the gameplay-inert renderer identity owned by an entity."""
    return APIAppearance(
        portrait_key=appearance.portrait_key,
        presentation_kind=appearance.presentation_kind,
        visual_scale=appearance.visual_scale,
        visual_scale_x=appearance.visual_scale_x,
        placeholder_tint=appearance.placeholder_tint,
        body_category=appearance.body_category,
        skin_tint=appearance.skin_tint,
        head_category=appearance.head_category,
        hair_tint=appearance.hair_tint,
        has_beard=appearance.has_beard,
        beard_tint=appearance.beard_tint,
    )


def project_condition_summary(condition: BaseCondition) -> APIConditionSummary:
    """Project one live condition without exposing private engine ownership."""
    binding = condition.behavior_binding
    if binding is None:
        raise ValueError(
            "Player-visible condition has no exact authored content binding: "
            f"{type(condition).__module__}.{type(condition).__qualname__}",
        )
    remaining_rounds = (
        cast(int, condition.duration.duration)
        if condition.duration.duration_type is DurationType.ROUNDS
        else None
    )
    return APIConditionSummary(
        content_ref=APIContentRefSnapshot.model_validate(
            binding.definition_ref.model_dump(mode="python"),
        ),
        semantic_key=condition.get_semantic_key(),
        name=condition.name or "",
        description=condition.description,
        category=condition.condition_category.value,
        duration_type=condition.duration.duration_type.value,
        remaining_rounds=remaining_rounds,
    )


def _project_public_condition_details(
    conditions: Iterable[BaseCondition],
) -> list[APIConditionSummary]:
    """Filter and deterministically order public condition presentation."""
    details = [
        project_condition_summary(condition)
        for condition in conditions
        if condition.condition_category is not ConditionCategory.INTERNAL
    ]
    return sorted(details, key=lambda detail: (detail.name, detail.semantic_key))


def _spatial_conditions_at(
    grid: GridMap,
    position: tuple[int, int],
) -> list[BaseCondition]:
    """Return only genuine tile-owned conditions affecting one cell."""
    tile = grid.get_tile(*position)
    return list(tile.active_conditions.values()) if tile is not None else []


def project_spatial_effect_summary(
    effect: SpatialEffect,
) -> APISpatialEffectSummary:
    """Project one observed effect through its authenticated cold descriptor."""
    declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.resolve_definition(
        effect.content_ref,
    )
    definition = declaration.spatial_effect_definition
    if definition is None:
        raise ValueError(
            f"Observed spatial effect {effect.uuid} has no authored definition",
        )
    if (
        effect.layer is not definition.layer
        or effect.occupancy_policy is not definition.occupancy_policy
        or effect.anchor_kind is not definition.anchor_kind
        or effect.blocking_policy is not definition.blocking_policy
    ):
        raise ValueError(
            f"Observed spatial effect {effect.uuid} disagrees with its "
            "authored layer contract",
        )
    presentation = declaration.descriptor.presentation
    return APISpatialEffectSummary(
        uuid=str(effect.uuid),
        content_ref=APIContentRefSnapshot.model_validate(
            effect.content_ref.model_dump(mode="python"),
        ),
        layer=effect.layer.value,
        anchor_kind=effect.anchor_kind.value,
        safe_presentation_ref=SafeContentPresentationRef(
            presentation_contract_hash=compute_safe_content_presentation_hash(
                presentation,
            ),
        ),
        presentation=APISpatialEffectPresentation(
            sprite_key=presentation.sprite_key,
            visual_variant_key=presentation.visual_variant_key,
            tint_rgb=presentation.tint_rgb,
            vfx_profile=presentation.vfx_profile,
            audio_key=presentation.audio_key,
        ),
    )


def _project_spatial_effects_at(
    grid: GridMap,
    position: tuple[int, int],
    *,
    observer_perceptions: tuple[int, ...] | None,
) -> list[APISpatialEffectSummary]:
    """Project effects disclosed by at least one authorized observer."""
    visible: list[SpatialEffect] = []
    for block in grid.get_spatial_effect_blocks_at(position):
        if not isinstance(block, SpatialEffect):
            raise TypeError("Grid spatial-effect index contains a non-effect block")
        if observer_perceptions is not None:
            controllers = tuple(block.active_conditions.values())
            if controllers and not any(
                controller.condition_stealth_dc is None
                or controller.condition_stealth_dc < perception
                for controller in controllers
                for perception in observer_perceptions
            ):
                continue
        visible.append(block)
    return [
        project_spatial_effect_summary(effect)
        for effect in sorted(
            visible,
            key=lambda row: (
                row.layer.value,
                row.content_ref.identity_key,
                str(row.uuid),
            ),
        )
    ]


def project_entity_summary(entity: Entity) -> APIEntitySummary:
    """Project one renderer-complete entity summary."""
    if entity.content_ref is None:
        raise ValueError(
            "Player-visible entity has no exact authored creature identity: "
            f"{entity.uuid}",
        )
    constitution_modifier = (
        entity.ability_scores
        .get_ability("constitution")
        .get_combined_values()
        .normalized_score
    )
    max_hp = (
        entity.health.get_max_hit_dices_points(constitution_modifier)
        + entity.health.max_hit_points_bonus.score
    )
    condition_details = _project_public_condition_details(
        entity.active_conditions.values()
    )
    return APIEntitySummary(
        uuid=str(entity.uuid),
        content_ref=APIContentRefSnapshot.model_validate(
            entity.content_ref.model_dump(mode="python"),
        ),
        species_ref=(
            APIContentRefSnapshot.model_validate(
                entity.character_species_ref.model_dump(mode="python"),
            )
            if entity.character_species_ref is not None
            else None
        ),
        species_variant_ref=(
            APIContentRefSnapshot.model_validate(
                entity.character_species_variant_ref.model_dump(
                    mode="python",
                ),
            )
            if entity.character_species_variant_ref is not None
            else None
        ),
        background_ref=(
            APIContentRefSnapshot.model_validate(
                entity.character_background_ref.model_dump(mode="python"),
            )
            if entity.character_background_ref is not None
            else None
        ),
        name=entity.name,
        position=entity.position,
        hp=entity.get_hp(),
        max_hp=max_hp,
        ac=entity.ac_bonus().normalized_score,
        conditions=[detail.name for detail in condition_details],
        condition_details=condition_details,
        life_state=entity.health.life_state,
        faction=entity.faction,
        creature_type=entity.creature_type.value,
        size=entity.size.value,
        appearance=project_appearance(entity.appearance),
    )


def project_grid(
    grid: GridMap,
    requesting_entity_uuid: Optional[UUID] = None,
) -> APIGrid:
    """Project grid terrain under an optional observer's hazard knowledge."""
    observer_perception = 0
    connector_observer: Optional[Entity] = None
    if requesting_entity_uuid is not None:
        connector_observer = Entity.get(requesting_entity_uuid)
        if connector_observer is None:
            raise ValueError("subjective grid projection requires a known entity")
        observer_perception = connector_observer.get_passive_perception()

    tiles: list[APITile] = []
    for (x, y), tile in grid.get_all_tiles().items():
        if connector_observer is not None:
            if not connector_observer.senses.visible.get((x, y), False):
                continue
            tiles.append(
                project_observed_tile(
                    grid,
                    (x, y),
                    (connector_observer.uuid,),
                )
            )
            continue
        walking_cost = int(tile.walking_cost.normalized_score)
        condition_details = _project_public_condition_details(
            condition
            for condition in _spatial_conditions_at(grid, (x, y))
            if (
                condition.condition_stealth_dc is None
                or condition.condition_stealth_dc < observer_perception
            )
        )
        spatial_effects = _project_spatial_effects_at(
            grid,
            (x, y),
            observer_perceptions=(
                (observer_perception,)
                if requesting_entity_uuid is not None
                else None
            ),
        )
        tiles.append(
            APITile(
                x=x,
                y=y,
                visual_key=tile.sprite_name or "floor.png",
                walkable=tile.walkable,
                visible=tile.visible,
                name=tile.name,
                walking_cost=walking_cost,
                elevation_steps=tile.height,
                elevation_surface_kind=tile.elevation_surface_kind,
                slope_axis=tile.slope_axis,
                is_hazardous=grid.is_position_hazardous_for(
                    x,
                    y,
                    requesting_entity_uuid,
                ),
                conditions=[detail.name for detail in condition_details],
                condition_details=condition_details,
                spatial_effects=spatial_effects,
                light_level=tile.resolved_light_level.value,
                directional_blocks_movement=_project_directional_blocks(
                    tile,
                    "movement",
                ),
                directional_blocks_vision=_project_directional_blocks(tile, "vision"),
                directional_blocks_light=_project_directional_blocks(tile, "light"),
                directional_blocks_propagation=_project_directional_blocks(
                    tile,
                    "propagation",
                ),
                directional_structural_edges=_project_structural_edges(
                    grid,
                    (x, y),
                ),
            )
        )
    connectors: list[APITraversalConnector] = []
    for connector in grid.get_all_connectors():
        if connector_observer is not None and not all(
            connector_observer.senses.visible.get(endpoint.position, False)
            for endpoint in connector.endpoints
        ):
            continue
        connectors.append(APITraversalConnector(
            uuid=str(connector.uuid),
            authored_id=connector.authored_id,
            kind=connector.kind,
            presentation_key=connector.presentation_key,
            endpoints=(
                APITraversalConnectorEndpoint(
                    position=connector.endpoints[0].position,
                    support_tile_uuid=str(connector.endpoints[0].support_tile_uuid),
                    elevation_feet=connector.endpoints[0].elevation_feet,
                ),
                APITraversalConnectorEndpoint(
                    position=connector.endpoints[1].position,
                    support_tile_uuid=str(connector.endpoints[1].support_tile_uuid),
                    elevation_feet=connector.endpoints[1].elevation_feet,
                ),
            ),
            movement_cost_feet=connector.movement_cost_feet,
            action_cost_type=connector.action_cost_type,
            action_cost_amount=connector.action_cost_amount,
            bidirectional=connector.bidirectional,
            enabled=connector.enabled,
            provocation_policy=connector.provocation_policy,
            revision=connector.revision,
            objective_digest=connector.objective_digest,
        ))
    min_x, min_y, max_x, max_y = grid.bounds
    return APIGrid(
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        tiles=tiles,
        connectors=connectors,
    )


def project_observed_tile(
    grid: GridMap,
    position: tuple[int, int],
    observer_uuids: tuple[UUID, ...],
) -> APITile:
    """Project one currently observed cell under an explicit knowledge union."""
    if not observer_uuids:
        raise ValueError("observed tile projection requires at least one observer")
    tile = grid.get_tile(*position)
    if tile is None:
        raise ValueError(f"observed tile does not exist at {position}")

    observer_perceptions: list[int] = []
    directional_rows: list[dict[str, dict[str, bool]]] = []
    structural_rows: list[DirectionalStructuralEdgeMap] = []
    for observer_uuid in observer_uuids:
        observer = BaseBlock.get(observer_uuid)
        if observer is None:
            raise ValueError("observed tile projection requires known observers")
        observer_perceptions.append(observer.get_passive_perception())
        directional_row = grid.get_subjective_directional_block_map(
            position,
            observer_uuid,
        )
        structural_row = _project_structural_edges(
            grid,
            position,
            requesting_entity_uuid=observer_uuid,
        )
        # Vision owns a physical boundary, not just the tile-local half that
        # happened to author it. If the adjacent tile's reciprocal side stops
        # sight, the currently visible side must still carry that edge;
        # otherwise the blocker makes its own renderer fact impossible to
        # observe. The subjective map filters imperceivable derived blockers.
        for direction, (dx, dy) in _CARDINAL_DIRECTION_DELTAS.items():
            neighbor_position = (position[0] + dx, position[1] + dy)
            neighbor_row = grid.get_subjective_directional_block_map(
                neighbor_position,
                observer_uuid,
            )
            if neighbor_row["vision"][_OPPOSITE_DIRECTION[direction]]:
                directional_row["vision"][direction] = True
                neighbor_edges = _project_structural_edges(
                    grid,
                    neighbor_position,
                    requesting_entity_uuid=observer_uuid,
                )
                reciprocal = getattr(
                    neighbor_edges,
                    _OPPOSITE_DIRECTION[direction],
                )
                if reciprocal is not None:
                    structural_row = structural_row.model_copy(
                        update={
                            direction: _prefer_structural_edge(
                                getattr(structural_row, direction),
                                reciprocal,
                            )
                        }
                    )
        directional_rows.append(directional_row)
        structural_rows.append(structural_row)

    condition_details = _project_public_condition_details(
        condition
        for condition in _spatial_conditions_at(grid, position)
        if any(
            condition.condition_stealth_dc is None
            or condition.condition_stealth_dc < observer_perception
            for observer_perception in observer_perceptions
        )
    )
    spatial_effects = _project_spatial_effects_at(
        grid,
        position,
        observer_perceptions=tuple(observer_perceptions),
    )

    def merged_directional(channel: str) -> APIDirectionalBlockMap:
        return APIDirectionalBlockMap(
            north=any(row[channel]["north"] for row in directional_rows),
            south=any(row[channel]["south"] for row in directional_rows),
            east=any(row[channel]["east"] for row in directional_rows),
            west=any(row[channel]["west"] for row in directional_rows),
        )

    def merged_structural_edges() -> DirectionalStructuralEdgeMap:
        merged: dict[str, StructuralEdgeAppearance | None] = {}
        for direction in _CARDINAL_DIRECTION_DELTAS:
            edge: StructuralEdgeAppearance | None = None
            for row in structural_rows:
                edge = _prefer_structural_edge(edge, getattr(row, direction))
            merged[direction] = edge
        return DirectionalStructuralEdgeMap(**merged)

    walking_cost = int(tile.walking_cost.normalized_score)
    return APITile(
        x=position[0],
        y=position[1],
        visual_key=tile.sprite_name or "floor.png",
        walkable=tile.walkable,
        visible=True,
        name=tile.name,
        walking_cost=walking_cost,
        elevation_steps=tile.height,
        elevation_surface_kind=tile.elevation_surface_kind,
        slope_axis=tile.slope_axis,
        is_hazardous=any(
            grid.is_position_hazardous_for(*position, observer_uuid)
            for observer_uuid in observer_uuids
        ),
        conditions=[detail.name for detail in condition_details],
        condition_details=condition_details,
        spatial_effects=spatial_effects,
        light_level=tile.resolved_light_level.value,
        directional_blocks_movement=merged_directional("movement"),
        directional_blocks_vision=merged_directional("vision"),
        directional_blocks_light=merged_directional("light"),
        directional_blocks_propagation=merged_directional("propagation"),
        directional_structural_edges=merged_structural_edges(),
    )


def project_encounter(
    encounter: Encounter,
    entities: Optional[Iterable[Entity]] = None,
) -> APIEncounter:
    """Project objective initiative state using supplied actors when available."""
    supplied_entities = (
        {entity.uuid: entity for entity in entities}
        if entities is not None
        else None
    )
    combatants: list[APICombatant] = []
    for entity_uuid in encounter.initiative_order:
        entity = (
            supplied_entities.get(entity_uuid)
            if supplied_entities is not None
            else Entity.get(entity_uuid)
        )
        life_state = entity.health.life_state if entity is not None else None
        combatants.append(
            APICombatant(
                uuid=str(entity_uuid),
                name=entity.name if entity is not None else "Unknown",
                initiative=encounter.combatants[entity_uuid].initiative_total,
                life_state=life_state,
            )
        )
    current_entity_uuid: Optional[str] = None
    if (
        encounter.initiative_order
        and encounter.current_turn_index < len(encounter.initiative_order)
    ):
        current_entity_uuid = str(
            encounter.initiative_order[encounter.current_turn_index]
        )
    return APIEncounter(
        uuid=str(encounter.uuid),
        name=encounter.name,
        state=encounter.state.value,
        round_number=encounter.round_number,
        current_turn_index=encounter.current_turn_index,
        current_entity_uuid=current_entity_uuid,
        initiative_order=combatants,
    )


def _project_directional_blocks(tile: Tile, channel: str) -> APIDirectionalBlockMap:
    """Project one tile's directional allowance function as blocking flags."""
    return APIDirectionalBlockMap(
        north=not tile.allows_direction("north", channel),
        south=not tile.allows_direction("south", channel),
        east=not tile.allows_direction("east", channel),
        west=not tile.allows_direction("west", channel),
    )


def _project_structural_edges(
    grid: GridMap,
    position: tuple[int, int],
    requesting_entity_uuid: Optional[UUID] = None,
) -> DirectionalStructuralEdgeMap:
    """Project only privacy-safe visual identity for tile-local structures."""

    tile = grid.get_tile(*position)
    if tile is None:
        return DirectionalStructuralEdgeMap()

    edges: dict[str, StructuralEdgeAppearance | None] = {
        direction: None for direction in _CARDINAL_DIRECTION_DELTAS
    }
    for direction in _CARDINAL_DIRECTION_DELTAS:
        if any(
            not tile.allows_direction(
                direction,
                channel,
                include_derived=False,
            )
            for channel in ("movement", "vision", "light", "propagation")
        ):
            edges[direction] = StructuralEdgeAppearance(
                kind=StructuralEdgeKind.WALL,
            )

    for object_uuid in sorted(grid.get_objects_at(position), key=str):
        block = BaseBlock.get(object_uuid)
        if not isinstance(block, BaseItem):
            continue
        if (
            requesting_entity_uuid is not None
            and not block.is_perceivable_by(requesting_entity_uuid)
        ):
            continue
        structure = block.get_directional_structure_state()
        if structure is None:
            continue
        directions = structure.blocked_directions
        channels = structure.blocked_channels
        if not directions or not channels:
            continue
        is_open = block.get_spatial_open_state()
        appearance = StructuralEdgeAppearance(
            kind=(
                StructuralEdgeKind.DOOR
                if is_open is not None
                else StructuralEdgeKind.WALL
            ),
            is_open=is_open,
        )
        for direction in directions:
            if direction not in _CARDINAL_DIRECTION_DELTAS:
                continue
            edges[direction] = _prefer_structural_edge(
                edges[direction],
                appearance,
            )
    return DirectionalStructuralEdgeMap(**edges)


def _prefer_structural_edge(
    current: StructuralEdgeAppearance | None,
    candidate: StructuralEdgeAppearance | None,
) -> StructuralEdgeAppearance | None:
    """Choose the most specific safe appearance independently of iteration order."""

    if candidate is None:
        return current
    if current is None or candidate == current:
        return candidate
    if (
        current.kind is StructuralEdgeKind.DOOR
        and candidate.kind is StructuralEdgeKind.DOOR
    ):
        # An impossible-but-defensive observer disagreement must not make the
        # union depend on observer iteration order. Closed is conservative: it
        # never grants traversal or suppresses an observed blocker.
        return StructuralEdgeAppearance(
            kind=StructuralEdgeKind.DOOR,
            is_open=False,
        )
    if current.kind is StructuralEdgeKind.DOOR:
        return current
    if candidate.kind is StructuralEdgeKind.DOOR:
        return candidate
    return current


__all__ = [
    "project_appearance",
    "project_encounter",
    "project_entity_summary",
    "project_equipment_overview",
    "project_grid",
    "project_item_summary",
    "project_observed_tile",
    "project_safe_item_presentation_ref",
]
