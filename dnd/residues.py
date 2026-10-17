"""Tile-owned residue profiles and their optional native entry damage."""

from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from functools import partial
from typing import Literal, cast
from uuid import UUID, uuid4, uuid5

from dnd.conditions import Frightened, residue_fear_origin, same_residue_ground
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventQueue, EventType, SavingThrowEvent, SpatialChangeEvent, SpatialHandler
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.types.abilities import AbilityName
from dnd.types.residues import ObjectResidueState, ResidueContribution, ResidueEllipse, ResidueFieldState, TileResidueState
from dnd.types.material_deposits import MaterialDepositSource
from dnd.types.world import CardinalDirection, OccupancyLayer, WorldEdgeChannel


@dataclass(frozen=True, slots=True)
class ResidueDamage:
    dice_count: int
    dice_sides: Literal[4, 6, 8, 10, 12, 20]
    damage_type: DamageType


@dataclass(frozen=True, slots=True)
class ResidueFear:
    save_dc: int
    save_ability: AbilityName = "wisdom"


@dataclass(frozen=True, slots=True)
class ResidueProfile:
    residue_id: str
    name: str
    description: str
    entry_damage: ResidueDamage | None = None
    entry_fear: ResidueFear | None = None
    max_amount: int = 1


BLOOD_RESIDUE = ResidueProfile(
    "residue.blood", "Bloodied", "Blood stains the ground.", max_amount=5,
)
BONE_RESIDUE = ResidueProfile(
    "residue.bone_fragments", "Bone Fragments", "Bone fragments lie scattered on the ground.",
)
ASHEN_RESIDUE = ResidueProfile(
    "residue.ashen", "Ashen", "Ash and scorch marks cover the ground.",
)
CORROSIVE_RESIDUE = ResidueProfile(
    "residue.corrosive_demonic_blood", "Corrosive Demonic Blood",
    "Corrosive demonic blood coats the ground, dealing 1d4 acid damage on entry.",
    ResidueDamage(1, 4, DamageType.ACID),
)
POISON_RESIDUE = ResidueProfile(
    "residue.poison", "Poison Pool",
    "Poison coats the ground, dealing 1d4 poison damage on entry.",
    ResidueDamage(1, 4, DamageType.POISON),
)
DREAD_RESIDUE = ResidueProfile(
    "residue.dread_blood", "Dread Blood",
    "Dread blood stains the ground. Entry requires a Wisdom DC 10 save or a frightened retreat.",
    entry_fear=ResidueFear(10),
)


def _hazardous(profile: ResidueProfile) -> bool:
    return profile.entry_damage is not None or profile.entry_fear is not None


def _cell_identity(field: ResidueFieldState, position: tuple[int, int]) -> UUID:
    """The stable identity of one cell's residue membership in its material's field."""
    return uuid5(field.uuid, f"{position[0]},{position[1]}")


# Authored profiles by material id; every deposit of a material carries the same immutable profile.
_PROFILES: dict[str, ResidueProfile] = {}


def _residue_field(profile: ResidueProfile) -> ResidueFieldState:
    _PROFILES.setdefault(profile.residue_id, profile)
    grid = get_map()
    field = grid.residue_field(profile.residue_id)
    if field is None:
        field = ResidueFieldState(uuid=uuid4(), residue_id=profile.residue_id)
        grid.install_residue_field(field)
    return field


def _admits_ground_transition(entry: SpatialChangeEvent) -> bool:
    """A ground entry, not a repeated contact of an unchanged ground occupant."""
    entering = entry.event_type is EventType.SPATIAL_ENTITY_ENTERED
    layer = entry.occupancy_layer if entering else entry.previous_occupancy_layer
    if layer is not None and layer is not OccupancyLayer.GROUND:
        return False
    other_layer = entry.previous_occupancy_layer if entering else entry.occupancy_layer
    return not (entry.old_position == entry.position and layer is not None
                and other_layer is OccupancyLayer.GROUND)


def _on_residue_entry(profile: ResidueProfile, event: Event, _source_uuid: UUID) -> Event:
    """The material's one entry rule, at whichever of its cells was entered."""
    entry = cast(SpatialChangeEvent, event)
    if not _admits_ground_transition(entry):
        return event
    entity = Entity.get(entry.entity_uuid) if entry.entity_uuid is not None else None
    tile = get_map().get_tile(*entry.position) if entry.position is not None else None
    state = tile.residue_state(profile.residue_id) if tile is not None else None
    if entity is None or tile is None or state is None:
        return event
    if entry.occupancy_layer is None and entity.get_occupancy_layer() is not OccupancyLayer.GROUND:
        return event
    if profile.entry_damage is not None:
        _damage_entrant(profile, profile.entry_damage, tile, entity, entry)
    if profile.entry_fear is not None and entity.is_encounter_alive:
        _frighten_entrant(profile, profile.entry_fear, tile, state, entity, entry)
    return event


