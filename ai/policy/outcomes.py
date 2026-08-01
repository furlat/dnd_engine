"""Exact discrete outcome estimates over disclosed subjective action models."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Sequence

from ai.knowledge.models import TargetEffectBlockHypothesis
from dnd.ai.contracts.observation import ObservationEntityFact
from ai.policy.contracts import EffectBlockHypothesisEvidence
from dnd.ai.contracts.control import (
    ActionOutcomeProfile,
    DamageRollProfile,
    OutcomeResolution,
)
from dnd.core.roll_types import AdvantageStatus
from dnd.ai.contracts.semantics import CapabilityOutcomeAdjustment


DamageDistribution = dict[int, float]
EffectBlockHypothesisKey = tuple[
    str,
    str,
    int,
    int,
    int,
    int,
    tuple[int, ...],
    float,
]
_MAX_SHARED_DAMAGE_ESTIMATES = 4096


@dataclass(frozen=True)
class SubjectiveEffectBlocker:
    """Visible typed protection matched to one modeled effect."""

    protection_id: str
    effect_id: str
    source_condition_semantic_key: Optional[str] = None


@dataclass(frozen=True)
class _SubjectiveDefenseState:
    """Disclosed target facts that change one application distribution."""

    attack_ac: Optional[int]
    damage_multipliers: tuple[float, ...]
    effect_blockers: tuple[SubjectiveEffectBlocker, ...]


@dataclass(frozen=True)
class SubjectiveDamageEstimate:
    """Damage distribution summary bounded by disclosed subjective facts."""

    expected_raw_damage: float
    expected_hp_loss: float
    defeat_probability: float
    nonzero_probability: float
    guaranteed_zero: bool
    blocker_evidence: tuple[SubjectiveEffectBlocker, ...] = tuple()
    effect_block_hypothesis: Optional[EffectBlockHypothesisEvidence] = None
    model_scope: str = "actor_baseline+known_target"


@dataclass(frozen=True)
class _CompiledDamageDistribution:
    """Canonical immutable distribution reused across target summaries."""

    items: tuple[tuple[int, float], ...]

    def summarize(
        self,
        known_target_hp: Optional[int],
        model_scope: str,
        blocker_evidence: tuple[SubjectiveEffectBlocker, ...],
        effect_block_hypothesis: Optional[EffectBlockHypothesisEvidence],
    ) -> SubjectiveDamageEstimate:
        """Return an HP-capped summary with stable historical arithmetic."""
        return _cached_distribution_summary(
            self.items,
            known_target_hp,
            model_scope,
            blocker_evidence=blocker_evidence,
            effect_block_hypothesis_key=_effect_block_hypothesis_key(
                effect_block_hypothesis
            ),
        )


@dataclass
class DamageOutcomeWorkspace:
    """Decision-scoped exact distributions shared across candidate allocations."""

    shared_value_cache: bool = False
    _applications: dict[
        tuple[object, ...],
        Optional[tuple[DamageDistribution, str, tuple[SubjectiveEffectBlocker, ...]]],
    ] = field(default_factory=dict)
    _totals: dict[
        tuple[object, ...],
        list[DamageDistribution],
    ] = field(default_factory=dict)
    _raw_damage: dict[tuple[object, ...], DamageDistribution] = field(default_factory=dict)
    _compiled_totals: dict[
        tuple[object, ...],
        _CompiledDamageDistribution,
    ] = field(default_factory=dict)
    _application_keys: dict[int, tuple[object, ...]] = field(default_factory=dict)
    _target_outcome_keys: dict[int, tuple[object, ...]] = field(default_factory=dict)
    _defense_states: dict[
        tuple[tuple[object, ...], int],
        _SubjectiveDefenseState,
    ] = field(default_factory=dict)

    def estimate(
        self,
        profile: ActionOutcomeProfile,
        target: ObservationEntityFact,
        *,
        applications: int,
        effect_block_hypothesis: Optional[TargetEffectBlockHypothesis] = None,
    ) -> Optional[SubjectiveDamageEstimate]:
        """Return an exact estimate while extending cached convolutions."""
        if applications <= 0 or not profile.damage_rolls:
            return None
        hypothesis_evidence = _matching_effect_block_hypothesis(
            profile,
            target,
            effect_block_hypothesis,
        )
        profile_identity = id(profile)
        application_key = self._application_keys.get(profile_identity)
        if application_key is None:
            application_key = outcome_application_key(profile)
            self._application_keys[profile_identity] = application_key
        target_identity = id(target)
        target_outcome_key = self._target_outcome_keys.get(target_identity)
        if target_outcome_key is None:
            target_outcome_key = _subjective_target_outcome_key(target)
            self._target_outcome_keys[target_identity] = target_outcome_key
        shared_key = (
            application_key,
            applications,
            target_outcome_key,
            _effect_block_hypothesis_key(hypothesis_evidence),
        )
        if self.shared_value_cache and shared_key in _SHARED_DAMAGE_ESTIMATES:
            return _SHARED_DAMAGE_ESTIMATES[shared_key]
        defense_key = (application_key, target_identity)
        defense_state = self._defense_states.get(defense_key)
        if defense_state is None:
            defense_state = _subjective_defense_state(profile, target)
            self._defense_states[defense_key] = defense_state
        key = (application_key, defense_state)
        if key not in self._applications:
            self._applications[key] = _application_distribution(
                profile,
                target,
                self,
                defense_state,
            )
        prepared = self._applications[key]
        if prepared is None:
            return None
        application, model_scope, blocker_evidence = prepared
        totals = self._totals.setdefault(key, [{0: 1.0}])
        while len(totals) <= applications:
            totals.append(_convolve(totals[-1], application))
        total = totals[applications]
        hypothesis_key = _effect_block_hypothesis_key(hypothesis_evidence)
        if blocker_evidence:
            hypothesis_evidence = None
            hypothesis_key = None
        elif hypothesis_evidence is not None:
            total = _mixture_distribution((
                ({0: 1.0}, hypothesis_evidence.block_probability),
                (total, 1.0 - hypothesis_evidence.block_probability),
            ))
            model_scope += "+observed_effect_block_hypothesis"
        compiled_key = (key, applications, hypothesis_key)
        compiled = self._compiled_totals.get(compiled_key)
        if compiled is None:
            compiled = _compile_damage_distribution(total)
            self._compiled_totals[compiled_key] = compiled
        estimate = compiled.summarize(
            target.hp,
            model_scope,
            blocker_evidence,
            hypothesis_evidence,
        )
        if self.shared_value_cache:
            if len(_SHARED_DAMAGE_ESTIMATES) >= _MAX_SHARED_DAMAGE_ESTIMATES:
                _SHARED_DAMAGE_ESTIMATES.pop(next(iter(_SHARED_DAMAGE_ESTIMATES)))
            _SHARED_DAMAGE_ESTIMATES[shared_key] = estimate
        return estimate

    def damage_distribution(
        self,
        profiles: Sequence[DamageRollProfile],
        target: ObservationEntityFact,
        *,
        critical: bool,
        critical_extra_dice: int,
    ) -> DamageDistribution:
        """Return raw typed damage shared by equal known affinity profiles."""
        key = (
            tuple(
                (
                    profile.dice_count,
                    profile.die_size,
                    profile.flat_bonus,
                    profile.damage_type,
                    _known_damage_multiplier(profile.damage_type, target),
                )
                for profile in profiles
            ),
            critical,
            critical_extra_dice,
        )
        if key not in self._raw_damage:
            self._raw_damage[key] = _damage_distribution(
                profiles,
                target,
                critical=critical,
                critical_extra_dice=critical_extra_dice,
            )
        return self._raw_damage[key]


def estimate_damage_outcome(
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
    *,
    applications: Optional[int] = None,
    workspace: Optional[DamageOutcomeWorkspace] = None,
    effect_block_hypothesis: Optional[TargetEffectBlockHypothesis] = None,
) -> Optional[SubjectiveDamageEstimate]:
    """Derive an exact finite distribution from an action model and known target.

    Args:
        profile: Actor-baseline action model disclosed by the engine rule.
        target: Subjective target fact. Only populated fields are consumed.
        applications: Optional allocation-specific repetition count.
        workspace: Optional decision-scoped cache for repeated allocations.
        effect_block_hypothesis: Bounded subjective evidence for this exact target/effect pair.

    Returns:
        Exact estimate over disclosed inputs, or ``None`` when a required input
        such as target AC is unknown. Undisclosed defenses are never guessed.
    """
    repetitions = applications if applications is not None else profile.applications
    active_workspace = workspace or DamageOutcomeWorkspace()
    return active_workspace.estimate(
        profile,
        target,
        applications=repetitions,
        effect_block_hypothesis=effect_block_hypothesis,
    )


def _subjective_target_outcome_key(
    target: ObservationEntityFact,
) -> tuple[object, ...]:
    """Return exactly the disclosed target fields consumed by outcome math."""
    protections = tuple(sorted(
        (
            protection.protection_id,
            tuple(sorted(protection.blocked_effect_ids)),
            protection.source_condition_semantic_key,
        )
        for protection in target.effect_protections or tuple()
    ))
    return (
        target.hp,
        target.ac,
        tuple(sorted(value.casefold() for value in target.damage_vulnerabilities)),
        tuple(sorted(value.casefold() for value in target.damage_resistances)),
        tuple(sorted(value.casefold() for value in target.damage_immunities)),
        protections,
    )


_SHARED_DAMAGE_ESTIMATES: dict[
    tuple[object, ...],
    Optional[SubjectiveDamageEstimate],
] = {}


def project_outcome_profile(
    profile: ActionOutcomeProfile,
    adjustments: Sequence[CapabilityOutcomeAdjustment],
) -> ActionOutcomeProfile:
    """Apply typed temporary adjustments to one non-executable outcome model.

    Advantage and disadvantage are represented as a signed bounded state, so
    opposing adjustments cancel and repeated equal adjustments do not stack.
    The projection grants no legality and exists only for routine comparison.
    """
    advantage_step = {
        AdvantageStatus.DISADVANTAGE: -1,
        AdvantageStatus.NONE: 0,
        AdvantageStatus.ADVANTAGE: 1,
    }[profile.advantage]
    for adjustment in adjustments:
        advantage_step = max(
            -1,
            min(1, advantage_step + adjustment.advantage_step_delta),
        )
    advantage = {
        -1: AdvantageStatus.DISADVANTAGE,
        0: AdvantageStatus.NONE,
        1: AdvantageStatus.ADVANTAGE,
    }[advantage_step]
    return profile.model_copy(update={"advantage": advantage})


def _application_distribution(
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
    workspace: DamageOutcomeWorkspace,
    defense_state: _SubjectiveDefenseState,
) -> Optional[
    tuple[DamageDistribution, str, tuple[SubjectiveEffectBlocker, ...]]
]:
    """Build one action/target application distribution from disclosed facts."""
    blockers = defense_state.effect_blockers
    if blockers:
        return (
            {0: 1.0},
            "actor_baseline+known_target+visible_effect_protection",
            blockers,
        )
    normal_damage = workspace.damage_distribution(
        profile.damage_rolls,
        target,
        critical=False,
        critical_extra_dice=0,
    )
    model_scope = "actor_baseline+known_target"
    if profile.resolution is OutcomeResolution.ATTACK_ROLL:
        critical_damage = workspace.damage_distribution(
            profile.damage_rolls,
            target,
            critical=True,
            critical_extra_dice=profile.critical_extra_dice,
        )
        damage_is_guaranteed_zero = (
            _distribution_is_guaranteed_zero(normal_damage)
            and _distribution_is_guaranteed_zero(critical_damage)
        )
    else:
        critical_damage = None
        damage_is_guaranteed_zero = _distribution_is_guaranteed_zero(normal_damage)
    if damage_is_guaranteed_zero:
        return (
            {0: 1.0},
            "actor_baseline+known_target+known_damage_affinity",
            tuple(),
        )
    if profile.resolution is OutcomeResolution.AUTOMATIC:
        application = normal_damage
    elif profile.resolution is OutcomeResolution.ATTACK_ROLL:
        if profile.attack_bonus is None or defense_state.attack_ac is None:
            return None
        miss, hit, critical = _attack_outcome_probabilities(
            attack_bonus=profile.attack_bonus,
            target_ac=defense_state.attack_ac,
            advantage=profile.advantage,
            critical_threshold=profile.critical_threshold,
        )
        assert critical_damage is not None
        application = _mixture_distribution(
            (({0: 1.0}, miss), (normal_damage, hit), (critical_damage, critical))
        )
    elif profile.resolution is OutcomeResolution.SAVING_THROW:
        if not profile.half_damage_on_save:
            return None
        application = _floor_scaled_distribution(normal_damage, 0.5)
        model_scope = "actor_baseline+known_target+successful_save_lower_bound"
    else:
        return None
    return application, model_scope, tuple()


def _subjective_defense_state(
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
) -> _SubjectiveDefenseState:
    """Project only disclosed target facts consumed by one application."""
    return _SubjectiveDefenseState(
        attack_ac=(
            target.ac
            if profile.resolution is OutcomeResolution.ATTACK_ROLL
            else None
        ),
        damage_multipliers=tuple(
            _known_damage_multiplier(roll.damage_type, target)
            for roll in profile.damage_rolls
        ),
        effect_blockers=_matching_effect_blockers(profile, target),
    )


def _distribution_is_guaranteed_zero(distribution: DamageDistribution) -> bool:
    """Return whether every disclosed damage outcome is exactly zero."""
    return bool(distribution) and all(
        damage == 0
        for damage, probability in distribution.items()
        if probability > 0
    )


def _compile_damage_distribution(
    distribution: DamageDistribution,
) -> _CompiledDamageDistribution:
    """Compile one exact distribution into its canonical immutable key."""
    return _CompiledDamageDistribution(
        items=tuple(sorted(distribution.items())),
    )


@lru_cache(maxsize=4096)
def _cached_distribution_summary(
    total_items: tuple[tuple[int, float], ...],
    known_target_hp: Optional[int],
    model_scope: str,
    blocker_evidence: tuple[SubjectiveEffectBlocker, ...],
    effect_block_hypothesis_key: Optional[EffectBlockHypothesisKey],
) -> SubjectiveDamageEstimate:
    """Return one immutable HP-capped summary keyed by disclosed values."""
    expected_raw = sum(
        damage * probability
        for damage, probability in total_items
    )
    if known_target_hp is None:
        expected_hp_loss = expected_raw
        defeat_probability = 0.0
    else:
        known_hp = max(0, known_target_hp)
        expected_hp_loss = sum(
            min(damage, known_hp) * probability
            for damage, probability in total_items
        )
        defeat_probability = 1.0 if known_hp == 0 else sum(
            probability
            for damage, probability in total_items
            if damage >= known_hp
        )
    zero_probability = next(
        (probability for damage, probability in total_items if damage == 0),
        0.0,
    )
    nonzero_probability = max(0.0, 1.0 - zero_probability)
    return SubjectiveDamageEstimate(
        expected_raw_damage=expected_raw,
        expected_hp_loss=expected_hp_loss,
        defeat_probability=defeat_probability,
        nonzero_probability=nonzero_probability,
        guaranteed_zero=nonzero_probability == 0.0,
        blocker_evidence=blocker_evidence,
        effect_block_hypothesis=_effect_block_hypothesis_from_key(
            effect_block_hypothesis_key,
        ),
        model_scope=model_scope,
    )


def _effect_block_hypothesis_key(
    evidence: Optional[EffectBlockHypothesisEvidence],
) -> Optional[EffectBlockHypothesisKey]:
    """Return a hashable cache key for typed observed-block evidence."""
    if evidence is None:
        return None
    return (
        evidence.target_uuid,
        evidence.effect_id,
        evidence.blocked_episodes,
        evidence.total_episodes,
        evidence.blocked_applications,
        evidence.total_applications,
        evidence.episode_log_indices,
        evidence.block_probability,
    )


def _effect_block_hypothesis_from_key(
    key: Optional[EffectBlockHypothesisKey],
) -> Optional[EffectBlockHypothesisEvidence]:
    """Restore inspectable evidence after cached distribution summarization."""
    if key is None:
        return None
    return EffectBlockHypothesisEvidence.model_construct(
        target_uuid=key[0],
        effect_id=key[1],
        blocked_episodes=key[2],
        total_episodes=key[3],
        blocked_applications=key[4],
        total_applications=key[5],
        episode_log_indices=key[6],
        block_probability=key[7],
    )


def _matching_effect_block_hypothesis(
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
    hypothesis: Optional[TargetEffectBlockHypothesis],
) -> Optional[EffectBlockHypothesisEvidence]:
    """Return exact typed historical evidence without generalizing identities."""
    if (
        hypothesis is None
        or profile.effect_id is None
        or hypothesis.effect_id != profile.effect_id
        or hypothesis.target_uuid != target.uuid
    ):
        return None
    return EffectBlockHypothesisEvidence.model_construct(
        target_uuid=hypothesis.target_uuid,
        effect_id=hypothesis.effect_id,
        blocked_episodes=hypothesis.blocked_episodes,
        total_episodes=hypothesis.total_episodes,
        blocked_applications=hypothesis.blocked_applications,
        total_applications=hypothesis.total_applications,
        episode_log_indices=hypothesis.episode_log_indices,
        block_probability=hypothesis.block_probability,
    )


def _matching_effect_blockers(
    profile: ActionOutcomeProfile,
    target: ObservationEntityFact,
) -> tuple[SubjectiveEffectBlocker, ...]:
    """Return visible typed protections matching the modeled effect identity."""
    if profile.effect_id is None or target.effect_protections is None:
        return tuple()
    return tuple(
        SubjectiveEffectBlocker(
            protection_id=protection.protection_id,
            effect_id=profile.effect_id,
            source_condition_semantic_key=protection.source_condition_semantic_key,
        )
        for protection in target.effect_protections
        if profile.effect_id in protection.blocked_effect_ids
    )


def outcome_profile_key(profile: ActionOutcomeProfile) -> tuple[object, ...]:
    """Return a hashable value key for one disclosed outcome model."""
    return (
        profile.effect_id,
        profile.resolution.value,
        profile.applications,
        profile.application_scope.value,
        tuple(
            (roll.dice_count, roll.die_size, roll.flat_bonus, roll.damage_type)
            for roll in profile.damage_rolls
        ),
        profile.attack_bonus,
        profile.advantage.value,
        profile.critical_threshold,
        profile.critical_extra_dice,
        profile.save_dc,
        profile.save_ability,
        profile.half_damage_on_save,
        profile.scope,
    )


def outcome_application_key(profile: ActionOutcomeProfile) -> tuple[object, ...]:
    """Return the exact fields consumed by one application distribution.

    Allocation scope and total application count describe how an action uses
    this distribution; they do not change one projectile, ray, dart, or area
    application. Keeping that distinction explicit lets slot-scaled variants
    share exact convolution work without conflating their action contracts.
    """
    return (
        profile.effect_id,
        profile.resolution.value,
        tuple(
            (roll.dice_count, roll.die_size, roll.flat_bonus, roll.damage_type)
            for roll in profile.damage_rolls
        ),
        profile.attack_bonus,
        profile.advantage.value,
        profile.critical_threshold,
        profile.critical_extra_dice,
        profile.half_damage_on_save,
    )


def _floor_scaled_distribution(
    distribution: DamageDistribution,
    multiplier: float,
) -> DamageDistribution:
    """Scale integer damage outcomes with the engine's floor rounding."""
    return dict(_cached_floor_scaled_distribution_items(
        tuple(sorted(distribution.items())),
        multiplier,
    ))


