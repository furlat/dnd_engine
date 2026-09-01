"""Dependency-neutral recipes for rosters, deployments, and encounters.

These values are the authored/persistent composition boundary.  They contain
exact content recipes or durable character identities, but never import
``Entity``, a runtime controller, a directory service, or server transport.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Annotated, Literal, Self, Union
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from dnd.core.content.identities import (
    ContentDefinitionKind,
    ContentRef,
    validate_namespaced_id,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import EquipmentSlot


_LOCAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:[.-][a-z0-9_]+)*$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_local_id(value: str, field_name: str) -> str:
    if not _LOCAL_ID_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a lowercase stable identifier; got {value!r}",
        )
    return value


def _validate_digest(value: str, field_name: str) -> str:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _validate_trimmed(value: str, field_name: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and trimmed")
    return value


class RosterControllerKind(str, Enum):
    """Supported controller ownership modes for one roster or member."""

    HUMAN = "human"
    AI = "ai"
    CODEX = "codex"


class RosterItemPlacement(str, Enum):
    """Encounter-local placement for an exact item grant."""

    INVENTORY = "inventory"
    EQUIPPED = "equipped"
    EQUIPPED_DEFAULT = "equipped_default"


class DamageAffinityStatus(str, Enum):
    """Encounter-local damage affinity applied before initiative."""

    RESISTANCE = "resistance"
    VULNERABILITY = "vulnerability"
    IMMUNITY = "immunity"


class EncounterCompatibilitySeverity(str, Enum):
    """Whether one preflight issue rejects or annotates the recipe."""

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
    MISSING_CHARACTER = "missing_character"
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
    """Preflight result for one self-authenticating encounter recipe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encounter_recipe_digest: str
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
            raise ValueError(
                "Compatibility admission must match its hard issues",
            )
        return self


class AuthoredCreatureRosterSource(BaseModel):
    """One exact authored creature construction request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["authored_creature"] = "authored_creature"
    recipe: ContentRecipe

    @model_validator(mode="after")
    def _validate_creature_recipe(self) -> Self:
        if self.recipe.ref.definition_kind != ContentDefinitionKind.CREATURE:
            raise ValueError("authored roster source requires a creature recipe")
        return self


class OwnedCharacterRosterSource(BaseModel):
    """One exact durable character head-set resolved by the owning directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["owned_character"] = "owned_character"
    character_id: UUID
    expected_character_row_version: int = Field(ge=1)
    expected_definition_revision: int = Field(ge=1)
    expected_definition_digest: str
    expected_holdings_revision: int = Field(ge=1)
    expected_holdings_digest: str
    expected_loadout_revision: int = Field(ge=1)
    expected_loadout_digest: str
    expected_ruleset_digest: str

    @field_validator(
        "expected_definition_digest",
        "expected_holdings_digest",
        "expected_loadout_digest",
        "expected_ruleset_digest",
    )
    @classmethod
    def _validate_expected_digest(cls, value: str, info) -> str:
        return _validate_digest(value, info.field_name)


EncounterRosterMemberSource = Annotated[
    Union[AuthoredCreatureRosterSource, OwnedCharacterRosterSource],
    Field(discriminator="kind"),
]


