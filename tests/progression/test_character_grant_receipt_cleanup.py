"""Exact cleanup regressions for heterogeneous structural modifier handles."""

from uuid import uuid4

from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    ConditionImmunityHandle,
    ModifierHandle,
    ModifierHandleChannel,
    ModifierHandleKind,
)
from dnd.content_system.character_materialization import (
    CharacterCompositionReceipt,
    remove_character_composition,
)
from dnd.content_system.condition_definitions import (
    CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS,
)
from dnd.classes.rage import Raging
from dnd.core.modifiers import (
    AdvantageModifier,
    AdvantageStatus,
    ContextualAdvantageModifier,
    ContextualNumericalModifier,
    NumericalModifier,
)
from dnd.entity import Entity


def test_receipt_removes_each_modifier_collection_from_its_exact_channel() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    initiative = entity.initiative
    source = entity.uuid

    value = NumericalModifier.create(
        source_entity_uuid=source,
        name="Static value",
        value=2,
    )
    maximum = NumericalModifier.create(
        source_entity_uuid=source,
        name="Static maximum",
        value=30,
    )
    advantage = AdvantageModifier(
        source_entity_uuid=source,
        name="Static advantage",
        value=AdvantageStatus.ADVANTAGE,
    )
    contextual_value = ContextualNumericalModifier(
        source_entity_uuid=source,
        name="Contextual value",
        callable=lambda *_: NumericalModifier.create(
            source_entity_uuid=source,
            name="Resolved contextual value",
            value=3,
        ),
    )
    contextual_advantage = ContextualAdvantageModifier(
        source_entity_uuid=source,
        name="Contextual advantage",
        callable=lambda *_: AdvantageModifier(
            source_entity_uuid=source,
            name="Resolved contextual advantage",
            value=AdvantageStatus.ADVANTAGE,
        ),
    )

    initiative.self_static.add_value_modifier(value)
    initiative.self_static.add_max_constraint(maximum)
    initiative.self_static.add_advantage_modifier(advantage)
    initiative.self_contextual.add_value_modifier(contextual_value)
    initiative.self_contextual.add_advantage_modifier(contextual_advantage)

    grant = CharacterGrantReceipt(
        grant_id=uuid4(),
        modifier_handles=(
            ModifierHandle(
                value_uuid=initiative.uuid,
                modifier_uuid=value.uuid,
            ),
            ModifierHandle(
                value_uuid=initiative.uuid,
                modifier_uuid=maximum.uuid,
                kind=ModifierHandleKind.MAX_CONSTRAINT,
            ),
            ModifierHandle(
                value_uuid=initiative.uuid,
                modifier_uuid=advantage.uuid,
                kind=ModifierHandleKind.ADVANTAGE,
            ),
            ModifierHandle(
                value_uuid=initiative.uuid,
                modifier_uuid=contextual_value.uuid,
                channel=ModifierHandleChannel.SELF_CONTEXTUAL,
            ),
            ModifierHandle(
                value_uuid=initiative.uuid,
                modifier_uuid=contextual_advantage.uuid,
                channel=ModifierHandleChannel.SELF_CONTEXTUAL,
                kind=ModifierHandleKind.ADVANTAGE,
            ),
        ),
    )
    receipt = CharacterCompositionReceipt(
        runtime_entity_uuid=entity.uuid,
        character_id=uuid4(),
        definition_revision=1,
        definition_digest="definition",
        loadout_revision=1,
        loadout_digest="loadout",
        grants=(grant,),
        automatic_grant_refs=(),
    )

    remove_character_composition(entity, receipt)

    assert value.uuid not in initiative.self_static.value_modifiers
    assert maximum.uuid not in initiative.self_static.max_constraints
    assert advantage.uuid not in initiative.self_static.advantage_modifiers
    assert (
        contextual_value.uuid
        not in initiative.self_contextual.value_modifiers
    )
    assert (
        contextual_advantage.uuid
        not in initiative.self_contextual.advantage_modifiers
    )


def test_receipt_removes_only_its_exact_condition_immunity_sources() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    owned = uuid4()
    sibling = uuid4()
    entity.add_condition_immunity_source(
        "Frightened",
        owned,
        immunity_check=lambda *_: True,
    )
    entity.add_condition_immunity_source(
        "Frightened",
        sibling,
        immunity_check=lambda *_: True,
    )
    receipt = CharacterCompositionReceipt(
        runtime_entity_uuid=entity.uuid,
        character_id=uuid4(),
        definition_revision=1,
        definition_digest="definition",
        loadout_revision=1,
        loadout_digest="loadout",
        grants=(
            CharacterGrantReceipt(
                grant_id=owned,
                condition_immunity_handles=(
                    ConditionImmunityHandle(
                        block_uuid=entity.uuid,
                        condition_name="Frightened",
                        source_id=owned,
                    ),
                ),
            ),
        ),
        automatic_grant_refs=(),
    )

    remove_character_composition(entity, receipt)

    names = {
        name
        for name, _ in entity.contextual_condition_immunities["Frightened"]
    }
    assert entity._condition_immunity_source_name(owned) not in names
    assert entity._condition_immunity_source_name(sibling) in names


def test_receipt_removes_dynamic_state_by_exact_condition_ref() -> None:
    entity = Entity.create(source_entity_uuid=uuid4())
    raging = Raging(
        source_entity_uuid=entity.uuid,
        target_entity_uuid=entity.uuid,
    )
    entity.add_condition(raging)
    assert raging.behavior_binding is not None
    raging_ref = CONDITION_BEHAVIOR_DECLARATIONS_BY_CLASS[Raging].ref
    handler_uuids = set(raging.event_handlers_uuids)
    assert "Raging" in entity.active_conditions
    receipt = CharacterCompositionReceipt(
        runtime_entity_uuid=entity.uuid,
        character_id=uuid4(),
        definition_revision=1,
        definition_digest="definition",
        loadout_revision=1,
        loadout_digest="loadout",
        grants=(
            CharacterGrantReceipt(
                grant_id=uuid4(),
                transient_condition_refs_to_remove=(raging_ref,),
            ),
        ),
        automatic_grant_refs=(),
    )

    remove_character_composition(entity, receipt)

    assert "Raging" not in entity.active_conditions
    assert not handler_uuids.intersection(entity.event_handlers)
