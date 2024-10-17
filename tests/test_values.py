import pytest
from uuid import UUID, uuid4
from typing import Dict, Any, List
from dnd.values import (
    BaseValue, StaticValue, ContextualValue, ModifiableValue,
    NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier,
    ContextualNumericalModifier, ContextualAdvantageModifier, ContextualCriticalModifier, ContextualAutoHitModifier,
    AdvantageStatus, CriticalStatus, AutoHitStatus
)
import threading
from dnd.modifiers import score_normaliziation_method
import json

@pytest.fixture
def source_uuid():
    return uuid4()

@pytest.fixture
def target_uuid():
    return uuid4()

@pytest.fixture
def sample_context():
    return {"test_key": "test_value"}

class TestBaseValue:
    def test_base_value_initialization(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid)
        
        assert isinstance(value.uuid, UUID)
        assert value.source_entity_uuid == source_uuid
        assert value.name == "A Value"
        assert value.source_entity_name is None
        assert value.target_entity_uuid is None
        assert value.target_entity_name is None
        assert value.context is None
        assert callable(value.score_normalizer)
        assert value.generated_from == []

    def test_base_value_with_all_attributes(self, source_uuid, target_uuid, sample_context):
        value = BaseValue(
            name="Test Value",
            source_entity_uuid=source_uuid,
            source_entity_name="Source",
            target_entity_uuid=target_uuid,
            target_entity_name="Target",
            context=sample_context,
            score_normalizer=lambda x: x * 2,
            generated_from=[uuid4()]
        )
        
        assert value.name == "Test Value"
        assert value.source_entity_uuid == source_uuid
        assert value.source_entity_name == "Source"
        assert value.target_entity_uuid == target_uuid
        assert value.target_entity_name == "Target"
        assert value.context == sample_context
        assert value.score_normalizer(5) == 10
        assert len(value.generated_from) == 1

    def test_base_value_registry(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid)
        
        retrieved_value = BaseValue.get(value.uuid)
        assert retrieved_value == value

    def test_base_value_unregister(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid)
        
        BaseValue.unregister(value.uuid)
        assert BaseValue.get(value.uuid) is None

    def test_base_value_register(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid)
        
        BaseValue.unregister(value.uuid)
        BaseValue.register(value)
        
        retrieved_value = BaseValue.get(value.uuid)
        assert retrieved_value == value

    def test_get_non_existent_value(self):
        non_existent_uuid = uuid4()
        assert BaseValue.get(non_existent_uuid) is None

    def test_get_wrong_type_value(self, source_uuid):
        class FakeValue(BaseValue):
            pass

        fake_value = FakeValue(source_entity_uuid=source_uuid)
        BaseValue.register(fake_value)

        # This should not raise an exception
        retrieved_value = BaseValue.get(fake_value.uuid)
        assert retrieved_value is not None
        assert isinstance(retrieved_value, FakeValue)

        # This should raise a ValueError
        with pytest.raises(ValueError):
            StaticValue.get(fake_value.uuid)

        # Clean up
        BaseValue.unregister(fake_value.uuid)

    def test_get_generation_chain(self, source_uuid):
        parent = BaseValue(source_entity_uuid=source_uuid)
        child = BaseValue(source_entity_uuid=source_uuid, generated_from=[parent.uuid])
        grandchild = BaseValue(source_entity_uuid=source_uuid, generated_from=[child.uuid])

        chain = grandchild.get_generation_chain()
        assert len(chain) == 2
        assert chain[0] == child
        assert chain[1] == parent

    def test_validate_source_id(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid)
        value.validate_source_id(source_uuid)
        with pytest.raises(ValueError):
            value.validate_source_id(uuid4())

    def test_validate_target_id(self, source_uuid, target_uuid):
        value = BaseValue(source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)
        value.validate_target_id(target_uuid)
        with pytest.raises(ValueError):
            value.validate_target_id(uuid4())

    def test_custom_score_normalizer(self, source_uuid):
        def custom_normalizer(x: int) -> int:
            return max(0, min(x, 20))  # Clamp between 0 and 20
        
        value = BaseValue(source_entity_uuid=source_uuid, score_normalizer=custom_normalizer)
        assert value.score_normalizer(30) == 20
        assert value.score_normalizer(-5) == 0
        assert value.score_normalizer(15) == 15

    def test_concurrent_registry_access(self, source_uuid):
        counter = 0
        lock = threading.Lock()

        def create_value():
            nonlocal counter
            BaseValue(source_entity_uuid=source_uuid)
            with lock:
                counter += 1

        threads = [threading.Thread(target=create_value) for _ in range(100)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert counter == 100

    def test_field_validation_errors(self, source_uuid):
        with pytest.raises(ValueError):
            BaseValue(source_entity_uuid="not-a-uuid")

    def test_serialization_deserialization(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid, name="Test Value")
        serialized = value.json()
        deserialized = BaseValue.parse_raw(serialized)
        assert deserialized == value

    def test_registry_isolation_across_subclasses(self, source_uuid):
        base_value = BaseValue(source_entity_uuid=source_uuid)
        custom_value = StaticValue(source_entity_uuid=source_uuid)

        assert BaseValue.get(base_value.uuid) == base_value
        assert StaticValue.get(custom_value.uuid) == custom_value
        with pytest.raises(ValueError):
            StaticValue.get(base_value.uuid)

    def test_circular_generation_chain(self, source_uuid):
        value1 = BaseValue(source_entity_uuid=source_uuid)
        value2 = BaseValue(source_entity_uuid=source_uuid, generated_from=[value1.uuid])
        value1.generated_from = [value2.uuid]

        chain = value1.get_generation_chain()
        assert len(chain) == 1
        assert chain[0] == value2

class TestStaticValue:
    def test_static_value_initialization(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        
        assert isinstance(value, BaseValue)
        assert value.value_modifiers == []
        assert value.min_constraints == []
        assert value.max_constraints == []
        assert value.advantage_modifiers == []
        assert value.critical_modifiers == []
        assert value.auto_hit_modifiers == []

    def test_static_value_computed_fields(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]
        value.min_constraints = [NumericalModifier(target_entity_uuid=source_uuid, value=0)]
        value.max_constraints = [NumericalModifier(target_entity_uuid=source_uuid, value=10)]
        value.advantage_modifiers = [AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE)]
        value.critical_modifiers = [CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT)]
        value.auto_hit_modifiers = [AutoHitModifier(target_entity_uuid=source_uuid, value=AutoHitStatus.AUTOHIT)]

        assert value.min == 0
        assert value.max == 10
        assert value.score == 5
        assert value.normalized_score == 5  # Default normalizer
        assert value.advantage_sum == 1
        assert value.advantage == AdvantageStatus.ADVANTAGE
        assert value.critical == CriticalStatus.AUTOCRIT
        assert value.auto_hit == AutoHitStatus.AUTOHIT

    def test_static_value_combine(self, source_uuid):
        value1 = StaticValue(source_entity_uuid=source_uuid, name="Value1")
        value1.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]
        
        value2 = StaticValue(source_entity_uuid=source_uuid, name="Value2")
        value2.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=3)]

        combined = value1.combine_values([value2])
        assert combined.name == "Value1_Value2"
        assert len(combined.value_modifiers) == 2
        assert combined.score == 8

    def test_static_value_combine_with_custom_naming(self, source_uuid):
        value1 = StaticValue(source_entity_uuid=source_uuid, name="Value1")
        value2 = StaticValue(source_entity_uuid=source_uuid, name="Value2")
        
        custom_naming = lambda names: "+".join(names)
        combined = value1.combine_values([value2], naming_callable=custom_naming)
        assert combined.name == "Value1+Value2"

    def test_static_value_with_multiple_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.value_modifiers = [
            NumericalModifier(target_entity_uuid=source_uuid, value=5),
            NumericalModifier(target_entity_uuid=source_uuid, value=-2),
            NumericalModifier(target_entity_uuid=source_uuid, value=3)
        ]
        assert value.score == 6

    def test_static_value_with_conflicting_advantage(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.advantage_modifiers = [
            AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE),
            AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.DISADVANTAGE)
        ]
        assert value.advantage == AdvantageStatus.NONE

    def test_static_value_with_multiple_critical_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.critical_modifiers = [
            CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT),
            CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.NOCRIT)
        ]
        assert value.critical == CriticalStatus.NOCRIT

    def test_min_max_constraints_conflict(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.min_constraints = [NumericalModifier(target_entity_uuid=source_uuid, value=10)]
        value.max_constraints = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]
        value.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=7)]

        assert value.score == 10  # Should respect the min constraint

    def test_empty_modifiers_and_constraints(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        assert value.score == 0
        assert value.min is None
        assert value.max is None
        assert value.advantage == AdvantageStatus.NONE
        assert value.critical == CriticalStatus.NONE
        assert value.auto_hit == AutoHitStatus.NONE

    def test_modifiers_with_invalid_target_uuid(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        invalid_modifier = NumericalModifier(target_entity_uuid=uuid4(), value=5)
        with pytest.raises(ValueError):
            value = value.model_copy(update={"value_modifiers": [invalid_modifier]})

    def test_extreme_modifier_values(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        value.value_modifiers = [
            NumericalModifier(target_entity_uuid=source_uuid, value=2**63 - 1),
            NumericalModifier(target_entity_uuid=source_uuid, value=-(2**63))
        ]
        assert value.score == -1

class TestContextualValue:
    def test_contextual_value_initialization(self, source_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        
        assert isinstance(value, BaseValue)
        assert isinstance(value.value_modifiers, dict)
        assert isinstance(value.min_constraints, dict)
        assert isinstance(value.max_constraints, dict)
        assert isinstance(value.advantage_modifiers, dict)
        assert isinstance(value.critical_modifiers, dict)
        assert isinstance(value.auto_hit_modifiers, dict)

    def test_contextual_value_computed_fields(self, source_uuid, target_uuid, sample_context):
        def context_aware_numerical(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)

        def context_aware_advantage(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)

        def context_aware_critical(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=target_uuid, value=CriticalStatus.AUTOCRIT)

        def context_aware_auto_hit(source_uuid, target_uuid, context):
            return AutoHitModifier(target_entity_uuid=target_uuid, value=AutoHitStatus.AUTOHIT)

        def min_constraint(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=0)

        def max_constraint(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=10)

        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)

        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=context_aware_numerical))
        value.add_min_constraint(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=min_constraint))
        value.add_max_constraint(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=max_constraint))
        value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=context_aware_advantage))
        value.add_critical_modifier(ContextualCriticalModifier(target_entity_uuid=target_uuid, callable=context_aware_critical))
        value.add_auto_hit_modifier(ContextualAutoHitModifier(target_entity_uuid=target_uuid, callable=context_aware_auto_hit))

        assert value.min == 0
        assert value.max == 10
        assert value.score == 5
        assert value.normalized_score == 5  # Default normalizer
        assert value.advantage_sum == 1
        assert value.advantage == AdvantageStatus.ADVANTAGE
        assert value.critical == CriticalStatus.AUTOCRIT
        assert value.auto_hit == AutoHitStatus.AUTOHIT

    def test_contextual_value_add_remove_modifiers(self, source_uuid, target_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)

        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)

        modifier_uuid = value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable))
        assert len(value.value_modifiers) == 1

        value.remove_value_modifier(modifier_uuid)
        assert len(value.value_modifiers) == 0

    def test_contextual_value_combine(self, source_uuid):
        value1 = ContextualValue(source_entity_uuid=source_uuid, name="Value1")
        value2 = ContextualValue(source_entity_uuid=source_uuid, name="Value2")

        combined = value1.combine_values([value2])
        assert combined.name == "Value1_Value2"
        assert isinstance(combined, ContextualValue)

    def test_contextual_value_changing_context(self, source_uuid, target_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)

        def context_aware_numerical(source_uuid, target_uuid, context):
            if context is None:
                return NumericalModifier(target_entity_uuid=target_uuid, value=0)
            return NumericalModifier(target_entity_uuid=target_uuid, value=context.get('modifier', 0))

        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=context_aware_numerical))

        value.set_context({'modifier': 5})
        assert value.score == 5

        value.set_context({'modifier': 10})
        assert value.score == 10

        value.clear_context()
        assert value.score == 0

    def test_contextual_value_remove_all_modifiers(self, source_uuid, target_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        
        def dummy_numerical_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        def dummy_advantage_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        
        modifier1 = value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_numerical_callable))
        modifier2 = value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=dummy_advantage_callable))
        
        value.remove_modifier(modifier1)
        value.remove_modifier(modifier2)
        
        assert len(value.value_modifiers) == 0
        assert len(value.advantage_modifiers) == 0

    def test_callable_exception_handling(self, source_uuid, target_uuid):
        def faulty_callable(source_uuid, target_uuid, context):
            raise ValueError("Intentional error")

        value = ContextualValue(source_entity_uuid=source_uuid)
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=faulty_callable))

        with pytest.raises(ValueError):
            _ = value.score

    def test_duplicate_modifier_uuids(self, source_uuid, target_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)

        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        value.add_value_modifier(modifier)

        with pytest.raises(ValueError):
            value.add_value_modifier(modifier)  # Attempting to add the same modifier again

    def test_remove_non_existent_modifier(self, source_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        non_existent_uuid = uuid4()
        value.remove_modifier(non_existent_uuid)  # Should not raise an exception

    def test_callable_returning_invalid_type(self, source_uuid, target_uuid):
        def invalid_callable(source_uuid, target_uuid, context):
            return "Not a modifier"

        value = ContextualValue(source_entity_uuid=source_uuid)
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=invalid_callable)) # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Callable returned unexpected type"):
            _ = value.score