class RosterItemGrant(BaseModel):
    """Exact item created as a genuinely encounter-local setup effect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["item_grant"] = "item_grant"
    item_id: str
    count: int = Field(default=1, ge=1)
    placement: RosterItemPlacement = RosterItemPlacement.INVENTORY
    equipment_slot: EquipmentSlot | None = None
    replace_existing: bool = False
    on_grant: Literal["none", "ignite"] = "none"
    heal_amount: int | None = Field(default=None, ge=0)
    cast_level: int | None = Field(default=None, ge=1, le=9)
    charges: int | None = Field(default=None, ge=0)

    @field_validator("item_id")
    @classmethod
    def _validate_item_id(cls, value: str) -> str:
        return validate_namespaced_id(value, "item_id")

    @model_validator(mode="after")
    def _validate_item_grant(self) -> Self:
        if self.placement is RosterItemPlacement.EQUIPPED:
            if self.equipment_slot is None:
                raise ValueError(
                    "explicit equipped item grants require equipment_slot",
                )
        elif self.equipment_slot is not None:
            raise ValueError(
                "inventory/default-slot item grants forbid equipment_slot",
            )
        finite_fields = {
            "heal_amount": self.heal_amount,
            "cast_level": self.cast_level,
            "charges": self.charges,
        }
        supplied = {
            name for name, value in finite_fields.items() if value is not None
        }
        allowed_by_item = {
            "consumable.healing_potion": {"heal_amount"},
            "spell_item.scroll_fireball": {"cast_level"},
            "spell_item.scroll_hold_person": {"cast_level"},
            "spell_item.scroll_magic_missile": {"cast_level"},
            "spell_item.scroll_spike_growth": {"cast_level"},
            "spell_item.wand_fire": {"charges"},
            "spell_item.wand_magic_missiles": {"charges"},
        }
        if not supplied <= allowed_by_item.get(self.item_id, set()):
            raise ValueError(
                f"item grant {self.item_id!r} has incompatible finite state",
            )
        if self.on_grant == "ignite" and self.item_id != "equipment.portable_torch":
            raise ValueError("ignite setup effect requires equipment.portable_torch")
        return self


class RosterSpellGrant(BaseModel):
    """Exact spells registered only for this encounter composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["spell_grant"] = "spell_grant"
    spell_refs: tuple[ContentRef, ...] = Field(min_length=1)
    caster_level: int = Field(ge=1, le=20)

    @model_validator(mode="after")
    def _validate_spells(self) -> Self:
        if any(
            ref.definition_kind != ContentDefinitionKind.SPELL
            for ref in self.spell_refs
        ):
            raise ValueError("spell grants require spell content references")
        if len(self.spell_refs) != len({
            ref.identity_key for ref in self.spell_refs
        }):
            raise ValueError("spell grants cannot repeat a spell reference")
        return self


