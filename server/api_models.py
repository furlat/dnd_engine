"""
Pydantic models for the REST API.

These models are the serialization layer between game Entity objects
(which have callables and can't serialize) and JSON responses.

Each model has a .create() classmethod that takes the game object and
extracts the relevant data.
"""

from pydantic import BaseModel
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from dnd.entity import Entity
    from dnd.core.gridmap import GridMap
    from dnd.encounter import Encounter


class APIEntitySummary(BaseModel):
    """Lightweight entity for list views and event-driven updates."""
    uuid: str
    name: str
    position: Tuple[int, int]
    hp: int
    max_hp: int
    ac: int
    conditions: List[str]
    is_dead: bool

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntitySummary':
        # Compute max HP (needs constitution modifier)
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
            is_dead=entity.get_hp() <= 0
        )


class APIEntityFull(APIEntitySummary):
    """Full entity details for single-entity queries."""
    action_economy: dict
    ability_scores: dict
    weapon_name: Optional[str]

    @classmethod
    def create(cls, entity: 'Entity') -> 'APIEntityFull':
        # Compute max HP
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
            is_dead=entity.get_hp() <= 0,
            action_economy={
                'actions': entity.action_economy.actions.normalized_score,
                'bonus_actions': entity.action_economy.bonus_actions.normalized_score,
                'reactions': entity.action_economy.reactions.normalized_score,
                'movement': entity.action_economy.movement.normalized_score,
            },
            ability_scores={
                'strength': entity.ability_scores.strength.ability_score.normalized_score,
                'dexterity': entity.ability_scores.dexterity.ability_score.normalized_score,
                'constitution': entity.ability_scores.constitution.ability_score.normalized_score,
                'intelligence': entity.ability_scores.intelligence.ability_score.normalized_score,
                'wisdom': entity.ability_scores.wisdom.ability_score.normalized_score,
                'charisma': entity.ability_scores.charisma.ability_score.normalized_score,
            },
            weapon_name=weapon.name if weapon else None
        )


class APITile(BaseModel):
    """Single tile data."""
    x: int
    y: int
    walkable: bool
    visible: bool


class APIGrid(BaseModel):
    """Grid/map data."""
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    tiles: List[APITile]

    @classmethod
    def create(cls, grid: 'GridMap') -> 'APIGrid':
        bounds = grid.bounds  # Returns (min_x, min_y, max_x, max_y)
        tiles = [
            APITile(x=x, y=y, walkable=td.walkable, visible=td.visible)
            for (x, y), td in grid._tiles.items()
        ]
        return cls(
            min_x=bounds[0], min_y=bounds[1],
            max_x=bounds[2], max_y=bounds[3],
            tiles=tiles
        )


class APICombatant(BaseModel):
    """Combatant in initiative order."""
    uuid: str
    name: str
    initiative: int
    is_dead: bool


class APIEncounter(BaseModel):
    """Encounter/combat state."""
    uuid: str
    name: str
    state: str
    round_number: int
    current_turn_index: int
    current_entity_uuid: Optional[str]
    initiative_order: List[APICombatant]

    @classmethod
    def create(cls, encounter: 'Encounter') -> 'APIEncounter':
        from dnd.entity import Entity
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


class APIGameState(BaseModel):
    """Full state for initial load."""
    grid: APIGrid
    entities: List[APIEntitySummary]
    encounter: Optional[APIEncounter]


class APISimulationStatus(BaseModel):
    """Simulation control status."""
    has_encounter: bool
    paused: bool
    encounter_state: Optional[str]
    round_number: Optional[int]
    turn_delay: float


# =============================================================================
# Human Control Models
# =============================================================================

class APICurrentTurn(BaseModel):
    """Current turn information."""
    encounter_active: bool
    round_number: int
    turn_index: int
    current_entity_uuid: Optional[str]
    current_entity_name: Optional[str]
    is_human_turn: bool
    waiting_for_input: bool
    controller_type: Optional[str]

    # Action economy for current entity
    actions_remaining: int = 0
    bonus_actions_remaining: int = 0
    reactions_remaining: int = 0
    movement_remaining: int = 0


# =============================================================================
# Session Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new player session."""
    player_type: str  # "human" or "claude"
    name: Optional[str] = None  # Display name (optional)


class CreateSessionResponse(BaseModel):
    """Response from creating a session."""
    session_id: str
    player_type: str
    name: str


class SessionPingResponse(BaseModel):
    """Response from session ping."""
    status: str
    session_id: str
    connection_status: str
    is_my_turn: bool
    active_entity_uuid: Optional[str]
    active_entity_name: Optional[str]
    controlled_entities: List[str]


class JoinGameRequest(BaseModel):
    """Request to join a game with a session."""
    session_id: str
    entity_uuids: Optional[List[str]] = None  # Entities to control (optional, auto-assign if not provided)


class JoinGameResponse(BaseModel):
    """Response from joining a game."""
    success: bool
    game_id: str
    session_id: str
    controlled_entities: List[str]
    message: str


# =============================================================================
# Request models for action endpoints (with session support)
# =============================================================================

class MoveRequest(BaseModel):
    """Request body for move action."""
    session_id: str  # Required: session performing the action
    entity_uuid: str
    position: Tuple[int, int]


class AttackRequest(BaseModel):
    """Request body for attack action."""
    session_id: str  # Required: session performing the action
    entity_uuid: str
    target_uuid: str
    weapon_slot: str = "main_hand"  # "main_hand" or "off_hand"


class SimpleActionRequest(BaseModel):
    """Request body for simple actions (dash, dodge, disengage, end-turn)."""
    session_id: str  # Required: session performing the action
    entity_uuid: str


# =============================================================================
# Generic Action Request Models (New API)
# =============================================================================

class SelfActionRequest(BaseModel):
    """Request for self-targeting actions (Dash, Dodge, Disengage, StandUp)."""
    session_id: str
    entity_uuid: str
    action_name: str  # Template name: "Dash", "Dodge", "Disengage", "StandUp"


class EntityActionRequest(BaseModel):
    """Request for entity-targeting actions (Attack)."""
    session_id: str
    entity_uuid: str
    action_name: str  # Template name: "Attack_MELEE_MAIN", etc.
    target_uuid: str


class PositionActionRequest(BaseModel):
    """Request for position-targeting actions (Move)."""
    session_id: str
    entity_uuid: str
    action_name: str  # Template name: "Move"
    position: Tuple[int, int]


class ExecuteByIndexRequest(BaseModel):
    """Request to execute action by template name + target index.

    Enables 'attack 0', 'move 3' style commands.
    """
    session_id: str
    entity_uuid: str
    template_name: str  # Action template name
    target_index: int   # Index from valid_targets list


# Response models

class ActionResult(BaseModel):
    """Result of an action execution."""
    success: bool
    message: str
    event_type: Optional[str] = None
    event_data: Optional[dict] = None

    # Updated state after action
    entity_hp: Optional[int] = None
    target_hp: Optional[int] = None
    deaths: List[str] = []  # Names of entities that died

    # Triggered reactions (e.g., opportunity attacks during movement)
    triggered_reactions: List[dict] = []

    # Turn continuation info
    turn_continues: bool = True  # False if turn ended or entity died
    encounter_ended: bool = False