@lru_cache(maxsize=2048)
def _cached_floor_scaled_distribution_items(
    distribution_items: tuple[tuple[int, float], ...],
    multiplier: float,
) -> tuple[tuple[int, float], ...]:
    """Return immutable floor-scaled outcomes keyed by disclosed values."""
    adjusted: DamageDistribution = {}
    for damage, probability in distribution_items:
        value = max(0, int(damage * multiplier))
        adjusted[value] = adjusted.get(value, 0.0) + probability
    return tuple(sorted(adjusted.items()))


@lru_cache(maxsize=512)
def _attack_outcome_probabilities(
    *,
    attack_bonus: int,
    target_ac: int,
    advantage: str,
    critical_threshold: int,
) -> tuple[float, float, float]:
    """Enumerate d20 faces using the engine's hit and critical ordering."""
    label = advantage.casefold()
    if label == "advantage":
        selected_faces = [(max(first, second), 1.0 / 400.0) for first in range(1, 21) for second in range(1, 21)]
    elif label == "disadvantage":
        selected_faces = [(min(first, second), 1.0 / 400.0) for first in range(1, 21) for second in range(1, 21)]
    else:
        selected_faces = [(face, 1.0 / 20.0) for face in range(1, 21)]

    miss = hit = critical = 0.0
    for natural, probability in selected_faces:
        if natural == 1:
            miss += probability
        elif natural == 20:
            critical += probability
        elif natural + attack_bonus < target_ac:
            miss += probability
        elif natural >= critical_threshold:
            critical += probability
        else:
            hit += probability
    return miss, hit, critical


