import pytest
from uuid import UUID, uuid4
from typing import Dict, Any, List
from dnd.blocks import BaseBlock, Ability, AbilityScores, ability_score_normalizer, Skill, SkillSet, SavingThrow, SavingThrowSet, HitDice, Health, ABILITY_TO_SKILLS, skills, saving_throws
from dnd.modifiers import DamageType, ResistanceStatus, ResistanceModifier
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
        assert ability.name == "strength"

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

    def test_abilities_list(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        abilities = ability_scores.abilities_list
        assert len(abilities) == 6
        assert all(isinstance(ability, Ability) for ability in abilities)

    def test_ability_blocks_uuid_by_name(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        uuid_by_name = ability_scores.ability_blocks_uuid_by_name
        assert len(uuid_by_name) == 6
        assert all(isinstance(uuid, UUID) for uuid in uuid_by_name.values())

    def test_ability_blocks_names_by_uuid(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        names_by_uuid = ability_scores.ability_blocks_names_by_uuid
        assert len(names_by_uuid) == 6
        assert all(name in ABILITY_TO_SKILLS.keys() for name in names_by_uuid.values())

    def test_get_modifier(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        strength_uuid = ability_scores.strength.uuid
        modifier = ability_scores.get_modifier(strength_uuid)
        assert isinstance(modifier, int)

    def test_get_modifier_from_uuid(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        strength_uuid = ability_scores.strength.uuid
        modifier = ability_scores.get_modifier_from_uuid(strength_uuid)
        assert isinstance(modifier, int)

    def test_get_modifier_from_name(self, source_uuid):
        ability_scores = AbilityScores(source_entity_uuid=source_uuid)
        modifier = ability_scores.get_modifier_from_name("strength")
        assert isinstance(modifier, int)

class TestSkill:
    def test_skill_initialization(self, source_uuid):
        skill = Skill(source_entity_uuid=source_uuid, name="acrobatics")
        assert isinstance(skill, BaseBlock)
        assert isinstance(skill.skill_bonus, ModifiableValue)
        assert skill.name == "acrobatics"
        assert not skill.expertise
        assert not skill.proficiency

    def test_set_proficiency(self, source_uuid):
        skill = Skill(source_entity_uuid=source_uuid, name="acrobatics")
        skill.set_proficiency(True)
        assert skill.proficiency

    def test_set_expertise(self, source_uuid):
        skill = Skill(source_entity_uuid=source_uuid, name="acrobatics")
        skill.set_expertise(True)
        assert skill.expertise
        assert skill.proficiency  # Expertise implies proficiency

    def test_get_score(self, source_uuid):
        skill = Skill(source_entity_uuid=source_uuid, name="acrobatics")
        skill.set_proficiency(True)
        score = skill.get_score(2)  # Assuming proficiency bonus of 2
        assert score == 2

    def test_create_method(self, source_uuid):
        skill = Skill.create(source_entity_uuid=source_uuid, name="acrobatics", expertise=True)
        assert skill.expertise
        assert skill.proficiency

class TestSkillSet:
    def test_skillset_initialization(self, source_uuid):
        skillset = SkillSet(source_entity_uuid=source_uuid)
        assert isinstance(skillset, BaseBlock)
        assert all(isinstance(getattr(skillset, skill), Skill) for skill in skills.__args__)

    def test_proficiencies(self, source_uuid):
        skillset = SkillSet(source_entity_uuid=source_uuid)
        skillset.acrobatics.set_proficiency(True)
        proficiencies = skillset.proficiencies
        assert len(proficiencies) == 1
        assert proficiencies[0].name == "acrobatics"

    def test_expertise(self, source_uuid):
        skillset = SkillSet(source_entity_uuid=source_uuid)
        skillset.acrobatics.set_expertise(True)
        expertise = skillset.expertise
        assert len(expertise) == 1
        assert expertise[0].name == "acrobatics"

class TestSavingThrow:
    def test_saving_throw_initialization(self, source_uuid):
        saving_throw = SavingThrow(source_entity_uuid=source_uuid, name="strength_saving_throw")
        assert isinstance(saving_throw, BaseBlock)
        assert isinstance(saving_throw.bonus, ModifiableValue)
        assert saving_throw.name == "strength_saving_throw"
        assert not saving_throw.proficiency

    def test_get_bonus(self, source_uuid):
        saving_throw = SavingThrow(source_entity_uuid=source_uuid, name="strength_saving_throw")
        saving_throw.proficiency = True
        bonus = saving_throw.get_bonus(2)  # Assuming proficiency bonus of 2
        assert bonus == 2

    def test_create_method(self, source_uuid):
        saving_throw = SavingThrow.create(source_entity_uuid=source_uuid, name="strength_saving_throw", proficiency=True)
        assert saving_throw.proficiency

class TestSavingThrowSet:
    def test_saving_throw_set_initialization(self, source_uuid):
        saving_throw_set = SavingThrowSet(source_entity_uuid=source_uuid)
        assert isinstance(saving_throw_set, BaseBlock)
        assert all(isinstance(getattr(saving_throw_set, st), SavingThrow) for st in saving_throws.__args__)

    def test_proficiencies(self, source_uuid):
        saving_throw_set = SavingThrowSet(source_entity_uuid=source_uuid)
        saving_throw_set.strength_saving_throw.proficiency = True
        proficiencies = saving_throw_set.proficiencies
        assert len(proficiencies) == 1
        assert proficiencies[0].name == "strength_saving_throw"

class TestHitDice:
    def test_hit_dice_initialization(self, source_uuid):
        hit_dice = HitDice(source_entity_uuid=source_uuid)
        assert isinstance(hit_dice, BaseBlock)
        assert isinstance(hit_dice.hit_dice_value, ModifiableValue)
        assert isinstance(hit_dice.hit_dice_count, ModifiableValue)
        assert hit_dice.mode == "average"

    def test_hit_points_calculation(self, source_uuid):
        hit_dice = HitDice.create(source_entity_uuid=source_uuid, hit_dice_value=8, hit_dice_count=3, mode="average")
        
        assert hit_dice.hit_points == 18  # 8 + (2 * 5)

    def test_hit_dice_value_validator(self, source_uuid):
        with pytest.raises(ValueError):
            HitDice(source_entity_uuid=source_uuid, hit_dice_value=ModifiableValue.create(source_entity_uuid=source_uuid, base_value=7))

    def test_hit_dice_count_validator(self, source_uuid):
        with pytest.raises(ValueError):
            HitDice(source_entity_uuid=source_uuid, hit_dice_count=ModifiableValue.create(source_entity_uuid=source_uuid, base_value=0))

    def test_create_method(self, source_uuid):
        hit_dice = HitDice.create(source_entity_uuid=source_uuid, hit_dice_value=10, hit_dice_count=2, mode="maximums")
        assert hit_dice.hit_dice_value.score == 10
        assert hit_dice.hit_dice_count.score == 2
        assert hit_dice.mode == "maximums"

class TestHealth:
    def test_health_initialization(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        assert isinstance(health, BaseBlock)
        assert isinstance(health.hit_dices[0], HitDice)
        assert isinstance(health.max_hit_points_bonus, ModifiableValue)
        assert isinstance(health.temporary_hit_points, ModifiableValue)
        assert health.damage_taken == 0

    def test_hit_dices_total_hit_points(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.hit_dices[0].hit_dice_value.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_value.self_static.value_modifiers.keys())[0]].value = 8
        health.hit_dices[0].hit_dice_count.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_count.self_static.value_modifiers.keys())[0]].value = 3
        assert health.hit_dices_total_hit_points == 18

    def test_total_hit_dices_number(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.hit_dices[0].hit_dice_count.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_count.self_static.value_modifiers.keys())[0]].value = 3
        assert health.total_hit_dices_number == 3

    def test_add_remove_damage(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.add_damage(5)
        assert health.damage_taken == 5
        health.remove_damage(3)
        assert health.damage_taken == 2

    def test_damage_multiplier(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.FIRE
        ))
        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.COLD
        ))
        assert health.damage_multiplier(DamageType.FIRE) == 2
        assert health.damage_multiplier(DamageType.COLD) == 0.5
        assert health.damage_multiplier(DamageType.PIERCING) == 1

    def test_take_damage(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.take_damage(10, DamageType.FIRE, source_uuid)
        assert health.damage_taken == 10

        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.COLD
        ))
        health.take_damage(10, DamageType.COLD, source_uuid)
        assert health.damage_taken == 15  # 10 + 5 (10 * 0.5)

    def test_heal(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.add_damage(10)
        health.heal(6)
        assert health.damage_taken == 4

    def test_add_remove_temporary_hit_points(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.add_temporary_hit_points(5, source_uuid)
        assert health.temporary_hit_points.score == 5
        health.remove_temporary_hit_points(3, source_uuid)
        assert health.temporary_hit_points.score == 2

    def test_get_max_hit_dices_points(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.hit_dices[0].hit_dice_value.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_value.self_static.value_modifiers.keys())[0]].value = 8
        health.hit_dices[0].hit_dice_count.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_count.self_static.value_modifiers.keys())[0]].value = 3
        max_points = health.get_max_hit_dices_points(2)  # Assuming Constitution modifier of 2
        assert max_points == 24  # 18 (from hit dice) + 6 (3 * 2 from Constitution)

    def test_get_total_hit_points(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.hit_dices[0].hit_dice_value.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_value.self_static.value_modifiers.keys())[0]].value = 8
        health.hit_dices[0].hit_dice_count.self_static.value_modifiers[list(health.hit_dices[0].hit_dice_count.self_static.value_modifiers.keys())[0]].value = 3
        health.max_hit_points_bonus.self_static.value_modifiers[list(health.max_hit_points_bonus.self_static.value_modifiers.keys())[0]].value = 5
        health.add_temporary_hit_points(3, source_uuid)
        health.add_damage(7)
        total_hp = health.get_total_hit_points(2)  # Assuming Constitution modifier of 2
        assert total_hp == 25  # 24 (max) + 5 (bonus) + 3 (temp) - 7 (damage)

    def test_add_remove_vulnerability(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.VULNERABILITY,
            damage_type=DamageType.FIRE
        ))
        assert health.get_resistance(DamageType.FIRE) == ResistanceStatus.VULNERABILITY
        health.damage_reduction.self_static.remove_resistance_modifier(list(health.damage_reduction.self_static.resistance_modifiers.keys())[0])
        assert health.get_resistance(DamageType.FIRE) == ResistanceStatus.NONE

    def test_add_remove_resistance(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.COLD
        ))
        assert health.get_resistance(DamageType.COLD) == ResistanceStatus.RESISTANCE
        health.damage_reduction.self_static.remove_resistance_modifier(list(health.damage_reduction.self_static.resistance_modifiers.keys())[0])
        assert health.get_resistance(DamageType.COLD) == ResistanceStatus.NONE

    def test_add_remove_immunity(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            value=ResistanceStatus.IMMUNITY,
            damage_type=DamageType.POISON
        ))
        assert health.get_resistance(DamageType.POISON) == ResistanceStatus.IMMUNITY
        health.damage_reduction.self_static.remove_resistance_modifier(list(health.damage_reduction.self_static.resistance_modifiers.keys())[0])
        assert health.get_resistance(DamageType.POISON) == ResistanceStatus.NONE

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

    def test_invalid_skill_name(self, source_uuid):
        with pytest.raises(ValueError):
            Skill(source_entity_uuid=source_uuid, name="invalid_skill") # type: ignore[arg-type]

    def test_invalid_saving_throw_name(self, source_uuid):
        with pytest.raises(ValueError):
            SavingThrow(source_entity_uuid=source_uuid, name="invalid_saving_throw") # type: ignore[arg-type]

    def test_invalid_hit_dice_mode(self, source_uuid):
        with pytest.raises(ValueError):
            HitDice(source_entity_uuid=source_uuid, mode="invalid_mode") # type: ignore[arg-type]

    def test_negative_damage(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        with pytest.raises(ValueError):
            health.take_damage(-5, DamageType.FIRE, source_uuid)

    def test_invalid_damage_type(self, source_uuid):
        health = Health(source_entity_uuid=source_uuid)
        with pytest.raises(ValueError):
            health.take_damage(5, "invalid_damage_type", source_uuid) # type: ignore[arg-type]

if __name__ == "__main__":
    pytest.main([__file__])
