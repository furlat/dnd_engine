"""Dependency-neutral authored roster, deployment, and encounter values."""

from enum import Enum
import re
from typing import Annotated, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from dnd.types.damage import DamageType
from dnd.types.equipment import EquipmentSlot


_LOCAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$")


def _validate_local_id(value: str, field_name: str) -> str:
    if not _LOCAL_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a lowercase stable identifier; got {value!r}",
        )
    return value


def _validate_trimmed(value: str, field_name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and trimmed")
    return value


class RosterItemPlacement(str, Enum):
    """Encounter-local placement for one direct item grant."""

    INVENTORY = "inventory"
    EQUIPPED = "equipped"
    EQUIPPED_DEFAULT = "equipped_default"


class DamageAffinityStatus(str, Enum):
    """Encounter-local affinity applied before initiative."""

    RESISTANCE = "resistance"
    VULNERABILITY = "vulnerability"
    IMMUNITY = "immunity"


class EncounterCompatibilitySeverity(str, Enum):
    """Whether one preflight issue rejects or annotates a scenario."""

    HARD = "hard"
    DIAGNOSTIC = "diagnostic"


class EncounterCompatibilityPhase(str, Enum):
    """Furthest validation boundary represented by a report."""

    STATIC = "static"
    BUILT = "built"


class EncounterCompatibilityCode(str, Enum):
    """Closed neutral encounter-preflight diagnostics."""

    BATTLEFIELD_MISMATCH = "battlefield_mismatch"
    BLOCKED_SPAWN = "blocked_spawn"
    DUPLICATE_SPAWN = "duplicate_spawn"
    FORBIDDEN_CAPABILITY = "forbidden_capability"
    MEMBER_CAPACITY = "member_capacity"
    MISSING_CAPABILITY = "missing_capability"
    MISSING_ROLE_SLOT = "missing_role_slot"
    OCCUPIED_SPAWN = "occupied_spawn"
    OUT_OF_BOUNDS_SPAWN = "out_of_bounds_spawn"
    UNREACHABLE_FACTIONS = "unreachable_factions"


class EncounterCompatibilityIssue(BaseModel):
    """One exact neutral reason emitted by preflight."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: EncounterCompatibilityCode
    severity: EncounterCompatibilitySeverity
    message: str
    roster_slot_id: str | None = None
    member_id: str | None = None
    position: tuple[int, int] | None = None


class EncounterCompatibilityReport(BaseModel):
    """Preflight result for one authored encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encounter_id: str
    battlefield_id: str
    deployment_id: str
    phase: EncounterCompatibilityPhase
    issues: tuple[EncounterCompatibilityIssue, ...] = ()
    admitted: bool

    @model_validator(mode="after")
    def _validate_admission(self) -> Self:
        expected = not any(
            issue.severity is EncounterCompatibilitySeverity.HARD
            for issue in self.issues
        )
        if self.admitted != expected:
            raise ValueError("admission must match the report's hard issues")
        return self


class DirectEntitySource(BaseModel):
    """One direct authored entity construction request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["entity"] = "entity"
    entity_id: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("entity_id")
    @classmethod
    def _validate_entity_id(cls, value: str) -> str:
        return _validate_local_id(value, "entity_id")


class RosterItemGrant(BaseModel):
    """Direct item created as an encounter-local setup effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["item_grant"] = "item_grant"
    item_id: str
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    count: int = Field(default=1, ge=1)
    placement: RosterItemPlacement = RosterItemPlacement.INVENTORY
    equipment_slot: EquipmentSlot | None = None
    replace_existing: bool = False
    on_grant: Literal["none", "ignite"] = "none"

    @field_validator("item_id")
    @classmethod
    def _validate_item_id(cls, value: str) -> str:
        return _validate_local_id(value, "item_id")

    @model_validator(mode="after")
    def _validate_placement(self) -> Self:
        if self.placement is RosterItemPlacement.EQUIPPED:
            if self.equipment_slot is None:
                raise ValueError("explicit equipped grants require a slot")
        elif self.equipment_slot is not None:
            raise ValueError("inventory/default-slot grants forbid a slot")
        return self


class RosterSpellGrant(BaseModel):
    """Direct spells registered only for one scenario composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["spell_grant"] = "spell_grant"
    spell_ids: tuple[str, ...] = Field(min_length=1)
    caster_level: int = Field(ge=1, le=20)

    @model_validator(mode="after")
    def _validate_spells(self) -> Self:
        if len(self.spell_ids) != len(set(self.spell_ids)):
            raise ValueError("spell grants cannot repeat a spell ID")
        for spell_id in self.spell_ids:
            _validate_local_id(spell_id, "spell_id")
        return self


class RosterBehaviorGrant(BaseModel):
    """Direct action or reaction installed for one scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["behavior_grant"] = "behavior_grant"
    behavior_id: str
    configured_display_name: str | None = None
    action_cost_variant: Literal["default", "bonus_action"] = "default"

    @field_validator("behavior_id")
    @classmethod
    def _validate_behavior_id(cls, value: str) -> str:
        return _validate_local_id(value, "behavior_id")

    @field_validator("configured_display_name")
    @classmethod
    def _validate_display_name(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_trimmed(value, "configured_display_name")
        return None


class RosterStartingDamage(BaseModel):
    """Damage applied through the engine before initiative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["starting_damage"] = "starting_damage"
    amount: int = Field(ge=1)
    damage_type: DamageType
    source_member_role: str | None = None

    @field_validator("source_member_role")
    @classmethod
    def _validate_source_role(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_local_id(value, "source_member_role")
        return None


class RosterStartingCondition(BaseModel):
    """Direct condition applied through the engine before initiative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["starting_condition"] = "starting_condition"
    condition_id: str
    source_member_role: str | None = None

    @field_validator("condition_id")
    @classmethod
    def _validate_condition_id(cls, value: str) -> str:
        return _validate_local_id(value, "condition_id")

    @field_validator("source_member_role")
    @classmethod
    def _validate_source_role(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_local_id(value, "source_member_role")
        return None


class RosterDamageAffinity(BaseModel):
    """Exact static damage affinity applied before initiative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["damage_affinity"] = "damage_affinity"
    status: DamageAffinityStatus
    damage_type: DamageType
    label: str

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _validate_trimmed(value, "label")


class RosterResourceState(BaseModel):
    """Explicit initial value for one semantic resource ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["resource_state"] = "resource_state"
    resource_id: str
    value: JsonValue

    @field_validator("resource_id")
    @classmethod
    def _validate_resource_id(cls, value: str) -> str:
        return _validate_local_id(value, "resource_id")


EncounterSetupEffect = Annotated[
    Union[
        RosterItemGrant,
        RosterSpellGrant,
        RosterBehaviorGrant,
        RosterStartingDamage,
        RosterStartingCondition,
        RosterDamageAffinity,
        RosterResourceState,
    ],
    Field(discriminator="kind"),
]


class EncounterRosterMember(BaseModel):
    """One ordered entity in an authored roster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    display_name: str
    deployment_role: str
    source: DirectEntitySource
    scenario_setup_effects: tuple[EncounterSetupEffect, ...] = ()

    @field_validator("member_id", "deployment_role")
    @classmethod
    def _validate_ids(cls, value: str, info) -> str:
        return _validate_local_id(value, info.field_name)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _validate_trimmed(value, "display_name")


class EncounterRosterDefinition(BaseModel):
    """Cold ordered entity roster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_id: str
    title: str
    members: tuple[EncounterRosterMember, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    required_battlefield_capabilities: tuple[str, ...] = ()
    forbidden_battlefield_capabilities: tuple[str, ...] = ()

    @field_validator("roster_id")
    @classmethod
    def _validate_roster_id(cls, value: str) -> str:
        return _validate_local_id(value, "roster_id")

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _validate_trimmed(value, "title")

    @model_validator(mode="after")
    def _validate_roster(self) -> Self:
        member_ids = [member.member_id for member in self.members]
        roles = [member.deployment_role for member in self.members]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("roster member IDs must be unique")
        if len(roles) != len(set(roles)):
            raise ValueError("roster deployment roles must be unique")
        if set(self.required_battlefield_capabilities) & set(
            self.forbidden_battlefield_capabilities,
        ):
            raise ValueError("a battlefield capability cannot be both required and forbidden")
        return self


class EncounterDeploymentRoleSlot(BaseModel):
    """Role-addressed coordinate inside one neutral deployment zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    position: tuple[int, int]


class EncounterDeploymentZone(BaseModel):
    """One neutral named formation zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    zone_id: str
    ordered_slots: tuple[tuple[int, int], ...] = Field(min_length=1)
    role_slots: tuple[EncounterDeploymentRoleSlot, ...] = ()
    max_members: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_zone(self) -> Self:
        roles = [slot.role for slot in self.role_slots]
        coordinates = [slot.position for slot in self.role_slots]
        if len(roles) != len(set(roles)):
            raise ValueError("deployment role slots must be unique")
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("deployment role-slot coordinates must be unique")
        if (self.max_members or len(self.ordered_slots)) > len(self.ordered_slots):
            raise ValueError("max_members cannot exceed ordered slot count")
        return self


class EncounterDeploymentDefinition(BaseModel):
    """Cold neutral deployment formation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deployment_id: str
    title: str
    battlefield_id: str
    zones: tuple[EncounterDeploymentZone, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_deployment(self) -> Self:
        zone_ids = [zone.zone_id for zone in self.zones]
        coordinates = [
            position
            for zone in self.zones
            for position in zone.ordered_slots
        ]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("deployment zone IDs must be unique")
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("deployment coordinates cannot cross zones")
        return self


class EncounterMemberPresentation(BaseModel):
    """Encounter-specific display override for one roster member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    display_name: str


class EncounterRosterSlot(BaseModel):
    """One roster assigned to a faction and deployment zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_slot_id: str
    roster: EncounterRosterDefinition
    faction_id: str
    deployment_zone_id: str
    participant_name: str
    member_presentations: tuple[EncounterMemberPresentation, ...] = ()

    @model_validator(mode="after")
    def _validate_presentations(self) -> Self:
        member_ids = {member.member_id for member in self.roster.members}
        presentation_ids = [row.member_id for row in self.member_presentations]
        if len(presentation_ids) != len(set(presentation_ids)):
            raise ValueError("member presentation overrides must be unique")
        if not set(presentation_ids) <= member_ids:
            raise ValueError("member presentation must reference this roster")
        return self


class InitiativeOpeningPolicy(BaseModel):
    """Encounter begins with ordinary initiative ordering."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["initiative"] = "initiative"


class FixedRosterOpeningPolicy(BaseModel):
    """Encounter begins with one explicit roster slot."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["fixed_roster"] = "fixed_roster"
    roster_slot_id: str


EncounterOpeningPolicy = Annotated[
    Union[InitiativeOpeningPolicy, FixedRosterOpeningPolicy],
    Field(discriminator="kind"),
]


class EncounterNotablePosition(BaseModel):
    """Named map coordinate retained in an authored encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str
    position: tuple[int, int]


class EncounterDefinition(BaseModel):
    """Cold launch definition for one complete encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encounter_id: str
    title: str
    roster_slots: tuple[EncounterRosterSlot, ...] = Field(min_length=2)
    battlefield_id: str
    deployment: EncounterDeploymentDefinition
    opening_policy: EncounterOpeningPolicy
    notable_positions: tuple[EncounterNotablePosition, ...] = ()
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate_encounter(self) -> Self:
        if self.battlefield_id != self.deployment.battlefield_id:
            raise ValueError("encounter battlefield must match deployment")
        slot_ids = [slot.roster_slot_id for slot in self.roster_slots]
        zone_ids = [slot.deployment_zone_id for slot in self.roster_slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("encounter roster slot IDs must be unique")
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("each roster requires a distinct deployment zone")
        deployment_zones = {zone.zone_id: zone for zone in self.deployment.zones}
        roles = [
            member.deployment_role
            for slot in self.roster_slots
            for member in slot.roster.members
        ]
        for slot in self.roster_slots:
            zone = deployment_zones.get(slot.deployment_zone_id)
            if zone is None:
                raise ValueError(f"unknown deployment zone {slot.deployment_zone_id!r}")
            if len(slot.roster.members) > (zone.max_members or len(zone.ordered_slots)):
                raise ValueError(f"roster {slot.roster_slot_id!r} exceeds zone capacity")
            for member in slot.roster.members:
                for effect in member.scenario_setup_effects:
                    if isinstance(effect, (RosterStartingDamage, RosterStartingCondition)):
                        source_role = effect.source_member_role
                        if source_role is not None and roles.count(source_role) != 1:
                            raise ValueError("setup source_member_role must resolve exactly once")
        if isinstance(self.opening_policy, FixedRosterOpeningPolicy):
            if self.opening_policy.roster_slot_id not in set(slot_ids):
                raise ValueError("opening roster slot must reference this encounter")
        labels = [row.label for row in self.notable_positions]
        if len(labels) != len(set(labels)):
            raise ValueError("notable position labels must be unique")
        return self


__all__ = [
    "DamageAffinityStatus",
    "DirectEntitySource",
    "EncounterCompatibilityCode",
    "EncounterCompatibilityIssue",
    "EncounterCompatibilityPhase",
    "EncounterCompatibilityReport",
    "EncounterCompatibilitySeverity",
    "EncounterDefinition",
    "EncounterDeploymentDefinition",
    "EncounterDeploymentRoleSlot",
    "EncounterDeploymentZone",
    "EncounterMemberPresentation",
    "EncounterNotablePosition",
    "EncounterOpeningPolicy",
    "EncounterRosterDefinition",
    "EncounterRosterMember",
    "EncounterRosterSlot",
    "EncounterSetupEffect",
    "FixedRosterOpeningPolicy",
    "InitiativeOpeningPolicy",
    "RosterBehaviorGrant",
    "RosterDamageAffinity",
    "RosterItemGrant",
    "RosterItemPlacement",
    "RosterResourceState",
    "RosterSpellGrant",
    "RosterStartingCondition",
    "RosterStartingDamage",
]