def _damage_distribution(
    profiles: Sequence[DamageRollProfile],
    target: ObservationEntityFact,
    *,
    critical: bool,
    critical_extra_dice: int,
) -> DamageDistribution:
    """Combine typed damage components after known target affinities."""
    profile_values = tuple(
        (
            profile.dice_count,
            profile.die_size,
            profile.flat_bonus,
            _known_damage_multiplier(profile.damage_type, target),
        )
        for profile in profiles
    )
    return dict(_cached_damage_distribution_items(
        profile_values,
        critical,
        critical_extra_dice,
    ))


@lru_cache(maxsize=1024)
def _cached_damage_distribution_items(
    profile_values: tuple[tuple[int, int, int, float], ...],
    critical: bool,
    critical_extra_dice: int,
) -> tuple[tuple[int, float], ...]:
    """Return immutable exact damage outcomes keyed only by disclosed values."""
    total = {0: 1.0}
    for base_dice_count, die_size, flat_bonus, multiplier in profile_values:
        dice_count = base_dice_count * (2 if critical else 1)
        if critical:
            dice_count += critical_extra_dice
        component = _dice_distribution(dice_count, die_size, flat_bonus)
        adjusted: DamageDistribution = {}
        for damage, probability in component.items():
            value = max(0, int(damage * multiplier))
            adjusted[value] = adjusted.get(value, 0.0) + probability
        total = _convolve(total, adjusted)
    return tuple(sorted(total.items()))


