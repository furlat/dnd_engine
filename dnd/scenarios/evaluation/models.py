"""Typed mechanical blueprints for composable evaluation scenarios."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import WeaponSlot


AbilityName = Literal["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
SideKind = Literal["hero", "monster_party"]
DamageTypeName = Literal[
    "Acid",
    "Bludgeoning",
    "Cold",
    "Fire",
    "Force",
    "Lightning",
    "Necrotic",
    "Piercing",
    "Poison",
    "Psychic",
    "Radiant",
    "Slashing",
    "Thunder",
]
LightLevelName = Literal["bright", "darkness"]
BattlefieldPreviewTerrain = Literal["water", "difficult_terrain", "spikes"]
BattlefieldPreviewDirection = Literal["north", "south", "east", "west"]
BattlefieldPreviewObjectKind = Literal[
    "wall",
    "door",
    "wall_torch",
    "healing_potion",
    "trap_lever",
    "fireball_cannon",
    "loot_chest",
]
BestiaryArchetype = Literal[
    "caster",
    "goblin",
    "goblin_archer",
    "skeleton_archer",
    "skeleton_warlock",
    "skeleton_warrior",
]
FighterStyleName = Literal["archery", "defense", "dueling", "great_weapon", "protection", "two_weapon"]
FighterEquipmentPreset = Literal["sword_shield", "greatsword", "dual_wield", "archery"]
BarbarianEquipmentPreset = Literal["greataxe", "dual_axes", "sword_shield"]


class SpellGrant(BaseModel):
    """Additional spells registered after base actor construction."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["spell_grant"] = Field(default="spell_grant", description="Discriminator for spell augmentation.")
    spell_names: tuple[str, ...] = Field(description="Spell names registered on the actor.")
    caster_level: int = Field(ge=1, le=20, description="Caster level used while registering spells.")


class ItemGrant(BaseModel):
    """Inventory item granted to an actor before combat."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["item_grant"] = Field(default="item_grant", description="Discriminator for item augmentation.")
    recipe: ContentRecipe = Field(
        description="Exact installed item recipe materialized for this grant.",
    )
    count: int = Field(default=1, ge=1, description="Number of identical items granted.")
    on_grant: Literal["none", "ignite"] = Field(
        default="none",
        description="Typed post-loot setup behavior, when explicitly authored.",
    )


class ReactionGrant(BaseModel):
    """Reaction or tactical handler registered on an actor."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["reaction_grant"] = Field(default="reaction_grant", description="Discriminator for reaction augmentation.")
    reaction_id: Literal["counterspell", "goblin_nimble_escape", "shield"] = Field(
        description="Stable reaction registration identifier."
    )


class StartingDamage(BaseModel):
    """Damage applied through the event system before initiative begins."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["starting_damage"] = Field(default="starting_damage", description="Discriminator for starting damage.")
    amount: int = Field(ge=1, description="Damage applied before combat.")
    damage_type: DamageTypeName = Field(description="Engine damage type name.")
    source_role: str | None = Field(
        default=None,
        description="Optional deployment role that caused the damage; defaults to the damaged actor.",
    )


class StartingCondition(BaseModel):
    """Condition applied to the actor before initiative begins."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["starting_condition"] = Field(
        default="starting_condition",
        description="Discriminator for starting condition.",
    )
    condition_name: Literal["Blinded", "Poisoned"] = Field(description="Condition class registered before combat.")
    source_role: str | None = Field(
        default=None,
        description="Optional deployment role that caused the condition; defaults to the affected actor.",
    )


class DamageAffinity(BaseModel):
    """Static resistance, vulnerability, or immunity added to actor health."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["damage_affinity"] = Field(default="damage_affinity", description="Discriminator for damage affinity.")
    status: Literal["resistance", "vulnerability", "immunity"] = Field(description="Damage affinity status.")
    damage_type: DamageTypeName = Field(description="Engine damage type name.")
    label: str = Field(description="Stable modifier label used for inspection.")


class EquipmentGrant(BaseModel):
    """Weapon granted and equipped into an explicit combat loadout slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["equipment_grant"] = Field(default="equipment_grant", description="Discriminator for equipment grant.")
    recipe: ContentRecipe = Field(
        description="Exact installed equippable-item recipe.",
    )
    slot: WeaponSlot = Field(description="Target weapon slot.")
    replace: bool = Field(default=False, description="Whether an occupied target slot is unequipped before the grant.")


