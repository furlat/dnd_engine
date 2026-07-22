"""Pydantic DTOs for REST API serialization."""

from uuid import UUID
from pydantic import BaseModel, Field, JsonValue, RootModel, SerializeAsAny, field_serializer
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.equipment import Armor, Shield, Weapon
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import AvailableActionsResult, AvailableHandlerInfo
from dnd.core.base_conditions import ConditionCategory
from dnd.core.combat_log import CombatLogEntry
from dnd.core.events import Event
from dnd.core.gridmap import GridMap
from dnd.core.senses import SenseMode
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.scenarios.evaluation.compatibility import CompatibilityReport
from dnd.scenarios.evaluation.models import (
    BattlefieldSpec,
    DeploymentSpec,
    LegacyScenarioRecipe,
    SideConfigurationSpec,
)
from server.event_contract import serialize_event


class ServerCapabilitiesResponse(BaseModel):
    """Describe the server topology available to a connecting game client."""

    server_mode: Literal["standalone", "gateway"] = Field(
        description="Active deployment topology exposed by this HTTP origin."
    )
    game_directory_enabled: bool = Field(
        description="Whether hosted-game discovery and attachment routes are available."
    )
    persistent_game_history: bool = Field(
        description="Whether completed game metadata and summaries persist across restarts."
    )
    isolated_game_workers: bool = Field(
        description="Whether each hosted game executes in an isolated hot worker process."
    )


class APIItemSummary(BaseModel):
    """Expose lightweight item metadata for inventory and equipment views.

    Attributes:
        uuid: Stable item UUID serialized as text.
        name: Display name of the item.
        description: Optional player-facing item description.
        item_type: API category for the concrete item kind.
        rarity: Item rarity value.
        weight: Item weight in pounds.
        is_equipped: Whether the item is currently equipped.
        equipped_slot: Equipment slot name when the item is equipped.
        visual_item_name: Effective renderer registry key for the item.
        visual_variant_id: Renderer variant identifier for the item, if any.
        equipped_visual_policy: Whether the item contributes a separate actor layer.
        damage_dice: Weapon damage dice such as `1d8` or `2d6`.
        damage_type: Weapon damage type.
        weapon_properties: Weapon property names.
        armor_type: Armor category such as light, medium, or heavy.
        armor_ac: Base armor class value from worn armor.
        shield_ac_bonus: Armor class bonus granted by a shield.
        charges: Current usable-item charges, with -1 meaning unlimited.
        max_charges: Maximum usable-item charges.
        stack_count: Number of items represented by this stack.
        is_consumable: Whether use consumes the item or stack.
    """

    uuid: str = Field(description="Stable item UUID serialized as text.")
    name: str = Field(description="Display name of the item.")
    description: Optional[str] = Field(default=None, description="Optional player-facing item description.")
    item_type: str = Field(description="API category for the concrete item kind.")
    rarity: str = Field(description="Item rarity value.")
    weight: float = Field(description="Item weight in pounds.")
    is_equipped: bool = Field(description="Whether the item is currently equipped.")
    equipped_slot: Optional[str] = Field(default=None, description="Equipment slot name when the item is equipped.")
    visual_item_name: str = Field(description="Effective renderer registry key for the item.")
    visual_variant_id: Optional[str] = Field(default=None, description="Renderer variant identifier for the item, if any.")
    equipped_visual_policy: Literal["visible", "hidden"] = Field(description="Whether the equipped item contributes a separate actor layer.")
    damage_dice: Optional[str] = Field(default=None, description="Weapon damage dice such as 1d8 or 2d6.")
    damage_type: Optional[str] = Field(default=None, description="Weapon damage type.")
    weapon_properties: List[str] = Field(default_factory=list, description="Weapon property names.")
    armor_type: Optional[str] = Field(default=None, description="Armor category such as light, medium, or heavy.")
    armor_ac: Optional[int] = Field(default=None, description="Base armor class value from worn armor.")
    shield_ac_bonus: Optional[int] = Field(default=None, description="Armor class bonus granted by a shield.")
    charges: Optional[int] = Field(default=None, description="Current usable-item charges, with -1 meaning unlimited.")
    max_charges: Optional[int] = Field(default=None, description="Maximum usable-item charges.")
    stack_count: Optional[int] = Field(default=None, description="Number of items represented by this stack.")
    is_consumable: bool = Field(default=False, description="Whether use consumes the item or stack.")

    @classmethod
    def create(cls, item: BaseItem) -> 'APIItemSummary':
        if isinstance(item, Weapon):
            item_type = "weapon"
        elif isinstance(item, Shield):
            item_type = "shield"
        elif isinstance(item, Armor):
            item_type = "armor"
        elif isinstance(item, UsableItem):
            item_type = "usable"
        else:
            item_type = "item"

        data: Dict[str, Any] = {
            "uuid": str(item.uuid),
            "name": item.name,
            "description": item.description,
            "item_type": item_type,
            "rarity": item.rarity.value,
            "weight": item.weight,
            "is_equipped": item.is_equipped,
            "equipped_slot": item.equipped_slot,
            "visual_item_name": item.visual_item_name or item.name,
            "visual_variant_id": item.visual_variant_id,
            "equipped_visual_policy": item.equipped_visual_policy.value,
        }

        if isinstance(item, Weapon):
            dice_str = f"{item.dice_numbers}d{item.damage_dice}"
            data["damage_dice"] = dice_str
            data["damage_type"] = item.damage_type.value
            data["weapon_properties"] = [p.value for p in item.properties]

        if isinstance(item, Armor):
            data["armor_type"] = item.type.value
            data["armor_ac"] = item.ac.score

        if isinstance(item, Shield):
            data["shield_ac_bonus"] = item.ac_bonus.score

        if isinstance(item, UsableItem):
            data["charges"] = item.charges
            data["max_charges"] = item.max_charges
            data["stack_count"] = item.stack_count
            data["is_consumable"] = item.is_consumable

        return cls(**data)


class APIEquipmentSlot(BaseModel):
    """Expose one equipment slot and its current item.

    Attributes:
        slot: Stable API slot name.
        slot_type: Slot category for client grouping.
        item: Equipped item summary when the slot is occupied.
    """

    slot: str = Field(description="Stable API slot name.")
    slot_type: str = Field(description="Slot category for client grouping.")
    item: Optional[APIItemSummary] = Field(default=None, description="Equipped item summary when the slot is occupied.")


class APIEquipmentOverview(BaseModel):
    """Expose equipped slots, armor class, and carried inventory.

    Attributes:
        slots: Equipment slots in stable display order.
        ac: Current armor class after equipment and modifiers.
        inventory: Unequipped inventory item summaries.
    """

    slots: List[APIEquipmentSlot] = Field(description="Equipment slots in stable display order.")
    ac: int = Field(description="Current armor class after equipment and modifiers.")
    inventory: List[APIItemSummary] = Field(description="Unequipped inventory item summaries.")

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEquipmentOverview':
        equipment = entity.equipment

        slot_defs: List[Tuple[str, str, Any]] = [
            ("weapon_melee_main", "weapon", equipment.weapon_melee_main),
            ("weapon_melee_off", "weapon", equipment.weapon_melee_off),
            ("weapon_ranged_main", "weapon", equipment.weapon_ranged_main),
            ("weapon_ranged_off", "weapon", equipment.weapon_ranged_off),
            ("helmet", "armor", equipment.helmet),
            ("body_armor", "armor", equipment.body_armor),
            ("gauntlets", "armor", equipment.gauntlets),
            ("greaves", "armor", equipment.greaves),
            ("boots", "armor", equipment.boots),
            ("amulet", "armor", equipment.amulet),
            ("cloak", "armor", equipment.cloak),
            ("ring_left", "ring", equipment.ring_left),
            ("ring_right", "ring", equipment.ring_right),
        ]

        slots = []
        for slot_name, slot_type, item in slot_defs:
            actual_type = slot_type
            if item is not None:
                if isinstance(item, Shield):
                    actual_type = "shield"
                elif isinstance(item, Weapon):
                    actual_type = "weapon"
            slots.append(APIEquipmentSlot(
                slot=slot_name,
                slot_type=actual_type,
                item=APIItemSummary.create(item) if item is not None else None,
            ))

        inv_items = [APIItemSummary.create(item) for item in entity.inventory.items.values()]

        return cls(
            slots=slots,
            ac=entity.ac_bonus().normalized_score,
            inventory=inv_items,
        )


class APIEquippableEntry(BaseModel):
    """One inventory item and the item it would displace from a slot."""

    item_uuid: str = Field(description="Inventory item UUID.")
    item_name: str = Field(description="Inventory item display name.")
    swap_item_name: Optional[str] = Field(default=None, description="Currently equipped item name, if any.")
    swap_item_uuid: Optional[str] = Field(default=None, description="Currently equipped item UUID, if any.")


class APIEquippableItems(BaseModel):
    """Inventory equipment candidates grouped by canonical slot name."""

    entity_uuid: str = Field(description="Entity whose inventory was inspected.")
    equippable: Dict[str, List[APIEquippableEntry]] = Field(
        default_factory=dict,
        description="Equipment candidates grouped by canonical slot name.",
    )


class APIEntityHandlersResponse(BaseModel):
    """Player-toggleable handlers registered on one entity."""

    entity_uuid: str = Field(description="Entity whose handlers were inspected.")
    handlers: List[AvailableHandlerInfo] = Field(description="Player-toggleable handler summaries.")


class ToggleHandlerResponse(BaseModel):
    """Result of changing one player-toggleable handler."""

    success: bool = Field(description="Whether the handler state changed.")
    handler_name: str = Field(description="Handler display name.")
    enabled: bool = Field(description="Resulting enabled state.")


