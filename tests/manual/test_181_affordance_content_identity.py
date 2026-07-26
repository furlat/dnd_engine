"""Exact authored identity on player action and reaction affordances."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.classes.barbarian import Retaliation
from dnd.classes.feats import LuckyFeature
from dnd.classes.fighter import (
    FightingStyleProtection,
    GreatWeaponFighting,
    Indomitable,
)
from dnd.classes.paladin import create_divine_smite_handler
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.reaction_definitions import (
    REACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.core.base_actions import (
    ActionAvailabilityStatus,
    AvailableActionInfo,
    AvailableHandlerInfo,
    AvailableTarget,
    BaseAction,
    TargetType,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.runtime import (
    AuthoredBehaviorAttribution,
    BehaviorBinding,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventHandler
from dnd.entity import Entity
from dnd.items.test_reactions import DodgeRollFeature, Intercepting
from dnd.monsters.bestiary import create_goblin
from dnd.premade_characters import PREMADE_CHARACTER_TEMPLATES
from dnd.reactions import create_opportunity_attack_handler
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import (
    create_counterspell_reaction_handler,
    create_shield_reaction_handler,
)
from server.content_catalog import build_public_content_catalog
from server.event_server import _serialize_entity_handlers


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _ref(
    content_id: str,
    *,
    definition_kind: ContentDefinitionKind = ContentDefinitionKind.ACTION,
) -> ContentRef:
    return ContentRef(
        pack_id="tests.affordance_identity",
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash="a" * 64,
    )


def _attribution() -> AuthoredBehaviorAttribution:
    return AuthoredBehaviorAttribution.from_binding(
        BehaviorBinding(
            definition_ref=_ref("action.test"),
            provided_by_ref=_ref(
                "creature.test",
                definition_kind=ContentDefinitionKind.CREATURE,
            ),
            origin_root_ref=_ref(
                "creature.test",
                definition_kind=ContentDefinitionKind.CREATURE,
            ),
            runtime_owner_uuid=uuid4(),
        ),
    )


def test_authored_behavior_attribution_excludes_runtime_instance_identity() -> None:
    """Affordance identity freezes authored refs, never an encounter owner UUID."""
    attribution = _attribution()

    assert set(AuthoredBehaviorAttribution.model_fields) == {
        "definition_ref",
        "provided_by_ref",
        "origin_root_ref",
    }
    assert attribution.definition_ref.content_id == "action.test"
    assert attribution.provided_by_ref.content_id == "creature.test"
    assert attribution.origin_root_ref == attribution.provided_by_ref
    assert "runtime_owner_uuid" not in attribution.model_dump()
    with pytest.raises(ValidationError, match="runtime_owner_uuid"):
        AuthoredBehaviorAttribution.model_validate({
            **attribution.model_dump(mode="json"),
            "runtime_owner_uuid": str(uuid4()),
        })


def test_action_and_handler_affordance_identity_is_required_and_singular() -> None:
    """Discovery rows expose one exact behavior attribution with no alias."""
    attribution = _attribution()
    action = AvailableActionInfo(
        template_name="Test",
        behavior_attribution=attribution,
        target_type=TargetType.SELF,
        availability_status=ActionAvailabilityStatus.AVAILABLE,
        valid_targets=[AvailableTarget(index=0)],
        can_afford=True,
        display_name="Test",
        cost_type="actions",
    )
    handler = AvailableHandlerInfo(
        name="Test Reaction",
        behavior_attribution=attribution,
        uuid=uuid4(),
        enabled=True,
        trigger_event="attack",
    )

    assert action.behavior_attribution is attribution
    assert handler.behavior_attribution is attribution
    assert "content_attributions" not in AvailableActionInfo.model_fields
    assert "content_attributions" not in AvailableHandlerInfo.model_fields

    for availability_status, can_afford in (
        (ActionAvailabilityStatus.SOURCE_UNAFFORDABLE, True),
        (ActionAvailabilityStatus.NO_VALID_TARGETS, False),
    ):
        with pytest.raises(
            ValidationError,
            match="source_unaffordable requires can_afford=false",
        ):
            AvailableActionInfo.model_validate({
                **action.model_dump(mode="json"),
                "availability_status": availability_status.value,
                "can_afford": can_afford,
            })

    with pytest.raises(
        ValidationError,
        match="available requires at least one executable target",
    ):
        AvailableActionInfo.model_validate({
            **action.model_dump(mode="json"),
            "availability_status": (
                ActionAvailabilityStatus.NO_VALID_TARGETS.value
            ),
        })

    with pytest.raises(ValidationError, match="behavior_attribution"):
        AvailableActionInfo.model_validate({
            "template_name": "Unidentified",
            "target_type": TargetType.SELF,
            "can_afford": True,
            "display_name": "Unidentified",
            "cost_type": "actions",
        })
    with pytest.raises(ValidationError, match="behavior_attribution"):
        AvailableHandlerInfo.model_validate({
            "name": "Unidentified",
            "uuid": uuid4(),
            "enabled": True,
            "trigger_event": "attack",
        })


def test_action_discovery_rejects_an_unbound_execution_template() -> None:
    """A custom action cannot leak through names when it has no exact binding."""
    entity = Entity.create(source_entity_uuid=uuid4(), name="Identity Probe")
    action = BaseAction(
        name="Unbound Custom Action",
        source_entity_uuid=entity.uuid,
        target_type=TargetType.SELF,
        use_register=False,
    )

    with pytest.raises(ValueError, match="authored behavior binding"):
        entity._make_action_info(
            template_name="Unbound Custom Action",
            target_type=TargetType.SELF,
            valid_targets=[AvailableTarget(index=0)],
            can_afford=True,
            availability_status=ActionAvailabilityStatus.AVAILABLE,
            template=action,
        )


def test_weapon_attack_affordance_names_its_exact_equipped_item_provider() -> None:
    """Dynamic Attack presentation resolves through the equipped weapon UUID."""
    attack_catalog_entry = next(
        entry
        for entry in build_public_content_catalog(
            bootstrap_content_system(),
        ).entries
        if entry.ref.identity_key == "core.rules:action:action.attack@1"
    )
    assert attack_catalog_entry.presentation.icon_key is None

    actor = create_goblin(
        name="Armed Affordance Probe",
        position=(2, 2),
        faction="heroes",
    )

    attack_rows = [
        row
        for row in actor.get_available_actions().entity_actions
        if (
            row.behavior_attribution.definition_ref.identity_key
            == "core.rules:action:action.attack@1"
        )
    ]

    assert attack_rows
    for row in attack_rows:
        assert row.weapon_slot is not None
        weapon = actor.equipment.get_weapon(WeaponSlot(row.weapon_slot))
        assert weapon is not None
        assert weapon.content_ref is not None
        assert row.source_item_uuid == weapon.uuid
        assert row.is_item_use is False


def test_every_direct_toggleable_reaction_binds_and_resolves_in_catalog() -> None:
    """Direct handlers use explicit definitions; variation remains runtime data."""
    loaded = bootstrap_content_system()
    public_keys = {
        entry.ref.identity_key
        for entry in build_public_content_catalog(loaded).entries
    }
    owner = Entity.create(source_entity_uuid=uuid4(), name="Reaction Probe")
    handlers = (
        create_opportunity_attack_handler(owner.uuid),
        create_shield_reaction_handler(owner.uuid),
        create_counterspell_reaction_handler(owner.uuid),
        create_divine_smite_handler(owner.uuid, 1),
        create_divine_smite_handler(owner.uuid, 5),
    )

    for handler in handlers:
        owner.add_event_handler(handler)
        assert handler.behavior_binding is not None
        assert (
            handler.behavior_binding.definition_ref.identity_key
            in public_keys
        )
        assert (
            handler.behavior_binding.provided_by_ref
            == handler.behavior_binding.definition_ref
        )
        assert handler.behavior_binding.origin_root_ref is None

    first_divine_smite_binding = handlers[3].behavior_binding
    fifth_divine_smite_binding = handlers[4].behavior_binding
    assert first_divine_smite_binding is not None
    assert fifth_divine_smite_binding is not None
    assert (
        first_divine_smite_binding.definition_ref
        == fifth_divine_smite_binding.definition_ref
    )
    assert tuple(
        declaration.ref.content_id
        for declaration in REACTION_BEHAVIOR_DECLARATIONS
    ) == (
        "reaction.opportunity_attack",
        "reaction.spell.shield",
        "reaction.class_feature.paladin.divine_smite",
    )


def test_condition_owned_toggleable_handlers_inherit_provider_identity() -> None:
    """Private handler implementations expose their exact owning rule."""
    owner = Entity.create(source_entity_uuid=uuid4(), name="Feature Probe")
    conditions = (
        LuckyFeature(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
        ),
        Retaliation(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
        ),
        GreatWeaponFighting(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
        ),
        FightingStyleProtection(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
        ),
        Indomitable(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            num_uses=1,
        ),
        Intercepting(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            charge_destination=(2, 2),
        ),
        DodgeRollFeature(
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
        ),
    )

    for condition in conditions:
        owner.add_condition(condition)
        assert condition.behavior_binding is not None

    infos = owner.get_player_toggleable_handler_infos()
    assert {info.name for info in infos} == {
        "Dodge Roll",
        "Great Weapon Fighting",
        "Indomitable",
        "Intercept",
        "Lucky",
        "Protection",
        "Retaliation",
    }
    expected_provider_refs = {
        condition.behavior_binding.definition_ref.identity_key
        for condition in conditions
        if condition.behavior_binding is not None
    }
    assert {
        info.behavior_attribution.definition_ref.identity_key
        for info in infos
    } == expected_provider_refs
    assert all(
        info.behavior_attribution.provided_by_ref
        == info.behavior_attribution.definition_ref
        for info in infos
    )


def test_unbound_toggleable_handler_fails_closed_on_both_discovery_paths() -> None:
    """Neither engine nor HTTP projection may fall back to a handler name."""
    owner = Entity.create(source_entity_uuid=uuid4(), name="Unbound Probe")

    def no_effect(_event, _source_entity_uuid):
        return None

    owner.add_event_handler(EventHandler(
        name="Unbound Toggleable",
        source_entity_uuid=owner.uuid,
        trigger_conditions=[],
        event_processor=no_effect,
        player_toggleable=True,
    ))

    with pytest.raises(ValueError, match="authored behavior binding"):
        owner.get_player_toggleable_handler_infos()
    with pytest.raises(ValueError, match="authored behavior binding"):
        _serialize_entity_handlers(owner)
    with pytest.raises(ValueError, match="authored behavior binding"):
        owner.get_available_actions()


def test_every_premade_affordance_ref_resolves_in_the_public_catalog() -> None:
    """Approved playable roots expose catalog-closed action/reaction rows."""
    loaded = bootstrap_content_system()
    public_refs = {
        entry.ref.identity_key
        for entry in build_public_content_catalog(loaded).entries
    }

    for index, template in enumerate(PREMADE_CHARACTER_TEMPLATES.values()):
        reset_engine_runtime(grid_size=(8, 8))
        entity = materialize_creature(
            template.creature_recipe,
            runtime_entity_uuid=uuid4(),
            display_name=f"Affordance Premade {index}",
            faction="heroes",
            position=(2, 2),
            deployment_role=CreatureDeploymentRole(
                role_id=f"tests.affordance.premade_{index}",
            ),
            possession_mode=(
                CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
            ),
        )
        discovered = entity.get_available_actions()
        action_rows = discovered.all_actions
        assert action_rows
        attributions = [
            *(row.behavior_attribution for row in action_rows),
            *(
                row.behavior_attribution
                for row in discovered.handler_details
            ),
        ]
        assert attributions
        for attribution in attributions:
            assert attribution.definition_ref.identity_key in public_refs
            assert attribution.provided_by_ref.identity_key in public_refs
            if attribution.origin_root_ref is not None:
                assert attribution.origin_root_ref.identity_key in public_refs
