"""Engine semantic tests for object identity and registries."""

from uuid import uuid4

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.values import BaseValue, ContextualValue, ModifiableValue, StaticValue
from dnd.entity import Entity, EntityConfig
from tests.engine.support import reset_combat_state


class RegistryProbe(BaseObject):
    """Small concrete object used to isolate BaseObject registry behavior."""


class OtherRegistryProbe(BaseObject):
    """Second concrete object used to verify typed registry lookup."""


def reset_identity_state() -> None:
    """Clear the global state touched by these registry examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def test_eb_01_001_base_object_registration_lifecycle() -> None:
    """EB-01-001: BaseObject registers by default and can opt out."""
    reset_identity_state()
    source_uuid = uuid4()

    registered = RegistryProbe(source_entity_uuid=source_uuid)
    assert RegistryProbe.get(registered.uuid) is registered
    assert registered.use_register is True

    transient = RegistryProbe(source_entity_uuid=source_uuid, use_register=False)
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False

    transient.add_to_register()
    assert RegistryProbe.get(transient.uuid) is transient
    assert transient.use_register is True

    transient.remove_from_register()
    assert RegistryProbe.get(transient.uuid) is None
    assert transient.use_register is False


def test_eb_01_002_base_object_lookup_is_typed() -> None:
    """EB-01-002: subclass lookup rejects another registered object type."""
    reset_identity_state()
    source_uuid = uuid4()

    other = OtherRegistryProbe(source_entity_uuid=source_uuid)

    try:
        RegistryProbe.get(other.uuid)
    except ValueError as error:
        assert "is not a RegistryProbe" in str(error)
    else:
        raise AssertionError("RegistryProbe.get() should reject OtherRegistryProbe")


def test_eb_01_003_value_and_block_registries_are_separate() -> None:
    """EB-01-003: values and blocks use registries separate from BaseObject."""
    reset_identity_state()
    source_uuid = uuid4()

    value = BaseValue(source_entity_uuid=source_uuid)
    block = BaseBlock(source_entity_uuid=source_uuid)

    assert BaseValue.get(value.uuid) is value
    assert BaseObject.get(value.uuid) is None

    assert BaseBlock.get(block.uuid) is block
    assert BaseValue.get(block.uuid) is None


def test_eb_01_004_entity_registers_as_block_and_entity() -> None:
    """EB-01-004: Entity creation populates block and entity registries."""
    reset_identity_state()
    entity_uuid = uuid4()
    config = EntityConfig(position=(2, 3))

    entity = Entity.create(
        source_entity_uuid=entity_uuid,
        name="Registry Hero",
        config=config,
    )

    assert Entity.get(entity_uuid) is entity
    assert BaseBlock.get(entity_uuid) is entity
    assert entity in Entity.get_all_entities_at_position((2, 3))

    Entity.update_entity_position(entity, (4, 5))

    assert entity.position == (4, 5)
    assert entity.senses.position == (4, 5)
    assert entity not in Entity.get_all_entities_at_position((2, 3))
    assert entity in Entity.get_all_entities_at_position((4, 5))


def test_eb_01_005_value_subclass_lookup_contracts() -> None:
    """EB-01-005: value subclasses share one registry but differ on misses."""
    reset_identity_state()
    source_uuid = uuid4()

    static_value = StaticValue(source_entity_uuid=source_uuid)
    contextual_value = ContextualValue(source_entity_uuid=source_uuid)
    modifiable_value = ModifiableValue.create(source_entity_uuid=source_uuid)

    assert BaseValue.get(static_value.uuid) is static_value
    assert BaseValue.get(contextual_value.uuid) is contextual_value
    assert BaseValue.get(modifiable_value.uuid) is modifiable_value

    assert StaticValue.get(static_value.uuid) is static_value
    assert ContextualValue.get(contextual_value.uuid) is contextual_value
    assert ModifiableValue.get(modifiable_value.uuid) is modifiable_value

    try:
        StaticValue.get(contextual_value.uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
    else:
        raise AssertionError("StaticValue.get() should reject ContextualValue")

    try:
        ContextualValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ContextualValue" in str(error)
    else:
        raise AssertionError("ContextualValue.get() should reject StaticValue")

    try:
        ModifiableValue.get(static_value.uuid)
    except ValueError as error:
        assert "is not a ModifiableValue" in str(error)
    else:
        raise AssertionError("ModifiableValue.get() should reject StaticValue")

    missing_uuid = uuid4()
    assert BaseValue.get(missing_uuid) is None
    assert ContextualValue.get(missing_uuid) is None
    assert ModifiableValue.get(missing_uuid) is None

    try:
        StaticValue.get(missing_uuid)
    except ValueError as error:
        assert "is not a StaticValue" in str(error)
        assert "NoneType" in str(error)
    else:
        raise AssertionError("StaticValue.get() should raise on missing UUID")


if __name__ == "__main__":
    test_eb_01_001_base_object_registration_lifecycle()
    test_eb_01_002_base_object_lookup_is_typed()
    test_eb_01_003_value_and_block_registries_are_separate()
    test_eb_01_004_entity_registers_as_block_and_entity()
    test_eb_01_005_value_subclass_lookup_contracts()
    print("PASS: engine book registry tests")