class RosterBehaviorGrant(BaseModel):
    """Exact action/reaction behavior registered for one encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["behavior_grant"] = "behavior_grant"
    behavior_ref: ContentRef
    configured_display_name: str | None = None
    action_cost_variant: Literal["default", "bonus_action"] = "default"

    @field_validator("configured_display_name")
    @classmethod
    def _validate_configured_display_name(
        cls,
        value: str | None,
    ) -> str | None:
        if value is not None:
            return _validate_trimmed(value, "configured_display_name")
        return value

    @model_validator(mode="after")
    def _validate_behavior(self) -> Self:
        if self.behavior_ref.definition_kind not in {
            ContentDefinitionKind.ACTION,
            ContentDefinitionKind.REACTION,
            ContentDefinitionKind.CLASS_FEATURE,
            ContentDefinitionKind.TRAIT,
        }:
            raise ValueError(
                "behavior grants require action, reaction, class_feature, or "
                "trait content",
            )
        if (
            self.action_cost_variant != "default"
            and self.behavior_ref.definition_kind
            != ContentDefinitionKind.ACTION
        ):
            raise ValueError(
                "alternate action costs require an action definition",
            )
        return self


class RosterStartingDamage(BaseModel):
    """Damage applied through the engine before initiative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["starting_damage"] = "starting_damage"
    amount: int = Field(ge=1)
    damage_type: DamageType
    source_member_role: str | None = None

    @field_validator("source_member_role")
    @classmethod
    def _validate_source_member_role(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_local_id(value, "source_member_role")
        return value


class RosterStartingCondition(BaseModel):
    """Exact condition applied through the engine before initiative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["starting_condition"] = "starting_condition"
    condition_ref: ContentRef
    source_member_role: str | None = None

    @field_validator("source_member_role")
    @classmethod
    def _validate_source_member_role(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_local_id(value, "source_member_role")
        return value

    @model_validator(mode="after")
    def _validate_condition(self) -> Self:
        if self.condition_ref.definition_kind != ContentDefinitionKind.CONDITION:
            raise ValueError("starting condition requires condition content")
        return self


class RosterDamageAffinity(BaseModel):
    """Exact static affinity applied before initiative."""

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
    """Explicit initial value for a content-authenticated resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["resource_state"] = "resource_state"
    resource_ref: ContentRef
    value: JsonValue


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
    """One ordered creature or character in an encounter roster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    display_name: str
    deployment_role: str
    source: EncounterRosterMemberSource
    scenario_setup_effects: tuple[EncounterSetupEffect, ...] = ()

    @field_validator("member_id", "deployment_role")
    @classmethod
    def _validate_ids(cls, value: str, info) -> str:
        return _validate_local_id(value, info.field_name)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _validate_trimmed(value, "display_name")


def compute_roster_recipe_digest(
    *,
    roster_id: str,
    title: str,
    members: tuple[EncounterRosterMember, ...],
    tags: tuple[str, ...],
    required_battlefield_capabilities: tuple[str, ...],
    forbidden_battlefield_capabilities: tuple[str, ...],
) -> str:
    return _canonical_digest({
        "roster_id": roster_id,
        "title": title,
        "members": [member.model_dump(mode="json") for member in members],
        "tags": list(tags),
        "required_battlefield_capabilities": list(
            required_battlefield_capabilities,
        ),
        "forbidden_battlefield_capabilities": list(
            forbidden_battlefield_capabilities,
        ),
    })


class EncounterRosterRecipe(BaseModel):
    """Self-authenticating ordered creature/character roster."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_id: str
    title: str
    members: tuple[EncounterRosterMember, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    required_battlefield_capabilities: tuple[str, ...] = ()
    forbidden_battlefield_capabilities: tuple[str, ...] = ()
    recipe_digest: str

    @classmethod
    def create(
        cls,
        *,
        roster_id: str,
        title: str,
        members: tuple[EncounterRosterMember, ...],
        tags: tuple[str, ...] = (),
        required_battlefield_capabilities: tuple[str, ...] = (),
        forbidden_battlefield_capabilities: tuple[str, ...] = (),
    ) -> Self:
        return cls(
            roster_id=roster_id,
            title=title,
            members=members,
            tags=tags,
            required_battlefield_capabilities=required_battlefield_capabilities,
            forbidden_battlefield_capabilities=forbidden_battlefield_capabilities,
            recipe_digest=compute_roster_recipe_digest(
                roster_id=roster_id,
                title=title,
                members=members,
                tags=tags,
                required_battlefield_capabilities=(
                    required_battlefield_capabilities
                ),
                forbidden_battlefield_capabilities=(
                    forbidden_battlefield_capabilities
                ),
            ),
        )

    @field_validator("roster_id")
    @classmethod
    def _validate_roster_id(cls, value: str) -> str:
        return _validate_local_id(value, "roster_id")

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _validate_trimmed(value, "title")

    @field_validator("recipe_digest")
    @classmethod
    def _validate_recipe_digest_shape(cls, value: str) -> str:
        return _validate_digest(value, "recipe_digest")

    @model_validator(mode="after")
    def _validate_roster(self) -> Self:
        member_ids = [member.member_id for member in self.members]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("roster member ids must be unique")
        roles = [member.deployment_role for member in self.members]
        if len(roles) != len(set(roles)):
            raise ValueError("roster deployment roles must be unique")
        required = set(self.required_battlefield_capabilities)
        forbidden = set(self.forbidden_battlefield_capabilities)
        if required & forbidden:
            raise ValueError(
                "a battlefield capability cannot be required and forbidden",
            )
        expected = compute_roster_recipe_digest(
            roster_id=self.roster_id,
            title=self.title,
            members=self.members,
            tags=self.tags,
            required_battlefield_capabilities=(
                self.required_battlefield_capabilities
            ),
            forbidden_battlefield_capabilities=(
                self.forbidden_battlefield_capabilities
            ),
        )
        if self.recipe_digest != expected:
            raise ValueError(
                "recipe_digest does not authenticate the roster recipe",
            )
        return self


class EncounterDeploymentRoleSlot(BaseModel):
    """Role-addressed coordinate inside one neutral deployment zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    position: tuple[int, int]

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        return _validate_local_id(value, "role")


class EncounterDeploymentZone(BaseModel):
    """One neutral named formation zone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    zone_id: str
    ordered_slots: tuple[tuple[int, int], ...] = Field(min_length=1)
    role_slots: tuple[EncounterDeploymentRoleSlot, ...] = ()
    max_members: int | None = Field(default=None, ge=1)

    @field_validator("zone_id")
    @classmethod
    def _validate_zone_id(cls, value: str) -> str:
        return _validate_local_id(value, "zone_id")

    @model_validator(mode="after")
    def _validate_zone(self) -> Self:
        roles = [slot.role for slot in self.role_slots]
        if len(roles) != len(set(roles)):
            raise ValueError("deployment role slots must be unique in a zone")
        coordinates = [slot.position for slot in self.role_slots]
        if len(coordinates) != len(set(coordinates)):
            raise ValueError(
                "deployment role-slot coordinates must be unique in a zone",
            )
        capacity = self.max_members or len(self.ordered_slots)
        if capacity > len(self.ordered_slots):
            raise ValueError(
                "max_members cannot exceed the number of ordered slots",
            )
        return self


def compute_deployment_digest(
    *,
    deployment_id: str,
    title: str,
    battlefield_id: str,
    zones: tuple[EncounterDeploymentZone, ...],
    tags: tuple[str, ...],
) -> str:
    return _canonical_digest({
        "deployment_id": deployment_id,
        "title": title,
        "battlefield_id": battlefield_id,
        "zones": [zone.model_dump(mode="json") for zone in zones],
        "tags": list(tags),
    })


class EncounterDeploymentSpec(BaseModel):
    """Self-authenticating neutral deployment formation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    deployment_id: str
    title: str
    battlefield_id: str
    zones: tuple[EncounterDeploymentZone, ...] = Field(min_length=1)
    tags: tuple[str, ...] = ()
    content_digest: str

    @classmethod
    def create(
        cls,
        *,
        deployment_id: str,
        title: str,
        battlefield_id: str,
        zones: tuple[EncounterDeploymentZone, ...],
        tags: tuple[str, ...] = (),
    ) -> Self:
        return cls(
            deployment_id=deployment_id,
            title=title,
            battlefield_id=battlefield_id,
            zones=zones,
            tags=tags,
            content_digest=compute_deployment_digest(
                deployment_id=deployment_id,
                title=title,
                battlefield_id=battlefield_id,
                zones=zones,
                tags=tags,
            ),
        )

    @field_validator("deployment_id", "battlefield_id")
    @classmethod
    def _validate_ids(cls, value: str, info) -> str:
        return _validate_local_id(value, info.field_name)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _validate_trimmed(value, "title")

    @field_validator("content_digest")
    @classmethod
    def _validate_content_digest_shape(cls, value: str) -> str:
        return _validate_digest(value, "content_digest")

    @model_validator(mode="after")
    def _validate_deployment(self) -> Self:
        zone_ids = [zone.zone_id for zone in self.zones]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("deployment zone ids must be unique")
        all_coordinates = [
            position
            for zone in self.zones
            for position in zone.ordered_slots
        ]
        if len(all_coordinates) != len(set(all_coordinates)):
            raise ValueError(
                "deployment coordinate cannot appear in multiple zones",
            )
        expected = compute_deployment_digest(
            deployment_id=self.deployment_id,
            title=self.title,
            battlefield_id=self.battlefield_id,
            zones=self.zones,
            tags=self.tags,
        )
        if self.content_digest != expected:
            raise ValueError(
                "content_digest does not authenticate the deployment",
            )
        return self


class RosterMemberControllerOverride(BaseModel):
    """Per-member override of a roster controller default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    controller: RosterControllerKind
    policy_id: str | None = None

    @field_validator("member_id")
    @classmethod
    def _validate_member_id(cls, value: str) -> str:
        return _validate_local_id(value, "member_id")

    @model_validator(mode="after")
    def _validate_policy(self) -> Self:
        if self.controller is RosterControllerKind.AI:
            if self.policy_id is None:
                raise ValueError("AI controller override requires policy_id")
        elif self.policy_id is not None:
            raise ValueError(
                "non-AI controller overrides forbid policy_id",
            )
        return self


class RosterControllerDefaults(BaseModel):
    """Default controller and exact optional member overrides."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    controller: RosterControllerKind
    participant_name: str
    policy_id: str | None = None
    member_overrides: tuple[RosterMemberControllerOverride, ...] = ()

    @field_validator("participant_name")
    @classmethod
    def _validate_participant_name(cls, value: str) -> str:
        return _validate_trimmed(value, "participant_name")

    @model_validator(mode="after")
    def _validate_controller_defaults(self) -> Self:
        if self.controller is RosterControllerKind.AI:
            if self.policy_id is None:
                raise ValueError("AI roster controller requires policy_id")
        elif self.policy_id is not None:
            raise ValueError(
                "non-AI roster controllers forbid policy_id",
            )
        member_ids = [row.member_id for row in self.member_overrides]
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("member controller overrides must be unique")
        return self


class EncounterMemberPresentation(BaseModel):
    """Encounter-specific display override for one roster member."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    member_id: str
    display_name: str

    @field_validator("member_id")
    @classmethod
    def _validate_member_id(cls, value: str) -> str:
        return _validate_local_id(value, "member_id")

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _validate_trimmed(value, "display_name")


class EncounterRosterSlot(BaseModel):
    """One roster assigned to a faction, deployment zone, and controllers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roster_slot_id: str
    roster: EncounterRosterRecipe
    faction_id: str
    deployment_zone_id: str
    controller_defaults: RosterControllerDefaults
    member_presentations: tuple[EncounterMemberPresentation, ...] = ()

    @field_validator(
        "roster_slot_id",
        "faction_id",
        "deployment_zone_id",
    )
    @classmethod
    def _validate_ids(cls, value: str, info) -> str:
        return _validate_local_id(value, info.field_name)

    @model_validator(mode="after")
    def _validate_member_references(self) -> Self:
        roster_member_ids = {
            member.member_id for member in self.roster.members
        }
        presentation_ids = [
            presentation.member_id
            for presentation in self.member_presentations
        ]
        if len(presentation_ids) != len(set(presentation_ids)):
            raise ValueError("member presentation overrides must be unique")
        if not set(presentation_ids) <= roster_member_ids:
            raise ValueError(
                "member presentation must reference this roster",
            )
        override_ids = {
            override.member_id
            for override in self.controller_defaults.member_overrides
        }
        if not override_ids <= roster_member_ids:
            raise ValueError(
                "controller override must reference this roster",
            )
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

    @field_validator("roster_slot_id")
    @classmethod
    def _validate_roster_slot_id(cls, value: str) -> str:
        return _validate_local_id(value, "roster_slot_id")


EncounterOpeningPolicy = Annotated[
    Union[InitiativeOpeningPolicy, FixedRosterOpeningPolicy],
    Field(discriminator="kind"),
]


class EncounterNotablePosition(BaseModel):
    """Named map coordinate retained in an authored encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    position: tuple[int, int]

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _validate_local_id(value, "label")


def compute_encounter_recipe_digest(
    *,
    encounter_id: str,
    title: str,
    roster_slots: tuple[EncounterRosterSlot, ...],
    battlefield_id: str,
    deployment: EncounterDeploymentSpec,
    opening_policy: InitiativeOpeningPolicy | FixedRosterOpeningPolicy,
    notable_positions: tuple[EncounterNotablePosition, ...],
    tags: tuple[str, ...],
) -> str:
    return _canonical_digest({
        "encounter_id": encounter_id,
        "title": title,
        "roster_slots": [
            slot.model_dump(mode="json") for slot in roster_slots
        ],
        "battlefield_id": battlefield_id,
        "deployment": deployment.model_dump(mode="json"),
        "opening_policy": opening_policy.model_dump(mode="json"),
        "notable_positions": [
            row.model_dump(mode="json") for row in notable_positions
        ],
        "tags": list(tags),
    })


class EncounterRecipe(BaseModel):
    """Self-authenticating launch recipe for one complete encounter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    encounter_id: str
    title: str
    roster_slots: tuple[EncounterRosterSlot, ...] = Field(min_length=2)
    battlefield_id: str
    deployment: EncounterDeploymentSpec
    opening_policy: EncounterOpeningPolicy
    notable_positions: tuple[EncounterNotablePosition, ...] = ()
    tags: tuple[str, ...] = ()
    recipe_digest: str

    @classmethod
    def create(
        cls,
        *,
        encounter_id: str,
        title: str,
        roster_slots: tuple[EncounterRosterSlot, ...],
        battlefield_id: str,
        deployment: EncounterDeploymentSpec,
        opening_policy: (
            InitiativeOpeningPolicy | FixedRosterOpeningPolicy
        ),
        notable_positions: tuple[EncounterNotablePosition, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> Self:
        return cls(
            encounter_id=encounter_id,
            title=title,
            roster_slots=roster_slots,
            battlefield_id=battlefield_id,
            deployment=deployment,
            opening_policy=opening_policy,
            notable_positions=notable_positions,
            tags=tags,
            recipe_digest=compute_encounter_recipe_digest(
                encounter_id=encounter_id,
                title=title,
                roster_slots=roster_slots,
                battlefield_id=battlefield_id,
                deployment=deployment,
                opening_policy=opening_policy,
                notable_positions=notable_positions,
                tags=tags,
            ),
        )

    @field_validator("encounter_id", "battlefield_id")
    @classmethod
    def _validate_ids(cls, value: str, info) -> str:
        return _validate_local_id(value, info.field_name)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _validate_trimmed(value, "title")

    @field_validator("recipe_digest")
    @classmethod
    def _validate_recipe_digest_shape(cls, value: str) -> str:
        return _validate_digest(value, "recipe_digest")

    @model_validator(mode="after")
    def _validate_encounter(self) -> Self:
        if self.battlefield_id != self.deployment.battlefield_id:
            raise ValueError(
                "encounter battlefield must match deployment battlefield",
            )
        slot_ids = [slot.roster_slot_id for slot in self.roster_slots]
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError("encounter roster slot ids must be unique")
        zone_ids = [slot.deployment_zone_id for slot in self.roster_slots]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError(
                "each encounter roster requires a distinct deployment zone",
            )
        deployment_zones = {
            zone.zone_id: zone for zone in self.deployment.zones
        }
        for slot in self.roster_slots:
            zone = deployment_zones.get(slot.deployment_zone_id)
            if zone is None:
                raise ValueError(
                    f"encounter deployment zone "
                    f"{slot.deployment_zone_id!r} is not defined",
                )
            capacity = zone.max_members or len(zone.ordered_slots)
            if len(slot.roster.members) > capacity:
                raise ValueError(
                    f"roster {slot.roster_slot_id!r} exceeds deployment zone "
                    f"{zone.zone_id!r} capacity",
                )
        roles = [
            member.deployment_role
            for slot in self.roster_slots
            for member in slot.roster.members
        ]
        role_counts = {
            role: roles.count(role)
            for role in set(roles)
        }
        for slot in self.roster_slots:
            for member in slot.roster.members:
                for effect in member.scenario_setup_effects:
                    source_role = getattr(
                        effect,
                        "source_member_role",
                        None,
                    )
                    if (
                        source_role is not None
                        and role_counts.get(source_role) != 1
                    ):
                        raise ValueError(
                            "setup effect source_member_role must resolve "
                            "exactly once in the complete encounter",
                        )
        if (
            isinstance(self.opening_policy, FixedRosterOpeningPolicy)
            and self.opening_policy.roster_slot_id not in set(slot_ids)
        ):
            raise ValueError(
                "opening roster slot must reference this encounter",
            )
        notable_labels = [row.label for row in self.notable_positions]
        if len(notable_labels) != len(set(notable_labels)):
            raise ValueError("notable position labels must be unique")
        expected = compute_encounter_recipe_digest(
            encounter_id=self.encounter_id,
            title=self.title,
            roster_slots=self.roster_slots,
            battlefield_id=self.battlefield_id,
            deployment=self.deployment,
            opening_policy=self.opening_policy,
            notable_positions=self.notable_positions,
            tags=self.tags,
        )
        if self.recipe_digest != expected:
            raise ValueError(
                "recipe_digest does not authenticate the encounter recipe",
            )
        return self


__all__ = [
    "AuthoredCreatureRosterSource",
    "DamageAffinityStatus",
    "EncounterDeploymentRoleSlot",
    "EncounterDeploymentSpec",
    "EncounterDeploymentZone",
    "EncounterCompatibilityCode",
    "EncounterCompatibilityIssue",
    "EncounterCompatibilityPhase",
    "EncounterCompatibilityReport",
    "EncounterCompatibilitySeverity",
    "EncounterMemberPresentation",
    "EncounterNotablePosition",
    "EncounterOpeningPolicy",
    "EncounterRecipe",
    "EncounterRosterMember",
    "EncounterRosterMemberSource",
    "EncounterRosterRecipe",
    "EncounterRosterSlot",
    "EncounterSetupEffect",
    "FixedRosterOpeningPolicy",
    "InitiativeOpeningPolicy",
    "OwnedCharacterRosterSource",
    "RosterBehaviorGrant",
    "RosterControllerDefaults",
    "RosterControllerKind",
    "RosterDamageAffinity",
    "RosterItemGrant",
    "RosterItemPlacement",
    "RosterMemberControllerOverride",
    "RosterResourceState",
    "RosterSpellGrant",
    "RosterStartingCondition",
    "RosterStartingDamage",
    "compute_deployment_digest",
    "compute_encounter_recipe_digest",
    "compute_roster_recipe_digest",
]