class EquipRequest(BaseModel):
    """Request to equip an item from inventory.

    Attributes:
        session_id: Acting player session UUID.
        entity_uuid: Entity performing the equipment change.
        item_uuid: Inventory item to equip.
        slot: Optional explicit target slot; omitted means auto-assign.
    """

    session_id: str = Field(description="Acting player session UUID.")
    entity_uuid: str = Field(description="Entity performing the equipment change.")
    item_uuid: str = Field(description="Inventory item to equip.")
    slot: Optional[str] = Field(default=None, description="Optional explicit target slot; omitted means auto-assign.")


class UnequipRequest(BaseModel):
    """Request to unequip an item from a slot.

    Attributes:
        session_id: Acting player session UUID.
        entity_uuid: Entity performing the equipment change.
        slot: Equipment slot to clear.
    """

    session_id: str = Field(description="Acting player session UUID.")
    entity_uuid: str = Field(description="Entity performing the equipment change.")
    slot: str = Field(description="Equipment slot to clear.")


class EquipmentMutationResult(BaseModel):
    """Response after an equipment mutation request.

    Attributes:
        success: Whether the equipment command succeeded.
        message: Human-readable result summary.
        equipment: Equipment snapshot after the command.
        event_cursor_after: Event-history cursor after side effects.
        combat_log_cursor_after: Combat-log cursor after side effects.
    """

    success: bool = Field(description="Whether the equipment command succeeded.")
    message: str = Field(description="Human-readable result summary.")
    equipment: APIEquipmentOverview = Field(description="Equipment snapshot after the command.")
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after side effects.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after side effects.")


class APIAppearance(AppearanceConfig):
    """Public appearance projection using the engine's canonical configuration."""

    @classmethod
    def create(cls, appearance: Any) -> 'APIAppearance':
        return cls(
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


class APIConditionSummary(BaseModel):
    """Condition identity needed by game clients."""

    name: str = Field(description="Stable condition name.")
    category: str = Field(description="Condition category value.")


class APIActionEconomySnapshot(BaseModel):
    """Current primitive action-economy values for one entity."""

    actions: int = Field(description="Actions currently available.")
    bonus_actions: int = Field(description="Bonus actions currently available.")
    reactions: int = Field(description="Reactions currently available.")
    movement: int = Field(description="Movement currently available in feet.")


class APIAbilityScoresSnapshot(BaseModel):
    """Resolved ability scores for one entity."""

    strength: int = Field(description="Resolved Strength score.")
    dexterity: int = Field(description="Resolved Dexterity score.")
    constitution: int = Field(description="Resolved Constitution score.")
    intelligence: int = Field(description="Resolved Intelligence score.")
    wisdom: int = Field(description="Resolved Wisdom score.")
    charisma: int = Field(description="Resolved Charisma score.")


class APIEntitySummary(BaseModel):
    """Lightweight entity for list views and event-driven updates.

    Attributes:
        uuid: Stable entity UUID serialized as a string.
        name: Display name for the entity.
        position: Current grid position as an ``(x, y)`` pair.
        hp: Current hit points.
        max_hp: Maximum hit points after constitution and bonus HP.
        ac: Current armor class.
        conditions: Active condition names keyed on the entity.
        condition_details: Active condition names and categories for UI filters.
        is_dead: Whether the entity currently has no hit points.
        faction: Optional faction identifier used for ally/enemy grouping.
        creature_type: D&D creature taxonomy value.
        size: D&D rules size value.
        appearance: Passive renderer identity metadata.
    """

    uuid: str = Field(description="Stable entity UUID serialized as a string.")
    name: str = Field(description="Display name for the entity.")
    position: Tuple[int, int] = Field(description="Current grid position as an (x, y) pair.")
    hp: int = Field(description="Current hit points.")
    max_hp: int = Field(description="Maximum hit points after constitution and bonus HP.")
    ac: int = Field(description="Current armor class.")
    conditions: List[str] = Field(description="Active condition names keyed on the entity.")
    condition_details: List[APIConditionSummary] = Field(
        default_factory=list,
        description="Active condition names and categories for UI filters.",
    )
    is_dead: bool = Field(description="Whether the entity currently has no hit points.")
    faction: Optional[str] = Field(default=None, description="Optional faction identifier used for ally/enemy grouping.")
    creature_type: str = Field(description="D&D creature taxonomy value.")
    size: str = Field(description="D&D rules size value.")
    appearance: APIAppearance = Field(description="Passive renderer identity metadata.")

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntitySummary':
        con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = entity.health.get_max_hit_dices_points(con_mod) + entity.health.max_hit_points_bonus.score

        return cls(
            uuid=str(entity.uuid),
            name=entity.name,
            position=entity.position,
            hp=entity.get_hp(),
            max_hp=max_hp,
            ac=entity.ac_bonus().normalized_score,
            conditions=list(entity.active_conditions.keys()),
            condition_details=[
                APIConditionSummary(
                    name=c.name or type(c).__name__,
                    category=c.condition_category.value,
                )
                for c in entity.active_conditions.values()
            ],
            is_dead=not entity.has_hp,
            faction=entity.faction,
            creature_type=entity.creature_type.value,
            size=entity.size.value,
            appearance=APIAppearance.create(entity.appearance),
        )


class APIEntityFull(APIEntitySummary):
    """Full entity details for single-entity queries.

    Attributes:
        action_economy: Current action, bonus-action, reaction, and movement counts.
        ability_scores: Current ability score values keyed by ability name.
        weapon_name: Name of the equipped main-hand melee weapon, if any.
        equipment: Full equipment overview for the entity.
    """

    action_economy: APIActionEconomySnapshot = Field(
        description="Current action, bonus-action, reaction, and movement counts."
    )
    ability_scores: APIAbilityScoresSnapshot = Field(
        description="Current resolved ability scores."
    )
    weapon_name: Optional[str] = Field(default=None, description="Name of the equipped main-hand melee weapon, if any.")
    equipment: Optional[APIEquipmentOverview] = Field(default=None, description="Full equipment overview for the entity.")

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntityFull':
        con_mod = entity.ability_scores.get_ability("constitution").get_combined_values().normalized_score
        max_hp = entity.health.get_max_hit_dices_points(con_mod) + entity.health.max_hit_points_bonus.score

        weapon = entity.equipment.weapon_melee_main
        return cls(
            uuid=str(entity.uuid),
            name=entity.name,
            position=entity.position,
            hp=entity.get_hp(),
            max_hp=max_hp,
            ac=entity.ac_bonus().normalized_score,
            conditions=list(entity.active_conditions.keys()),
            condition_details=[
                APIConditionSummary(
                    name=c.name or type(c).__name__,
                    category=c.condition_category.value,
                )
                for c in entity.active_conditions.values()
            ],
            is_dead=not entity.has_hp,
            faction=entity.faction,
            creature_type=entity.creature_type.value,
            size=entity.size.value,
            appearance=APIAppearance.create(entity.appearance),
            action_economy=APIActionEconomySnapshot(
                actions=entity.action_economy.actions.normalized_score,
                bonus_actions=entity.action_economy.bonus_actions.normalized_score,
                reactions=entity.action_economy.reactions.normalized_score,
                movement=entity.action_economy.movement.normalized_score,
            ),
            ability_scores=APIAbilityScoresSnapshot(
                strength=entity.ability_scores.strength.ability_score.normalized_score,
                dexterity=entity.ability_scores.dexterity.ability_score.normalized_score,
                constitution=entity.ability_scores.constitution.ability_score.normalized_score,
                intelligence=entity.ability_scores.intelligence.ability_score.normalized_score,
                wisdom=entity.ability_scores.wisdom.ability_score.normalized_score,
                charisma=entity.ability_scores.charisma.ability_score.normalized_score,
            ),
            weapon_name=weapon.name if weapon else None,
            equipment=APIEquipmentOverview.create(entity),
        )


class APIDirectionalBlockMap(BaseModel):
    """Blocking flags for the four cardinal directions."""

    north: bool = Field(description="Whether passage toward north is blocked.")
    south: bool = Field(description="Whether passage toward south is blocked.")
    east: bool = Field(description="Whether passage toward east is blocked.")
    west: bool = Field(description="Whether passage toward west is blocked.")


class APITile(BaseModel):
    """Single public tile snapshot.

    Attributes:
        x: Tile x-coordinate.
        y: Tile y-coordinate.
        walkable: Whether the tile is passable before entity and object checks.
        visible: Whether the tile is visible in the current map view.
        name: Tile terrain name.
        walking_cost: Normalized movement cost for entering the tile.
        is_hazardous: Whether the tile is hazardous for the requesting entity.
        conditions: Public condition names visible on the tile.
        light_level: Resolved light level enum value.
        directional_blocks_movement: Directional movement blockers keyed by compass direction.
        directional_blocks_vision: Directional vision blockers keyed by compass direction.
        directional_blocks_light: Directional light blockers keyed by compass direction.
        directional_blocks_propagation: Directional propagation blockers keyed by compass direction.
    """

    x: int = Field(description="Tile x-coordinate.")
    y: int = Field(description="Tile y-coordinate.")
    walkable: bool = Field(description="Whether the tile is passable before entity and object checks.")
    visible: bool = Field(description="Whether the tile is visible in the current map view.")
    name: str = Field(default="Floor", description="Tile terrain name.")
    walking_cost: int = Field(default=1, description="Normalized movement cost for entering the tile.")
    is_hazardous: bool = Field(default=False, description="Whether the tile is hazardous for the requesting entity.")
    conditions: List[str] = Field(default_factory=list, description="Public condition names visible on the tile.")
    light_level: int = Field(default=3, description="Resolved light level enum value.")
    directional_blocks_movement: APIDirectionalBlockMap = Field(
        description="Directional movement blockers keyed by compass direction.",
    )
    directional_blocks_vision: APIDirectionalBlockMap = Field(
        description="Directional vision blockers keyed by compass direction.",
    )
    directional_blocks_light: APIDirectionalBlockMap = Field(
        description="Directional light blockers keyed by compass direction.",
    )
    directional_blocks_propagation: APIDirectionalBlockMap = Field(
        description="Directional propagation blockers keyed by compass direction.",
    )


class APIGrid(BaseModel):
    """Public grid snapshot.

    Attributes:
        min_x: Minimum x-coordinate included in the grid bounds.
        min_y: Minimum y-coordinate included in the grid bounds.
        max_x: Maximum x-coordinate included in the grid bounds.
        max_y: Maximum y-coordinate included in the grid bounds.
        tiles: Serialized tiles in the grid.
    """

    min_x: int = Field(description="Minimum x-coordinate included in the grid bounds.")
    min_y: int = Field(description="Minimum y-coordinate included in the grid bounds.")
    max_x: int = Field(description="Maximum x-coordinate included in the grid bounds.")
    max_y: int = Field(description="Maximum y-coordinate included in the grid bounds.")
    tiles: List[APITile] = Field(description="Serialized tiles in the grid.")

    @classmethod
    def create(cls, grid: GridMap, requesting_entity_uuid: Optional[UUID] = None) -> 'APIGrid':
        bounds = grid.bounds

        observer_perception = 0
        if requesting_entity_uuid:
            obs = BaseBlock.get(requesting_entity_uuid)
            if obs is not None:
                observer_perception = obs.get_passive_perception()

        tiles: List[APITile] = []
        for (x, y), td in grid._tiles.items():
            walking_cost = int(td.walking_cost.normalized_score) if hasattr(td, 'walking_cost') else 1
            is_hazardous = grid.is_position_hazardous_for(x, y, requesting_entity_uuid)

            conditions: List[str] = []
            if hasattr(td, 'active_conditions'):
                for cond_name, cond in td.active_conditions.items():
                    if cond.condition_category == ConditionCategory.INTERNAL:
                        continue
                    if cond.condition_stealth_dc is not None and cond.condition_stealth_dc >= observer_perception:
                        continue
                    conditions.append(cond_name)

            tiles.append(APITile(
                x=x, y=y,
                walkable=td.walkable,
                visible=td.visible,
                name=td.name,
                walking_cost=walking_cost,
                is_hazardous=is_hazardous,
                conditions=conditions,
                light_level=td.resolved_light_level.value,
                directional_blocks_movement=APIDirectionalBlockMap(
                    north=not td.allows_direction("north", "movement"),
                    south=not td.allows_direction("south", "movement"),
                    east=not td.allows_direction("east", "movement"),
                    west=not td.allows_direction("west", "movement"),
                ),
                directional_blocks_vision=APIDirectionalBlockMap(
                    north=not td.allows_direction("north", "vision"),
                    south=not td.allows_direction("south", "vision"),
                    east=not td.allows_direction("east", "vision"),
                    west=not td.allows_direction("west", "vision"),
                ),
                directional_blocks_light=APIDirectionalBlockMap(
                    north=not td.allows_direction("north", "light"),
                    south=not td.allows_direction("south", "light"),
                    east=not td.allows_direction("east", "light"),
                    west=not td.allows_direction("west", "light"),
                ),
                directional_blocks_propagation=APIDirectionalBlockMap(
                    north=not td.allows_direction("north", "propagation"),
                    south=not td.allows_direction("south", "propagation"),
                    east=not td.allows_direction("east", "propagation"),
                    west=not td.allows_direction("west", "propagation"),
                ),
            ))
        return cls(
            min_x=bounds[0], min_y=bounds[1],
            max_x=bounds[2], max_y=bounds[3],
            tiles=tiles
        )


class APICombatant(BaseModel):
    """Combatant in initiative order.

    Attributes:
        uuid: Stable combatant entity UUID serialized as a string.
        name: Combatant display name.
        initiative: Initiative total used for turn ordering.
        is_dead: Whether the combatant is currently dead.
    """

    uuid: str = Field(description="Stable combatant entity UUID serialized as a string.")
    name: str = Field(description="Combatant display name.")
    initiative: int = Field(description="Initiative total used for turn ordering.")
    is_dead: bool = Field(description="Whether the combatant is currently dead.")


class APIEncounter(BaseModel):
    """Encounter combat state.

    Attributes:
        uuid: Stable encounter UUID serialized as a string.
        name: Encounter display name.
        state: Encounter lifecycle state value.
        round_number: Current combat round number.
        current_turn_index: Index of the acting combatant in initiative order.
        current_entity_uuid: UUID of the current acting entity, if any.
        initiative_order: Combatants ordered by initiative.
    """

    uuid: str = Field(description="Stable encounter UUID serialized as a string.")
    name: str = Field(description="Encounter display name.")
    state: str = Field(description="Encounter lifecycle state value.")
    round_number: int = Field(description="Current combat round number.")
    current_turn_index: int = Field(description="Index of the acting combatant in initiative order.")
    current_entity_uuid: Optional[str] = Field(default=None, description="UUID of the current acting entity, if any.")
    initiative_order: List[APICombatant] = Field(description="Combatants ordered by initiative.")

    @classmethod
    def create(cls, encounter: Encounter) -> 'APIEncounter':
        combatants = []
        for uuid in encounter.initiative_order:
            entity = Entity.get(uuid)
            combatants.append(APICombatant(
                uuid=str(uuid),
                name=entity.name if entity else "Unknown",
                initiative=encounter.combatants[uuid].initiative_total,
                is_dead=encounter.combatants[uuid].is_dead
            ))
        current_uuid = None
        if encounter.initiative_order and encounter.current_turn_index < len(encounter.initiative_order):
            current_uuid = str(encounter.initiative_order[encounter.current_turn_index])
        return cls(
            uuid=str(encounter.uuid),
            name=encounter.name,
            state=encounter.state.value,
            round_number=encounter.round_number,
            current_turn_index=encounter.current_turn_index,
            current_entity_uuid=current_uuid,
            initiative_order=combatants
        )


class APIFloorObject(BaseModel):
    """Floor object or item on the ground.

    Attributes:
        uuid: Stable object UUID serialized as a string.
        name: Object display name.
        position: Grid position serialized as an ``(x, y)`` pair.
        map_char: Map glyph used to render the object.
        state: Object-specific public state fields.
    """

    uuid: str = Field(description="Stable object UUID serialized as a string.")
    name: str = Field(description="Object display name.")
    position: Tuple[int, int] = Field(description="Grid position serialized as an (x, y) pair.")
    map_char: str = Field(default="\u03c6", description="Map glyph used to render the object.")
    state: Dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Object-specific JSON state keyed by the concrete item model.",
    )