def _damage_entrant(profile: ResidueProfile, payload: ResidueDamage, tile: Tile, entity: Entity,
                    entry: SpatialChangeEvent) -> None:
    damage = Damage(
        name=profile.name,
        source_entity_uuid=tile.uuid,
        target_entity_uuid=entity.uuid,
        damage_dice=payload.dice_sides,
        dice_numbers=payload.dice_count,
        damage_type=payload.damage_type,
        damage_bonus=ModifiableValue.create(
            source_entity_uuid=tile.uuid,
            base_value=0,
            value_name=f"{profile.name} Damage",
        ),
    )
    roll = damage.get_dice(AttackOutcome.HIT).roll
    entity.receive_damage(
        roll.total, payload.damage_type, tile.uuid,
        damage_rolls=[roll], damages=[damage], parent_event=entry.uuid,
        effect_id=profile.residue_id, independent_resolution=True,
    )


def _frighten_entrant(profile: ResidueProfile, payload: ResidueFear, tile: Tile, state: TileResidueState,
                      entity: Entity, entry: SpatialChangeEvent) -> None:
    if (entry.old_position is not None and entry.previous_occupancy_layer is OccupancyLayer.GROUND
            and same_residue_ground(entry.old_position, entry.position, profile.residue_id)):
        return
    request = SavingThrowEvent(
        source_entity_uuid=tile.uuid, target_entity_uuid=entity.uuid,
        source_entity_name=profile.name, target_entity_name=entity.name,
        ability_name=payload.save_ability, dc=payload.save_dc,
        parent_event=entry.uuid,
        saving_throw_context=SavingThrowContext(
            cause_id="condition.tile.residue", effect_id=profile.residue_id,
            condition_id="condition.frightened", is_magical=False,
            effect_tags=(SavingThrowEffectTag.FEAR,),
        ),
    )
    _, _, success = entity.saving_throw(request)
    if success:
        return
    fear = Frightened(
        source_entity_uuid=state.condition_uuid, target_entity_uuid=entity.uuid,
        description=(
            "Frightened by this pool: attacks and ability checks have disadvantage while it is visible. "
            "Retreat toward the entry direction using available movement; the fear ends on exit."
        ),
        residue_origin=residue_fear_origin(
            entry, tile_uuid=tile.uuid, condition_uuid=state.condition_uuid,
            residue_id=profile.residue_id,
        ),
    )
    # The actor remains afraid while contacting this connected material,
    # rather than being a child of the first tile's particular membership.
    entity.add_condition(fear, check_save_throw=False, parent_event=entry)


def deposit_residues(
    profile: ResidueProfile, cells: Mapping[tuple[int, int], tuple[ResidueEllipse, ...]], *,
    source_entity_uuid: UUID, parent_event: Event | None = None,
    amount: int = 1, deposit_source: MaterialDepositSource | None = None,
) -> dict[tuple[int, int], TileResidueState]:
    """One deposit of one material over many cells: one field update, one fact (plan §5.9, D15).

    Each cell accumulates the authored amount up to the material's maximum; a
    cell already at its maximum keeps its after-value. Returns every existing
    cell's after-value.
    """
    if amount < 1:
        raise ValueError("Deposited residue amount must be positive")
    grid = get_map()
    field = _residue_field(profile)
    hazardous = _hazardous(profile)
    results: dict[tuple[int, int], TileResidueState] = {}
    changed: list[tuple[int, int]] = []
    new_cells: list[tuple[int, int]] = []
    for position, ellipses in cells.items():
        tile = grid.get_tile(*position)
        if tile is None:
            continue
        previous = tile.residue_state(profile.residue_id)
        if previous is None:
            added = min(amount, profile.max_amount)
            state = TileResidueState(
                condition_uuid=_cell_identity(field, position), residue_id=profile.residue_id,
                description=profile.description, amount=added, max_amount=profile.max_amount,
                contributions=((ResidueContribution(ellipses=ellipses, amount=added, deposit_source=deposit_source),)
                               if ellipses or deposit_source is not None else ()))
            new_cells.append(position)
        elif previous.amount < profile.max_amount:
            added = min(amount, profile.max_amount - previous.amount)
            contributions = previous.contributions
            if ellipses or deposit_source is not None:
                matching = next((index for index, row in enumerate(contributions)
                    if row.ellipses == ellipses and row.deposit_source == deposit_source), None)
                if matching is None:
                    contributions += (ResidueContribution(ellipses=ellipses, amount=added, deposit_source=deposit_source),)
                else:
                    rows = list(contributions)
                    rows[matching] = rows[matching].model_copy(update={"amount": rows[matching].amount + added})
                    contributions = tuple(rows)
            state = previous.model_copy(update={"amount": previous.amount + added, "contributions": contributions})
        else:
            results[position] = previous
            continue
        tile.record_residue(state, name=profile.name, hazardous=hazardous)
        results[position] = state
        changed.append(position)
    field.cells.update(new_cells)
    parent_uuid = parent_event.uuid if parent_event is not None else None
    if new_cells and hazardous:
        # The material's one entry rule covers every cell it now lies on.
        _cover_entry_cells(field, profile)
        # New hazards change traversal (hazard avoidance) at those cells.
        grid.commit_tile_mechanics(changed, source_entity_uuid=source_entity_uuid, parent_event=parent_uuid)
    elif changed:
        grid.publish_tiles_state_changed(changed, source_entity_uuid=source_entity_uuid, parent_event=parent_uuid)
    return results


