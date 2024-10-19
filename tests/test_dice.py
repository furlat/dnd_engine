import pytest
from uuid import UUID, uuid4
from dnd.dice import DiceRoll, Dice, AttackOutcome, RollType
from dnd.values import ModifiableValue, AdvantageStatus, CriticalStatus, AutoHitStatus, StaticValue, NumericalModifier, ContextualValue
from dnd.modifiers import AdvantageModifier
import random

@pytest.fixture
def source_uuid():
    return uuid4()

@pytest.fixture
def target_uuid():
    return uuid4()

@pytest.fixture
def sample_modifiable_value(source_uuid, target_uuid):
    modifer_uuid = uuid4()
    return ModifiableValue(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        self_static=StaticValue(
            name="example_static",
            source_entity_uuid=source_uuid,
            value_modifiers={modifer_uuid: NumericalModifier(
                uuid=modifer_uuid,
                name="example_numerical_modifier",
                value=10,
                target_entity_uuid=source_uuid
            )}
        ),
        self_contextual=ContextualValue(
            name="example_contextual",
            source_entity_uuid=source_uuid
        ),
        to_target_contextual=ContextualValue(
            name="example_to_target_contextual",
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            is_outgoing_modifier=True
        ),
        to_target_static=StaticValue(
            name="example_to_target_static",
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            is_outgoing_modifier=True
        )
    )

class TestDiceRoll:
    def test_dice_roll_initialization(self, source_uuid):
        dice_uuid = uuid4()
        roll = DiceRoll(
            dice_uuid=dice_uuid,
            roll_type=RollType.ATTACK,
            results=15,
            total=25,
            bonus=10,
            advantage_status=AdvantageStatus.NONE,
            critical_status=CriticalStatus.NONE,
            auto_hit_status=AutoHitStatus.NONE,
            source_entity_uuid=source_uuid
        )

        assert isinstance(roll.roll_uuid, UUID)
        assert roll.dice_uuid == dice_uuid
        assert roll.roll_type == RollType.ATTACK
        assert roll.results == 15
        assert roll.total == 25
        assert roll.bonus == 10
        assert roll.advantage_status == AdvantageStatus.NONE
        assert roll.critical_status == CriticalStatus.NONE
        assert roll.auto_hit_status == AutoHitStatus.NONE
        assert roll.source_entity_uuid == source_uuid
        assert roll.target_entity_uuid is None
        assert roll.attack_outcome is None

    def test_dice_roll_with_all_attributes(self, source_uuid, target_uuid):
        dice_uuid = uuid4()
        roll = DiceRoll(
            dice_uuid=dice_uuid,
            roll_type=RollType.DAMAGE,
            results=[6, 4],
            total=20,
            bonus=10,
            advantage_status=AdvantageStatus.ADVANTAGE,
            critical_status=CriticalStatus.AUTOCRIT,
            auto_hit_status=AutoHitStatus.AUTOHIT,
            source_entity_uuid=source_uuid,
            target_entity_uuid=target_uuid,
            attack_outcome=AttackOutcome.CRIT
        )

        assert isinstance(roll.roll_uuid, UUID)
        assert roll.dice_uuid == dice_uuid
        assert roll.roll_type == RollType.DAMAGE
        assert roll.results == [6, 4]
        assert roll.total == 20
        assert roll.bonus == 10
        assert roll.advantage_status == AdvantageStatus.ADVANTAGE
        assert roll.critical_status == CriticalStatus.AUTOCRIT
        assert roll.auto_hit_status == AutoHitStatus.AUTOHIT
        assert roll.source_entity_uuid == source_uuid
        assert roll.target_entity_uuid == target_uuid
        assert roll.attack_outcome == AttackOutcome.CRIT

    def test_dice_roll_registry(self, source_uuid):
        dice_uuid = uuid4()
        roll = DiceRoll(
            dice_uuid=dice_uuid,
            roll_type=RollType.ATTACK,
            results=15,
            total=25,
            bonus=10,
            advantage_status=AdvantageStatus.NONE,
            critical_status=CriticalStatus.NONE,
            auto_hit_status=AutoHitStatus.NONE,
            source_entity_uuid=source_uuid
        )

        retrieved_roll = DiceRoll.get(roll.roll_uuid)
        assert retrieved_roll == roll

