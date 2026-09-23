"""Tile-owned residue profiles and their optional native entry damage."""

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Literal, cast
from uuid import UUID

from pydantic import Field

from dnd.conditions import Frightened, residue_fear_origin, same_residue_ground
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.condition_types import HazardFilter
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome
from dnd.core.events import Damage, Event, EventPhase, EventQueue, SavingThrowEvent, SpatialChangeEvent, SpatialHandler
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.core.saving_throw_types import SavingThrowContext, SavingThrowEffectTag
from dnd.entity import Entity
from dnd.types.abilities import AbilityName
from dnd.types.residues import ObjectResidueState, ResidueContribution, ResidueEllipse, TileResidueState
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


class TileResidueCondition(BaseCondition):
    """One persistent residue membership; the Tile owns all its mechanics."""

    name: str = "Tile Residue"
    description: str = "Persistent material deposited on a tile."
    profile: ResidueProfile
    amount: int = Field(default=1, ge=1)
    contributions: tuple[ResidueContribution, ...] = ()
    affected_occupancy_layers: frozenset[OccupancyLayer] = Field(
        default_factory=lambda: frozenset({OccupancyLayer.GROUND}),
    )

    def snapshot_tile_residue(self) -> TileResidueState:
        return TileResidueState(
            condition_uuid=self.uuid,
            residue_id=self.profile.residue_id,
            description=self.description,
            amount=self.amount,
            max_amount=self.profile.max_amount,
            contributions=self.contributions,
        )

    def on_membership_changed(self, event: Event) -> None:
        if self.hazard_filter is None:
            return
        grid = get_map()
        tile = grid.get_tile_by_uuid(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if tile is None:
            return
        grid.invalidate_spatial_caches({"movement"})
        grid.publish_tile_mechanics_changed(
            tile.position, source_entity_uuid=tile.uuid, parent_event=event.uuid,
        )

    def _apply(self, execution_event: Event):
        tile = get_map().get_tile_by_uuid(self.target_entity_uuid) if self.target_entity_uuid is not None else None
        if tile is None:
            return [], [], [], [], execution_event.cancel(status_message="Residue tile is absent")
        handlers: list[UUID] = []
        if self.profile.entry_damage is not None or self.profile.entry_fear is not None:
            handler = SpatialHandler(
                name=f"{self.name} Entry",
                source_entity_uuid=tile.uuid,
                positions={tile.position},
                event_processor=self._on_entry,
            )
            EventQueue.add_spatial_handler(handler)
            handlers.append(handler.uuid)
        return [], [], [], handlers, execution_event.phase_to(EventPhase.EFFECT)

    def _on_entry(self, event: Event, _source_uuid: UUID) -> Event:
        entry = cast(SpatialChangeEvent, event)
        if not self.admits_occupancy_transition(entry):
            return event
        entity = Entity.get(entry.entity_uuid) if entry.entity_uuid is not None else None
        payload = self.profile.entry_damage
        if entity is None:
            return event
        if entry.occupancy_layer is None and not self.affects_occupancy_layer(entity.get_occupancy_layer()):
            return event
        if payload is not None:
            self._damage_entrant(entity, payload, entry)
        fear_payload = self.profile.entry_fear
        if fear_payload is not None and entity.is_encounter_alive:
            self._frighten_entrant(entity, fear_payload, entry)
        return event

    def _damage_entrant(self, entity: Entity, payload: ResidueDamage, entry: SpatialChangeEvent) -> None:
        damage = Damage(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            damage_dice=payload.dice_sides,
            dice_numbers=payload.dice_count,
            damage_type=payload.damage_type,
            damage_bonus=ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=entity.uuid,
                base_value=0,
                value_name=f"{self.name} Damage",
            ),
        )
        roll = damage.get_dice(AttackOutcome.HIT).roll
        entity.receive_damage(
            roll.total, payload.damage_type, self.source_entity_uuid,
            damage_rolls=[roll], damages=[damage], parent_event=entry.uuid,
            effect_id=self.profile.residue_id,
        )

    def _frighten_entrant(self, entity: Entity, payload: ResidueFear, entry: SpatialChangeEvent) -> None:
        if (entry.old_position is not None and entry.previous_occupancy_layer is OccupancyLayer.GROUND
                and same_residue_ground(entry.old_position, entry.position, self.profile.residue_id)):
            return
        request = SavingThrowEvent(
            source_entity_uuid=self.source_entity_uuid, target_entity_uuid=entity.uuid,
            source_entity_name=self.name, target_entity_name=entity.name,
            ability_name=payload.save_ability, dc=payload.save_dc,
            parent_event=entry.uuid,
            saving_throw_context=SavingThrowContext(
                cause_id="condition.tile.residue", effect_id=self.profile.residue_id,
                condition_id="condition.frightened", is_magical=False,
                effect_tags=(SavingThrowEffectTag.FEAR,),
            ),
        )
        _, _, success = entity.saving_throw(request)
        if success:
            return
        fear = Frightened(
            source_entity_uuid=self.uuid, target_entity_uuid=entity.uuid,
            description=(
                "Frightened by this pool: attacks and ability checks have disadvantage while it is visible. "
                "Retreat toward the entry direction using available movement; the fear ends on exit."
            ),
            residue_origin=residue_fear_origin(
                entry, tile_uuid=self.source_entity_uuid, condition_uuid=self.uuid,
                residue_id=self.profile.residue_id,
            ),
        )
        # The actor remains afraid while contacting this connected material,
        # rather than being a child of the first tile's particular membership.
        entity.add_condition(fear, check_save_throw=False, parent_event=entry)


