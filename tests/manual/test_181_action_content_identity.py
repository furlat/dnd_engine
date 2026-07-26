"""Exact authored identity and admission for every active action behavior."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from pydantic import JsonValue

from dnd.actions import Move, SpellAction
from dnd.classes.barbarian import RecklessAttack, RecklessAttackFeature
from dnd.classes.content_factories import (
    PLAYER_CLASS_CREATURE_RECIPES_BY_ID,
)
from dnd.classes.fighter import (
    ActionSurge,
    ActionSurgeFeature,
    ExtraAttack,
    ExtraAttackFeature,
)
from dnd.classes.sorcerer import ConvertSPToSlot, SorceryPointsFeature
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.core.base_actions import BaseAction, StructuredAction
from dnd.core.content.dependencies import ContentDependencyRelation
from dnd.core.content.descriptors import ContentVisibility
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import (
    BehaviorBinding,
    RuntimeBehaviorKind,
    runtime_behavior_provider,
)
from dnd.entity import Entity, EntityConfig
from dnd.items.consumables import _PotionDrinkAction
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import MultiattackAction
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import (
    FreedomOfMovement,
    FreedomOfMovementEscape,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_CLASS
from dnd.spells.conjuration import CallLightning, CallLightningStrike
from dnd.spells.evocation import Sunbeam, SunbeamStrike
from dnd.spells.necromancy import Eyebite, EyebiteStrike
from dnd.spells.transmutation import (
    Telekinesis,
    TelekinesisGrab,
    TelekinesisMove,
    TelekinesisRestrain,
)
from server.content_catalog import build_public_content_catalog


EXPECTED_ABSTRACT_ACTION_MECHANISMS = frozenset({
    SpellAction,
    StructuredAction,
    _PotionDrinkAction,
})


def _active_descendants(
    action_type: type[BaseAction],
) -> set[type[BaseAction]]:
    descendants: set[type[BaseAction]] = set()
    for child_type in action_type.__subclasses__():
        if child_type.__module__.startswith("dnd."):
            descendants.add(child_type)
        descendants.update(_active_descendants(child_type))
    return descendants


def _concrete_action_types(
    action_types: Iterable[type[BaseAction]],
) -> tuple[type[BaseAction], ...]:
    return tuple(sorted(
        set(action_types) - EXPECTED_ABSTRACT_ACTION_MECHANISMS,
        key=lambda action_type: (
            action_type.__module__,
            action_type.__qualname__,
        ),
    ))


def test_active_action_inventory_is_exact_and_fully_declared() -> None:
    """Only three composition bases remain non-authored runtime mechanisms."""
    descendants = _active_descendants(BaseAction)
    assert EXPECTED_ABSTRACT_ACTION_MECHANISMS <= descendants

    concrete = _concrete_action_types(descendants)
    declarations = tuple(
        get_content_declaration(action_type)
        for action_type in concrete
    )

    assert len({
        declaration.ref.identity_key
        for declaration in declarations
    }) == len(concrete)
    assert all(
        declaration.runtime_behavior_kind
        in {
            RuntimeBehaviorKind.ACTION,
            RuntimeBehaviorKind.SPELL,
        }
        for declaration in declarations
    )
    for action_type in EXPECTED_ABSTRACT_ACTION_MECHANISMS:
        try:
            get_content_declaration(action_type)
        except ValueError:
            continue
        raise AssertionError(
            f"Abstract action mechanism acquired authored identity: {action_type!r}",
        )


def test_every_public_action_definition_resolves_in_public_catalog() -> None:
    """Player-visible action definitions have one exact catalog join."""
    loaded = bootstrap_content_system()
    public_keys = {
        entry.ref.identity_key
        for entry in build_public_content_catalog(loaded).entries
    }
    declarations = tuple(
        get_content_declaration(action_type)
        for action_type in _concrete_action_types(
            _active_descendants(BaseAction),
        )
    )

    for declaration in declarations:
        if declaration.descriptor.visibility is ContentVisibility.PUBLIC:
            assert declaration.ref.identity_key in public_keys
        else:
            assert declaration.ref.identity_key not in public_keys


def test_condition_granted_action_binds_as_exact_provider_child() -> None:
    """Action admission preserves the feature that causally granted it."""
    loaded = bootstrap_content_system()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(loaded)
    reset_engine_runtime(grid_size=(4, 4))
    owner = Entity.create(
        source_entity_uuid=uuid4(),
        name="Action identity owner",
        config=EntityConfig(),
    )
    feature = RecklessAttackFeature(
        source_entity_uuid=owner.uuid,
        target_entity_uuid=owner.uuid,
    )

    result = owner.add_condition(feature, check_save_throw=False)

    assert result is not None and not result.canceled
    granted = owner.get_action_template("Reckless Attack")
    assert isinstance(granted, RecklessAttack)
    action_declaration = get_content_declaration(RecklessAttack)
    provider_declaration = get_content_declaration(RecklessAttackFeature)
    assert granted.behavior_binding == BehaviorBinding(
        definition_ref=action_declaration.ref,
        provided_by_ref=provider_declaration.ref,
        origin_root_ref=None,
        runtime_owner_uuid=owner.uuid,
    )
    assert any(
        dependency.relation is ContentDependencyRelation.GRANTS_ACTION
        and dependency.target_ref == action_declaration.ref
        for dependency in provider_declaration.dependencies
    )


def _materialize_test_creature(
    recipe: ContentRecipe,
    *,
    parameters: dict[str, JsonValue] | None = None,
    possession_mode: CreaturePossessionMode = (
        CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
    ),
) -> Entity:
    exact_recipe = (
        recipe
        if parameters is None
        else ContentRecipe.create(ref=recipe.ref, parameters=parameters)
    )
    return materialize_creature(
        exact_recipe,
        runtime_entity_uuid=uuid4(),
        display_name=f"Action root {recipe.ref.content_id}",
        faction="tests",
        position=(2, 2),
        deployment_role=CreatureDeploymentRole(
            role_id=f"tests.action_identity.{recipe.ref.content_id}",
        ),
        possession_mode=possession_mode,
    )


def _require_action(
    entity: Entity,
    action_type: type[BaseAction],
) -> BaseAction:
    return next(
        action
        for action in entity.registered_actions
        if isinstance(action, action_type)
    )


def _assert_feature_granted_action(
    entity: Entity,
    *,
    action_type: type[BaseAction],
    feature_type: type[object],
) -> None:
    action = _require_action(entity, action_type)
    feature = next(
        condition
        for condition in entity.active_conditions.values()
        if isinstance(condition, feature_type)
    )
    action_declaration = get_content_declaration(action_type)
    feature_declaration = get_content_declaration(feature_type)
    root_ref = entity.content_ref
    assert root_ref is not None
    assert feature.behavior_binding == BehaviorBinding(
        definition_ref=feature_declaration.ref,
        provided_by_ref=root_ref,
        origin_root_ref=root_ref,
        runtime_owner_uuid=entity.uuid,
    )
    assert action.behavior_binding == BehaviorBinding(
        definition_ref=action_declaration.ref,
        provided_by_ref=feature_declaration.ref,
        origin_root_ref=root_ref,
        runtime_owner_uuid=entity.uuid,
    )


def test_class_and_monster_roots_preserve_exact_action_provider_chains() -> None:
    """Root composition binds universal, feature, and stat-block actions once."""
    SERVER_CONTENT_SYSTEM_RUNTIME.install(bootstrap_content_system())

    class_cases = (
        (
            PLAYER_CLASS_CREATURE_RECIPES_BY_ID["barbarian"],
            {
                "level": 5,
                "primal_path": "berserker",
                "asi_4": [["strength", 2]],
            },
            RecklessAttack,
            RecklessAttackFeature,
        ),
        (
            PLAYER_CLASS_CREATURE_RECIPES_BY_ID["fighter"],
            {"level": 5, "asi_4": [["strength", 2]]},
            ActionSurge,
            ActionSurgeFeature,
        ),
        (
            PLAYER_CLASS_CREATURE_RECIPES_BY_ID["sorcerer"],
            {
                "level": 5,
                "metamagic_choices": ["quickened", "twinned"],
                "asi_4": [["charisma", 2]],
            },
            ConvertSPToSlot,
            SorceryPointsFeature,
        ),
    )
    for recipe, parameters, action_type, feature_type in class_cases:
        reset_engine_runtime(grid_size=(6, 6))
        entity = _materialize_test_creature(
            recipe,
            parameters=parameters,
            possession_mode=(
                CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
                if recipe.ref.content_id
                in {
                    "creature.player.barbarian",
                    "creature.player.fighter",
                }
                else CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
            ),
        )
        _assert_feature_granted_action(
            entity,
            action_type=action_type,
            feature_type=feature_type,
        )
        move = _require_action(entity, Move)
        move_declaration = get_content_declaration(Move)
        assert move.behavior_binding == BehaviorBinding(
            definition_ref=move_declaration.ref,
            provided_by_ref=move_declaration.ref,
            origin_root_ref=None,
            runtime_owner_uuid=entity.uuid,
        )
        if recipe.ref.content_id in {
            "creature.player.barbarian",
            "creature.player.fighter",
        }:
            _assert_feature_granted_action(
                entity,
                action_type=ExtraAttack,
                feature_type=ExtraAttackFeature,
            )
            assert (
                get_content_declaration(ExtraAttackFeature).ref.content_id
                == "class_feature.extra_attack"
            )
            assert (
                get_content_declaration(ExtraAttack).ref.content_id
                == "action.feature.extra_attack"
            )

    reset_engine_runtime(grid_size=(6, 6))
    scout_recipe = SRD_CREATURE_RECIPES_BY_ID["scout"]
    scout = _materialize_test_creature(scout_recipe)
    multiattack = _require_action(scout, MultiattackAction)
    multiattack_declaration = get_content_declaration(MultiattackAction)
    assert multiattack.behavior_binding == BehaviorBinding(
        definition_ref=multiattack_declaration.ref,
        provided_by_ref=scout_recipe.ref,
        origin_root_ref=scout_recipe.ref,
        runtime_owner_uuid=scout.uuid,
    )
    scout_declaration = SERVER_CONTENT_SYSTEM_RUNTIME.require().registry.resolve_factory(
        scout_recipe.ref,
    )
    assert any(
        dependency.relation is ContentDependencyRelation.GRANTS_ACTION
        and dependency.target_ref == multiattack_declaration.ref
        for dependency in scout_declaration.dependencies
    )


def test_maintained_spell_action_closure_and_cross_owner_binding_are_exact() -> None:
    """Spell-granted actions use typed dependency edges, including follow-ups."""
    loaded = bootstrap_content_system()
    SERVER_CONTENT_SYSTEM_RUNTIME.install(loaded)
    direct_grants = {
        FreedomOfMovement: FreedomOfMovementEscape,
        CallLightning: CallLightningStrike,
        Sunbeam: SunbeamStrike,
        Eyebite: EyebiteStrike,
        Telekinesis: TelekinesisGrab,
    }
    for spell_type, action_type in direct_grants.items():
        spell_declaration = SPELL_CONTENT_DECLARATIONS_BY_CLASS[spell_type]
        action_declaration = get_content_declaration(action_type)
        assert any(
            dependency.relation is ContentDependencyRelation.GRANTS_ACTION
            and dependency.target_ref == action_declaration.ref
            for dependency in spell_declaration.dependencies
        )

    grab_declaration = get_content_declaration(TelekinesisGrab)
    follow_up_identity_keys = {
        get_content_declaration(TelekinesisMove).ref.identity_key,
        get_content_declaration(TelekinesisRestrain).ref.identity_key,
    }
    assert {
        dependency.target_ref.identity_key
        for dependency in grab_declaration.dependencies
        if dependency.relation is ContentDependencyRelation.GRANTS_ACTION
    } == follow_up_identity_keys

    reset_engine_runtime(grid_size=(4, 4))
    caster = Entity.create(
        source_entity_uuid=uuid4(),
        name="Caster",
        config=EntityConfig(),
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Target",
        config=EntityConfig(),
    )
    spell = FreedomOfMovement(
        source_entity_uuid=caster.uuid,
        template=True,
    )
    caster.register_action(spell)
    escape = FreedomOfMovementEscape(
        source_entity_uuid=target.uuid,
        template=True,
    )
    with runtime_behavior_provider(spell):
        target.register_action(escape)

    spell_declaration = get_content_declaration(FreedomOfMovement)
    escape_declaration = get_content_declaration(FreedomOfMovementEscape)
    assert escape.behavior_binding == BehaviorBinding(
        definition_ref=escape_declaration.ref,
        provided_by_ref=spell_declaration.ref,
        origin_root_ref=None,
        runtime_owner_uuid=target.uuid,
    )