class APIGameState(BaseModel):
    """Full public game-state snapshot.

    Attributes:
        grid: Public grid snapshot.
        entities: Lightweight entity summaries visible to the client.
        encounter: Active encounter snapshot, if combat is active.
        floor_objects: Public floor-object summaries.
    """

    grid: APIGrid = Field(description="Public grid snapshot.")
    entities: List[APIEntitySummary] = Field(description="Lightweight entity summaries visible to the client.")
    encounter: Optional[APIEncounter] = Field(default=None, description="Active encounter snapshot, if combat is active.")
    floor_objects: List[APIFloorObject] = Field(default_factory=list, description="Public floor-object summaries.")


class APIEntityVisibility(BaseModel):
    """Current perception state for one observing entity."""

    name: str = Field(description="Observer display name.")
    position: Tuple[int, int] = Field(description="Observer grid position.")
    visible_cells: List[Tuple[int, int]] = Field(description="Cells visible now.")
    visible_entities: List[str] = Field(description="Entity UUIDs visible now.")
    visible_objects: List[str] = Field(description="Object UUIDs visible now.")
    seen_cells: List[Tuple[int, int]] = Field(description="Cells observed previously or currently.")
    sense_modes: List[SenseMode] = Field(description="Active special senses.")
    effective_light_levels: Dict[str, int] = Field(
        description=(
            "Backend-resolved subjective light levels for currently visible cells, "
            "keyed as 'x,y'."
        )
    )


class APIVisibilityResponse(RootModel[Dict[str, APIEntityVisibility]]):
    """Visibility rows keyed by observer UUID."""


class APIEntityListResponse(BaseModel):
    """Lightweight summaries for every entity exposed by the server."""

    entities: List[APIEntitySummary] = Field(description="Public entity summaries.")


class MapEditorGridBounds(BaseModel):
    """Inclusive grid bounds.

    Attributes:
        min_x: Minimum x-coordinate included in the map.
        min_y: Minimum y-coordinate included in the map.
        max_x: Maximum x-coordinate included in the map.
        max_y: Maximum y-coordinate included in the map.
    """

    min_x: int = Field(description="Minimum x-coordinate included in the map.")
    min_y: int = Field(description="Minimum y-coordinate included in the map.")
    max_x: int = Field(description="Maximum x-coordinate included in the map.")
    max_y: int = Field(description="Maximum y-coordinate included in the map.")


class MapEditorMapSnapshot(BaseModel):
    """Entity-free map snapshot for editing and generation.

    Attributes:
        grid_bounds: Inclusive bounds for the serialized map.
        tiles: Serialized tile snapshots.
        floor_objects: Serialized floor objects placed on the map.
    """

    grid_bounds: MapEditorGridBounds = Field(description="Inclusive bounds for the serialized map.")
    tiles: List[APITile] = Field(description="Serialized tile snapshots.")
    floor_objects: List[APIFloorObject] = Field(
        default_factory=list,
        description="Serialized floor objects placed on the map.",
    )


class MapEditorSavedObjectPlacement(BaseModel):
    """Reloadable editor object placement without serializing entities.

    Attributes:
        catalog_id: Catalog identifier used to recreate the object.
        name: Object display name stored in the save document.
        position: Grid position where the object should be restored.
        state: Object-specific state to restore.
    """

    catalog_id: str = Field(description="Catalog identifier used to recreate the object.")
    name: str = Field(description="Object display name stored in the save document.")
    position: Tuple[int, int] = Field(description="Grid position where the object should be restored.")
    state: Dict[str, Any] = Field(default_factory=dict, description="Object-specific state to restore.")