class ApparelGrant(BaseModel):
    """Clothing or footwear equipped as part of a configured loadout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["apparel_grant"] = Field(default="apparel_grant", description="Discriminator for apparel grant.")
    recipe: ContentRecipe = Field(
        description=(
            "Exact content definition and typed visual/name parameters for "
            "the equipped apparel instance."
        ),
    )


ActorAugmentation = Annotated[
    Union[
        SpellGrant,
        ItemGrant,
        ReactionGrant,
        StartingDamage,
        StartingCondition,
        DamageAffinity,
        EquipmentGrant,
        ApparelGrant,
    ],
    Field(discriminator="kind"),
]


class ActorBlueprintBase(BaseModel):
    """Fields shared by all typed actor blueprints."""

    model_config = ConfigDict(frozen=True)

    actor_id: str = Field(description="Configuration-local semantic actor identifier.")
    deployment_role: str | None = Field(
        default=None,
        description="Stable formation role; actor_id is used when omitted.",
    )
    augmentations: tuple[ActorAugmentation, ...] = Field(
        default_factory=tuple,
        description="Typed post-construction changes applied to the actor.",
    )


class BarbarianActorBlueprint(ActorBlueprintBase):
    """Barbarian factory input without runtime name, faction, or position."""

    kind: Literal["barbarian"] = Field(default="barbarian", description="Actor blueprint discriminator.")
    level: int = Field(default=5, ge=1, le=20, description="Barbarian class level.")
    primal_path: Literal["berserker"] = Field(default="berserker", description="Selected primal path.")
    equipment_preset: BarbarianEquipmentPreset = Field(
        default="greataxe",
        description="Barbarian starter equipment preset.",
    )
    asi_4: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-four ASI choices.")
    asi_8: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-eight ASI choices.")


class FighterActorBlueprint(ActorBlueprintBase):
    """Fighter factory input without runtime name, faction, or position."""

    kind: Literal["fighter"] = Field(default="fighter", description="Actor blueprint discriminator.")
    level: int = Field(default=5, ge=1, le=20, description="Fighter class level.")
    fighting_style: FighterStyleName = Field(
        default="defense",
        description="Primary Fighter fighting style.",
    )
    equipment_preset: FighterEquipmentPreset = Field(
        default="sword_shield",
        description="Fighter starter equipment preset.",
    )
    asi_4: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-four ASI choices.")
    asi_6: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-six ASI choices.")
    asi_8: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-eight ASI choices.")


class SorcererActorBlueprint(ActorBlueprintBase):
    """Sorcerer factory input without runtime name, faction, or position."""

    kind: Literal["sorcerer"] = Field(default="sorcerer", description="Actor blueprint discriminator.")
    level: int = Field(default=5, ge=1, le=20, description="Sorcerer class level.")
    metamagic_choices: tuple[str, ...] = Field(default_factory=tuple, description="Selected metamagic options.")
    spell_names: tuple[str, ...] = Field(default_factory=tuple, description="Explicit registered spell names.")
    equipment_preset: Literal["dagger", "quarterstaff"] = Field(
        default="dagger",
        description="Sorcerer starter equipment preset.",
    )
    asi_4: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-four ASI choices.")
    asi_8: tuple[tuple[AbilityName, int], ...] = Field(default_factory=tuple, description="Level-eight ASI choices.")


class BestiaryActorBlueprint(ActorBlueprintBase):
    """Existing bestiary factory input."""

    kind: Literal["bestiary"] = Field(default="bestiary", description="Actor blueprint discriminator.")
    archetype: BestiaryArchetype = Field(description="Stable bestiary factory identifier.")
    level: int = Field(default=5, ge=1, le=20, description="Caster level when the archetype supports levels.")
    darkvision: bool | None = Field(default=None, description="Optional bestiary darkvision override.")
    weight: int | None = Field(default=None, ge=1, description="Optional actor weight override.")


class SrdMonsterActorBlueprint(ActorBlueprintBase):
    """SRD roster factory input."""

    kind: Literal["srd_monster"] = Field(default="srd_monster", description="Actor blueprint discriminator.")
    monster_id: str = Field(description="Stable SRD roster identifier.")


ActorBlueprint = Annotated[
    Union[
        BarbarianActorBlueprint,
        FighterActorBlueprint,
        SorcererActorBlueprint,
        BestiaryActorBlueprint,
        SrdMonsterActorBlueprint,
    ],
    Field(discriminator="kind"),
]


class SideConfigurationSpec(BaseModel):
    """Complete mechanically rated combat side independent of battlefield."""

    model_config = ConfigDict(frozen=True)

    configuration_id: str = Field(description="Stable catalog identifier.")
    title: str = Field(description="Human-readable report title.")
    side_kind: SideKind = Field(description="Whether this is a hero or monster-party configuration.")
    members: tuple[ActorBlueprint, ...] = Field(min_length=1, description="Typed actor blueprints in this side.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Searchable mechanical and role tags.")
    rating_eligible: bool = Field(default=True, description="Whether the configuration enters official ratings.")
    portable: bool = Field(default=True, description="Whether the configuration participates in portable compositions.")
    exclusion_reason: str | None = Field(default=None, description="Reason a diagnostic-only configuration is excluded.")
    diagnostic_warnings: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Non-excluding caveats retained for reports and compatibility evidence.",
    )
    source_arena_ids: tuple[str, ...] = Field(default_factory=tuple, description="Legacy arenas that originally exercised this build.")
    required_battlefield_capabilities: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Battlefield capabilities required for this side to be mechanically valid.",
    )
    forbidden_battlefield_capabilities: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Battlefield capabilities that make this side mechanically invalid.",
    )

    @model_validator(mode="after")
    def validate_side_shape(self) -> SideConfigurationSpec:
        """Validate side cardinality and exclusion metadata."""
        if self.side_kind == "hero" and len(self.members) != 1:
            raise ValueError("Hero configurations must contain exactly one actor.")
        if not self.rating_eligible and not self.exclusion_reason:
            raise ValueError("Excluded configurations require an exclusion reason.")
        actor_ids = [member.actor_id for member in self.members]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("Configuration actor ids must be unique.")
        deployment_roles = [member.deployment_role or member.actor_id for member in self.members]
        if len(deployment_roles) != len(set(deployment_roles)):
            raise ValueError("Configuration deployment roles must be unique.")
        if set(self.required_battlefield_capabilities) & set(self.forbidden_battlefield_capabilities):
            raise ValueError("A battlefield capability cannot be both required and forbidden.")
        return self

    @computed_field(return_type=str)
    @property
    def mechanical_hash(self) -> str:
        """Return order-independent hash of complete mechanical membership."""
        payloads = []
        for member in self.members:
            payload = member.model_dump(mode="json", exclude={"actor_id"})
            payloads.append(payload)
        payloads.sort(key=_canonical_json)
        return _stable_hash({"side_kind": self.side_kind, "members": payloads})


class BattlefieldPreviewCell(BaseModel):
    """Non-default terrain cell used by the match-creator preview."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Grid coordinate of the terrain override.")
    terrain: BattlefieldPreviewTerrain = Field(description="Stable visual and mechanical terrain category.")
    walkable: bool = Field(description="Whether actors can enter the cell.")
    walking_cost: int = Field(default=1, ge=1, description="Movement-cost multiplier for entering the cell.")
    hazardous: bool = Field(default=False, description="Whether entering the cell can cause harm.")


