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
from dnd.modifiers import Size, DamageType, SizeModifier, DamageTypeModifier, ResistanceModifier, ResistanceStatus, ContextualResistanceModifier, ContextualDamageTypeModifier, ContextualSizeModifier

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
            BaseValue(source_entity_uuid="not-a-uuid") #type: ignore

    def test_serialization_deserialization(self, source_uuid):
        value = BaseValue(source_entity_uuid=source_uuid, name="Test Value")
        serialized = value.model_dump_json()
        deserialized = BaseValue.model_validate_json(serialized)
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
        assert value.value_modifiers == {}
        assert value.min_constraints == {}
        assert value.max_constraints == {}
        assert value.advantage_modifiers == {}
        assert value.critical_modifiers == {}
        assert value.auto_hit_modifiers == {}

    def test_static_value_computed_fields(self, source_uuid):
        modifier_source_uuid = uuid4()
        value = StaticValue(source_entity_uuid=source_uuid)
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.add_min_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=0, source_entity_uuid=modifier_source_uuid))
        value.add_max_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid))
        value.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid))
        value.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid))
        value.add_auto_hit_modifier(AutoHitModifier(target_entity_uuid=source_uuid, value=AutoHitStatus.AUTOHIT, source_entity_uuid=modifier_source_uuid))

        assert value.min == 0
        assert value.max == 10
        assert value.score == 5
        assert value.normalized_score == 5  # Default normalizer
        assert value.advantage_sum == 1
        assert value.advantage == AdvantageStatus.ADVANTAGE
        assert value.critical == CriticalStatus.AUTOCRIT
        assert value.auto_hit == AutoHitStatus.AUTOHIT

    def test_static_value_combine(self, source_uuid):
        modifier_source_uuid = uuid4()
        value1 = StaticValue(source_entity_uuid=source_uuid, name="Value1")
        value1.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        
        value2 = StaticValue(source_entity_uuid=source_uuid, name="Value2")
        value2.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid))

        combined = value1.combine_values([value2])
        assert combined.name == "Value1_Value2"
        assert len(combined.value_modifiers) == 2
        assert combined.score == 8

    def test_static_value_with_multiple_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=-2, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid))
        assert value.score == 6

    def test_static_value_with_conflicting_advantage(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid))
        value.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=modifier_source_uuid))
        assert value.advantage == AdvantageStatus.NONE

    def test_static_value_with_multiple_critical_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid))
        value.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.NOCRIT, source_entity_uuid=modifier_source_uuid))
        assert value.critical == CriticalStatus.NOCRIT

    def test_min_max_constraints_conflict(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_min_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid))
        value.add_max_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=7, source_entity_uuid=modifier_source_uuid))

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
        modifier_source_uuid = uuid4()
        invalid_modifier = NumericalModifier(target_entity_uuid=uuid4(), value=5, source_entity_uuid=modifier_source_uuid)
        with pytest.raises(ValueError):
            StaticValue.model_validate(value.model_copy(update={"value_modifiers": {invalid_modifier.uuid: invalid_modifier}}))

    def test_extreme_modifier_values(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=2**63 - 1, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=-(2**63), source_entity_uuid=modifier_source_uuid))
        assert value.score == -1

    def test_static_value_size_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.HUGE, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.HUGE  # Default is largest size

    def test_static_value_size_modifiers_smallest_priority(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid, largest_size_priority=False)
        modifier_source_uuid = uuid4()
        value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.TINY, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.TINY

    def test_static_value_damage_type_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert set(value.damage_types) == {DamageType.FIRE, DamageType.COLD}

    def test_static_value_damage_type_random_selection(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        # Run multiple times to ensure randomness
        damage_types = set()
        for _ in range(100):
            damage_types.add(value.damage_type)
        
        assert damage_types == {DamageType.FIRE}  # FIRE should always be selected as it's the most common

    def test_static_value_resistance_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.IMMUNITY

    def test_static_value_resistance_sum(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance_sum[DamageType.FIRE] == 3  # RESISTANCE (1) + IMMUNITY (2)

    def test_static_value_resistance_calculation(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.VULNERABILITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.LIGHTNING, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.VULNERABILITY
        assert value.resistance[DamageType.LIGHTNING] == ResistanceStatus.IMMUNITY
        assert value.resistance[DamageType.ACID] == ResistanceStatus.NONE

    def test_static_value_remove_size_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.remove_size_modifier(modifier_uuid)
        
        assert value.size == Size.MEDIUM  # Default size

    def test_static_value_remove_damage_type_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.remove_damage_type_modifier(modifier_uuid)
        
        assert len(value.damage_types) == 0

    def test_static_value_remove_resistance_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.remove_resistance_modifier(modifier_uuid)
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.NONE

    def test_static_value_get_all_modifier_uuids(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        size_uuid = value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        damage_uuid = value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        resistance_uuid = value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        all_uuids = value.get_all_modifier_uuids()
        assert size_uuid in all_uuids
        assert damage_uuid in all_uuids
        assert resistance_uuid in all_uuids

    def test_static_value_remove_all_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        value.remove_all_modifiers()
        
        assert value.size == Size.MEDIUM
        assert len(value.damage_types) == 0
        assert all(status == ResistanceStatus.NONE for status in value.resistance.values())

    def test_static_value_combine_with_new_modifiers(self, source_uuid):
        value1 = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value1.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        
        value2 = StaticValue(source_entity_uuid=source_uuid)
        value2.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        combined = value1.combine_values([value2])
        
        assert combined.size == Size.LARGE
        assert DamageType.FIRE in combined.damage_types

class TestStaticValueNewFeatures:
    def test_size_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier = SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        uuid = value.add_size_modifier(modifier)
        
        assert value.size == Size.LARGE
        
        value.remove_size_modifier(uuid)
        assert value.size == Size.MEDIUM

    def test_damage_type_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier1 = DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        modifier2 = DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        value.add_damage_type_modifier(modifier1)
        value.add_damage_type_modifier(modifier2)
        
        assert set(value.damage_types) == {DamageType.FIRE, DamageType.COLD}
        assert value.damage_type in {DamageType.FIRE, DamageType.COLD}

    def test_resistance_modifiers(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        modifier1 = ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        modifier2 = ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        value.add_resistance_modifier(modifier1)
        value.add_resistance_modifier(modifier2)
        
        assert value.resistance_sum[DamageType.FIRE] == 1
        assert value.resistance_sum[DamageType.COLD] == 2
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.IMMUNITY

class TestContextualValue:
    def test_contextual_value_initialization(self, source_uuid):
        value = ContextualValue(source_entity_uuid=source_uuid)
        
        assert isinstance(value, BaseValue)
        assert value.value_modifiers == {}
        assert value.min_constraints == {}
        assert value.max_constraints == {}
        assert value.advantage_modifiers == {}
        assert value.critical_modifiers == {}
        assert value.auto_hit_modifiers == {}
        assert value.target_entity_uuid is None
        assert value.context is None

    def test_contextual_value_computed_fields(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def value_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid)
        
        def min_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=0, source_entity_uuid=modifier_source_uuid)
        
        def max_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid)
        
        def advantage_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid)
        
        def critical_callable(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid)
        
        def auto_hit_callable(source_uuid, target_uuid, context):
            return AutoHitModifier(target_entity_uuid=source_uuid, value=AutoHitStatus.AUTOHIT, source_entity_uuid=modifier_source_uuid)
        
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable, source_entity_uuid=modifier_source_uuid))
        value.add_min_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=min_callable, source_entity_uuid=modifier_source_uuid))
        value.add_max_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=max_callable, source_entity_uuid=modifier_source_uuid))
        value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=source_uuid, callable=advantage_callable, source_entity_uuid=modifier_source_uuid))
        value.add_critical_modifier(ContextualCriticalModifier(target_entity_uuid=source_uuid, callable=critical_callable, source_entity_uuid=modifier_source_uuid))
        value.add_auto_hit_modifier(ContextualAutoHitModifier(target_entity_uuid=source_uuid, callable=auto_hit_callable, source_entity_uuid=modifier_source_uuid))

        assert value.min == 0
        assert value.max == 10
        assert value.score == 5
        assert value.normalized_score == 5  # Default normalizer
        assert value.advantage_sum == 1
        assert value.advantage == AdvantageStatus.ADVANTAGE
        assert value.critical == CriticalStatus.AUTOCRIT
        assert value.auto_hit == AutoHitStatus.AUTOHIT

    def test_contextual_value_combine(self, source_uuid, target_uuid, sample_context):
        value1 = ContextualValue(source_entity_uuid=source_uuid, name="Value1")
        value1.set_target_entity(target_uuid)
        value1.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def value_callable1(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid)
        
        value1.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable1, source_entity_uuid=modifier_source_uuid))
        
        
        value2 = ContextualValue(source_entity_uuid=source_uuid, name="Value2")
        value2.set_target_entity(target_uuid)
        value2.set_context(sample_context)
        
        def value_callable2(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid)
        
        value2.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable2, source_entity_uuid=modifier_source_uuid))

        combined = value1.combine_values([value2])
        assert combined.name == "Value1_Value2"
        assert len(combined.value_modifiers) == 2
        assert combined.score == 8

    def test_contextual_value_with_multiple_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def value_callable1(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid)
        
        def value_callable2(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=-2, source_entity_uuid=modifier_source_uuid)
        
        def value_callable3(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid)
        
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable2, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable3, source_entity_uuid=modifier_source_uuid))
        assert value.score == 6

    def test_contextual_value_with_conflicting_advantage(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def advantage_callable1(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid)
        
        def advantage_callable2(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=modifier_source_uuid)
        
        value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=source_uuid, callable=advantage_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=source_uuid, callable=advantage_callable2, source_entity_uuid=modifier_source_uuid))
        assert value.advantage == AdvantageStatus.NONE

    def test_contextual_value_with_multiple_critical_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def critical_callable1(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid)
        
        def critical_callable2(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.NOCRIT, source_entity_uuid=modifier_source_uuid)
        
        value.add_critical_modifier(ContextualCriticalModifier(target_entity_uuid=source_uuid, callable=critical_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_critical_modifier(ContextualCriticalModifier(target_entity_uuid=source_uuid, callable=critical_callable2, source_entity_uuid=modifier_source_uuid))
        assert value.critical == CriticalStatus.NOCRIT

    def test_min_max_constraints_conflict(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def min_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid)
        
        def max_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid)
        
        def value_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=7, source_entity_uuid=modifier_source_uuid)
        
        value.add_min_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=min_callable, source_entity_uuid=modifier_source_uuid))
        value.add_max_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=max_callable, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable, source_entity_uuid=modifier_source_uuid))

        assert value.score == 10  # Should respect the min constraint

    def test_empty_modifiers_and_constraints(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        assert value.score == 0
        assert value.min is None
        assert value.max is None
        assert value.advantage == AdvantageStatus.NONE
        assert value.critical == CriticalStatus.NONE
        assert value.auto_hit == AutoHitStatus.NONE

    def test_modifiers_with_invalid_target_uuid(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def invalid_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=uuid4(), value=5, source_entity_uuid=modifier_source_uuid)
        
        with pytest.raises(ValueError):
            value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=uuid4(), callable=invalid_callable, source_entity_uuid=modifier_source_uuid))

    def test_extreme_modifier_values(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def value_callable1(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=2**63 - 1, source_entity_uuid=modifier_source_uuid)
        
        def value_callable2(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=-(2**63), source_entity_uuid=modifier_source_uuid)
        
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable2, source_entity_uuid=modifier_source_uuid))
        assert value.score == -1

    def test_contextual_value_size_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable1(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        def size_callable2(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.HUGE, source_entity_uuid=modifier_source_uuid)
        
        value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable2, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.HUGE  # Default is largest size

    def test_contextual_value_size_modifiers_smallest_priority(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid, largest_size_priority=False)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable1(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        def size_callable2(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.TINY, source_entity_uuid=modifier_source_uuid)
        
        value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable2, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.TINY

    def test_contextual_value_damage_type_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def damage_type_callable1(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def damage_type_callable2(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable2, source_entity_uuid=modifier_source_uuid))
        
        assert set(value.damage_types) == {DamageType.FIRE, DamageType.COLD}

    def test_contextual_value_damage_type_random_selection(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def damage_type_callable1(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def damage_type_callable2(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        def damage_type_callable3(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable2, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable3, source_entity_uuid=modifier_source_uuid))
        
        # Run multiple times to ensure randomness
        damage_types = set()
        for _ in range(100):
            damage_types.add(value.damage_type)
        
        assert damage_types == {DamageType.FIRE}  # FIRE should always be selected as it's the most common

    def test_contextual_value_resistance_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def resistance_callable1(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable2(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable2, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.IMMUNITY

    def test_contextual_value_resistance_sum(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def resistance_callable1(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable2(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable2, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance_sum[DamageType.FIRE] == 3  # RESISTANCE (1) + IMMUNITY (2)

    def test_contextual_value_resistance_calculation(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def resistance_callable1(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable2(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.VULNERABILITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable3(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.LIGHTNING, source_entity_uuid=modifier_source_uuid)
        
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable1, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable2, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable3, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.VULNERABILITY
        assert value.resistance[DamageType.LIGHTNING] == ResistanceStatus.IMMUNITY
        assert value.resistance[DamageType.ACID] == ResistanceStatus.NONE

    def test_contextual_value_remove_size_modifier(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable, source_entity_uuid=modifier_source_uuid)
        uuid = value.add_size_modifier(modifier)
        value.remove_size_modifier(uuid)
        
        assert value.size == Size.MEDIUM  # Default size

    def test_contextual_value_remove_damage_type_modifier(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def damage_type_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable, source_entity_uuid=modifier_source_uuid)
        uuid = value.add_damage_type_modifier(modifier)
        value.remove_damage_type_modifier(uuid)
        
        assert len(value.damage_types) == 0

    def test_contextual_value_remove_resistance_modifier(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def resistance_callable(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable, source_entity_uuid=modifier_source_uuid)
        uuid = value.add_resistance_modifier(modifier)
        value.remove_resistance_modifier(uuid)
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.NONE

    def test_contextual_value_get_all_modifier_uuids(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        def damage_type_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        size_uuid = value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable, source_entity_uuid=modifier_source_uuid))
        damage_uuid = value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable, source_entity_uuid=modifier_source_uuid))
        resistance_uuid = value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable, source_entity_uuid=modifier_source_uuid))
        
        all_uuids = value.get_all_modifier_uuids()
        assert size_uuid in all_uuids
        assert damage_uuid in all_uuids
        assert resistance_uuid in all_uuids

    def test_contextual_value_remove_all_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        def damage_type_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        def resistance_callable(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        value.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable, source_entity_uuid=modifier_source_uuid))
        value.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable, source_entity_uuid=modifier_source_uuid))
        value.add_resistance_modifier(ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable, source_entity_uuid=modifier_source_uuid))
        
        value.remove_all_modifiers()
        
        assert value.size == Size.MEDIUM
        assert len(value.damage_types) == 0
        assert all(status == ResistanceStatus.NONE for status in value.resistance.values())

    def test_contextual_value_combine_with_new_modifiers(self, source_uuid, target_uuid, sample_context):
        value1 = ContextualValue(source_entity_uuid=source_uuid)
        value1.set_target_entity(target_uuid)
        value1.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        value1.add_size_modifier(ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable, source_entity_uuid=modifier_source_uuid))
        
        value2 = ContextualValue(source_entity_uuid=source_uuid)
        value2.set_target_entity(target_uuid)
        value2.set_context(sample_context)
        
        def damage_type_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        value2.add_damage_type_modifier(ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable, source_entity_uuid=modifier_source_uuid))
        
        combined = value1.combine_values([value2])
        
        assert combined.size == Size.LARGE
        assert DamageType.FIRE in combined.damage_types

class TestContextualValueNewFeatures:
    def test_size_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def size_callable(source_uuid, target_uuid, context):
            return SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualSizeModifier(target_entity_uuid=source_uuid, callable=size_callable, source_entity_uuid=modifier_source_uuid)
        value.add_size_modifier(modifier)
        
        assert value.size == Size.LARGE

    def test_damage_type_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def damage_type_callable(source_uuid, target_uuid, context):
            return DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualDamageTypeModifier(target_entity_uuid=source_uuid, callable=damage_type_callable, source_entity_uuid=modifier_source_uuid)
        value.add_damage_type_modifier(modifier)
        
        assert DamageType.FIRE in value.damage_types
        assert value.damage_type == DamageType.FIRE

    def test_resistance_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ContextualValue(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        
        def resistance_callable(source_uuid, target_uuid, context):
            return ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid)
        
        modifier = ContextualResistanceModifier(target_entity_uuid=source_uuid, callable=resistance_callable, source_entity_uuid=modifier_source_uuid)
        value.add_resistance_modifier(modifier)
        
        assert value.resistance_sum[DamageType.FIRE] == 1
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE

class TestModifiableValue:
    def test_modifiable_value_initialization(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        
        assert isinstance(value, BaseValue)
        assert isinstance(value.self_static, StaticValue)
        assert isinstance(value.self_contextual, ContextualValue)
        assert isinstance(value.to_target_static, StaticValue)
        assert isinstance(value.to_target_contextual, ContextualValue)
        assert value.from_target_static is None
        assert value.from_target_contextual is None

    def test_modifiable_value_computed_fields(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        
        modifier_source_uuid = uuid4()
        
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_min_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=0, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_max_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_auto_hit_modifier(AutoHitModifier(target_entity_uuid=source_uuid, value=AutoHitStatus.AUTOHIT, source_entity_uuid=modifier_source_uuid))
        

        
        def value_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid)
        
        def min_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=0, source_entity_uuid=modifier_source_uuid)
        
        def max_callable(source_uuid, target_uuid, context):
            return NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid)
        
        def advantage_callable(source_uuid, target_uuid, context):
            return AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid)
        
        def critical_callable(source_uuid, target_uuid, context):
            return CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid)
        
        def auto_hit_callable(source_uuid, target_uuid, context):
            return AutoHitModifier(target_entity_uuid=source_uuid, value=AutoHitStatus.AUTOHIT, source_entity_uuid=modifier_source_uuid)
        
        value.self_contextual.add_value_modifier(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=value_callable, source_entity_uuid=modifier_source_uuid))
        value.self_contextual.add_min_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=min_callable, source_entity_uuid=modifier_source_uuid))
        value.self_contextual.add_max_constraint(ContextualNumericalModifier(target_entity_uuid=source_uuid, callable=max_callable, source_entity_uuid=modifier_source_uuid))
        value.self_contextual.add_advantage_modifier(ContextualAdvantageModifier(target_entity_uuid=source_uuid, callable=advantage_callable, source_entity_uuid=modifier_source_uuid))
        value.self_contextual.add_critical_modifier(ContextualCriticalModifier(target_entity_uuid=source_uuid, callable=critical_callable, source_entity_uuid=modifier_source_uuid))
        value.self_contextual.add_auto_hit_modifier(ContextualAutoHitModifier(target_entity_uuid=source_uuid, callable=auto_hit_callable, source_entity_uuid=modifier_source_uuid))
        


        assert value.min == 0
        assert value.max == 10
        assert value.score == 8
        assert value.normalized_score == 8  # Default normalizer
        assert value.advantage_sum == 2
        assert value.advantage == AdvantageStatus.ADVANTAGE
        assert value.critical == CriticalStatus.AUTOCRIT
        assert value.auto_hit == AutoHitStatus.AUTOHIT

    def test_modifiable_value_combine(self, source_uuid, target_uuid, sample_context):
        value1 = ModifiableValue.create(source_entity_uuid=source_uuid, value_name="Value1")
        value1.set_target_entity(target_uuid)
        value1.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value1.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value1.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        
        value2 = ModifiableValue.create(source_entity_uuid=source_uuid, value_name="Value2")
        value2.set_target_entity(target_uuid)
        value2.set_context(sample_context)
        value2.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid))

        combined = value1.combine_values([value2])
        assert combined.name == "Value1_Value2"
        assert len(combined.self_static.value_modifiers) == 5 # 3 added and 2 base values.
        assert combined.score == 13

    def test_modifiable_value_with_multiple_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        
        modifier_source_uuid = uuid4()
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=-2, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=3, source_entity_uuid=modifier_source_uuid))
        assert value.score == 6

    def test_modifiable_value_with_conflicting_advantage(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        
        modifier_source_uuid = uuid4()
        value.self_static.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.ADVANTAGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_advantage_modifier(AdvantageModifier(target_entity_uuid=source_uuid, value=AdvantageStatus.DISADVANTAGE, source_entity_uuid=modifier_source_uuid))
        assert value.advantage == AdvantageStatus.NONE

    def test_modifiable_value_with_multiple_critical_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        
        modifier_source_uuid = uuid4()
        value.self_static.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.AUTOCRIT, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_critical_modifier(CriticalModifier(target_entity_uuid=source_uuid, value=CriticalStatus.NOCRIT, source_entity_uuid=modifier_source_uuid))
        assert value.critical == CriticalStatus.NOCRIT

    def test_min_max_constraints_conflict(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        
        modifier_source_uuid = uuid4()
        value.self_static.add_min_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=10, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_max_constraint(NumericalModifier(target_entity_uuid=source_uuid, value=5, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=7, source_entity_uuid=modifier_source_uuid))

        assert value.score == 10  # Should respect the min constraint

    def test_empty_modifiers_and_constraints(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        assert value.score == 0
        assert value.min is None
        assert value.max is None
        assert value.advantage == AdvantageStatus.NONE
        assert value.critical == CriticalStatus.NONE
        assert value.auto_hit == AutoHitStatus.NONE

    def test_modifiers_with_invalid_target_uuid(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        invalid_modifier = NumericalModifier(target_entity_uuid=uuid4(), value=5, source_entity_uuid=modifier_source_uuid)
        with pytest.raises(ValueError):
            value.self_static.add_value_modifier(invalid_modifier)

    def test_extreme_modifier_values(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=2**63 - 1, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_value_modifier(NumericalModifier(target_entity_uuid=source_uuid, value=-(2**63), source_entity_uuid=modifier_source_uuid))
        assert value.score == -1

    def test_modifiable_value_size_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.HUGE, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.HUGE  # Default is largest size

    def test_modifiable_value_size_modifiers_smallest_priority(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.self_static.largest_size_priority = False
        value.self_contextual.largest_size_priority = False
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.TINY, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.TINY

    def test_modifiable_value_damage_type_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert set(value.damage_types) == {DamageType.FIRE, DamageType.COLD}

    def test_modifiable_value_damage_type_random_selection(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        # Run multiple times to ensure randomness
        damage_types = set()
        for _ in range(100):
            damage_types.add(value.damage_type)
        
        assert damage_types == {DamageType.FIRE}  # FIRE should always be selected as it's the most common

    def test_modifiable_value_resistance_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.IMMUNITY

    def test_modifiable_value_resistance_sum(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance_sum[DamageType.FIRE] == 3  # RESISTANCE (1) + IMMUNITY (2)

    def test_modifiable_value_resistance_calculation(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.VULNERABILITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.LIGHTNING, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.VULNERABILITY
        assert value.resistance[DamageType.LIGHTNING] == ResistanceStatus.IMMUNITY
        assert value.resistance[DamageType.ACID] == ResistanceStatus.NONE

    def test_modifiable_value_remove_size_modifier(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.remove_size_modifier(modifier_uuid)
        
        assert value.size == Size.MEDIUM  # Default size

    def test_modifiable_value_remove_damage_type_modifier(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.remove_damage_type_modifier(modifier_uuid)
        
        assert len(value.damage_types) == 0

    def test_modifiable_value_remove_resistance_modifier(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        modifier_uuid = value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.remove_resistance_modifier(modifier_uuid)
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.NONE

    def test_modifiable_value_get_all_modifier_uuids(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        size_uuid = value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        damage_uuid = value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        resistance_uuid = value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        all_uuids = value.get_all_modifier_uuids()
        assert size_uuid in all_uuids
        assert damage_uuid in all_uuids
        assert resistance_uuid in all_uuids

    def test_modifiable_value_remove_all_modifiers(self, source_uuid, target_uuid, sample_context):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        value.set_target_entity(target_uuid)
        value.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        value.remove_all_modifiers()
        
        assert value.size == Size.MEDIUM
        assert len(value.damage_types) == 0
        assert all(status == ResistanceStatus.NONE for status in value.resistance.values())

    def test_modifiable_value_combine_with_new_modifiers(self, source_uuid, target_uuid, sample_context):
        value1 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value1.set_target_entity(target_uuid)
        value1.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value1.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        
        value2 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value2.set_target_entity(target_uuid)
        value2.set_context(sample_context)
        value2.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        combined = value1.combine_values([value2])
        
        assert combined.size == Size.LARGE
        assert DamageType.FIRE in combined.damage_types

class TestModifiableValueNewFeatures:
    def test_get_typed_modifiers(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        typed_modifiers = value.get_typed_modifiers()
        
        assert len(typed_modifiers) == 2  # self_static, , self_contextual,
        assert all(isinstance(mod, (StaticValue, ContextualValue)) for mod in typed_modifiers)

    def test_set_from_target(self, source_uuid, target_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        target_value = ModifiableValue.create(source_entity_uuid=target_uuid)
        
        value.set_target_entity(target_uuid)
        target_value.set_target_entity(source_uuid)
        
        value.set_from_target(target_value)
        
        assert value.from_target_contextual is not None
        assert value.from_target_static is not None
        assert value.from_target_contextual.source_entity_uuid == target_uuid
        assert value.from_target_static.source_entity_uuid == target_uuid

    def test_size_property(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        
        assert value.size == Size.LARGE

    def test_damage_types_property(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.to_target_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert set(value.damage_types) == {DamageType.FIRE, DamageType.COLD}

    def test_resistance_property(self, source_uuid):
        value = ModifiableValue.create(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        value.self_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        value.to_target_static.add_resistance_modifier(ResistanceModifier(target_entity_uuid=source_uuid, value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD, source_entity_uuid=modifier_source_uuid))
        
        assert value.resistance[DamageType.FIRE] == ResistanceStatus.RESISTANCE
        assert value.resistance[DamageType.COLD] == ResistanceStatus.IMMUNITY

class TestEdgeCasesAndErrorHandling:
    def test_invalid_size_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        with pytest.raises(ValueError):
            value.add_size_modifier(SizeModifier(target_entity_uuid=uuid4(), value=Size.LARGE, source_entity_uuid=modifier_source_uuid))

    def test_invalid_damage_type_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        with pytest.raises(ValueError):
            value.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=uuid4(), value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))

    def test_invalid_resistance_modifier(self, source_uuid):
        value = StaticValue(source_entity_uuid=source_uuid)
        modifier_source_uuid = uuid4()
        with pytest.raises(ValueError):
            value.add_resistance_modifier(ResistanceModifier(target_entity_uuid=uuid4(), value=ResistanceStatus.RESISTANCE, damage_type=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))


    def test_modifiable_value_combine_with_new_modifiers(self, source_uuid, target_uuid, sample_context):
        value1 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value1.set_target_entity(target_uuid)
        value1.set_context(sample_context)
        modifier_source_uuid = uuid4()
        value1.self_static.add_size_modifier(SizeModifier(target_entity_uuid=source_uuid, value=Size.LARGE, source_entity_uuid=modifier_source_uuid))
        
        value2 = ModifiableValue.create(source_entity_uuid=source_uuid)
        value2.set_target_entity(target_uuid)
        value2.set_context(sample_context)
        value2.self_static.add_damage_type_modifier(DamageTypeModifier(target_entity_uuid=source_uuid, value=DamageType.FIRE, source_entity_uuid=modifier_source_uuid))
        
        combined = value1.combine_values([value2])
        
        assert combined.size == Size.LARGE
        assert DamageType.FIRE in combined.damage_types

if __name__ == "__main__":
    pytest.main([__file__])