class TestModifiableValue:
    def test_modifiable_value_initialization(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        
        assert isinstance(value, BaseValue)
        assert isinstance(value.self_static, StaticValue)
        assert isinstance(value.to_target_static, StaticValue)
        assert isinstance(value.self_contextual, ContextualValue)
        assert isinstance(value.to_target_contextual, ContextualValue)
        assert value.from_target_contextual is None
        assert value.from_target_static is None

    def test_modifiable_value_computed_fields(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)

        value.self_static.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]
        value.to_target_static.value_modifiers = [NumericalModifier(target_entity_uuid=target_uuid, value=3)]

        def context_aware_numerical(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=2)

        value.self_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=context_aware_numerical))
        value.to_target_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=context_aware_numerical))

        assert value.score == 12  # 5 + 3 + 2 + 2
        assert value.normalized_score == 12  # Default normalizer

    def test_modifiable_value_set_from_target(self, source_uuid, target_uuid):
        # Create the main value with source_uuid
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        
        # Create the target value with target_uuid
        target_value = ModifiableValue.create(source_entity_uuid=target_uuid)

        # Set the target entity for the main value
        value.set_target_entity(target_uuid)

        # Set up the target value's modifiers
        target_value.to_target_static.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]

        def context_aware_numerical(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=3)

        target_value.to_target_contextual.add_value_modifier(
            ContextualNumericalModifier(
                target_entity_uuid=source_uuid,
                callable=context_aware_numerical
            )
        )

        # Set the from_target values
        value.set_from_target(target_value)

        # Assertions
        assert value.from_target_static is not None
        assert value.from_target_contextual is not None
        assert value.from_target_static.score == 5
        assert value.from_target_contextual.score == 3

        # Additional checks to ensure correct setup
        assert value.target_entity_uuid == target_uuid
        assert target_value.source_entity_uuid == target_uuid
        assert value.from_target_static.source_entity_uuid == target_uuid
        assert value.from_target_contextual.source_entity_uuid == target_uuid

    def test_modifiable_value_combine(self, source_uuid):
        value1 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value1.self_static.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=5)]
        
        value2 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value2.self_static.value_modifiers = [NumericalModifier(target_entity_uuid=source_uuid, value=3)]

        combined = value1.combine_values([value2])
        assert isinstance(combined, ModifiableValue)
        assert combined.self_static.score == 8

    def test_modifiable_value_complex_scenario(self, source_uuid, target_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        
        # Add modifiers to all components
        value.self_static.value_modifiers.append(NumericalModifier(target_entity_uuid=source_uuid, value=1))
        value.to_target_static.value_modifiers.append(NumericalModifier(target_entity_uuid=target_uuid, value=2))
        
        def context_aware_self(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=3)
        
        def context_aware_target(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=4)
        
        value.self_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=context_aware_self))
        value.to_target_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=context_aware_target))
        
        # Set from_target components
        from_target_static = StaticValue(source_entity_uuid=target_uuid)
        from_target_static.value_modifiers.append(NumericalModifier(target_entity_uuid=source_uuid, value=5))
        value.set_from_target_static(from_target_static)
        
        from_target_contextual = ContextualValue(source_entity_uuid=target_uuid)
        def context_aware_from_target(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=6)
        from_target_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=context_aware_from_target))
        value.set_from_target_contextual(from_target_contextual)
        
        # Assert the total score
        assert value.score == 21  # 1 + 2 + 3 + 4 + 5 + 6

    def test_modifiable_value_advantage_interaction(self, source_uuid, target_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        
        value.self_static.advantage_modifiers.append(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE))
        value.to_target_static.advantage_modifiers.append(AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.DISADVANTAGE))
        
        def context_aware_advantage(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        
        value.self_contextual.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=source_uuid, callable=context_aware_advantage))
        
        assert value.advantage == AdvantageStatus.ADVANTAGE  # 2 advantages vs 1 disadvantage

    def test_modifiable_value_with_none_components(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.from_target_contextual = None
        value.from_target_static = None

        assert value.score == 0  # Should not raise an exception

    def test_modifiable_value_multiple_targets(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        target1 = uuid4()
        target2 = uuid4()

        value.set_target_entity(target1)
        assert value.target_entity_uuid == target1

        value.set_target_entity(target2)
        assert value.target_entity_uuid == target2

    def test_modifiable_value_invalid_uuid_in_set_methods(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)

        with pytest.raises(ValueError):
            value.set_target_entity("not-a-uuid") # type: ignore[arg-type]

    def test_modifiable_value_conflicting_data(self, source_uuid):
        value1 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value2 = ModifiableValue.create(source_entity_uuid=uuid4())  # Different source UUID

        with pytest.raises(ValueError):
            value1.combine_values([value2])

    def test_modifiable_value_edge_case_computations(self, source_uuid, target_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)

        value.self_static.value_modifiers.append(NumericalModifier(target_entity_uuid=source_uuid, value=10))
        value.to_target_static.value_modifiers.append(NumericalModifier(target_entity_uuid=target_uuid, value=-10))

        assert value.score == 0  # Should cancel out

class TestEdgeCasesAndErrorHandling:
    def test_missing_required_field(self):
        with pytest.raises(ValueError):
            BaseValue()  # Missing required source_entity_uuid

    def test_invalid_enum_value(self, source_uuid):
        with pytest.raises(ValueError):
            StaticValue(source_entity_uuid=source_uuid, advantage_modifiers=[
                AdvantageModifier(target_entity_uuid=source_uuid, value="InvalidValue") # type: ignore[arg-type]
            ])

    def test_contextual_value_invalid_callable(self, source_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        with pytest.raises(ValueError):
            value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable="not_a_callable")) # type: ignore[arg-type]

    def test_modifiable_value_set_from_target_mismatch(self, source_uuid, target_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        wrong_target_value = ModifiableValue.create(source_entity_uuid=uuid4())  # Different from target_uuid

        with pytest.raises(ValueError):
            value.set_from_target(wrong_target_value)

    def test_combine_values_with_different_source(self, source_uuid):
        value1 = StaticValue(source_entity_uuid=source_uuid)
        value2 = StaticValue(source_entity_uuid=uuid4())  # Different source_entity_uuid

        with pytest.raises(ValueError):
            value1.combine_values([value2])

    def test_contextual_value_execute_callable_without_setup(self, source_uuid, target_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)

        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        value.add_value_modifier(modifier)

        # Trying to calculate score without setting up target and context
        with pytest.raises(ValueError):
            _ = value.score

    def test_modifiable_value_clear_target_and_context(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)

        value.clear_target_entity()
        assert value.target_entity_uuid is None
        assert value.self_contextual.target_entity_uuid is None
        assert value.to_target_contextual.target_entity_uuid is None

        value.clear_context()
        assert value.context is None
        assert value.self_contextual.context is None
        assert value.to_target_contextual.context is None

    def test_invalid_score_normalizer(self, source_uuid):
        with pytest.raises(ValueError):
            BaseValue(source_entity_uuid=source_uuid, score_normalizer="not_a_callable")

    def test_modifiable_value_set_invalid_from_target(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        invalid_target = BaseValue(source_entity_uuid=uuid4())
        
        with pytest.raises(AttributeError):
            value.set_from_target(invalid_target) # type: ignore[arg-type]  

    def test_invalid_enum_value_in_callable(self, source_uuid, target_uuid):
        def invalid_enum_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value="InvalidValue") # type: ignore[arg-type]

        value = ContextualValue(source_entity_uuid=source_uuid)
        value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=invalid_enum_callable))

        with pytest.raises(ValueError):
            _ = value.advantage

    def test_deep_copy_independence(self, source_uuid):
        import copy

        original = StaticValue(source_entity_uuid=source_uuid)
        original.value_modifiers.append(NumericalModifier(target_entity_uuid=source_uuid, value=5))

        copied = copy.deepcopy(original)
        copied.value_modifiers[0].value = 10

        assert original.score == 5
        assert copied.score == 10

if __name__ == "__main__":
    pytest.main([__file__])