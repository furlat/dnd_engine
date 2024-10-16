import pytest
from old_dnd.contextual import BaseValue, StaticModifier, ContextualModifier, ModifiableValue
from old_dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus, Size, MonsterType, Alignment
from old_dnd.statsblock import StatsBlock, MetaData
from old_dnd.logger import ValueOut, BonusTracker, AdvantageTracker, AutoHitTracker, CriticalTracker

# Mock StatsBlock for testing
class MockStatsBlock(StatsBlock):
    def __init__(self, id):
        super().__init__(meta=MetaData(id=id, name="Mock", size=Size.MEDIUM, type=MonsterType.HUMANOID, alignment=Alignment.TRUE_NEUTRAL))

@pytest.fixture
def mock_stats_block():
    return MockStatsBlock("test_id")

@pytest.fixture
def mock_target():
    return MockStatsBlock("target_id")

class TestBaseValue:
    def test_base_value_init(self):
        bv = BaseValue(name="test", base_value=10)
        assert bv.name == "test"
        assert bv.base_value == 10

    def test_base_value_apply(self):
        bv = BaseValue(name="test", base_value=10, min_value=5, max_value=15, advantage=AdvantageStatus.ADVANTAGE)
        result = bv.apply()
        assert isinstance(result, ValueOut)
        assert result.bonuses.bonuses == {"test": 10}
        assert result.min_constraints.bonuses == {"test": 5}
        assert result.max_constraints.bonuses == {"test": 15}
        assert result.advantage_tracker.active_sources == {"test": [AdvantageStatus.ADVANTAGE]}

class TestStaticModifier:
    def test_static_modifier_init(self):
        sm = StaticModifier(name="test")
        assert sm.name == "test"

    def test_static_modifier_add_bonus(self):
        sm = StaticModifier()
        sm.add_bonus("source1", 5)
        assert sm.bonuses == {"source1": 5}

    def test_static_modifier_apply(self):
        sm = StaticModifier(name="test")
        sm.add_bonus("source1", 5)
        sm.add_advantage_condition("source2", AdvantageStatus.ADVANTAGE)
        result = sm.apply()
        assert isinstance(result, ValueOut)
        assert result.bonuses.bonuses == {"source1": 5}
        assert result.advantage_tracker.active_sources == {"source2": [AdvantageStatus.ADVANTAGE]}

    def test_static_modifier_remove_effect(self):
        sm = StaticModifier()
        sm.add_bonus("source1", 5)
        sm.add_advantage_condition("source1", AdvantageStatus.ADVANTAGE)
        sm.remove_effect("source1")
        assert "source1" not in sm.bonuses
        assert "source1" not in sm.advantage_conditions

class TestContextualModifier:
    def test_contextual_modifier_init(self):
        cm = ContextualModifier(name="test")
        assert cm.name == "test"

    def test_contextual_modifier_add_bonus(self):
        cm = ContextualModifier()
        cm.add_bonus("source1", lambda sb, t, c: 5)
        assert "source1" in cm.bonuses

    def test_contextual_modifier_apply(self, mock_stats_block, mock_target):
        cm = ContextualModifier(name="test")
        cm.add_bonus("source1", lambda sb, t, c: 5)
        cm.add_advantage_condition("source2", lambda sb, t, c: AdvantageStatus.ADVANTAGE)
        result = cm.apply(mock_stats_block, mock_target)
        assert isinstance(result, ValueOut)
        assert result.bonuses.bonuses == {"source1": 5}
        assert result.advantage_tracker.active_sources == {"source2": [AdvantageStatus.ADVANTAGE]}
        assert result.source_entity_id == mock_stats_block.id
        assert result.target_entity_id == mock_target.id

    def test_contextual_modifier_remove_effect(self):
        cm = ContextualModifier()
        cm.add_bonus("source1", lambda sb, t, c: 5)
        cm.add_advantage_condition("source1", lambda sb, t, c: AdvantageStatus.ADVANTAGE)
        cm.remove_effect("source1")
        assert "source1" not in cm.bonuses
        assert "source1" not in cm.advantage_conditions