class MapEditorSaveMapRequest(BaseModel):
    """Request to save the current entity-free editor map.

    Attributes:
        id: Optional save identifier to create or overwrite.
        name: Human-readable saved map name.
        overwrite: Whether an existing save with the same identifier may be replaced.
    """

    id: Optional[str] = Field(default=None, description="Optional save identifier to create or overwrite.")
    name: str = Field(default="Untitled Map", description="Human-readable saved map name.")
    overwrite: bool = Field(
        default=False,
        description="Whether an existing save with the same identifier may be replaced.",
    )


class MapEditorSavedMapMetadata(BaseModel):
    """Saved editor map metadata.

    Attributes:
        id: Stable saved map identifier.
        name: Human-readable saved map name.
        created_at: ISO timestamp for save creation.
        updated_at: ISO timestamp for the latest save update.
        revision: Save document revision number.
        grid_bounds: Inclusive saved map bounds.
        tile_count: Number of serialized tiles.
        floor_object_count: Number of serialized floor objects.
    """

    id: str = Field(description="Stable saved map identifier.")
    name: str = Field(description="Human-readable saved map name.")
    created_at: str = Field(description="ISO timestamp for save creation.")
    updated_at: str = Field(description="ISO timestamp for the latest save update.")
    revision: int = Field(default=1, description="Save document revision number.")
    grid_bounds: MapEditorGridBounds = Field(description="Inclusive saved map bounds.")
    tile_count: int = Field(description="Number of serialized tiles.")
    floor_object_count: int = Field(description="Number of serialized floor objects.")


class MapEditorSavedMapDocument(BaseModel):
    """Durable editor map document.

    Attributes:
        schema_version: Saved map schema version.
        metadata: Saved map metadata.
        snapshot: Entity-free map snapshot.
        object_placements: Reloadable object placement records.
    """

    schema_version: int = Field(default=1, description="Saved map schema version.")
    metadata: MapEditorSavedMapMetadata = Field(description="Saved map metadata.")
    snapshot: MapEditorMapSnapshot = Field(description="Entity-free map snapshot.")
    object_placements: List[MapEditorSavedObjectPlacement] = Field(
        default_factory=list,
        description="Reloadable object placement records.",
    )


class MapEditorSavedMapList(BaseModel):
    """List of saved editor maps.

    Attributes:
        maps: Saved map metadata entries.
    """

    maps: List[MapEditorSavedMapMetadata] = Field(description="Saved map metadata entries.")


class MapEditorCreateMapRequest(BaseModel):
    """Request to create or reset the editor map.

    Attributes:
        source: Whether to build from scratch or from a preset.
        width: Scratch-map width in tiles.
        height: Scratch-map height in tiles.
        origin: Scratch-map origin position.
        default_tile: Terrain name used for scratch-map tiles.
        default_light: Initial light level for scratch-map tiles.
        preset_id: Optional preset identifier when source is preset.
        include_entities: Whether preset creation should include entity fixtures.
    """

    source: Literal["scratch", "preset"] = Field(default="scratch", description="Whether to build from scratch or from a preset.")
    width: int = Field(default=16, description="Scratch-map width in tiles.")
    height: int = Field(default=16, description="Scratch-map height in tiles.")
    origin: Tuple[int, int] = Field(default=(0, 0), description="Scratch-map origin position.")
    default_tile: str = Field(default="Floor", description="Terrain name used for scratch-map tiles.")
    default_light: int = Field(default=1, description="Initial light level for scratch-map tiles.")
    preset_id: Optional[str] = Field(default=None, description="Optional preset identifier when source is preset.")
    include_entities: bool = Field(default=False, description="Whether preset creation should include entity fixtures.")


class MapEditorTilePatch(BaseModel):
    """Single editor tile update.

    Attributes:
        x: Tile x-coordinate to patch.
        y: Tile y-coordinate to patch.
        type: Optional replacement terrain type.
        light_level: Optional replacement light level.
        directional_channel: Directional blocking channel to patch.
        direction: Directional side to patch.
        passable: Whether the patched directional side is passable.
    """

    x: int = Field(description="Tile x-coordinate to patch.")
    y: int = Field(description="Tile y-coordinate to patch.")
    type: Optional[str] = Field(default=None, description="Optional replacement terrain type.")
    light_level: Optional[int] = Field(default=None, description="Optional replacement light level.")
    directional_channel: Optional[Literal["movement", "vision", "light", "propagation"]] = Field(
        default=None,
        description="Directional blocking channel to patch.",
    )
    direction: Optional[Literal["north", "south", "east", "west"]] = Field(
        default=None,
        description="Directional side to patch.",
    )
    passable: Optional[bool] = Field(default=None, description="Whether the patched directional side is passable.")


class MapEditorTilePatchRequest(BaseModel):
    """Batch tile update request.

    Attributes:
        tiles: Tile patches to apply.
    """

    tiles: List[MapEditorTilePatch] = Field(description="Tile patches to apply.")


class MapEditorObjectPlaceRequest(BaseModel):
    """Request to place a catalog object on the editor map.

    Attributes:
        catalog_id: Catalog identifier for the object to place.
        position: Grid position where the object should be placed.
        options: Object-specific placement options.
    """

    catalog_id: str = Field(description="Catalog identifier for the object to place.")
    position: Tuple[int, int] = Field(description="Grid position where the object should be placed.")
    options: Dict[str, Any] = Field(default_factory=dict, description="Object-specific placement options.")


class MapEditorObjectDeleteRequest(BaseModel):
    """Request to delete editor objects by UUID or tile position.

    Attributes:
        object_uuid: Optional object UUID to delete.
        position: Optional tile position whose objects should be deleted.
    """

    object_uuid: Optional[str] = Field(default=None, description="Optional object UUID to delete.")
    position: Optional[Tuple[int, int]] = Field(default=None, description="Optional tile position whose objects should be deleted.")

ProjectileCatalogType = Literal["bolt", "ray", "orb", "beam", "dart", "spray", "radiance", "touch", "rain"]
AoeCatalogShapeType = Literal["sphere", "cone", "line", "cube", "cylinder"]
SpellCatalogRangeType = Literal["self", "touch", "ranged"]
SpellCatalogRouteHint = Literal[
    "self", "touch", "single_projectile", "missile_volley", "aoe",
    "aoe_projectile", "beam", "ray", "none"
]


class SpellCatalogSavingThrow(BaseModel):
    """Saving throw metadata for a catalog spell.

    Attributes:
        ability: Short ability label used for the saving throw.
        dc_source: Source used to compute the save DC.
    """

    ability: str = Field(description="Short ability label used for the saving throw.")
    dc_source: Optional[str] = Field(default=None, description="Source used to compute the save DC.")


class SpellCatalogMultiTarget(BaseModel):
    """Multi-target and projectile semantics for a catalog spell.

    Attributes:
        min_targets: Minimum number of targets required by the spell.
        max_targets: Maximum number of targets the spell can affect.
        allow_same_target: Whether multiple projectiles may choose the same target.
        projectiles_per_cast: Number of projectiles created by one base cast.
    """

    min_targets: Optional[int] = Field(default=None, description="Minimum number of targets required by the spell.")
    max_targets: Optional[int] = Field(default=None, description="Maximum number of targets the spell can affect.")
    allow_same_target: Optional[bool] = Field(default=None, description="Whether multiple projectiles may choose the same target.")
    projectiles_per_cast: Optional[int] = Field(default=None, description="Number of projectiles created by one base cast.")


class SpellCatalogVfx(BaseModel):
    """Visual routing hints derived from spell rules metadata.

    Attributes:
        projectile_type: Normalized projectile style for visual routing.
        aoe_shape_type: Normalized area-of-effect shape for visual routing.
        route_hint: Recommended animation route category.
        recommended_asset_tags: Asset tags inferred from rules metadata.
    """

    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style for visual routing.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape for visual routing.")
    route_hint: SpellCatalogRouteHint = Field(description="Recommended animation route category.")
    recommended_asset_tags: List[str] = Field(default_factory=list, description="Asset tags inferred from rules metadata.")


