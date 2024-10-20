import pytest
from uuid import UUID, uuid4
from dnd.modifiers import (
    BaseModifier, NumericalModifier, AdvantageModifier, CriticalModifier, AutoHitModifier,
    ContextualModifier, ContextualAdvantageModifier, ContextualCriticalModifier,
    ContextualAutoHitModifier, ContextualNumericalModifier,
    AdvantageStatus, CriticalStatus, AutoHitStatus,
    SizeModifier, DamageTypeModifier, ContextualSizeModifier, ContextualDamageTypeModifier,
    Size, DamageType
)
import threading
from pydantic import ValidationError

@pytest.fixture
def target_uuid():
    return uuid4()

@pytest.fixture
def source_uuid():
    return uuid4()

class TestBaseModifier:
    def test_base_modifier_initialization(self, target_uuid):
        modifier = BaseModifier(target_entity_uuid=target_uuid)
        
        assert isinstance(modifier.uuid, UUID)
        assert modifier.target_entity_uuid == target_uuid
        assert modifier.name is None
        assert modifier.source_entity_uuid is None
        assert modifier.source_entity_name is None
        assert modifier.target_entity_name is None

    def test_base_modifier_with_all_attributes(self, target_uuid, source_uuid):
        modifier = BaseModifier(
            name="Test Modifier",
            target_entity_uuid=target_uuid,
            source_entity_uuid=source_uuid,
            source_entity_name="Source",
            target_entity_name="Target"
        )
        
        assert modifier.name == "Test Modifier"
        assert modifier.target_entity_uuid == target_uuid
        assert modifier.source_entity_uuid == source_uuid
        assert modifier.source_entity_name == "Source"
        assert modifier.target_entity_name == "Target"

    def test_base_modifier_registry(self, target_uuid):
        modifier = BaseModifier(target_entity_uuid=target_uuid)
        
        retrieved_modifier = BaseModifier.get(modifier.uuid)
        assert retrieved_modifier == modifier

    def test_base_modifier_unregister(self, target_uuid):
        modifier = BaseModifier(target_entity_uuid=target_uuid)
        
        BaseModifier.unregister(modifier.uuid)
        assert BaseModifier.get(modifier.uuid) is None

    def test_base_modifier_register(self, target_uuid):
        modifier = BaseModifier(target_entity_uuid=target_uuid)
        
        BaseModifier.unregister(modifier.uuid)
        BaseModifier.register(modifier)
        
        retrieved_modifier = BaseModifier.get(modifier.uuid)
        assert retrieved_modifier == modifier

    def test_get_non_existent_modifier(self):
        non_existent_uuid = uuid4()
        assert BaseModifier.get(non_existent_uuid) is None

    def test_get_wrong_type_modifier(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass

        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)

        # This should not raise an exception
        retrieved_modifier = BaseModifier.get(fake_modifier.uuid)
        assert retrieved_modifier is not None
        assert isinstance(retrieved_modifier, FakeModifier)

        # This should raise a ValueError
        with pytest.raises(ValueError):
            NumericalModifier.get(fake_modifier.uuid)

        # Clean up
        BaseModifier.unregister(fake_modifier.uuid)

class TestNumericalModifier:
    def test_numerical_modifier_initialization(self, target_uuid):
        modifier = NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == 5

    def test_numerical_modifier_get(self, target_uuid):
        modifier = NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        retrieved_modifier = NumericalModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier
        assert retrieved_modifier.value == 5

class TestAdvantageModifier:
    def test_advantage_modifier_initialization(self, target_uuid):
        modifier = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == AdvantageStatus.ADVANTAGE

    def test_advantage_modifier_numerical_value(self, target_uuid):
        advantage_modifier = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        disadvantage_modifier = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.DISADVANTAGE)
        none_modifier = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.NONE)
        
        assert advantage_modifier.numerical_value == 1
        assert disadvantage_modifier.numerical_value == -1
        assert none_modifier.numerical_value == 0

    def test_advantage_modifier_get(self, target_uuid):
        modifier = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        retrieved_modifier = AdvantageModifier.get(modifier.uuid)
        assert retrieved_modifier == modifier

    def test_advantage_modifier_get_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass
        
        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)
        
        with pytest.raises(ValueError):
            AdvantageModifier.get(fake_modifier.uuid)