class TestModifiableValue:
    def test_modifiable_value_init(self):
        mv = ModifiableValue(name="test")
        assert mv.name == "test"

    def test_modifiable_value_update_base_value(self):
        mv = ModifiableValue()
        mv.update_base_value(15)
        assert mv.base_value.base_value == 15

    def test_modifiable_value_apply(self, mock_stats_block, mock_target):
        mv = ModifiableValue(name="test")
        mv.update_base_value(10)
        mv.self_static.add_bonus("static1", 5)
        mv.self_contextual.add_bonus("context1", lambda sb, t, c: 3)
        result = mv.apply(mock_stats_block, mock_target)
        assert isinstance(result, ValueOut)
        assert result.bonuses.bonuses == {"base": 10, "static1": 5, "context1": 3}

    def test_modifiable_value_apply_to_target(self, mock_stats_block, mock_target):
        mv = ModifiableValue(name="test")
        mv.target_static.add_bonus("target_static1", 2)
        mv.target_contextual.add_bonus("target_context1", lambda sb, t, c: 4)
        result = mv.apply_to_target(mock_stats_block, mock_target)
        assert isinstance(result, ValueOut)
        assert result.bonuses.bonuses == {"target_static1": 2, "target_context1": 4}

    def test_modifiable_value_remove_effect(self):
        mv = ModifiableValue()
        mv.self_static.add_bonus("effect1", 5)
        mv.target_contextual.add_bonus("effect1", lambda sb, t, c: 3)
        mv.remove_effect("effect1")
        assert "effect1" not in mv.self_static.bonuses
        assert "effect1" not in mv.target_contextual.bonuses

# Additional tests for edge cases and complex scenarios

def test_complex_modifiable_value_scenario(mock_stats_block, mock_target):
    mv = ModifiableValue(name="complex_test")
    mv.update_base_value(20)
    mv.self_static.add_bonus("static_bonus", 5)
    mv.self_static.add_min_constraint("static_min", 15)
    mv.self_static.add_max_constraint("static_max", 30)
    mv.self_contextual.add_bonus("context_bonus", lambda sb, t, c: 3 if c and c.get("condition") else 0)
    mv.self_contextual.add_advantage_condition("context_advantage", lambda sb, t, c: AdvantageStatus.ADVANTAGE if c and c.get("advantage") else AdvantageStatus.NONE)
    mv.target_static.add_bonus("target_static_bonus", -2)
    mv.target_contextual.add_critical_condition("target_context_critical", lambda sb, t, c: CriticalStatus.AUTOCRIT if c and c.get("critical") else CriticalStatus.NONE)

    context = {"condition": True, "advantage": True, "critical": True}
    result = mv.apply(mock_stats_block, mock_target, context)
    target_result = mv.apply_to_target(mock_stats_block, mock_target, context)

    combined_result = result.combine_with(target_result)

    # Test bonuses
    assert combined_result.bonuses.bonuses == {
        "base": 20,
        "static_bonus": 5,
        "context_bonus": 3,
        "target_static_bonus": -2
    }
    assert combined_result.bonuses.total_bonus == 26

    # Test constraints
    assert combined_result.min_constraints.bonuses == {"static_min": 15}
    assert combined_result.max_constraints.bonuses == {"static_max": 30}

    # Test advantage
    assert combined_result.advantage_tracker.active_sources == {
        "base": [AdvantageStatus.NONE],
        "context_advantage": [AdvantageStatus.ADVANTAGE]
    }
    assert combined_result.advantage_tracker.status == AdvantageStatus.ADVANTAGE

    # Test critical
    assert combined_result.critical_tracker.critical_statuses == {
        "base": [CriticalStatus.NONE],
        "target_context_critical": [CriticalStatus.AUTOCRIT]
    }
    assert combined_result.critical_tracker.status == CriticalStatus.AUTOCRIT

    # Test auto hit (should be NONE as we didn't set any)
    assert combined_result.auto_hit_tracker.auto_hit_statuses == {"base": [AutoHitStatus.NONE]}
    assert combined_result.auto_hit_tracker.status == AutoHitStatus.NONE

    # Test entity IDs
    assert combined_result.source_entity_id == mock_stats_block.id
    assert combined_result.target_entity_id == mock_target.id

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__])