def deposit_residue(
    tile: Tile, profile: ResidueProfile, *, parent_event: Event | None = None,
    ellipses: tuple[ResidueEllipse, ...] = (),
    amount: int = 1,
    deposit_source: MaterialDepositSource | None = None,
) -> TileResidueState | None:
    """Accumulate the authored amount within one existing native membership."""
    if amount < 1:
        raise ValueError("Deposited residue amount must be positive")
    existing = tile.active_conditions.get(profile.name)
    if existing is not None:
        state = existing.snapshot_tile_residue()
        if state is None or state.residue_id != profile.residue_id:
            raise ValueError(f"Residue name collides with another condition: {profile.name}")
        if state.amount < profile.max_amount:
            condition = cast(TileResidueCondition, existing)
            added = min(amount, profile.max_amount - state.amount)
            condition.amount = state.amount + added
            if ellipses or deposit_source is not None:
                matching = next((i for i, row in enumerate(condition.contributions)
                    if row.ellipses == ellipses and row.deposit_source == deposit_source), None)
                if matching is None:
                    condition.contributions += (ResidueContribution(
                        ellipses=ellipses, amount=added, deposit_source=deposit_source),)
                else:
                    rows = list(condition.contributions)
                    row = rows[matching]
                    rows[matching] = row.model_copy(update={"amount": row.amount + added})
                    condition.contributions = tuple(rows)
            get_map().publish_tile_state_changed(tile.position, source_entity_uuid=tile.uuid,
                parent_event=parent_event.uuid if parent_event is not None else None)
            return condition.snapshot_tile_residue()
        return state
    condition = TileResidueCondition(
        name=profile.name, description=profile.description, profile=profile,
        amount=min(amount, profile.max_amount),
        contributions=(ResidueContribution(ellipses=ellipses, amount=min(amount, profile.max_amount),
            deposit_source=deposit_source),) if ellipses or deposit_source is not None else (),
        source_entity_uuid=tile.uuid, target_entity_uuid=tile.uuid,
        hazard_filter=HazardFilter.ALL if profile.entry_damage is not None or profile.entry_fear is not None else None,
    )
    result = tile.add_condition(condition, parent_event=parent_event)
    if result is None or result.canceled:
        return None
    return condition.snapshot_tile_residue()


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
    for position in positions:
        tile = grid.get_tile(*position)
        if tile is None:
            continue
        deposit_residue(tile, profile, parent_event=parent_event)
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