class TestCriticalModifier:
    def test_critical_modifier_initialization(self, target_uuid):
        modifier = CriticalModifier(target_entity_uuid=target_uuid, value=CriticalStatus.AUTOCRIT)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == CriticalStatus.AUTOCRIT

    def test_critical_modifier_get(self, target_uuid):
        modifier = CriticalModifier(target_entity_uuid=target_uuid, value=CriticalStatus.AUTOCRIT)
        retrieved_modifier = CriticalModifier.get(modifier.uuid)
        assert retrieved_modifier == modifier

    def test_critical_modifier_get_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass
        
        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)
        
        with pytest.raises(ValueError):
            CriticalModifier.get(fake_modifier.uuid)

class TestAutoHitModifier:
    def test_auto_hit_modifier_initialization(self, target_uuid):
        modifier = AutoHitModifier(target_entity_uuid=target_uuid, value=AutoHitStatus.AUTOHIT)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == AutoHitStatus.AUTOHIT

    def test_auto_hit_modifier_get(self, target_uuid):
        modifier = AutoHitModifier(target_entity_uuid=target_uuid, value=AutoHitStatus.AUTOHIT)
        retrieved_modifier = AutoHitModifier.get(modifier.uuid)
        assert retrieved_modifier == modifier

    def test_auto_hit_modifier_get_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass
        
        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)
        
        with pytest.raises(ValueError):
            AutoHitModifier.get(fake_modifier.uuid)

class TestContextualModifier:
    def test_contextual_modifier_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, BaseModifier)
        assert callable(modifier.callable)

    def test_contextual_modifier_setup_callable_arguments(self, target_uuid, source_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        # The source_entity_uuid should match the target_entity_uuid of the modifier
        modifier.setup_callable_arguments(target_uuid, source_uuid, {"test": "context"})
        
        assert modifier.callable_arguments == (target_uuid, source_uuid, {"test": "context"})

    def test_contextual_modifier_validate_callable_source_iid(self, target_uuid, source_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        # This should not raise an exception
        modifier.setup_callable_arguments(target_uuid, source_uuid, {"test": "context"})
        
        # This should raise a ValueError
        with pytest.raises(ValueError):
            modifier.setup_callable_arguments(source_uuid, target_uuid, {"test": "context"})

    def test_callable_returns_wrong_type(self, target_uuid):
        def wrong_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=wrong_callable) # type: ignore[arg-type] 
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        with pytest.raises(ValueError):
            modifier.execute_callable()

    def test_invalid_callable_arguments(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        with pytest.raises(ValueError):
            # Intentionally passing invalid UUID for testing
            modifier.setup_callable_arguments("not_a_uuid", target_uuid, {})  # type: ignore[arg-type]

    def test_callable_raises_exception(self, target_uuid):
        def faulty_callable(source_uuid, target_uuid, context):
            raise RuntimeError("Intentional Error")
        
        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=faulty_callable)
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        with pytest.raises(RuntimeError):
           
            modifier.callable(*modifier.callable_arguments)  # type: ignore[operator]

    def test_callable_with_none_context(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            assert context is None
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        modifier.setup_callable_arguments(target_uuid, target_uuid)
        
        result = modifier.callable(*modifier.callable_arguments) # type: ignore[operator]
        assert isinstance(result, NumericalModifier)

class TestContextualAdvantageModifier:
    def test_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        
        modifier = ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_get_method(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.ADVANTAGE)
        
        modifier = ContextualAdvantageModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualAdvantageModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

    def test_get_method_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass

        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)

        with pytest.raises(ValueError):
            ContextualAdvantageModifier.get(fake_modifier.uuid)

class TestContextualCriticalModifier:
    def test_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=target_uuid, value=CriticalStatus.AUTOCRIT)
        
        modifier = ContextualCriticalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_get_method(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=target_uuid, value=CriticalStatus.AUTOCRIT)
        
        modifier = ContextualCriticalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualCriticalModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