class SpellCatalogEntry(BaseModel):
    """Design-time spell metadata exposed by the backend catalog.

    Attributes:
        id: Stable normalized spell identifier.
        name: Display name for the spell.
        aliases: Alternate names accepted by tooling or clients.
        level: Spell level, with zero representing cantrips.
        school: Spell school name.
        description: Optional spell description text.
        action_category: Fixed action category for spell catalog entries.
        target_type: Engine target type used by the spell action.
        range_type: Normalized spell range category.
        range_ft: Spell range in feet when applicable.
        projectile_type: Normalized projectile style when present.
        aoe_shape_type: Normalized area-of-effect shape when present.
        aoe_radius_ft: Area radius in feet when applicable.
        aoe_length_ft: Area length in feet when applicable.
        aoe_width_ft: Area width in feet when applicable.
        damage_types: Damage type labels inferred from the spell.
        healing: Whether the spell restores hit points.
        attack_roll: Whether the spell uses a spell attack roll.
        saving_throw: Saving throw metadata when the spell prompts a save.
        concentration: Whether the spell requires concentration.
        ritual: Whether the spell can be cast as a ritual.
        verbal: Whether the spell has a verbal component.
        somatic: Whether the spell has a somatic component when known.
        material: Whether the spell has a material component when known.
        classes: Class names associated with the spell in catalog metadata.
        subclasses: Subclass names associated with the spell in catalog metadata.
        source: Source label for the catalog metadata.
        multi_target: Multi-target metadata when the spell supports it.
        vfx: Visual routing hints for the spell.
    """

    id: str = Field(description="Stable normalized spell identifier.")
    name: str = Field(description="Display name for the spell.")
    aliases: List[str] = Field(default_factory=list, description="Alternate names accepted by tooling or clients.")
    level: int = Field(description="Spell level, with zero representing cantrips.")
    school: str = Field(description="Spell school name.")
    description: Optional[str] = Field(default=None, description="Optional spell description text.")
    action_category: Literal["spell"] = Field(default="spell", description="Fixed action category for spell catalog entries.")
    target_type: str = Field(description="Engine target type used by the spell action.")
    range_type: Optional[SpellCatalogRangeType] = Field(default=None, description="Normalized spell range category.")
    range_ft: Optional[int] = Field(default=None, description="Spell range in feet when applicable.")
    projectile_type: Optional[ProjectileCatalogType] = Field(default=None, description="Normalized projectile style when present.")
    aoe_shape_type: Optional[AoeCatalogShapeType] = Field(default=None, description="Normalized area-of-effect shape when present.")
    aoe_radius_ft: Optional[int] = Field(default=None, description="Area radius in feet when applicable.")
    aoe_length_ft: Optional[int] = Field(default=None, description="Area length in feet when applicable.")
    aoe_width_ft: Optional[int] = Field(default=None, description="Area width in feet when applicable.")
    damage_types: List[str] = Field(default_factory=list, description="Damage type labels inferred from the spell.")
    healing: bool = Field(default=False, description="Whether the spell restores hit points.")
    attack_roll: bool = Field(default=False, description="Whether the spell uses a spell attack roll.")
    saving_throw: Optional[SpellCatalogSavingThrow] = Field(default=None, description="Saving throw metadata when the spell prompts a save.")
    concentration: bool = Field(default=False, description="Whether the spell requires concentration.")
    ritual: bool = Field(default=False, description="Whether the spell can be cast as a ritual.")
    verbal: bool = Field(default=True, description="Whether the spell has a verbal component.")
    somatic: Optional[bool] = Field(default=None, description="Whether the spell has a somatic component when known.")
    material: Optional[bool] = Field(default=None, description="Whether the spell has a material component when known.")
    classes: List[str] = Field(default_factory=list, description="Class names associated with the spell in catalog metadata.")
    subclasses: List[str] = Field(default_factory=list, description="Subclass names associated with the spell in catalog metadata.")
    source: Optional[str] = Field(default=None, description="Source label for the catalog metadata.")
    multi_target: Optional[SpellCatalogMultiTarget] = Field(default=None, description="Multi-target metadata when the spell supports it.")
    vfx: Optional[SpellCatalogVfx] = Field(default=None, description="Visual routing hints for the spell.")


class SpellCatalogResponse(BaseModel):
    """All backend spell templates known to the engine.

    Attributes:
        version: Catalog schema or generation version.
        generated_at: Optional generation timestamp.
        spells: Spell catalog entries known to the backend.
    """

    version: str = Field(description="Catalog schema or generation version.")
    generated_at: Optional[str] = Field(default=None, description="Optional generation timestamp.")
    spells: List[SpellCatalogEntry] = Field(description="Spell catalog entries known to the backend.")


class MapEditorCatalogEntry(BaseModel):
    """Normalized placeable editor catalog entry.

    Attributes:
        id: Stable catalog identifier.
        name: Display name shown in editor tools.
        group: High-level catalog group.
        category: Object, terrain, loot, or preset category.
        source_module: Runtime module that provides the catalog entry.
        stability: Whether the catalog entry is stable, candidate, or demo-only.
        placement: Placement mode used by the editor.
        map_char: Optional map glyph hint.
        visual_item_name: Optional renderer asset name.
        flags: Capability and behavior flags used by the editor.
        actions: Object actions exposed by the catalog entry.
        default_state: Default state applied when placing the entry.
    """

    id: str = Field(description="Stable catalog identifier.")
    name: str = Field(description="Display name shown in editor tools.")
    group: str = Field(description="High-level catalog group.")
    category: str = Field(description="Object, terrain, loot, or preset category.")
    source_module: str = Field(description="Runtime module that provides the catalog entry.")
    stability: Literal["stable", "candidate", "demo"] = Field(
        default="stable",
        description="Whether the catalog entry is stable, candidate, or demo-only.",
    )
    placement: str = Field(default="single_tile", description="Placement mode used by the editor.")
    map_char: Optional[str] = Field(default=None, description="Optional map glyph hint.")
    visual_item_name: Optional[str] = Field(default=None, description="Optional renderer asset name.")
    flags: Dict[str, Any] = Field(default_factory=dict, description="Capability and behavior flags used by the editor.")
    actions: List[str] = Field(default_factory=list, description="Object actions exposed by the catalog entry.")
    default_state: Dict[str, Any] = Field(default_factory=dict, description="Default state applied when placing the entry.")


class MapEditorCatalog(BaseModel):
    """All mapeditor presets, terrain, objects, and loot known to the backend.

    Attributes:
        presets: Map preset catalog entries.
        tiles: Terrain tile catalog entries.
        objects: Placeable object catalog entries.
        loot: Loot and item catalog entries.
    """

    presets: List[MapEditorCatalogEntry] = Field(description="Map preset catalog entries.")
    tiles: List[MapEditorCatalogEntry] = Field(description="Terrain tile catalog entries.")
    objects: List[MapEditorCatalogEntry] = Field(description="Placeable object catalog entries.")
    loot: List[MapEditorCatalogEntry] = Field(description="Loot and item catalog entries.")


class MapEditorWalkabilityCell(BaseModel):
    """Walkability status for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        walkable: Whether the cell can be entered.
        blocker: Optional blocker name when the cell is not walkable.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    walkable: bool = Field(description="Whether the cell can be entered.")
    blocker: Optional[str] = Field(default=None, description="Optional blocker name when the cell is not walkable.")


class MapEditorWalkabilityResponse(BaseModel):
    """Walkability layer response.

    Attributes:
        cells: Walkability cells for the current editor map.
    """

    cells: List[MapEditorWalkabilityCell] = Field(description="Walkability cells for the current editor map.")


class MapEditorVisibilityCell(BaseModel):
    """Visibility-blocking status for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        blocks_visibility: Whether the cell blocks line of sight.
        blocker: Optional blocker name when visibility is blocked.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    blocks_visibility: bool = Field(description="Whether the cell blocks line of sight.")
    blocker: Optional[str] = Field(default=None, description="Optional blocker name when visibility is blocked.")


class MapEditorVisibilityResponse(BaseModel):
    """Visibility layer response.

    Attributes:
        cells: Visibility cells for the current editor map.
    """

    cells: List[MapEditorVisibilityCell] = Field(description="Visibility cells for the current editor map.")


class MapEditorLightCell(BaseModel):
    """Objective light level for one editor map cell.

    Attributes:
        x: Cell x-coordinate.
        y: Cell y-coordinate.
        light_level: Resolved light level enum value.
    """

    x: int = Field(description="Cell x-coordinate.")
    y: int = Field(description="Cell y-coordinate.")
    light_level: int = Field(description="Resolved light level enum value.")


class MapEditorLightResponse(BaseModel):
    """Objective light layer response.

    Attributes:
        cells: Light-level cells for the current editor map.
    """

    cells: List[MapEditorLightCell] = Field(description="Light-level cells for the current editor map.")


class APISimulationStatus(BaseModel):
    """Simulation control status.

    Attributes:
        has_encounter: Whether a simulation encounter currently exists.
        paused: Whether automatic simulation advancement is paused.
        encounter_state: Current encounter state value, if any.
        round_number: Current encounter round number, if any.
        turn_delay: Delay between automated turns in seconds.
    """

    has_encounter: bool = Field(description="Whether a simulation encounter currently exists.")
    paused: bool = Field(description="Whether automatic simulation advancement is paused.")
    encounter_state: Optional[str] = Field(description="Current encounter state value, if any.")
    round_number: Optional[int] = Field(description="Current encounter round number, if any.")
    turn_delay: float = Field(description="Delay between automated turns in seconds.")


class APICurrentTurn(BaseModel):
    """Current turn information.

    Attributes:
        encounter_active: Whether the encounter is currently active.
        round_number: Current encounter round number.
        turn_index: Current index in initiative order.
        current_entity_uuid: UUID of the acting entity, if any.
        current_entity_name: Name of the acting entity, if any.
        is_human_turn: Whether the current controller expects manual input.
        waiting_for_input: Whether the simulation is waiting for input.
        controller_type: Current controller type, if any.
        actions_remaining: Actions remaining for the acting entity.
        bonus_actions_remaining: Bonus actions remaining for the acting entity.
        reactions_remaining: Reactions remaining for the acting entity.
        movement_remaining: Movement remaining for the acting entity.
    """

    encounter_active: bool = Field(description="Whether the encounter is currently active.")
    round_number: int = Field(description="Current encounter round number.")
    turn_index: int = Field(description="Current index in initiative order.")
    current_entity_uuid: Optional[str] = Field(description="UUID of the acting entity, if any.")
    current_entity_name: Optional[str] = Field(description="Name of the acting entity, if any.")
    is_human_turn: bool = Field(description="Whether the current controller expects manual input.")
    waiting_for_input: bool = Field(description="Whether the simulation is waiting for input.")
    controller_type: Optional[str] = Field(description="Current controller type, if any.")
    actions_remaining: int = Field(default=0, description="Actions remaining for the acting entity.")
    bonus_actions_remaining: int = Field(default=0, description="Bonus actions remaining for the acting entity.")
    reactions_remaining: int = Field(default=0, description="Reactions remaining for the acting entity.")
    movement_remaining: int = Field(default=0, description="Movement remaining for the acting entity.")


class CreateSessionRequest(BaseModel):
    """Request to create a new player session.

    Attributes:
        player_type: Controller type for the session, such as human or codex.
        name: Optional display name for the session.
    """

    player_type: str = Field(description="Controller type for the session, such as human or codex.")
    name: Optional[str] = Field(default=None, description="Optional display name for the session.")