class BattlefieldPreviewObject(BaseModel):
    """Static battlefield object placement used by the match-creator preview."""

    model_config = ConfigDict(frozen=True)

    position: tuple[int, int] = Field(description="Grid coordinate containing the object.")
    kind: BattlefieldPreviewObjectKind = Field(description="Stable object presentation category.")
    label: str = Field(description="Player-facing object label.")
    blocked_directions: tuple[BattlefieldPreviewDirection, ...] = Field(
        default_factory=tuple,
        description="Directions blocked by a wall or closed door.",
    )
    is_open: bool | None = Field(default=None, description="Door state when the object is a door.")


class BattlefieldPreview(BaseModel):
    """Compact, deterministic projection of canonical battlefield construction."""

    model_config = ConfigDict(frozen=True)

    cells: tuple[BattlefieldPreviewCell, ...] = Field(
        default_factory=tuple,
        description="Terrain cells that differ from the default rectangular floor.",
    )
    objects: tuple[BattlefieldPreviewObject, ...] = Field(
        default_factory=tuple,
        description="Walls, doors, lights, loot, and devices placed on the floor.",
    )


class BattlefieldSpec(BaseModel):
    """Battlefield geometry, lighting, and object package independent of actors."""

    model_config = ConfigDict(frozen=True)

    battlefield_id: str = Field(description="Stable battlefield catalog identifier.")
    title: str = Field(description="Human-readable battlefield title.")
    builder_id: str = Field(description="Registered battlefield construction function identifier.")
    width: int = Field(default=15, ge=1, description="Battlefield width in grid cells.")
    height: int = Field(default=15, ge=1, description="Battlefield height in grid cells.")
    deployment_ids: tuple[str, ...] = Field(min_length=1, description="Compatible deployment identifiers.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Terrain, lighting, and object tags.")
    light_level: LightLevelName = Field(default="bright", description="Default light level outside explicit light sources.")
    capabilities: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Mechanical features exposed for static compatibility checks.",
    )
    preview: BattlefieldPreview | None = Field(
        default=None,
        description="Exact compact preview derived from the canonical battlefield layout.",
    )
    portable: bool = Field(default=True, description="Whether the battlefield enters the connected ladder.")
    source_arena_ids: tuple[str, ...] = Field(default_factory=tuple, description="Legacy arenas sharing this battlefield.")

    @computed_field(return_type=str)
    @property
    def content_hash(self) -> str:
        """Return stable hash of battlefield construction identity."""
        return _stable_hash(self.model_dump(mode="json", exclude={"battlefield_id", "title", "source_arena_ids", "content_hash"}))


