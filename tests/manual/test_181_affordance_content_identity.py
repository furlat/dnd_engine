"""Exact authored identity on player action and reaction affordances."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.classes.barbarian import create_retaliation_handler
from dnd.classes.feats import lucky_processor
from dnd.classes.fighter import (
    create_indomitable_handler,
    create_protection_handler,
    great_weapon_fighting_processor,
)
from dnd.classes.permanent_feature_definitions import (
    BARBARIAN_RETALIATION_DECLARATION,
    FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION,
    FIGHTER_INDOMITABLE_DECLARATION,
    FIGHTER_PROTECTION_DECLARATION,
    LUCKY_FEAT_DECLARATION,
)
from dnd.classes.paladin import create_divine_smite_handler
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.content_system.reaction_definitions import (
    REACTION_BEHAVIOR_DECLARATIONS,
)
from dnd.core.base_actions import (
    ActionEvent,
    ActionAvailabilityStatus,
    AvailableActionInfo,
    AvailableHandlerInfo,
    AvailableTarget,
    BaseAction,
    TargetType,
)
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.runtime import (
    AuthoredBehaviorAttribution,
    BehaviorBinding,
    HandlerDispatchOutcome,
    RuntimeBehaviorKind,
)
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin
from dnd.monsters.traits import ParryFeature
from dnd.premade_characters import (
    BARBARIAN_L5_BERSERKER_TORCH_RECIPE,
    FIGHTER_L5_SHIELD_TORCH_RECIPE,
    SORCERER_L5_STANDARD_TORCH_RECIPE,
)
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
    assert attack_catalog_entry.presentation.icon_key == "ui.filter-attacks"

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
        create_protection_handler(owner.uuid),
        create_retaliation_handler(owner.uuid),
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
        "reaction.class_feature.paladin.divine_smite",
        "reaction.monster.parry",
        "reaction.class_feature.fighter.protection",
        "reaction.class_feature.barbarian.retaliation",
    )


def test_provider_owned_public_reactions_have_exact_install_edges() -> None:
    """Persistent features explicitly install their public reaction behavior."""

    expected = {
        get_content_declaration(ParryFeature).ref: "reaction.monster.parry",
        FIGHTER_PROTECTION_DECLARATION.ref: (
            "reaction.class_feature.fighter.protection"
        ),
        BARBARIAN_RETALIATION_DECLARATION.ref: (
            "reaction.class_feature.barbarian.retaliation"
        ),
    }
    registry = bootstrap_content_system().registry
    for provider_ref, reaction_content_id in expected.items():
        provider_declaration = registry.resolve_definition(provider_ref)
        install_edges = tuple(
            dependency
            for dependency in provider_declaration.dependencies
            if dependency.relation is ContentDependencyRelation.INSTALLS_HANDLER
        )
        assert len(install_edges) == 1
        assert (
            install_edges[0].target_ref.definition_kind
            is ContentDefinitionKind.REACTION
        )
        assert install_edges[0].target_ref.content_id == reaction_content_id


def test_effective_reaction_retains_exact_internal_presentation_evidence() -> None:
    """A state-changing handler leaves replay-safe evidence on its event lineage."""

    owner = Entity.create(source_entity_uuid=uuid4(), name="Reaction Evidence")
    reaction_ref = _ref(
        "reaction.test",
        definition_kind=ContentDefinitionKind.REACTION,
    )
    binding = BehaviorBinding(
        definition_ref=reaction_ref,
        provided_by_ref=reaction_ref,
        origin_root_ref=None,
        runtime_owner_uuid=owner.uuid,
    )

    emitted: list[Event] = []

    def modify(event: ActionEvent, _source_uuid):
        child = Event(
            name="Reaction Effect",
            event_type=EventType.TRIGGER_EVENT,
            phase=EventPhase.COMPLETION,
            source_entity_uuid=owner.uuid,
            target_entity_uuid=owner.uuid,
            parent_event=event.uuid,
            use_register=False,
        )
        emitted.append(EventQueue.register(child))
        return event.model_copy(update={"modified": True})

    handler = EventHandler(
        name="Test Reaction",
        semantic_key="reaction.test",
        behavior_binding=binding,
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=owner.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=modify,
    )
    owner.add_event_handler(handler)
    declaration = ActionEvent(
        name="Trigger",
        source_entity_uuid=owner.uuid,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )

    modified = EventQueue.register(declaration)
    completion = modified.phase_to(EventPhase.COMPLETION)

    evidence = completion.effective_handler_presentations
    assert len(evidence) == 1
    assert evidence[0].handler_name == "Test Reaction"
    assert evidence[0].behavior_binding == binding
    assert evidence[0].source_entity_uuid == owner.uuid
    assert evidence[0].triggering_event_uuid == declaration.uuid
    assert evidence[0].triggering_lineage_uuid == declaration.lineage_uuid
    assert evidence[0].emitted_lineage_uuids == (
        emitted[0].lineage_uuid,
    )
    assert evidence[0].outcome is HandlerDispatchOutcome.MODIFIED_EVENT
    assert "effective_handler_presentations" not in completion.model_dump()


def test_unchanged_already_modified_event_is_not_a_reaction_effect() -> None:
    """A later handler cannot claim an earlier handler's modified flag."""

    owner = Entity.create(source_entity_uuid=uuid4(), name="No Effect Evidence")
    reaction_ref = _ref(
        "reaction.no_effect",
        definition_kind=ContentDefinitionKind.REACTION,
    )
    binding = BehaviorBinding(
        definition_ref=reaction_ref,
        provided_by_ref=reaction_ref,
        origin_root_ref=None,
        runtime_owner_uuid=owner.uuid,
    )
    outcomes: list[HandlerDispatchOutcome] = []

    def unchanged(event: ActionEvent, _source_uuid):
        return event

    def capture(evidence):
        outcomes.append(evidence.outcome)

    handler = EventHandler(
        name="No Effect Reaction",
        semantic_key="reaction.no_effect",
        behavior_binding=binding,
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=owner.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.BASE_ACTION,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=unchanged,
    )
    owner.add_event_handler(handler)
    EventQueue.add_on_handler_dispatch_callback(capture)
    try:
        event = ActionEvent(
            name="Previously Modified Trigger",
            source_entity_uuid=owner.uuid,
            phase=EventPhase.DECLARATION,
            modified=True,
            use_register=False,
        )
        result = EventQueue.register(event)
    finally:
        EventQueue.remove_on_handler_dispatch_callback(capture)

    assert result is event
    assert outcomes == [HandlerDispatchOutcome.NO_EFFECT]
    assert result.effective_handler_presentations == ()