def _known_damage_multiplier(damage_type: str, target: ObservationEntityFact) -> float:
    """Return only affinities explicitly present in the subjective target fact."""
    normalized = damage_type.casefold()
    if normalized in {value.casefold() for value in target.damage_immunities}:
        return 0.0
    if normalized in {value.casefold() for value in target.damage_resistances}:
        return 0.5
    if normalized in {value.casefold() for value in target.damage_vulnerabilities}:
        return 2.0
    return 1.0


def _dice_distribution(count: int, sides: int, bonus: int) -> DamageDistribution:
    """Return the exact distribution for ``count`` d ``sides`` plus ``bonus``."""
    return dict(_cached_dice_distribution_items(count, sides, bonus))


@lru_cache(maxsize=512)
def _cached_dice_distribution_items(
    count: int,
    sides: int,
    bonus: int,
) -> tuple[tuple[int, float], ...]:
    """Return immutable dice outcomes keyed only by the roll expression."""
    distribution = _cached_dice_sum_items(count, sides)
    if bonus == 0:
        return distribution
    return tuple(
        (value + bonus, probability)
        for value, probability in distribution
    )


@lru_cache(maxsize=512)
def _cached_dice_sum_items(
    count: int,
    sides: int,
) -> tuple[tuple[int, float], ...]:
    """Extend one exact dice kernel from the preceding dice count."""
    if count <= 0:
        return ((0, 1.0),)
    prior = dict(_cached_dice_sum_items(count - 1, sides))
    face_probability = 1.0 / sides
    return tuple(_convolve(
        prior,
        {face: face_probability for face in range(1, sides + 1)},
    ).items())


