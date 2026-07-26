"""Runtime catalogue of implemented engine content identities."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from dnd import actions as _dnd_actions
from dnd import classes as _dnd_classes
from dnd import conditions as _dnd_conditions
from dnd import items as _dnd_items
from dnd import spells as _dnd_spells
from dnd.classes import feats as _dnd_feats
from dnd.monsters import traits as _monster_traits
from dnd.actions import SpellAction
from dnd.blocks.base_item import BaseItem
from dnd.core.base_actions import BaseAction
from dnd.core.base_conditions import BaseCondition
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.spells import ALL_SPELLS


_IMPORTED_CONTENT_MODULES = (
    _dnd_actions,
    _dnd_classes,
    _dnd_conditions,
    _dnd_items,
    _dnd_spells,
    _dnd_feats,
    _monster_traits,
)


class ImplementedContentDefinition(BaseModel):
    """One discoverable rules-content implementation in the engine."""

    model_config = ConfigDict(frozen=True)

    semantic_key: str = Field(description="Stable implementation identity.")
    display_name: str = Field(description="Human-readable content name.")
    content_kind: RuntimeBehaviorKind = Field(description="Rules-content family.")
    subtype: str = Field(description="More specific engine classification.")
    source_module: str = Field(description="Python module that owns the implementation.")
    source_class: str = Field(description="Python class or handler-definition name.")
    evidence_lifecycle: str = Field(
        description="Runtime lifecycle that proves opportunity and effect coverage.",
    )


_EXPLICIT_HANDLER_CONTENT: tuple[ImplementedContentDefinition, ...] = (
    ImplementedContentDefinition(
        semantic_key="reaction.opportunity_attack",
        display_name="Opportunity Attack",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="movement_reaction",
        source_module="dnd.reactions",
        source_class="create_opportunity_attack_handler",
        evidence_lifecycle="handler_dispatch",
    ),
    ImplementedContentDefinition(
        semantic_key="reaction.spell.shield",
        display_name="Shield",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="spell_reaction",
        source_module="dnd.spells.abjuration",
        source_class="create_shield_reaction_handler",
        evidence_lifecycle="handler_dispatch",
    ),
    ImplementedContentDefinition(
        semantic_key="reaction.spell.counterspell",
        display_name="Counterspell",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="spell_reaction",
        source_module="dnd.spells.abjuration",
        source_class="create_counterspell_reaction_handler",
        evidence_lifecycle="handler_dispatch",
    ),
    ImplementedContentDefinition(
        semantic_key="feature.fighter.protection",
        display_name="Protection",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="class_feature_reaction",
        source_module="dnd.classes.fighter",
        source_class="create_protection_handler",
        evidence_lifecycle="handler_dispatch",
    ),
    ImplementedContentDefinition(
        semantic_key="trait.monster.parry",
        display_name="Parry",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="monster_trait_reaction",
        source_module="dnd.monsters.traits",
        source_class="ParryFeature",
        evidence_lifecycle="handler_dispatch",
    ),
    ImplementedContentDefinition(
        semantic_key="feature.barbarian.retaliation",
        display_name="Retaliation",
        content_kind=RuntimeBehaviorKind.REACTION,
        subtype="class_feature_reaction",
        source_module="dnd.classes.barbarian",
        source_class="Retaliation",
        evidence_lifecycle="handler_dispatch",
    ),
)


def build_implemented_content_catalog() -> dict[str, ImplementedContentDefinition]:
    """Return all imported concrete content classes plus explicit handlers."""
    spell_names = {
        f"{spell_type.__module__}.{spell_type.__name__}": name
        for name, spell_type in ALL_SPELLS.items()
    }
    definitions: dict[str, ImplementedContentDefinition] = {
        definition.semantic_key: definition
        for definition in _EXPLICIT_HANDLER_CONTENT
    }
    for action_type in _recursive_subclasses(BaseAction):
        if not action_type.__module__.startswith("dnd."):
            continue
        semantic_key = _field_string(action_type, "semantic_key") or _class_key(action_type)
        is_spell = issubclass(action_type, SpellAction) or semantic_key in spell_names
        is_environment = action_type.__module__.startswith("dnd.items.environment")
        kind = (
            RuntimeBehaviorKind.SPELL
            if is_spell
            else RuntimeBehaviorKind.ENVIRONMENT_INTERACTION
            if is_environment
            else RuntimeBehaviorKind.ACTION
        )
        category = _field_string(action_type, "action_category") or "ability"
        definitions[semantic_key] = ImplementedContentDefinition(
            semantic_key=semantic_key,
            display_name=spell_names.get(semantic_key) or _field_string(action_type, "name") or action_type.__name__,
            content_kind=kind,
            subtype=category,
            source_module=action_type.__module__,
            source_class=action_type.__name__,
            evidence_lifecycle="decision_epoch_command",
        )
    for condition_type in _recursive_subclasses(BaseCondition):
        if not condition_type.__module__.startswith("dnd."):
            continue
        semantic_key = _field_string(condition_type, "semantic_key") or _class_key(condition_type)
        kind = _condition_kind(condition_type)
        definitions.setdefault(
            semantic_key,
            ImplementedContentDefinition(
                semantic_key=semantic_key,
                display_name=_field_string(condition_type, "name") or condition_type.__name__,
                content_kind=kind,
                subtype="condition_state",
                source_module=condition_type.__module__,
                source_class=condition_type.__name__,
                evidence_lifecycle="condition_transition",
            ),
        )
    for item_type in _recursive_subclasses(BaseItem):
        if not item_type.__module__.startswith("dnd."):
            continue
        semantic_key = _field_string(item_type, "semantic_key") or _class_key(item_type)
        kind = (
            RuntimeBehaviorKind.ENVIRONMENT_INTERACTION
            if item_type.__module__.startswith("dnd.items.environment")
            else RuntimeBehaviorKind.ITEM
        )
        definitions.setdefault(
            semantic_key,
            ImplementedContentDefinition(
                semantic_key=semantic_key,
                display_name=_field_string(item_type, "name") or item_type.__name__,
                content_kind=kind,
                subtype="item_class",
                source_module=item_type.__module__,
                source_class=item_type.__name__,
                evidence_lifecycle="manifest_item_use_or_event",
            ),
        )
    return dict(sorted(definitions.items()))


_T = TypeVar("_T", bound=type[Any])


def _recursive_subclasses(base: _T) -> tuple[_T, ...]:
    """Return every currently imported subclass exactly once."""
    found: list[_T] = []
    pending = list(base.__subclasses__())
    seen: set[type[Any]] = set()
    while pending:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        found.append(child)
        pending.extend(child.__subclasses__())
    return tuple(found)


def _class_key(content_type: type[Any]) -> str:
    return f"{content_type.__module__}.{content_type.__name__}"


def _field_string(content_type: type[Any], field_name: str) -> str | None:
    field = getattr(content_type, "model_fields", {}).get(field_name)
    if field is None:
        return None
    value = field.default
    if hasattr(value, "value"):
        value = value.value
    return value if isinstance(value, str) and value else None


def _condition_kind(condition_type: type[BaseCondition]) -> RuntimeBehaviorKind:
    module = condition_type.__module__
    if module == "dnd.classes.feats":
        return RuntimeBehaviorKind.FEAT
    if module.startswith("dnd.monsters"):
        return RuntimeBehaviorKind.TRAIT
    if module.startswith("dnd.classes"):
        return RuntimeBehaviorKind.CLASS_FEATURE
    return RuntimeBehaviorKind.CONDITION