class DeploymentRoleSlot(BaseModel):
    """A semantic combatant role assigned to one grid coordinate."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(description="Configuration-local deployment role.")
    position: tuple[int, int] = Field(description="Spawn coordinate for that role.")


class DeploymentSpec(BaseModel):
    """Actor spawn formation for one battlefield."""

    model_config = ConfigDict(frozen=True)

    deployment_id: str = Field(description="Stable deployment identifier.")
    title: str = Field(description="Human-readable deployment title.")
    battlefield_id: str = Field(description="Battlefield this deployment targets.")
    hero_slots: tuple[tuple[int, int], ...] = Field(min_length=1, description="Ordered hero-side spawn slots.")
    monster_slots: tuple[tuple[int, int], ...] = Field(min_length=1, description="Ordered monster-side spawn slots.")
    hero_role_slots: tuple[DeploymentRoleSlot, ...] = Field(
        default_factory=tuple,
        description="Role-addressed hero spawn slots; ordered slots remain as a compatibility fallback.",
    )
    monster_role_slots: tuple[DeploymentRoleSlot, ...] = Field(
        default_factory=tuple,
        description="Role-addressed monster spawn slots; ordered slots remain as a compatibility fallback.",
    )
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Formation and tactical tags.")
    mirrored: bool = Field(default=False, description="Whether this deployment mirrors another orientation.")
    portable: bool = Field(default=True, description="Whether this formation participates in portable compositions.")
    max_hero_members: int = Field(default=1, ge=1, description="Maximum hero-side members supported by the formation.")
    max_monster_members: int = Field(default=5, ge=1, description="Maximum monster-side members supported by the formation.")
    rating_eligible: bool = Field(default=True, description="Whether this deployment enters the general-strength ladder.")
    source_arena_id: str | None = Field(default=None, description="Legacy arena represented by this deployment, if any.")

    @model_validator(mode="after")
    def validate_role_slots(self) -> DeploymentSpec:
        """Reject ambiguous role mappings and duplicate active-side coordinates."""
        for slots in (self.hero_role_slots, self.monster_role_slots):
            roles = [slot.role for slot in slots]
            if len(roles) != len(set(roles)):
                raise ValueError("Deployment role mappings must be unique per side.")
        return self

    @computed_field(return_type=str)
    @property
    def content_hash(self) -> str:
        """Return stable hash of deployment geometry."""
        return _stable_hash(self.model_dump(mode="json", exclude={"deployment_id", "title", "content_hash"}))


class ActorPresentation(BaseModel):
    """Legacy display metadata kept outside mechanical configuration identity."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(description="Deployment role receiving the display name.")
    name: str = Field(description="Runtime display name used by the legacy scenario.")


class NotablePosition(BaseModel):
    """Named map coordinate exposed by a legacy scenario bundle."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(description="Stable coordinate label.")
    position: tuple[int, int] = Field(description="Grid coordinate associated with the label.")


class LegacyScenarioRecipe(BaseModel):
    """Composition metadata that reconstructs one historical validation arena."""

    model_config = ConfigDict(frozen=True)

    arena_id: str = Field(description="Stable legacy validation arena identifier.")
    hero_configuration_id: str = Field(description="Hero catalog entry used by the recipe.")
    monster_configuration_id: str = Field(description="Monster-party catalog entry used by the recipe.")
    battlefield_id: str = Field(description="Battlefield catalog entry used by the recipe.")
    deployment_id: str = Field(description="Deployment catalog entry used by the recipe.")
    encounter_name: str = Field(description="Runtime encounter display name.")
    actor_presentations: tuple[ActorPresentation, ...] = Field(
        default_factory=tuple,
        description="Role-addressed runtime actor names excluded from mechanical hashes.",
    )
    notable_positions: tuple[NotablePosition, ...] = Field(
        default_factory=tuple,
        description="Named coordinates returned with the assembled arena.",
    )


def _stable_hash(payload: object) -> str:
    """Return a compact SHA-256 identity for canonical JSON data."""
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]


def _canonical_json(payload: object) -> str:
    """Serialize a model payload deterministically."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