class CreateSessionResponse(BaseModel):
    """Response from creating a session.

    Attributes:
        session_id: Stable session identifier.
        player_type: Controller type assigned to the session.
        name: Display name assigned to the session.
    """

    session_id: str = Field(description="Stable session identifier.")
    player_type: str = Field(description="Controller type assigned to the session.")
    name: str = Field(description="Display name assigned to the session.")


class SessionPingResponse(BaseModel):
    """Response from session ping.

    Attributes:
        status: Ping result status.
        session_id: Stable session identifier.
        connection_status: Current connection status label.
        is_my_turn: Whether this session controls the acting entity.
        active_entity_uuid: UUID of the active entity, if any.
        active_entity_name: Name of the active entity, if any.
        controlled_entities: Entity UUIDs controlled by the session.
    """

    status: str = Field(description="Ping result status.")
    session_id: str = Field(description="Stable session identifier.")
    connection_status: str = Field(description="Current connection status label.")
    is_my_turn: bool = Field(description="Whether this session controls the acting entity.")
    active_entity_uuid: Optional[str] = Field(description="UUID of the active entity, if any.")
    active_entity_name: Optional[str] = Field(description="Name of the active entity, if any.")
    controlled_entities: List[str] = Field(description="Entity UUIDs controlled by the session.")


class JoinGameRequest(BaseModel):
    """Request to join a game with a session.

    Attributes:
        session_id: Session joining the game.
        entity_uuids: Optional entity UUIDs to control.
        entity_uuid: Optional single entity UUID convenience alias.
        faction: Optional faction whose entities should be controlled.
    """

    session_id: str = Field(description="Session joining the game.")
    entity_uuids: Optional[List[str]] = Field(default=None, description="Optional entity UUIDs to control.")
    entity_uuid: Optional[str] = Field(default=None, description="Optional single entity UUID to control.")
    faction: Optional[str] = Field(default=None, description="Optional faction whose entities should be controlled.")

    def requested_entity_uuids(self) -> List[str]:
        """Return requested entity UUIDs from list and single-entity inputs.

        Returns:
            De-duplicated entity UUID strings in request order.
        """
        requested: List[str] = []
        for uuid_str in self.entity_uuids or []:
            if uuid_str not in requested:
                requested.append(uuid_str)
        if self.entity_uuid and self.entity_uuid not in requested:
            requested.append(self.entity_uuid)
        return requested


class JoinGameResponse(BaseModel):
    """Response from joining a game.

    Attributes:
        success: Whether the join request succeeded.
        game_id: Game identifier joined by the session.
        session_id: Session that joined the game.
        controlled_entities: Entity UUIDs controlled after joining.
        message: Human-readable join result.
    """

    success: bool = Field(description="Whether the join request succeeded.")
    game_id: str = Field(description="Game identifier joined by the session.")
    session_id: str = Field(description="Session that joined the game.")
    controlled_entities: List[str] = Field(description="Entity UUIDs controlled after joining.")
    message: str = Field(description="Human-readable join result.")


GameCreationControllerKind = Literal["human", "ai", "codex"]
GameCreationOpeningSide = Literal["initiative", "side_a", "side_b"]


class GameCreationPreset(BaseModel):
    """Historical scenario recipe exposed as a quick game-creation preset.

    Attributes:
        arena_id: Stable historical scenario identifier.
        title: Human-readable scenario title.
        tags: Searchable mechanics and content labels.
        expected_pressure: Tactical behaviors the scenario exercises.
        map_notes: Important terrain and object facts.
        recipe: Canonical composition recipe used to reconstruct the scenario.
    """

    arena_id: str = Field(description="Stable historical scenario identifier.")
    title: str = Field(description="Human-readable scenario title.")
    tags: List[str] = Field(description="Searchable mechanics and content labels.")
    expected_pressure: List[str] = Field(description="Tactical behaviors exercised by the scenario.")
    map_notes: List[str] = Field(description="Important terrain and object facts.")
    recipe: LegacyScenarioRecipe = Field(description="Canonical composition recipe for the scenario.")


class GameCreationCatalogResponse(BaseModel):
    """Canonical content and controller choices for the game-creation UI."""

    schema_version: int = Field(default=1, description="Game-creation contract schema version.")
    controllers: List[GameCreationControllerKind] = Field(description="Supported side controller kinds.")
    opening_sides: List[GameCreationOpeningSide] = Field(description="Supported initiative-opening policies.")
    hero_configurations: List[SideConfigurationSpec] = Field(description="Canonical hero-side configurations.")
    monster_configurations: List[SideConfigurationSpec] = Field(description="Canonical monster-party configurations.")
    battlefields: List[BattlefieldSpec] = Field(description="Canonical battlefield definitions.")
    deployments: List[DeploymentSpec] = Field(description="Canonical spawn formations.")
    presets: List[GameCreationPreset] = Field(description="Historical scenario quick presets.")


class GameCreationPreflightRequest(BaseModel):
    """Four-part composed scenario selection checked without mutating game state."""

    hero_configuration_id: str = Field(description="Hero configuration catalog identifier.")
    monster_configuration_id: str = Field(description="Monster-party configuration catalog identifier.")
    battlefield_id: str = Field(description="Battlefield catalog identifier.")
    deployment_id: str = Field(description="Deployment catalog identifier.")


class GameCreationPresetScenario(BaseModel):
    """Historical scenario selected by stable preset identifier."""

    kind: Literal["preset"] = Field(default="preset", description="Scenario-selection discriminator.")
    arena_id: str = Field(description="Historical scenario preset identifier.")


class GameCreationComposedScenario(GameCreationPreflightRequest):
    """Custom scenario assembled from four canonical component identifiers."""

    kind: Literal["composed"] = Field(default="composed", description="Scenario-selection discriminator.")


GameCreationScenario = Annotated[
    Union[GameCreationPresetScenario, GameCreationComposedScenario],
    Field(discriminator="kind"),
]


class GameCreationSideRequest(BaseModel):
    """Requested controller assignment for one complete combat side."""

    controller: GameCreationControllerKind = Field(description="Controller kind assigned to every entity on the side.")
    name: str = Field(min_length=1, max_length=80, description="Participant display name.")


class GameCreationStartRequest(BaseModel):
    """Atomic scenario and controller assignment request."""

    scenario: GameCreationScenario = Field(description="Preset or composed scenario selection.")
    side_a: GameCreationSideRequest = Field(description="Controller assignment for the hero side.")
    side_b: GameCreationSideRequest = Field(description="Controller assignment for the opposition side.")
    opening_side: GameCreationOpeningSide = Field(
        default="initiative",
        description="Whether rolled initiative, Side A, or Side B opens combat.",
    )
    codex_lease_seconds: float = Field(
        default=600.0,
        gt=0,
        le=86400,
        description="Takeover lease duration for configured Codex sides.",
    )


class GameCreationSideResult(BaseModel):
    """Resolved entities, ownership, and attach data for one side."""

    side_id: Literal["side_a", "side_b"] = Field(description="Stable side identifier.")
    title: str = Field(description="Resolved side configuration title.")
    controller: GameCreationControllerKind = Field(description="Configured controller kind.")
    participant_name: str = Field(description="Configured participant display name.")
    entities: List[APIEntitySummary] = Field(description="Complete entity summaries belonging to the side.")
    human_entity_uuids: List[str] = Field(
        default_factory=list,
        description="Entity UUIDs a human participant may claim through game join.",
    )
    fallback_ai_session_id: Optional[str] = Field(
        default=None,
        description="External-AI session controlling the side or retained behind a Codex claim.",
    )
    codex_session_id: Optional[str] = Field(default=None, description="Configured Codex session UUID.")
    takeover_claim_id: Optional[str] = Field(default=None, description="Configured Codex takeover claim UUID.")
    takeover_expires_at: Optional[float] = Field(default=None, description="Codex claim expiry timestamp.")


class GameCreationStartResponse(BaseModel):
    """Resolved game, sides, sessions, and first external turn boundary."""

    schema_version: int = Field(default=1, description="Game-creation contract schema version.")
    scenario_kind: Literal["preset", "composed"] = Field(description="Scenario-selection kind used for the match.")
    preset_arena_id: Optional[str] = Field(default=None, description="Historical preset identifier when selected.")
    encounter_uuid: str = Field(description="Created encounter UUID.")
    game_id: str = Field(description="Created active game UUID.")
    encounter_name: str = Field(description="Created encounter display name.")
    opening_side: GameCreationOpeningSide = Field(description="Applied initiative-opening policy.")
    compatibility: CompatibilityReport = Field(description="Compatibility report used to admit the scenario.")
    side_a: GameCreationSideResult = Field(description="Resolved Side A assignment.")
    side_b: GameCreationSideResult = Field(description="Resolved Side B assignment.")
    status: str = Field(description="Current encounter advancement status.")
    entity_uuid: Optional[str] = Field(default=None, description="Entity waiting at the external turn boundary.")
    entity_name: Optional[str] = Field(default=None, description="Entity name waiting at the external turn boundary.")
    round: Optional[int] = Field(default=None, description="Current encounter round.")
    turn_index: Optional[int] = Field(default=None, description="Current initiative index.")
    ai_actions: List[CombatLogEntry] = Field(
        default_factory=list,
        description="Automated action log entries produced during startup advancement.",
    )
    new_log_since: Optional[int] = Field(default=None, description="Combat-log cursor used for startup advancement.")
    event_cursor_after: Optional[int] = Field(default=None, description="Event cursor after startup advancement.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after startup advancement.")


class StandaloneGameSessionSummary(BaseModel):
    """One reconnectable session exposed by a standalone game server."""

    session_id: str = Field(description="Runtime session identifier.")
    player_type: str = Field(description="Session controller type.")
    name: str = Field(description="Session display name.")
    connection_status: str = Field(description="Current session connection state.")
    controlled_entities: List[str] = Field(description="Entity UUIDs owned by the session.")
    is_their_turn: bool = Field(description="Whether this session owns the active turn.")


