"""Disclosed native values retain their meaning in controller decision rows."""

from uuid import uuid4

import pytest

from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionBucket,
    OutcomeAdvantage,
    OutcomeApplicationScope,
    OutcomeResolution,
)
from dnd.ai.runtime.decision_epoch import _build_affordance_rows_from_actions
from dnd.core.base_actions import (
    ActionAvailabilityStatus, ActionCategory,
    ActionOutcomeProfile as NativeOutcome,
    AvailableActionInfo, AvailableTarget, DamageRollProfile,
    OpportunityAttackExposure, OutcomeApplicationScope as NativeScope,
    OutcomeResolution as NativeResolution, TargetType,
)
from dnd.core.modifiers import AdvantageStatus


def controller_row(source: AvailableActionInfo, bucket: ActionBucket = "entity_actions") -> ActionAffordance:
    """Exercise the discovery-value to decision-row boundary without live rules."""
    return _build_affordance_rows_from_actions(bucket, [source], {})[0]


@pytest.mark.parametrize("profile", [
    *[
        NativeOutcome(
            effect_id="attack.test", resolution=NativeResolution.ATTACK_ROLL,
            applications=2, advantage=advantage, attack_bonus=7,
            critical_threshold=19, critical_extra_dice=1,
            damage_rolls=(
                DamageRollProfile(dice_count=2, die_size=6, flat_bonus=3, damage_type="Fire"),
                DamageRollProfile(dice_count=1, die_size=4, damage_type="Cold"),
            ),
        )
        for advantage in (AdvantageStatus.ADVANTAGE, AdvantageStatus.DISADVANTAGE)
    ],
    NativeOutcome(
        effect_id="save.test", resolution=NativeResolution.SAVING_THROW,
        application_scope=NativeScope.EACH_AFFECTED_ENTITY,
        save_dc=16, save_ability="dexterity", half_damage_on_save=True,
        damage_rolls=(DamageRollProfile(dice_count=3, die_size=8, damage_type="Lightning"),),
    ),
    NativeOutcome(
        effect_id="automatic.test", resolution=NativeResolution.AUTOMATIC,
        applications=3,
        damage_rolls=(DamageRollProfile(dice_count=1, die_size=4, flat_bonus=1, damage_type="Force"),),
    ),
    NativeOutcome(resolution=NativeResolution.UNKNOWN),
], ids=["advantage", "disadvantage", "save", "automatic", "unknown"])
def test_disclosed_outcome_values_survive_decision_projection(profile: NativeOutcome) -> None:
    source = AvailableActionInfo(
        template_name="Outcome example", display_name="Outcome example",
        semantic_key="test.outcome", cost_type="actions",
        behavior_id="action.test.outcome", provided_by_id="action.test.outcome",
        origin_root_id=None,
        target_type=TargetType.ENTITY, action_category=ActionCategory.ATTACK,
        availability_status=ActionAvailabilityStatus.AVAILABLE, can_afford=True,
        valid_targets=[AvailableTarget(index=0, target_uuid=uuid4())],
        outcome_profile=profile,
    )
    projected = controller_row(source).outcome_profile
    assert projected is not None
    assert projected.model_dump(mode="json") == profile.model_dump(mode="json")
    assert projected.resolution is OutcomeResolution(profile.resolution.value)
    assert projected.application_scope is OutcomeApplicationScope(profile.application_scope.value)
    assert projected.advantage is OutcomeAdvantage(profile.advantage.value)

    # Equal native values and a later changed value must both project correctly.
    source.outcome_profile = profile.model_copy()
    assert controller_row(source).outcome_profile == projected
    source.outcome_profile = profile.model_copy(update={"applications": profile.applications + 1})
    changed = controller_row(source).outcome_profile
    assert changed is not None and changed.applications == profile.applications + 1
    assert projected.applications == profile.applications


def test_normal_and_safe_route_threats_are_detached_controller_values() -> None:
    normal = OpportunityAttackExposure(
        reactor_uuid=uuid4(), reactor_name="Near guard",
        from_position=(1, 1), to_position=(2, 1),
    )
    safe = OpportunityAttackExposure(
        reactor_uuid=uuid4(), reactor_name="Far guard",
        from_position=(1, 2), to_position=(2, 2),
    )
    expected_normal, expected_safe = normal.model_dump(mode="json"), safe.model_dump(mode="json")
    target = AvailableTarget(
        index=0, position=(3, 1), path=[(1, 1), (2, 1), (3, 1)],
        safe_path=[(1, 1), (1, 2), (2, 2), (3, 2), (3, 1)],
        opportunity_attack_exposures=[normal], safe_path_opportunity_attack_exposures=[safe],
    )
    source = AvailableActionInfo(
        template_name="Move", display_name="Move", semantic_key="action.move",
        cost_type="movement",
        behavior_id="action.move", provided_by_id="action.move", origin_root_id=None,
        target_type=TargetType.POSITION_PATH, action_category=ActionCategory.MOVEMENT,
        availability_status=ActionAvailabilityStatus.AVAILABLE, can_afford=True,
        valid_targets=[target],
    )
    row = controller_row(source, "position_actions")
    assert row.outcome_profile is None
    projected = row.targets[0]
    assert projected.opportunity_attack_exposures[0].reactor_uuid == str(normal.reactor_uuid)
    assert projected.safe_path_opportunity_attack_exposures[0].reactor_uuid == str(safe.reactor_uuid)

    normal.reactor_name = "Changed guard"
    normal.from_position = (8, 8)
    safe.reactor_uuid = uuid4()
    target.opportunity_attack_exposures.clear()
    target.safe_path_opportunity_attack_exposures.clear()
    assert projected.opportunity_attack_exposures[0].model_dump(mode="json") == expected_normal
    assert projected.safe_path_opportunity_attack_exposures[0].model_dump(mode="json") == expected_safe