def test_structural_toggleable_handlers_preserve_public_reactions() -> None:
    """Structural handlers retain exact providers and public invocation identity."""
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())
    owner = Entity.create(source_entity_uuid=uuid4(), name="Feature Probe")
    structural_handlers = (
        (
            EventHandler(
                name="Lucky",
                source_entity_uuid=owner.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=event_type,
                        event_phase=EventPhase.EFFECT,
                        event_source_entity_uuid=owner.uuid,
                    )
                    for event_type in (
                        EventType.ATTACK_D20_ROLL_RESULT,
                        EventType.SAVE_D20_ROLL_RESULT,
                        EventType.CHECK_D20_ROLL_RESULT,
                    )
                ],
                event_processor=lucky_processor,
                player_toggleable=True,
            ),
            LUCKY_FEAT_DECLARATION,
        ),
        (
            create_retaliation_handler(owner.uuid),
            BARBARIAN_RETALIATION_DECLARATION,
        ),
        (
            EventHandler(
                name="Great Weapon Fighting",
                source_entity_uuid=owner.uuid,
                trigger_conditions=[
                    Trigger(
                        event_type=EventType.DAMAGE_ROLL_RESULT,
                        event_phase=EventPhase.EFFECT,
                    ),
                ],
                event_processor=great_weapon_fighting_processor,
                player_toggleable=True,
            ),
            FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION,
        ),
        (
            create_protection_handler(owner.uuid),
            FIGHTER_PROTECTION_DECLARATION,
        ),
        (
            create_indomitable_handler(owner.uuid),
            FIGHTER_INDOMITABLE_DECLARATION,
        ),
    )
    for handler, declaration in structural_handlers:
        SERVER_CONTENT_SYSTEM_RUNTIME.bind_granted_behavior(
            handler,
            provider_ref=declaration.ref,
            runtime_owner_uuid=owner.uuid,
        )
        owner.add_event_handler(handler)

    infos = owner.get_player_toggleable_handler_infos()
    assert {info.name for info in infos} == {
        "Great Weapon Fighting",
        "Indomitable",
        "Lucky",
        "Protection",
        "Retaliation",
    }
    provider_refs_by_name = {
        "Lucky": LUCKY_FEAT_DECLARATION.ref,
        "Retaliation": BARBARIAN_RETALIATION_DECLARATION.ref,
        "Great Weapon Fighting": (
            FIGHTER_GREAT_WEAPON_FIGHTING_DECLARATION.ref
        ),
        "Protection": FIGHTER_PROTECTION_DECLARATION.ref,
        "Indomitable": FIGHTER_INDOMITABLE_DECLARATION.ref,
    }
    public_reaction_refs = {
        declaration.ref.content_id: declaration.ref
        for declaration in REACTION_BEHAVIOR_DECLARATIONS
    }
    definition_refs_by_name = {
        **provider_refs_by_name,
        "Protection": public_reaction_refs[
            "reaction.class_feature.fighter.protection"
        ],
        "Retaliation": public_reaction_refs[
            "reaction.class_feature.barbarian.retaliation"
        ],
    }
    for info in infos:
        assert (
            info.behavior_attribution.definition_ref
            == definition_refs_by_name[info.name]
        )
        assert (
            info.behavior_attribution.provided_by_ref
            == provider_refs_by_name[info.name]
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

    recipes = (
        BARBARIAN_L5_BERSERKER_TORCH_RECIPE,
        FIGHTER_L5_SHIELD_TORCH_RECIPE,
        SORCERER_L5_STANDARD_TORCH_RECIPE,
    )
    for index, recipe in enumerate(recipes):
        reset_engine_runtime(grid_size=(8, 8))
        entity = materialize_creature(
            recipe,
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