class StandaloneGameStatusResponse(BaseModel):
    """Typed directory row for the single hot game held by a standalone server."""

    active: bool = Field(description="Whether the server currently holds a game session.")
    game_id: Optional[str] = Field(default=None, description="Current engine game UUID.")
    encounter_active: bool = Field(description="Whether the current encounter remains active.")
    active_entity_uuid: Optional[str] = Field(
        default=None,
        description="Entity currently holding the turn.",
    )
    sessions: List[StandaloneGameSessionSummary] = Field(
        default_factory=list,
        description="Runtime sessions available for local reconnection.",
    )
    creation: Optional[GameCreationStartResponse] = Field(
        default=None,
        description="Resolved creation metadata needed to reconstruct the client scene.",
    )


class AgentSessionEntityRow(BaseModel):
    """Entity label owned by an AI-observable session.

    Attributes:
        entity_uuid: Controlled entity UUID.
        entity_name: Controlled entity display name.
        faction: Controlled entity faction, if any.
        controller_type: Encounter controller type assigned to the entity.
        is_active_actor: Whether this entity is currently the active actor.
    """

    entity_uuid: str = Field(description="Controlled entity UUID.")
    entity_name: str = Field(description="Controlled entity display name.")
    faction: Optional[str] = Field(default=None, description="Controlled entity faction, if any.")
    controller_type: Optional[str] = Field(default=None, description="Encounter controller type assigned to the entity.")
    is_active_actor: bool = Field(description="Whether this entity is currently the active actor.")


class AgentSessionRow(BaseModel):
    """Read-only AI session row for observer clients.

    Attributes:
        session_id: Stable session UUID.
        player_type: Session player type such as ai or codex.
        name: Session display name.
        connection_status: Current connection status.
        is_active_turn: Whether this session controls the active actor.
        active_controlled_entity_uuid: Active actor UUID when controlled by this session.
        active_controlled_entity_name: Active actor name when controlled by this session.
        controlled_entities: Controlled entity labels.
        agent_cursor: Current telemetry cursor for the session.
        earliest_agent_cursor: Earliest retained telemetry cursor.
        observation_cursor: Current subjective observation cursor when available.
        current_epoch_id: Cached active epoch id when available.
        takeover_claim_ids: Live takeover claims owned by this session.
    """

    session_id: str = Field(description="Stable session UUID.")
    player_type: str = Field(description="Session player type such as ai or codex.")
    name: str = Field(description="Session display name.")
    connection_status: str = Field(description="Current connection status.")
    is_active_turn: bool = Field(description="Whether this session controls the active actor.")
    active_controlled_entity_uuid: Optional[str] = Field(
        default=None,
        description="Active actor UUID when controlled by this session.",
    )
    active_controlled_entity_name: Optional[str] = Field(
        default=None,
        description="Active actor name when controlled by this session.",
    )
    controlled_entities: List[AgentSessionEntityRow] = Field(description="Controlled entity labels.")
    agent_cursor: int = Field(description="Current telemetry cursor for the session.")
    earliest_agent_cursor: int = Field(description="Earliest retained telemetry cursor.")
    observation_cursor: Optional[int] = Field(default=None, description="Current subjective observation cursor when available.")
    current_epoch_id: Optional[str] = Field(default=None, description="Cached active epoch id when available.")
    takeover_claim_ids: List[str] = Field(default_factory=list, description="Live takeover claims owned by this session.")


class AgentSessionListResponse(BaseModel):
    """Read-only AI session index for observer clients.

    Attributes:
        sessions: AI or Codex sessions that can expose agent telemetry.
        active_game_id: Active game UUID, if any.
        encounter_active: Whether the active game has an active encounter.
    """

    sessions: List[AgentSessionRow] = Field(description="AI or Codex sessions that can expose agent telemetry.")
    active_game_id: Optional[str] = Field(default=None, description="Active game UUID, if any.")
    encounter_active: bool = Field(description="Whether the active game has an active encounter.")


class ControlledEntitiesResponse(BaseModel):
    """Response listing entities controlled by a session.

    Attributes:
        session_id: Session whose controlled entities are listed.
        controlled_entities: Controlled entity summaries.
    """

    session_id: str = Field(description="Session whose controlled entities are listed.")
    controlled_entities: List[APIEntitySummary] = Field(description="Controlled entity summaries.")


class AoEPreviewResult(BaseModel):
    """Result of an AoE position preview without execution.

    Attributes:
        success: Whether the preview request succeeded.
        message: Human-readable preview result.
        affected_positions: Grid positions affected by the preview.
        affected_entity_names: Names of entities affected by the preview.
        affected_count: Number of affected entities.
    """

    success: bool = Field(description="Whether the preview request succeeded.")
    message: str = Field(default="", description="Human-readable preview result.")
    affected_positions: List[Tuple[int, int]] = Field(default_factory=list, description="Grid positions affected by the preview.")
    affected_entity_names: List[str] = Field(default_factory=list, description="Names of entities affected by the preview.")
    affected_count: int = Field(default=0, description="Number of affected entities.")

class MoveRequest(BaseModel):
    """Request body for move action.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity that should move.
        position: Destination grid position.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity that should move.")
    position: Tuple[int, int] = Field(description="Destination grid position.")


class AttackRequest(BaseModel):
    """Request body for attack action.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Attacking entity UUID.
        target_uuid: Target entity UUID.
        weapon_slot: Weapon slot used for the attack.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Attacking entity UUID.")
    target_uuid: str = Field(description="Target entity UUID.")
    weapon_slot: str = Field(default="main_hand", description="Weapon slot used for the attack.")


class SimpleActionRequest(BaseModel):
    """Request body for simple session-gated actions.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")


class SelfActionRequest(BaseModel):
    """Request for self-targeting actions.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        action_name: Action template name.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    action_name: str = Field(description="Action template name.")


class EntityActionRequest(BaseModel):
    """Request for entity-targeting actions.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        action_name: Action template name.
        target_uuid: Target entity UUID.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    action_name: str = Field(description="Action template name.")
    target_uuid: str = Field(description="Target entity UUID.")


class PositionActionRequest(BaseModel):
    """Request for position-targeting actions.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        action_name: Action template name.
        position: Target grid position.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    action_name: str = Field(description="Action template name.")
    position: Tuple[int, int] = Field(description="Target grid position.")


class ExecuteByIndexRequest(BaseModel):
    """Request to execute action by template name + target index.

    Attributes:
        session_id: Session performing the action.
        entity_uuid: Entity performing the action.
        template_name: Action template name.
        target_index: Index from the action's valid target list.
        extra_target_uuids: Additional target UUIDs for multi-entity actions.
        prefer_safe: Whether movement should prefer safe paths when available.
        return_available_actions: Whether to include recomputed action rows in
            the response.
        include_state: Whether to include the full game state snapshot.
        include_timing: Whether to include server-side route timing.
    """

    session_id: str = Field(description="Session performing the action.")
    entity_uuid: str = Field(description="Entity performing the action.")
    template_name: str = Field(description="Action template name.")
    target_index: int = Field(description="Index from the action's valid target list.")
    extra_target_uuids: Optional[List[str]] = Field(
        default=None,
        description="Additional target UUIDs for multi-entity actions.",
    )
    prefer_safe: bool = Field(default=True, description="Whether movement should prefer safe paths when available.")
    return_available_actions: bool = Field(
        default=True,
        description="Whether the response should include recomputed available actions.",
    )
    include_state: bool = Field(
        default=True,
        description="Whether the response should include the full game state snapshot.",
    )
    include_timing: bool = Field(
        default=False,
        description="Whether the response should include server-side route timing.",
    )


class ToggleHandlerRequest(BaseModel):
    """Request to toggle a handler's enabled state.

    Attributes:
        session_id: Session performing the toggle.
        entity_uuid: Entity whose handler should be toggled.
        enabled: Desired handler enabled state.
    """

    session_id: str = Field(description="Session performing the toggle.")
    entity_uuid: str = Field(description="Entity whose handler should be toggled.")
    enabled: bool = Field(description="Desired handler enabled state.")


class APIResourcePool(BaseModel):
    """Current and maximum values for a named finite resource."""

    current: int = Field(description="Current resource value.")
    max: int = Field(description="Maximum resource value.")


class APIAvailableActions(AvailableActionsResult):
    """Engine-discovered legal actions plus current resource summaries."""

    actions_remaining: int = Field(description="Actions currently available.")
    bonus_actions_remaining: int = Field(description="Bonus actions currently available.")
    reactions_remaining: int = Field(description="Reactions currently available.")
    extra_attacks_remaining: int = Field(description="Extra attacks currently available.")
    spell_slots: Dict[str, APIResourcePool] = Field(
        default_factory=dict,
        description="Spell-slot pools keyed by slot level.",
    )
    resources: Dict[str, APIResourcePool] = Field(
        default_factory=dict,
        description="Named custom action resources.",
    )


class APIServerTiming(BaseModel):
    """Server-side command phase timing returned on request."""

    command_type: str = Field(description="Command category being measured.")
    diagnostics_enabled: bool = Field(description="Whether detailed diagnostics were active.")
    total_ms: float = Field(description="Total command time in milliseconds.")
    phases: Dict[str, float] = Field(description="Accumulated phase durations in milliseconds.")
    phase_counts: Dict[str, int] = Field(description="Invocation count for each measured phase.")
    phase_max_ms: Dict[str, float] = Field(description="Maximum duration for each measured phase.")

