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
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.gridmap import GridMap
from dnd.core.item_types import ItemPresentationKind
from dnd.core.life_types import LifeState
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.world_contracts import (
    APIAppearance,
    APICombatant,
    APIConditionSummary,
    APIDirectionalBlockMap,
    DirectionalStructuralEdgeMap,
    APIEncounter,
    APIEntitySummary,
    APIEquipmentOverview,
    APIEquipmentSlot,
    APIGrid,
    APIItemSummary,
    APITile,
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


def project_item_summary(item: BaseItem) -> APIItemSummary:
    """Project one item from its engine-owned cold presentation facts."""
    state = item.to_item_presentation_state()
    is_usable = state.item_kind is ItemPresentationKind.USABLE
    return APIItemSummary(
        uuid=str(state.item_uuid),
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
    remaining_rounds = (
        cast(int, condition.duration.duration)
        if condition.duration.duration_type is DurationType.ROUNDS
        else None
    )
    return APIConditionSummary(
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


def project_entity_summary(entity: Entity) -> APIEntitySummary:
    """Project one renderer-complete entity summary."""
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
        name=entity.name,
        position=entity.position,
        hp=entity.get_hp(),
        max_hp=max_hp,
        ac=entity.ac_bonus().normalized_score,
        conditions=[detail.name for detail in condition_details],
        condition_details=condition_details,
        life_state=entity.health.life_state,
        is_dead=entity.health.life_state is LifeState.DEAD,
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
    if requesting_entity_uuid is not None:
        observer = BaseBlock.get(requesting_entity_uuid)
        if observer is not None:
            observer_perception = observer.get_passive_perception()

    tiles: list[APITile] = []
    for (x, y), tile in grid._tiles.items():
        walking_cost = (
            int(tile.walking_cost.normalized_score)
            if hasattr(tile, "walking_cost")
            else 1
        )
        condition_details = _project_public_condition_details(
            condition
            for condition in tile.active_conditions.values()
            if (
                condition.condition_stealth_dc is None
                or condition.condition_stealth_dc < observer_perception
            )
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
                is_hazardous=grid.is_position_hazardous_for(
                    x,
                    y,
                    requesting_entity_uuid,
                ),
                conditions=[detail.name for detail in condition_details],
                condition_details=condition_details,
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
    min_x, min_y, max_x, max_y = grid.bounds
    return APIGrid(
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
        tiles=tiles,
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
        for condition in tile.active_conditions.values()
        if any(
            condition.condition_stealth_dc is None
            or condition.condition_stealth_dc < observer_perception
            for observer_perception in observer_perceptions
        )
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

    walking_cost = (
        int(tile.walking_cost.normalized_score)
        if hasattr(tile, "walking_cost")
        else 1
    )
    return APITile(
        x=position[0],
        y=position[1],
        visual_key=tile.sprite_name or "floor.png",
        walkable=tile.walkable,
        visible=True,
        name=tile.name,
        walking_cost=walking_cost,
        is_hazardous=any(
            grid.is_position_hazardous_for(*position, observer_uuid)
            for observer_uuid in observer_uuids
        ),
        conditions=[detail.name for detail in condition_details],
        condition_details=condition_details,
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
                is_dead=life_state is LifeState.DEAD,
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


def _project_directional_blocks(tile: object, channel: str) -> APIDirectionalBlockMap:
    """Project one tile's directional allowance function as blocking flags."""
    allows_direction = getattr(tile, "allows_direction")
    return APIDirectionalBlockMap(
        north=not allows_direction("north", channel),
        south=not allows_direction("south", channel),
        east=not allows_direction("east", channel),
        west=not allows_direction("west", channel),
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
        directions = cast(
            tuple[str, ...],
            tuple(getattr(block, "blocked_directions", ())),
        )
        channels = cast(
            tuple[str, ...],
            tuple(getattr(block, "blocked_channels", ())),
        )
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
]