def _convolve(left: DamageDistribution, right: DamageDistribution) -> DamageDistribution:
    """Convolve two finite integer-valued probability distributions."""
    return dict(_cached_convolution_items(
        tuple(sorted(left.items())),
        tuple(sorted(right.items())),
    ))


@lru_cache(maxsize=4096)
def _cached_convolution_items(
    left_items: tuple[tuple[int, float], ...],
    right_items: tuple[tuple[int, float], ...],
) -> tuple[tuple[int, float], ...]:
    """Return immutable convolution outcomes keyed by both distributions."""
    if not left_items or not right_items:
        return tuple()
    minimum = left_items[0][0] + right_items[0][0]
    maximum = left_items[-1][0] + right_items[-1][0]
    dense = [0.0] * (maximum - minimum + 1)
    for left_value, left_probability in left_items:
        base_index = left_value - minimum
        for right_value, right_probability in right_items:
            dense[base_index + right_value] += left_probability * right_probability
    return tuple(
        (minimum + index, probability)
        for index, probability in enumerate(dense)
        if probability > 0.0
    )


def _mixture_distribution(
    weighted: tuple[tuple[DamageDistribution, float], ...],
) -> DamageDistribution:
    """Combine mutually exclusive distributions with explicit probabilities."""
    result: DamageDistribution = {}
    for distribution, weight in weighted:
        for value, probability in distribution.items():
            result[value] = result.get(value, 0.0) + probability * weight
    return result