class ActionResult(BaseModel):
    """Result of an action execution.

    Attributes:
        success: Whether the action execution succeeded.
        message: Human-readable action result.
        event_type: Domain event type emitted by the action, if any.
        outcome_code: Stable machine-readable engine outcome, if any.
        event_data: Serialized domain event data, if any.
        entity_hp: Acting entity hit points after the action, if relevant.
        target_hp: Target entity hit points after the action, if relevant.
        deaths: Names of entities that died during the action.
        triggered_reactions: Reaction summaries triggered by the action.
        turn_continues: Whether the acting entity's turn continues.
        encounter_ended: Whether the encounter ended because of the action.
        combat_log_entries: Combat log entries generated by the action.
        available_actions: Updated available actions after execution.
        state: Full game-state snapshot after execution.
        server_timing: Optional server-side route timing.
        event_cursor_after: Event-history cursor after all side effects.
        combat_log_cursor_after: Combat-log cursor after all side effects.
    """

    success: bool = Field(description="Whether the action execution succeeded.")
    message: str = Field(description="Human-readable action result.")
    event_type: Optional[str] = Field(default=None, description="Domain event type emitted by the action, if any.")
    outcome_code: Optional[str] = Field(
        default=None,
        description="Stable machine-readable engine outcome, if any.",
    )
    event_data: Optional[Dict[str, JsonValue]] = Field(
        default=None,
        description="Serialized terminal domain-event data, if any.",
    )
    entity_hp: Optional[int] = Field(default=None, description="Acting entity hit points after the action, if relevant.")
    target_hp: Optional[int] = Field(default=None, description="Target entity hit points after the action, if relevant.")
    deaths: List[str] = Field(default_factory=list, description="Names of entities that died during the action.")
    triggered_reactions: List[Dict[str, JsonValue]] = Field(
        default_factory=list,
        description="Structured reaction summaries triggered by the action.",
    )
    turn_continues: bool = Field(default=True, description="Whether the acting entity's turn continues.")
    encounter_ended: bool = Field(default=False, description="Whether the encounter ended because of the action.")
    combat_log_entries: List[CombatLogEntry] = Field(
        default_factory=list,
        description="Combat log entries generated by the action.",
    )
    available_actions: Optional[APIAvailableActions] = Field(
        default=None,
        description="Updated available actions after execution.",
    )
    state: Optional[APIGameState] = Field(default=None, description="Full game-state snapshot after execution.")
    server_timing: Optional[APIServerTiming] = Field(
        default=None,
        description="Server-side route timing when requested.",
    )
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after all side effects.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after all side effects.")


class AdvanceEncounterResult(BaseModel):
    """Result of advancing combat until the next player-controlled turn.

    Attributes:
        status: Advancement status label.
        entity_uuid: UUID of the next player-controlled entity, if any.
        entity_name: Name of the next player-controlled entity, if any.
        round: Current encounter round after advancing.
        turn_index: Current turn index after advancing.
        ai_actions: Actions taken by automated controllers while advancing.
        new_log_since: Combat-log cursor used for newly generated logs.
        event_cursor_after: Event-history cursor after advancement.
        combat_log_cursor_after: Combat-log cursor after advancement.
    """

    status: str = Field(description="Advancement status label.")
    entity_uuid: Optional[str] = Field(default=None, description="UUID of the next player-controlled entity, if any.")
    entity_name: Optional[str] = Field(default=None, description="Name of the next player-controlled entity, if any.")
    round: Optional[int] = Field(default=None, description="Current encounter round after advancing.")
    turn_index: Optional[int] = Field(default=None, description="Current turn index after advancing.")
    ai_actions: List[CombatLogEntry] = Field(
        default_factory=list,
        description="Action log entries produced by automated controllers while advancing.",
    )
    new_log_since: Optional[int] = Field(default=None, description="Combat-log cursor used for newly generated logs.")
    event_cursor_after: Optional[int] = Field(default=None, description="Event-history cursor after advancement.")
    combat_log_cursor_after: Optional[int] = Field(default=None, description="Combat-log cursor after advancement.")


class StartHumanSimulationResponse(AdvanceEncounterResult):
    """Result of creating the standard human-versus-AI simulation.

    Attributes:
        ai_session_id: Session controlling the AI side.
        encounter_uuid: Newly created encounter UUID.
        hero_uuid: Human-controllable hero UUID, when present.
        message: Human-readable setup summary.
    """

    ai_session_id: str = Field(description="Session controlling the AI side.")
    encounter_uuid: str = Field(description="Newly created encounter UUID.")
    hero_uuid: Optional[str] = Field(default=None, description="Human-controllable hero UUID, when present.")
    message: str = Field(description="Human-readable setup summary.")


class TakeoverRequest(BaseModel):
    """Request to claim combatants for Codex control.

    Attributes:
        faction: Faction to claim when explicit entities are not provided.
        entity_uuids: Explicit entity UUIDs to claim.
        session_id: Existing Codex session to reuse.
        name: Display name for a newly created Codex session.
        force: Whether to replace an overlapping live takeover claim.
        lease_seconds: Number of seconds before the claim expires without a heartbeat.
    """

    faction: Optional[str] = Field(default="monsters", description="Faction to claim when explicit entities are not provided.")
    entity_uuids: Optional[List[str]] = Field(default=None, description="Explicit entity UUIDs to claim.")
    session_id: Optional[str] = Field(default=None, description="Existing Codex session to reuse.")
    name: str = Field(default="Codex Monsters", description="Display name for a newly created Codex session.")
    force: bool = Field(default=False, description="Whether to replace an overlapping live takeover claim.")
    lease_seconds: float = Field(default=120.0, gt=0, description="Seconds before claim expiry without heartbeat.")


class TakeoverEntityRow(BaseModel):
    """Entity row included in takeover claim responses."""

    entity_uuid: str = Field(description="Claimed entity UUID.")
    entity_name: str = Field(description="Claimed entity display name.")
    faction: Optional[str] = Field(default=None, description="Claimed entity faction.")
    previous_controller_uuid: str = Field(description="Controller UUID to restore on release.")
    previous_controller_type: Optional[str] = Field(default=None, description="Controller type to restore on release.")
    current_controller_type: Optional[str] = Field(default=None, description="Controller type currently assigned.")
    previous_owner_session_id: Optional[str] = Field(default=None, description="Previous owning session UUID.")


class TakeoverClaimResponse(BaseModel):
    """Serialized Codex takeover claim."""

    claim_id: str = Field(description="Takeover claim UUID.")
    session_id: str = Field(description="Codex session UUID controlling the claim.")
    name: str = Field(description="Claim display name.")
    faction: Optional[str] = Field(default=None, description="Faction claimed, when faction-based.")
    created_at: float = Field(description="Unix timestamp when the claim was created.")
    last_heartbeat_at: float = Field(description="Unix timestamp of the latest heartbeat.")
    lease_seconds: float = Field(description="Lease duration in seconds.")
    expires_at: float = Field(description="Unix timestamp when the claim expires.")
    is_expired: bool = Field(description="Whether the claim is expired at serialization time.")
    claimed_entities: List[TakeoverEntityRow] = Field(description="Entities controlled by the claim.")


class TakeoverListResponse(BaseModel):
    """List of active or known takeover claims."""

    claims: List[TakeoverClaimResponse] = Field(description="Takeover claim rows.")


class TakeoverHeartbeatResponse(BaseModel):
    """Response after refreshing a takeover claim."""

    status: str = Field(description="Heartbeat result status.")
    claim: TakeoverClaimResponse = Field(description="Refreshed claim.")


class TakeoverReleaseResponse(BaseModel):
    """Response after releasing a takeover claim."""

    status: str = Field(description="Release result status.")
    claim: Optional[TakeoverClaimResponse] = Field(default=None, description="Released claim, if found.")
    advance_result: Optional[AdvanceEncounterResult] = Field(default=None, description="Advancement result after release.")


class EventHistoryResponse(BaseModel):
    """Cursor-addressed history of original domain events.

    Attributes:
        events: Domain events in the requested cursor window.
        count: Number of returned events.
        total: Total number of stored events.
    """

    generation_id: str = Field(description="EventQueue generation containing these events.")
    events: List[SerializeAsAny[Event]] = Field(description="Domain events in the requested cursor window.")
    count: int = Field(description="Number of returned events.")
    total: int = Field(description="Total number of stored events.")

    @field_serializer("events")
    def serialize_wire_events(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Serialize history through the same contract used by live streams."""
        return [serialize_event(event) for event in events]


class CombatLogHistoryResponse(BaseModel):
    """Cursor-addressed history of combat log entries.

    Attributes:
        entries: Combat log entries in the requested cursor window.
        count: Number of returned combat log entries.
        total: Total number of stored combat log entries.
    """

    generation_id: str = Field(description="EventQueue generation paired with these log entries.")
    entries: List[CombatLogEntry] = Field(description="Combat log entries in the requested cursor window.")
    count: int = Field(description="Number of returned combat log entries.")
    total: int = Field(description="Total number of stored combat log entries.")


class ReplicationProtocolIdentity(BaseModel):
    """Identity of one compatible replication protocol and event history."""

    generation_id: str = Field(description="Current EventQueue generation UUID.")
    event_contract_version: int = Field(description="Generated event-contract version.")
    event_contract_hash: str = Field(description="Generated event-contract content hash.")


class EventContractSummary(BaseModel):
    """Public identity and discriminators for the generated event contract."""

    contract_version: int = Field(description="Generated event-contract version.")
    contract_hash: str = Field(description="Generated event-contract content hash.")
    event_types: List[str] = Field(description="All semantic event type values.")
    wire_types: List[str] = Field(description="All concrete event wire discriminators.")


class ReplicationBootstrapResponse(BaseModel):
    """Atomic base state and cursors used to start or recover replication."""

    protocol: ReplicationProtocolIdentity = Field(description="Protocol and history identity.")
    event_cursor: int = Field(description="First event cursor not represented by the snapshot.")
    combat_log_cursor: int = Field(description="First combat-log cursor not represented by the snapshot.")
    state: APIGameState = Field(description="Authoritative public game-state snapshot.")
    visibility: APIVisibilityResponse = Field(description="Current observer visibility snapshot.")
    combat_log: List[CombatLogEntry] = Field(
        description="Combat-log history represented by combat_log_cursor.",
    )
    session: Optional[SessionPingResponse] = Field(
        default=None,
        description="Current session status when a session was requested.",
    )
