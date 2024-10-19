import pytest
from uuid import UUID, uuid4
from typing import Dict, Any, List
from dnd.blocks import BaseBlock, Ability, AbilityScores, ability_score_normalizer
from dnd.values import ModifiableValue

@pytest.fixture
def source_uuid():
    return uuid4()

@pytest.fixture
def target_uuid():
    return uuid4()

@pytest.fixture
def sample_context():
    return {"test_key": "test_value"}

class TestBaseBlock:
    def test_base_block_initialization(self, source_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        
        assert isinstance(block.uuid, UUID)
        assert block.source_entity_uuid == source_uuid
        assert block.name == "A Block"
        assert block.source_entity_name is None
        assert block.target_entity_uuid is None
        assert block.target_entity_name is None
        assert block.context is None

    def test_base_block_with_all_attributes(self, source_uuid, target_uuid, sample_context):
        block = BaseBlock(
            name="Test Block",
            source_entity_uuid=source_uuid,
            source_entity_name="Source",
            target_entity_uuid=target_uuid,
            target_entity_name="Target",
            context=sample_context
        )
        
        assert block.name == "Test Block"
        assert block.source_entity_uuid == source_uuid
        assert block.source_entity_name == "Source"
        assert block.target_entity_uuid == target_uuid
        assert block.target_entity_name == "Target"
        assert block.context == sample_context

    def test_base_block_registry(self, source_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        
        retrieved_block = BaseBlock.get(block.uuid)
        assert retrieved_block == block

    def test_base_block_unregister(self, source_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        
        BaseBlock.unregister(block.uuid)
        assert BaseBlock.get(block.uuid) is None

    def test_base_block_register(self, source_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        
        BaseBlock.unregister(block.uuid)
        BaseBlock.register(block)
        
        retrieved_block = BaseBlock.get(block.uuid)
        assert retrieved_block == block

    def test_get_non_existent_block(self):
        non_existent_uuid = uuid4()
        assert BaseBlock.get(non_existent_uuid) is None

    def test_get_wrong_type_block(self, source_uuid):
        class FakeBlock(BaseBlock):
            pass

        fake_block = FakeBlock(source_entity_uuid=source_uuid)
        BaseBlock.register(fake_block)

        # This should not raise an exception
        retrieved_block = BaseBlock.get(fake_block.uuid)
        assert retrieved_block is not None
        assert isinstance(retrieved_block, FakeBlock)

        # This should raise a ValueError
        with pytest.raises(ValueError):
            Ability.get(fake_block.uuid)

        # Clean up
        BaseBlock.unregister(fake_block.uuid)

    def test_set_target_entity(self, source_uuid, target_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        block.set_target_entity(target_uuid, "Target")
        
        assert block.target_entity_uuid == target_uuid
        assert block.target_entity_name == "Target"

    def test_clear_target_entity(self, source_uuid, target_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)
        block.clear_target_entity()
        
        assert block.target_entity_uuid is None
        assert block.target_entity_name is None

    def test_set_context(self, source_uuid, sample_context):
        block = BaseBlock(source_entity_uuid=source_uuid)
        block.set_context(sample_context)
        
        assert block.context == sample_context

    def test_clear_context(self, source_uuid, sample_context):
        block = BaseBlock(source_entity_uuid=source_uuid, context=sample_context)
        block.clear_context()
        
        assert block.context is None

    def test_get_values(self, source_uuid):
        class TestBlock(BaseBlock):
            value1: ModifiableValue = ModifiableValue.create(source_entity_uuid=source_uuid)
            value2: ModifiableValue = ModifiableValue.create(source_entity_uuid=source_uuid)

        block = TestBlock(source_entity_uuid=source_uuid)
        values = block.get_values()
        
        assert len(values) == 2
        assert all(isinstance(value, ModifiableValue) for value in values)

    def test_get_blocks(self, source_uuid):
        class TestBlock(BaseBlock):
            sub_block1: BaseBlock = BaseBlock(source_entity_uuid=source_uuid)
            sub_block2: BaseBlock = BaseBlock(source_entity_uuid=source_uuid)

        block = TestBlock(source_entity_uuid=source_uuid)
        blocks = block.get_blocks()
        
        assert len(blocks) == 2
        assert all(isinstance(block, BaseBlock) for block in blocks)

    def test_validate_values_source_and_target(self, source_uuid, target_uuid):
        class TestBlock(BaseBlock):
            value: ModifiableValue = ModifiableValue.create(source_entity_uuid=source_uuid)

        block = TestBlock(source_entity_uuid=source_uuid, target_entity_uuid=target_uuid)
        
        # Revalidate the block
        validated_block = TestBlock.model_validate(block)
        
        # Check that the ModifiableValue's target UUID matches the block's target UUID
        assert validated_block.value.target_entity_uuid == validated_block.target_entity_uuid
        
        # Check that the ModifiableValue's source UUID matches the block's source UUID
        assert validated_block.value.source_entity_uuid == validated_block.source_entity_uuid

        # Change the target UUID and revalidate
        new_target_uuid = uuid4()
        block.target_entity_uuid = new_target_uuid
        revalidated_block = TestBlock.model_validate(block)
        
        # Check that the ModifiableValue's target UUID has been updated
        assert revalidated_block.value.target_entity_uuid == new_target_uuid

    def test_create_method(self, source_uuid, target_uuid):
        block = BaseBlock.create(
            source_entity_uuid=source_uuid,
            source_entity_name="Source",
            target_entity_uuid=target_uuid,
            target_entity_name="Target",
            name="Test Block"
        )
        
        assert isinstance(block, BaseBlock)
        assert block.source_entity_uuid == source_uuid
        assert block.source_entity_name == "Source"
        assert block.target_entity_uuid == target_uuid
        assert block.target_entity_name == "Target"
        assert block.name == "Test Block"

class TestAbility:
    def test_ability_initialization(self, source_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        
        assert isinstance(ability, BaseBlock)
        assert isinstance(ability.ability_score, ModifiableValue)
        assert isinstance(ability.modifier_bonus, ModifiableValue)
        assert ability.name == "Ability Score"

    def test_ability_score_normalization(self, source_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        ability.ability_score.self_static.value_modifiers[list(ability.ability_score.self_static.value_modifiers.keys())[0]].value = 15
        
        assert ability.modifier == 2

    def test_modifier_calculation(self, source_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        ability.ability_score.self_static.value_modifiers[list(ability.ability_score.self_static.value_modifiers.keys())[0]].value = 15
        ability.modifier_bonus.self_static.value_modifiers[list(ability.modifier_bonus.self_static.value_modifiers.keys())[0]].value = 1
        
        assert ability.modifier == 3

    def test_ability_get_method(self, source_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        retrieved_ability = Ability.get(ability.uuid)
        
        assert retrieved_ability == ability
        assert isinstance(retrieved_ability, Ability)

    def test_ability_uuid_consistency(self, source_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        
        assert ability.ability_score.source_entity_uuid == source_uuid
        assert ability.modifier_bonus.source_entity_uuid == source_uuid

    def test_ability_set_target_entity(self, source_uuid, target_uuid):
        ability = Ability(source_entity_uuid=source_uuid)
        ability.set_target_entity(target_uuid, "Target")
        
        assert ability.target_entity_uuid == target_uuid
        assert ability.target_entity_name == "Target"
        assert ability.ability_score.target_entity_uuid == target_uuid
        assert ability.modifier_bonus.target_entity_uuid == target_uuid

class TestAbilityScores:
    def test_ability_scores_initialization(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        
        assert isinstance(ability_scores, BaseBlock)
        assert all(isinstance(getattr(ability_scores, attr), Ability) for attr in 
                   ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"])

    def test_ability_scores_uuid_consistency(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability = getattr(ability_scores, attr)
            assert ability.source_entity_uuid == source_uuid
            assert ability.ability_score.source_entity_uuid == source_uuid
            assert ability.modifier_bonus.source_entity_uuid == source_uuid

    def test_ability_scores_set_target_entity(self, source_uuid, target_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        ability_scores.set_target_entity(target_uuid, "Target")
        
        assert ability_scores.target_entity_uuid == target_uuid
        assert ability_scores.target_entity_name == "Target"
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability = getattr(ability_scores, attr)
            assert ability.target_entity_uuid == target_uuid
            assert ability.ability_score.target_entity_uuid == target_uuid
            assert ability.modifier_bonus.target_entity_uuid == target_uuid

    def test_ability_scores_clear_target_entity(self, source_uuid, target_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        ability_scores.set_target_entity(target_uuid, "Target")
        ability_scores.clear_target_entity()
        
        assert ability_scores.target_entity_uuid is None
        assert ability_scores.target_entity_name is None
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability = getattr(ability_scores, attr)
            assert ability.target_entity_uuid is None
            assert ability.ability_score.target_entity_uuid is None
            assert ability.modifier_bonus.target_entity_uuid is None

    def test_ability_scores_set_context(self, source_uuid, sample_context):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        ability_scores.set_context(sample_context)
        
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability = getattr(ability_scores, attr)
            assert ability.ability_score.context == sample_context
            assert ability.modifier_bonus.context == sample_context

    def test_ability_scores_clear_context(self, source_uuid, sample_context):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        ability_scores.set_context(sample_context)
        ability_scores.clear_context()
        
        for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
            ability = getattr(ability_scores, attr)
            assert ability.ability_score.context is None
            assert ability.modifier_bonus.context is None

class TestEdgeCasesAndErrorHandling:
    def test_missing_required_field(self):
        with pytest.raises(ValueError):
            BaseBlock()  # Missing required source_entity_uuid

    def test_invalid_uuid(self):
        with pytest.raises(ValueError):
            BaseBlock(source_entity_uuid="not-a-uuid")

    def test_set_target_entity_invalid_uuid(self, source_uuid):
        block = BaseBlock(source_entity_uuid=source_uuid)
        with pytest.raises(ValueError):
            block.set_target_entity("not-a-uuid") # type: ignore[arg-type]

    def test_ability_score_normalizer(self):
        assert ability_score_normalizer(10) == 0
        assert ability_score_normalizer(1) == -5
        assert ability_score_normalizer(20) == 5
        assert ability_score_normalizer(15) == 2

    def test_nested_blocks_uuid_consistency(self, source_uuid):
        class NestedBlock(BaseBlock):
            sub_block: BaseBlock
            value: ModifiableValue

        nested_block = NestedBlock(
            source_entity_uuid=source_uuid,
            sub_block=BaseBlock(source_entity_uuid=source_uuid),
            value=ModifiableValue.create(source_entity_uuid=source_uuid)
        )

        assert nested_block.source_entity_uuid == source_uuid
        assert nested_block.sub_block.source_entity_uuid == source_uuid
        assert nested_block.value.source_entity_uuid == source_uuid

    def test_deep_get_values(self, source_uuid):
        class DeepBlock(BaseBlock):
            sub_block: BaseBlock
            value: ModifiableValue

        deep_block = DeepBlock(
            source_entity_uuid=source_uuid,
            sub_block=BaseBlock(source_entity_uuid=source_uuid),
            value=ModifiableValue.create(source_entity_uuid=source_uuid)
        )

        values = deep_block.get_values(deep=True)
        assert len(values) == 1
        assert isinstance(values[0], ModifiableValue)

    def test_ability_scores_get_values(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        values = ability_scores.get_values(deep=True)
        
        assert len(values) == 12  # 6 abilities, each with 2 ModifiableValues

    def test_block_clear(self, source_uuid, target_uuid, sample_context):
        block = BaseBlock(
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            context=sample_context
        )
        block.clear()
        
        assert block.target_entity_uuid is None
        assert block.target_entity_name is None
        assert block.context is None

if __name__ == "__main__":
    pytest.main([__file__])