class TestContextualAutoHitModifier:
    def test_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return AutoHitModifier(target_entity_uuid=target_uuid, value=AutoHitStatus.AUTOHIT)
        
        modifier = ContextualAutoHitModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_get_method(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return AutoHitModifier(target_entity_uuid=target_uuid, value=AutoHitStatus.AUTOHIT)
        
        modifier = ContextualAutoHitModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualAutoHitModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

class TestContextualNumericalModifier:
    def test_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_get_method(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualNumericalModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualNumericalModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

class TestSizeModifier:
    def test_size_modifier_initialization(self, target_uuid):
        modifier = SizeModifier(target_entity_uuid=target_uuid, value=Size.LARGE)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == Size.LARGE

    def test_size_modifier_get(self, target_uuid):
        modifier = SizeModifier(target_entity_uuid=target_uuid, value=Size.SMALL)
        
        retrieved_modifier = SizeModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier
        assert retrieved_modifier.value == Size.SMALL

    def test_size_modifier_get_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass
        
        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)
        
        with pytest.raises(ValueError):
            SizeModifier.get(fake_modifier.uuid)

class TestDamageTypeModifier:
    def test_damage_type_modifier_initialization(self, target_uuid):
        modifier = DamageTypeModifier(target_entity_uuid=target_uuid, value=DamageType.FIRE)
        
        assert isinstance(modifier, BaseModifier)
        assert modifier.value == DamageType.FIRE

    def test_damage_type_modifier_get(self, target_uuid):
        modifier = DamageTypeModifier(target_entity_uuid=target_uuid, value=DamageType.COLD)
        
        retrieved_modifier = DamageTypeModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier
        assert retrieved_modifier.value == DamageType.COLD

    def test_damage_type_modifier_get_wrong_type(self, target_uuid):
        class FakeModifier(BaseModifier):
            pass
        
        fake_modifier = FakeModifier(target_entity_uuid=target_uuid)
        BaseModifier.register(fake_modifier)
        
        with pytest.raises(ValueError):
            DamageTypeModifier.get(fake_modifier.uuid)

class TestContextualSizeModifier:
    def test_contextual_size_modifier_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=target_uuid, value=Size.HUGE)
        
        modifier = ContextualSizeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_contextual_size_modifier_get(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=target_uuid, value=Size.HUGE)
        
        modifier = ContextualSizeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualSizeModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

    def test_contextual_size_modifier_execute_callable(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=target_uuid, value=Size.HUGE)
        
        modifier = ContextualSizeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        result = modifier.execute_callable()
        assert isinstance(result, SizeModifier)
        assert result.value == Size.HUGE

    def test_contextual_size_modifier_wrong_return_type(self, target_uuid):
        def wrong_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualSizeModifier(target_entity_uuid=target_uuid, callable=wrong_callable) # type: ignore[arg-type]
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        with pytest.raises(ValueError, match="Callable returned unexpected type"):
            modifier.execute_callable()

    def test_contextual_size_modifier_wrong_callable_type(self, target_uuid):
        with pytest.raises(ValidationError):
            ContextualSizeModifier(target_entity_uuid=target_uuid, callable="not_a_callable") # type: ignore[arg-type]

class TestContextualDamageTypeModifier:
    def test_contextual_damage_type_modifier_initialization(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=target_uuid, value=DamageType.LIGHTNING)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        assert isinstance(modifier, ContextualModifier)
        assert callable(modifier.callable)

    def test_contextual_damage_type_modifier_get(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=target_uuid, value=DamageType.LIGHTNING)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        retrieved_modifier = ContextualDamageTypeModifier.get(modifier.uuid)
        assert retrieved_modifier is not None
        assert retrieved_modifier == modifier

    def test_contextual_damage_type_modifier_execute_callable(self, target_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=target_uuid, value=DamageType.LIGHTNING)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        result = modifier.execute_callable()
        assert isinstance(result, DamageTypeModifier)
        assert result.value == DamageType.LIGHTNING

    def test_contextual_damage_type_modifier_wrong_return_type(self, target_uuid):
        def wrong_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable=wrong_callable) # type: ignore[arg-type]
        modifier.setup_callable_arguments(target_uuid, target_uuid, {})
        
        with pytest.raises(ValueError, match="Callable returned unexpected type"):
            modifier.execute_callable()

    def test_contextual_damage_type_modifier_wrong_callable_type(self, target_uuid):
        with pytest.raises(ValidationError):
            ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable="not_a_callable") # type: ignore[arg-type]