def _cover_entry_cells(field: ResidueFieldState, profile: ResidueProfile) -> None:
    """Keep the material's one entry handler over exactly the cells it lies on."""
    if field.entry_handler_uuid is not None:
        EventQueue.remove_spatial_handler(field.entry_handler_uuid)
        field.entry_handler_uuid = None
    if field.cells:
        handler = SpatialHandler(name=f"{profile.name} Entry", source_entity_uuid=field.uuid,
            positions=set(field.cells), event_processor=partial(_on_residue_entry, profile))
        EventQueue.add_spatial_handler(handler)
        field.entry_handler_uuid = handler.uuid


def remove_residues(
    residue_id: str, positions: Iterable[tuple[int, int]], *,
    source_entity_uuid: UUID, parent_event: Event | None = None,
) -> dict[tuple[int, int], TileResidueState]:
    """Remove one material from many cells: one field update, one fact. Returns the removed after-values."""
    grid = get_map()
    field = grid.residue_field(residue_id)
    if field is None:
        return {}
    profile = _PROFILES[residue_id]
    removed: dict[tuple[int, int], TileResidueState] = {}
    for position in positions:
        tile = grid.get_tile(*position)
        state = tile.forget_residue(residue_id) if tile is not None else None
        if state is not None:
            removed[position] = state
            field.cells.discard(position)
    if not removed:
        return removed
    parent_uuid = parent_event.uuid if parent_event is not None else None
    if _hazardous(profile):
        _cover_entry_cells(field, profile)
        grid.commit_tile_mechanics(removed, source_entity_uuid=source_entity_uuid, parent_event=parent_uuid)
    else:
        grid.publish_tiles_state_changed(removed, source_entity_uuid=source_entity_uuid, parent_event=parent_uuid)
    return removed


def remove_tile_residue(tile: Tile, residue_id: str, *, parent_event: Event | None = None) -> bool:
    """Remove one material from one tile; whether it lay there."""
    return bool(remove_residues(residue_id, (tile.position,), source_entity_uuid=tile.uuid, parent_event=parent_event))


def deposit_residue(
    tile: Tile, profile: ResidueProfile, *, parent_event: Event | None = None,
    ellipses: tuple[ResidueEllipse, ...] = (),
    amount: int = 1,
    deposit_source: MaterialDepositSource | None = None,
) -> TileResidueState | None:
    """One cell's deposit; a deposit covering several cells calls `deposit_residues` once."""
    return deposit_residues(profile, {tile.position: ellipses}, source_entity_uuid=tile.uuid,
        parent_event=parent_event, amount=amount, deposit_source=deposit_source).get(tile.position)


class ObjectResidueCondition(BaseCondition):
    """Inert material on an object's contacted faces, using ordinary membership."""

    requires_intact_item: bool = False

    profile: ResidueProfile
    faces: tuple[CardinalDirection, ...]

    def snapshot_object_residue(self) -> ObjectResidueState:
        return ObjectResidueState(
            condition_uuid=self.uuid, residue_id=self.profile.residue_id,
            description=self.description, faces=self.faces,
        )


def deposit_area_residue(
    positions: Iterable[tuple[int, int]], profile: ResidueProfile, *, parent_event: Event,
) -> None:
    """Deposit one inert area residue on reached tiles and their contacted boundaries."""
    grid = get_map()
    contacted: dict[UUID, set[CardinalDirection]] = {}
    opposites = {
        CardinalDirection.NORTH: CardinalDirection.SOUTH,
        CardinalDirection.SOUTH: CardinalDirection.NORTH,
        CardinalDirection.EAST: CardinalDirection.WEST,
        CardinalDirection.WEST: CardinalDirection.EAST,
    }
    reached = [position for position in positions if grid.get_tile(*position) is not None]
    deposit_residues(profile, {position: () for position in reached},
        source_entity_uuid=parent_event.source_entity_uuid or parent_event.uuid, parent_event=parent_event)
    for position in reached:
        for direction, face in opposites.items():
            layers = grid.get_boundary_route_layers(position, direction, WorldEdgeChannel.PROPAGATION)
            for layer in layers:
                for identity in layer:
                    contacted.setdefault(identity, set()).add(face)
    for identity, faces in contacted.items():
        owner = BaseBlock.get(identity)
        if owner is None or owner.get_boundary_structure() is None:
            continue
        existing = owner.active_conditions.get(profile.name)
        if existing is not None:
            state = existing.snapshot_object_residue()
            if state is None or state.residue_id != profile.residue_id:
                raise ValueError(f"Residue name collides with another condition: {profile.name}")
            if faces.issubset(state.faces):
                continue
            faces.update(state.faces)
        condition = ObjectResidueCondition(
            name=profile.name, description=profile.description, profile=profile,
            faces=tuple(direction for direction in CardinalDirection if direction in faces),
            source_entity_uuid=identity, target_entity_uuid=identity,
        )
        owner.add_condition(condition, parent_event=parent_event)