class TestDice:
    def test_dice_initialization(self, sample_modifiable_value):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)

        assert isinstance(dice.uuid, UUID)
        assert dice.count == 1
        assert dice.value == 20
        assert dice.bonus == sample_modifiable_value
        assert dice.roll_type == RollType.ATTACK
        assert dice.attack_outcome is None

    def test_dice_with_all_attributes(self, sample_modifiable_value):
        dice = Dice(
            count=2,
            value=6,
            bonus=sample_modifiable_value,
            roll_type=RollType.DAMAGE,
            attack_outcome=AttackOutcome.HIT
        )

        assert dice.count == 2
        assert dice.value == 6
        assert dice.bonus == sample_modifiable_value
        assert dice.roll_type == RollType.DAMAGE
        assert dice.attack_outcome == AttackOutcome.HIT

    def test_dice_registry(self, sample_modifiable_value):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)

        retrieved_dice = Dice.get(dice.uuid)
        assert retrieved_dice == dice

    def test_dice_computed_fields(self, sample_modifiable_value):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)

        assert dice.source_entity_uuid == sample_modifiable_value.source_entity_uuid
        assert dice.target_entity_uuid == sample_modifiable_value.target_entity_uuid

    def test_dice_roll(self, sample_modifiable_value):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        roll = dice.roll

        assert isinstance(roll, DiceRoll)
        assert roll.dice_uuid == dice.uuid
        assert roll.roll_type == RollType.ATTACK
        assert isinstance(roll.results, int)
        assert 1 <= roll.results <= 20
        assert roll.total == roll.results + sample_modifiable_value.score
        assert roll.bonus == sample_modifiable_value.score
        assert roll.advantage_status == sample_modifiable_value.advantage
        assert roll.critical_status == sample_modifiable_value.critical
        assert roll.auto_hit_status == sample_modifiable_value.auto_hit
        assert roll.source_entity_uuid == dice.source_entity_uuid
        assert roll.target_entity_uuid == dice.target_entity_uuid

    def test_dice_roll_with_advantage(self, sample_modifiable_value):
        advantage_modifier = AdvantageModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=AdvantageStatus.ADVANTAGE)
        sample_modifiable_value.self_static.advantage_modifiers[advantage_modifier.uuid] = advantage_modifier
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        
        roll = dice.roll
        assert roll.advantage_status == AdvantageStatus.ADVANTAGE

    def test_dice_roll_damage(self, sample_modifiable_value):
        dice = Dice(count=2, value=6, bonus=sample_modifiable_value, roll_type=RollType.DAMAGE, attack_outcome=AttackOutcome.HIT)
        roll = dice.roll

        assert isinstance(roll.results, list)
        assert len(roll.results) == 2
        assert all(1 <= result <= 6 for result in roll.results)
        assert roll.total == sum(roll.results) + sample_modifiable_value.score

    def test_dice_roll_critical_damage(self, sample_modifiable_value):
        dice = Dice(count=2, value=6, bonus=sample_modifiable_value, roll_type=RollType.DAMAGE, attack_outcome=AttackOutcome.CRIT)
        roll = dice.roll

        assert isinstance(roll.results, list)
        assert len(roll.results) == 4  # Double dice on crit
        assert all(1 <= result <= 6 for result in roll.results)
        assert roll.total == sum(roll.results) + sample_modifiable_value.score

class TestEdgeCasesAndErrorHandling:
    def test_invalid_dice_count(self, sample_modifiable_value):
        with pytest.raises(ValueError):
            Dice(count=0, value=20, bonus=sample_modifiable_value)

    def test_invalid_dice_value(self, sample_modifiable_value):
        with pytest.raises(ValueError):
            Dice(count=1, value=0, bonus=sample_modifiable_value)

    def test_invalid_roll_type_dice_count(self, sample_modifiable_value):
        with pytest.raises(ValueError):
            Dice(count=2, value=20, bonus=sample_modifiable_value, roll_type=RollType.ATTACK)

    def test_invalid_attack_outcome_for_non_damage_roll(self, sample_modifiable_value):
        with pytest.raises(ValueError):
            Dice(count=1, value=20, bonus=sample_modifiable_value, roll_type=RollType.ATTACK, attack_outcome=AttackOutcome.HIT)

    def test_missing_attack_outcome_for_damage_roll(self, sample_modifiable_value):
        with pytest.raises(ValueError):
            Dice(count=2, value=6, bonus=sample_modifiable_value, roll_type=RollType.DAMAGE)

    def test_dice_roll_with_extreme_modifiers(self, sample_modifiable_value):
        extreme_modifier = NumericalModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=1000000)
        sample_modifiable_value.self_static.value_modifiers[extreme_modifier.uuid] = extreme_modifier
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        roll = dice.roll

        assert roll.total > 1000000

    def test_dice_roll_with_negative_modifiers(self, sample_modifiable_value):
        negative_modifier = NumericalModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=-100)
        sample_modifiable_value.self_static.value_modifiers[negative_modifier.uuid] = negative_modifier
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        roll = dice.roll

        assert roll.total < 0

    def test_multiple_advantage_disadvantage_modifiers(self, sample_modifiable_value):
        advantage_modifiers = [
            AdvantageModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=AdvantageStatus.ADVANTAGE),
            AdvantageModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=AdvantageStatus.DISADVANTAGE),
            AdvantageModifier(target_entity_uuid=sample_modifiable_value.source_entity_uuid, value=AdvantageStatus.ADVANTAGE)
        ]
        for modifier in advantage_modifiers:
            sample_modifiable_value.self_static.advantage_modifiers[modifier.uuid] = modifier
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        roll = dice.roll

        assert roll.advantage_status == AdvantageStatus.ADVANTAGE

    @pytest.mark.parametrize("roll_type", [RollType.ATTACK, RollType.SAVE, RollType.CHECK])
    def test_non_damage_roll_types(self, sample_modifiable_value, roll_type):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value, roll_type=roll_type)
        roll = dice.roll

        assert roll.roll_type == roll_type
        assert isinstance(roll.results, int)

    def test_dice_roll_determinism(self, sample_modifiable_value):
        dice = Dice(count=1, value=20, bonus=sample_modifiable_value)
        random.seed(42)
        roll1 = dice.roll
        random.seed(42)
        roll2 = dice.roll

        assert roll1.results == roll2.results

if __name__ == "__main__":
    pytest.main([__file__])
