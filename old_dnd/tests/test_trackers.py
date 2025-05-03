import pytest
from old_dnd.trackers import AdvantageTracker, CriticalTracker, AutoHitTracker, BonusTracker
from old_dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus

class TestAdvantageTracker:
    def test_advantage_tracker_init(self):
        tracker = AdvantageTracker()
        assert tracker.active_sources == {}
        assert tracker.counter == 0
        assert tracker.status == AdvantageStatus.NONE

    def test_advantage_tracker_add(self):
        tracker = AdvantageTracker()
        tracker.add(AdvantageStatus.ADVANTAGE, "source1")
        assert tracker.active_sources == {"source1": [AdvantageStatus.ADVANTAGE]}
        assert tracker.counter == 1
        assert tracker.status == AdvantageStatus.ADVANTAGE

    def test_advantage_tracker_combine(self):
        tracker1 = AdvantageTracker()
        tracker1.add(AdvantageStatus.ADVANTAGE, "source1")
        tracker2 = AdvantageTracker()
        tracker2.add(AdvantageStatus.DISADVANTAGE, "source2")
        combined = tracker1.combine_with(tracker2)
        assert combined.active_sources == {
            "source1": [AdvantageStatus.ADVANTAGE],
            "source2": [AdvantageStatus.DISADVANTAGE]
        }
        assert combined.counter == 0
        assert combined.status == AdvantageStatus.NONE

class TestCriticalTracker:
    def test_critical_tracker_init(self):
        tracker = CriticalTracker()
        assert tracker.critical_statuses == {}
        assert tracker.status == CriticalStatus.NONE

    def test_critical_tracker_add(self):
        tracker = CriticalTracker()
        tracker.add(CriticalStatus.AUTOCRIT, "source1")
        assert tracker.critical_statuses == {"source1": [CriticalStatus.AUTOCRIT]}
        assert tracker.status == CriticalStatus.AUTOCRIT

    def test_critical_tracker_combine(self):
        tracker1 = CriticalTracker()
        tracker1.add(CriticalStatus.AUTOCRIT, "source1")
        tracker2 = CriticalTracker()
        tracker2.add(CriticalStatus.NOCRIT, "source2")
        combined = tracker1.combine_with(tracker2)
        assert combined.critical_statuses == {
            "source1": [CriticalStatus.AUTOCRIT],
            "source2": [CriticalStatus.NOCRIT]
        }
        assert combined.status == CriticalStatus.NOCRIT

class TestAutoHitTracker:
    def test_auto_hit_tracker_init(self):
        tracker = AutoHitTracker()
        assert tracker.auto_hit_statuses == {}
        assert tracker.status == AutoHitStatus.NONE

    def test_auto_hit_tracker_add(self):
        tracker = AutoHitTracker()
        tracker.add(AutoHitStatus.AUTOHIT, "source1")
        assert tracker.auto_hit_statuses == {"source1": [AutoHitStatus.AUTOHIT]}
        assert tracker.status == AutoHitStatus.AUTOHIT

    def test_auto_hit_tracker_combine(self):
        tracker1 = AutoHitTracker()
        tracker1.add(AutoHitStatus.AUTOHIT, "source1")
        tracker2 = AutoHitTracker()
        tracker2.add(AutoHitStatus.AUTOMISS, "source2")
        combined = tracker1.combine_with(tracker2)
        assert combined.auto_hit_statuses == {
            "source1": [AutoHitStatus.AUTOHIT],
            "source2": [AutoHitStatus.AUTOMISS]
        }
        assert combined.status == AutoHitStatus.AUTOMISS

class TestBonusTracker:
    def test_bonus_tracker_init(self):
        tracker = BonusTracker()
        assert tracker.bonuses == {}
        assert tracker.total_bonus is None

    def test_bonus_tracker_add(self):
        tracker = BonusTracker()
        tracker.add(5, "source1")
        assert tracker.bonuses == {"source1": 5}
        assert tracker.total_bonus == 5

    def test_bonus_tracker_combine(self):
        tracker1 = BonusTracker()
        tracker1.add(5, "source1")
        tracker2 = BonusTracker()
        tracker2.add(3, "source2")
        combined = tracker1.combine_with(tracker2)
        assert combined.bonuses == {"source1": 5, "source2": 3}
        assert combined.total_bonus == 8

    def test_bonus_tracker_combine_with_converter(self):
        tracker1 = BonusTracker()
        tracker1.add(5, "source1")
        tracker2 = BonusTracker()
        tracker2.add(3, "source2")
        combined = tracker1.combine_with(tracker2, bonus_converter=lambda x: x * 2)
        assert combined.bonuses == {"source1": 5, "source2": 6}
        assert combined.total_bonus == 11

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__])