class TestEdgeCasesAndErrorHandling:
    def test_missing_required_field(self):
        with pytest.raises(ValueError):
            BaseModifier()  # Missing required target_entity_uuid

    def test_invalid_enum_value(self, target_uuid):
        with pytest.raises(ValueError):
            # Intentionally passing invalid enum value for testing
            
            AdvantageModifier(target_entity_uuid=target_uuid, value="InvalidValue") # type: ignore[arg-type]

    def test_contextual_modifier_invalid_callable(self, target_uuid):
        with pytest.raises(ValueError):
            # Intentionally passing invalid callable for testing
            
            ContextualModifier(target_entity_uuid=target_uuid, callable="not_a_callable") # type: ignore[arg-type]

    def test_contextual_modifier_invalid_setup(self, target_uuid, source_uuid):
        def dummy_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=target_uuid, value=5)
        
        modifier = ContextualModifier(target_entity_uuid=target_uuid, callable=dummy_callable)
        
        # Attempt to set up with mismatched UUIDs
        with pytest.raises(ValueError):
            modifier.setup_callable_arguments(source_uuid, target_uuid, {})

    def test_multiple_modifiers_on_same_target(self, target_uuid):
        modifier1 = NumericalModifier(target_entity_uuid=target_uuid, value=5)
        modifier2 = AdvantageModifier(target_entity_uuid=target_uuid, value=AdvantageStatus.DISADVANTAGE)
        
        # Assuming you have a method to aggregate modifiers
        modifiers = [modifier1, modifier2]
        # Implement logic to combine or apply modifiers and assert the expected outcome
        # This test is a placeholder and needs to be implemented based on your specific logic

    def test_unregister_non_existent_uuid(self):
        non_existent_uuid = uuid4()
        # Should not raise an exception
        BaseModifier.unregister(non_existent_uuid)

    def test_concurrent_access_to_registry(self, target_uuid):
        BaseModifier._registry.clear()  # Clear the registry before the test
        def register_modifier():
            modifier = BaseModifier(target_entity_uuid=target_uuid)
        
        threads = [threading.Thread(target=register_modifier) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        assert len(BaseModifier._registry) == 10
        BaseModifier._registry.clear()  # Clear the registry after the test

    def test_optional_fields_accept_none(self, target_uuid):
        modifier = BaseModifier(
            name=None,
            target_entity_uuid=target_uuid,
            source_entity_uuid=None,
            source_entity_name=None,
            target_entity_name=None
        )
        assert modifier.name is None
        assert modifier.source_entity_uuid is None

    def test_numerical_modifier_edge_values(self, target_uuid):
        modifier_zero = NumericalModifier(target_entity_uuid=target_uuid, value=0)
        modifier_negative = NumericalModifier(target_entity_uuid=target_uuid, value=-10)
        modifier_large = NumericalModifier(target_entity_uuid=target_uuid, value=1_000_000)
        
        assert modifier_zero.value == 0
        assert modifier_negative.value == -10
        assert modifier_large.value == 1_000_000

    def test_behavior_after_unregistration(self, target_uuid):
        modifier = BaseModifier(target_entity_uuid=target_uuid)
        BaseModifier.unregister(modifier.uuid)
        assert BaseModifier.get(modifier.uuid) is None

    def test_invalid_field_types(self):
        with pytest.raises(ValueError):  # or TypeError, depending on your validation
            BaseModifier(target_entity_uuid="not_a_uuid")

    def test_model_validation_for_fields(self, target_uuid):
        with pytest.raises(ValueError):
            BaseModifier(target_entity_uuid=target_uuid, source_entity_uuid="invalid_uuid")

    def test_contextual_modifier_with_none_callable(self, target_uuid):
        with pytest.raises(ValueError):
            # Intentionally passing None as callable for testing
            
            ContextualModifier(target_entity_uuid=target_uuid, callable=None) # type: ignore[arg-type]

    def test_size_modifier_invalid_value(self, target_uuid):
        with pytest.raises(ValueError):
            SizeModifier(target_entity_uuid=target_uuid, value="InvalidSize") # type: ignore[arg-type]

    def test_damage_type_modifier_invalid_value(self, target_uuid):
        with pytest.raises(ValueError):
            DamageTypeModifier(target_entity_uuid=target_uuid, value="InvalidDamageType") # type: ignore[arg-type]

    def test_contextual_size_modifier_invalid_callable(self, target_uuid):
        with pytest.raises(ValueError):
            ContextualSizeModifier(target_entity_uuid=target_uuid, callable="not_a_callable") # type: ignore[arg-type]

    def test_contextual_damage_type_modifier_invalid_callable(self, target_uuid):
        with pytest.raises(ValueError): 
            ContextualDamageTypeModifier(target_entity_uuid=target_uuid, callable="not_a_callable") # type: ignore[arg-type]

    def test_size_modifier_edge_values(self, target_uuid):
        for size in Size:
            modifier = SizeModifier(target_entity_uuid=target_uuid, value=size)
            assert modifier.value == size

    def test_damage_type_modifier_edge_values(self, target_uuid):
        for damage_type in DamageType:
            modifier = DamageTypeModifier(target_entity_uuid=target_uuid, value=damage_type)
            assert modifier.value == damage_type

if __name__ == "__main__":
    pytest.main([__file__])
