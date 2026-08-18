"""Validate direct class selections and resolve entity-owned level steps."""

from typing import Optional
from dnd.content.characters.class_definitions import (
    CLASS_DEFINITIONS,
    SUBCLASS_DEFINITIONS,
    ClassChoiceDefinition,
    ClassChoiceKind,
    ClassDefinition,
    ClassLevelRequest,
)
from dnd.content.characters.character_grants import (
    ability_score_improvement_transform,
    barbarian_feature_transform,
    common_level_transforms,
    draconic_resilience_hp_transform,
    feat_transform,
    fighter_feature_transform,
    normal_spell_slots_transform,
    rage_reconciliation_transform,
    second_wind_reconciliation_transform,
    sorcerer_feature_transform,
    sorcerer_spellcasting_transform,
    spell_caster_level_reconciliation_transform,
    spell_learning_transform,
    spell_replacement_transform,
)
from dnd.content.characters.origin_content import resolve_origin_level_transforms
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity import Entity
from dnd.entities.entity_progression import ResolvedLevelStep, apply_level
from dnd.types.abilities import AbilityName, SkillName
from dnd.types.progression import (
    AppliedClassLevel,
    AppliedOriginState,
    CharacterClass,
    CharacterSubclass,
    ClassChoiceSelection,
)


_SUBCLASS_SEMANTIC_IDS = {
    CharacterSubclass.BERSERKER: "subclass.barbarian.berserker",
    CharacterSubclass.CHAMPION: "subclass.fighter.champion",
    CharacterSubclass.DRACONIC_BLOODLINE: (
        "subclass.sorcerer.draconic_bloodline"
    ),
}
_SUBCLASS_BY_SEMANTIC_ID = {
    semantic_id: subclass
    for subclass, semantic_id in _SUBCLASS_SEMANTIC_IDS.items()
}


def _choice_map(
    selections: tuple[ClassChoiceSelection, ...],
) -> dict[str, ClassChoiceSelection]:
    return {selection.choice_id: selection for selection in selections}


def _validate_choice(
    definition: ClassChoiceDefinition,
    selection: ClassChoiceSelection,
) -> None:
    count = len(selection.values)
    if not definition.minimum_selections <= count <= definition.maximum_selections:
        raise ValueError(
            f"class choice {definition.choice_id} has wrong cardinality",
        )
    if definition.allowed_values:
        unsupported = set(selection.values) - set(definition.allowed_values)
        if unsupported:
            values = ", ".join(sorted(unsupported))
            raise ValueError(
                f"class choice {definition.choice_id} contains: {values}",
            )


def _expected_choices(
    definition: ClassDefinition,
    class_level: int,
    *,
    first_character_level: bool,
    subclass_id: Optional[CharacterSubclass],
) -> tuple[ClassChoiceDefinition, ...]:
    rows: list[ClassChoiceDefinition] = []
    if class_level == 1 and first_character_level:
        rows.extend(definition.first_class_choices)
    rows.extend(definition.levels[class_level - 1].choices)
    if subclass_id is not None:
        rows.extend(SUBCLASS_DEFINITIONS[subclass_id].levels[class_level - 1].choices)
    return tuple(rows)


def _resolve_subclass(
    request: ClassLevelRequest,
    definition: ClassDefinition,
    class_level: int,
    previous: tuple[AppliedClassLevel, ...],
) -> Optional[CharacterSubclass]:
    previous_for_class = tuple(
        row for row in previous if row.class_id is request.class_id
    )
    established = next(
        (row.subclass_id for row in previous_for_class if row.subclass_id is not None),
        None,
    )
    selection = _choice_map(request.choices)
    subclass_choice = next(
        (
            choice
            for choice in definition.levels[class_level - 1].choices
            if choice.choice_kind is ClassChoiceKind.SUBCLASS
        ),
        None,
    )
    selected: Optional[CharacterSubclass] = None
    if subclass_choice is not None:
        selected_row = selection.get(subclass_choice.choice_id)
        if selected_row is None:
            raise ValueError(f"missing subclass choice {subclass_choice.choice_id}")
        selected = _SUBCLASS_BY_SEMANTIC_ID[selected_row.values[0]]
    resolved = established or selected or request.subclass_id
    if established is not None and request.subclass_id not in {None, established}:
        raise ValueError("an applied class cannot change subclass")
    if selected is not None and request.subclass_id not in {None, selected}:
        raise ValueError("subclass request disagrees with its selected value")
    if resolved is not None:
        subclass_definition = SUBCLASS_DEFINITIONS[resolved]
        if subclass_definition.parent_class_id is not request.class_id:
            raise ValueError("subclass does not belong to requested class")
    if subclass_choice is None and established is None and request.subclass_id is not None:
        raise ValueError("subclass cannot be selected before its authored level")
    return resolved


def _validate_prerequisites(
    definition: ClassDefinition,
    ability_scores: dict[AbilityName, int],
) -> None:
    results = tuple(
        ability_scores[requirement.ability] >= requirement.minimum
        for requirement in definition.multiclass_prerequisites
    )
    accepted = any(results) if definition.multiclass_prerequisite_any else all(results)
    if not accepted:
        raise ValueError(
            f"ability scores do not satisfy {definition.class_id.value} "
            "multiclass prerequisites",
        )


def _decode_skills(selection: ClassChoiceSelection) -> tuple[SkillName, ...]:
    return tuple(
        SkillName(value.removeprefix("skill."))
        for value in selection.values
    )


def _level_feature_ids(
    definition: ClassDefinition,
    level: AppliedClassLevel,
    selections: dict[str, ClassChoiceSelection],
) -> tuple[str, ...]:
    rows = list(
        definition.levels[level.resulting_class_level - 1].automatic_grant_ids,
    )
    if level.subclass_id is not None:
        rows.extend(
            SUBCLASS_DEFINITIONS[level.subclass_id]
            .levels[level.resulting_class_level - 1]
            .automatic_grant_ids
        )
    choice_definitions = _expected_choices(
        definition,
        level.resulting_class_level,
        first_character_level=level.character_level == 1,
        subclass_id=level.subclass_id,
    )
    for choice in choice_definitions:
        selection = selections.get(choice.choice_id)
        if selection is None:
            continue
        if choice.choice_kind in {
            ClassChoiceKind.FIGHTING_STYLE,
            ClassChoiceKind.METAMAGIC,
            ClassChoiceKind.ELEMENTAL_ANCESTRY,
        }:
            rows.extend(selection.values)
        elif choice.choice_kind is ClassChoiceKind.ASI_OR_FEAT:
            rows.extend(
                value for value in selection.values if value.startswith("feat.")
            )
    return tuple(rows)


def _feature_transform(
    level: AppliedClassLevel,
    feature_id: str,
    *,
    ancestry_feature_id: Optional[str],
) -> EntityTransform:
    if feature_id.startswith("feat."):
        return feat_transform(level, feature_id)
    if level.class_id is CharacterClass.FIGHTER:
        return fighter_feature_transform(level, feature_id)
    if level.class_id is CharacterClass.BARBARIAN:
        return barbarian_feature_transform(level, feature_id)
    return sorcerer_feature_transform(
        level,
        feature_id,
        ancestry_feature_id=ancestry_feature_id,
    )


def _decode_spell_replacement(value: str) -> tuple[str, str]:
    replaced, separator, learned = value.partition("->")
    if separator != "->" or not replaced or not learned:
        raise ValueError(
            "spell replacement must use 'spell.old->spell.new'",
        )
    return replaced, learned


def _previous_sorcerer_spell_ids(
    previous: tuple[AppliedClassLevel, ...],
) -> set[str]:
    """Rebuild known Sorcerer spell IDs from the serialized level ledger."""
    known: set[str] = set()
    for row in previous:
        if row.class_id is not CharacterClass.SORCERER:
            continue
        for choice in row.choices:
            if choice.choice_id.endswith((".cantrips", ".spell_known")):
                known.update(choice.values)
            elif choice.choice_id.endswith(".spell_replacement"):
                replaced, learned = _decode_spell_replacement(choice.values[0])
                known.remove(replaced)
                known.add(learned)
    return known


def _sorcerer_spell_choices(
    definition: ClassDefinition,
    level: AppliedClassLevel,
    previous: tuple[AppliedClassLevel, ...],
) -> tuple[tuple[str, ...], Optional[tuple[str, str]]]:
    """Validate direct known-spell additions and the optional replacement."""
    selected = _choice_map(level.choices)
    learned = tuple(
        spell_id
        for choice in level.choices
        if choice.choice_id.endswith((".cantrips", ".spell_known"))
        for spell_id in choice.values
    )
    if len(set(learned)) != len(learned):
        raise ValueError("a Sorcerer level cannot learn the same spell twice")
    previous_known = _previous_sorcerer_spell_ids(previous)
    duplicate = previous_known.intersection(learned)
    if duplicate:
        raise ValueError(
            "Sorcerer already knows: " + ", ".join(sorted(duplicate)),
        )
    replacement_row = selected.get(
        f"class.sorcerer.level_{level.resulting_class_level}.spell_replacement",
    )
    if replacement_row is None:
        return learned, None
    replaced, replacement = _decode_spell_replacement(replacement_row.values[0])
    if replaced not in previous_known:
        raise ValueError(f"Sorcerer does not know replacement source {replaced}")
    entitlement_ranks = dict(definition.spell_entitlements)
    replacement_rank = entitlement_ranks.get(replacement)
    if replacement_rank is None or replacement_rank == 0:
        raise ValueError("replacement must be an entitled non-cantrip Sorcerer spell")
    maximum_rank = (level.resulting_class_level + 1) // 2
    if replacement_rank > maximum_rank:
        raise ValueError("replacement spell rank exceeds available Sorcerer slots")
    if replacement in previous_known - {replaced} or replacement in learned:
        raise ValueError(f"Sorcerer already knows replacement target {replacement}")
    return learned, (replaced, replacement)


def _sorcerer_ancestry_feature_id(
    previous: tuple[AppliedClassLevel, ...],
    level: AppliedClassLevel,
) -> Optional[str]:
    return next((
        value
        for row in (*previous, level)
        if row.class_id is CharacterClass.SORCERER
        for choice in row.choices
        for value in choice.values
        if value.startswith("class_feature.sorcerer.draconic_ancestry.")
    ), None)


def _resolve(
    request: ClassLevelRequest,
    previous: tuple[AppliedClassLevel, ...],
    ability_scores: dict[AbilityName, int],
) -> ResolvedLevelStep:
    definition = CLASS_DEFINITIONS[request.class_id]
    class_level = 1 + sum(
        row.class_id is request.class_id for row in previous
    )
    character_level = len(previous) + 1
    if character_level > 20 or class_level > 20:
        raise ValueError("character and class levels cannot exceed 20")
    first_character_level = not previous
    if class_level == 1 and not first_character_level:
        _validate_prerequisites(definition, ability_scores)

    subclass_id = _resolve_subclass(
        request,
        definition,
        class_level,
        previous,
    )
    expected = _expected_choices(
        definition,
        class_level,
        first_character_level=first_character_level,
        subclass_id=subclass_id,
    )
    selected = _choice_map(request.choices)
    expected_ids = {choice.choice_id for choice in expected}
    unexpected = set(selected) - expected_ids
    if unexpected:
        raise ValueError(
            "unexpected class choices: " + ", ".join(sorted(unexpected)),
        )
    canonical_ids: list[str] = []
    for choice in expected:
        selection = selected.get(choice.choice_id)
        if selection is None:
            if choice.minimum_selections:
                raise ValueError(f"missing class choice {choice.choice_id}")
            continue
        _validate_choice(choice, selection)
        canonical_ids.append(choice.choice_id)
    if tuple(selection.choice_id for selection in request.choices) != tuple(canonical_ids):
        raise ValueError("class choices must follow authored order")

    level = AppliedClassLevel(
        step_id=(
            request.step_id
            or f"character_level.{character_level}.class.{request.class_id.value}.{class_level}"
        ),
        character_level=character_level,
        class_id=request.class_id,
        resulting_class_level=class_level,
        subclass_id=subclass_id,
        choices=request.choices,
    )
    skills: tuple[SkillName, ...] = ()
    if first_character_level:
        skill_choice = next(
            (
                choice for choice in definition.first_class_choices
                if choice.choice_kind is ClassChoiceKind.CLASS_SKILL
            ),
            None,
        )
        if skill_choice is not None:
            skills = _decode_skills(selected[skill_choice.choice_id])
    proficiencies = (
        definition.first_class_proficiencies
        if first_character_level
        else definition.multiclass_proficiencies
        if class_level == 1
        else ()
    )
    saving_throws = (
        definition.saving_throw_proficiencies if first_character_level else ()
    )
    transforms: list[EntityTransform] = list(common_level_transforms(
        level,
        hit_die=definition.hit_die,
        proficiencies=proficiencies,
        saving_throws=saving_throws,
        skills=skills,
        first_character_level=first_character_level,
    ))
    ancestry_feature_id = _sorcerer_ancestry_feature_id(previous, level)
    learned_spell_ids: tuple[str, ...] = ()
    spell_replacement: Optional[tuple[str, str]] = None
    if request.class_id is CharacterClass.SORCERER:
        learned_spell_ids, spell_replacement = _sorcerer_spell_choices(
            definition,
            level,
            previous,
        )
        transforms.extend((
            sorcerer_spellcasting_transform(level),
            normal_spell_slots_transform(
                level,
                sum(
                    row.class_id is CharacterClass.SORCERER
                    for row in (*previous, level)
                ),
            ),
        ))
    feature_ids = _level_feature_ids(definition, level, selected)
    transforms.extend(
        _feature_transform(
            level,
            feature_id,
            ancestry_feature_id=ancestry_feature_id,
        )
        for feature_id in feature_ids
    )
    for choice in expected:
        selection = selected.get(choice.choice_id)
        if selection is None or choice.choice_kind is not ClassChoiceKind.ASI_OR_FEAT:
            continue
        asi_values = tuple(
            value for value in selection.values if value.startswith("ability.")
        )
        feat_values = tuple(
            value for value in selection.values if value.startswith("feat.")
        )
        if asi_values and feat_values:
            raise ValueError("choose either an ASI or a feat")
        if asi_values:
            transforms.append(ability_score_improvement_transform(level, asi_values))

    if request.class_id is CharacterClass.FIGHTER and class_level > 1:
        transforms.append(second_wind_reconciliation_transform(level))
    if request.class_id is CharacterClass.BARBARIAN:
        rage_grants = sum(
            1
            for row in (*previous, level)
            if row.class_id is CharacterClass.BARBARIAN
            and row.resulting_class_level in _RAGE_ADVANCEMENT_LEVELS
        )
        if rage_grants:
            transforms.append(rage_reconciliation_transform(
                level,
                damage=4 if class_level >= 16 else 3 if class_level >= 9 else 2,
                mindless=class_level >= 6 and subclass_id is CharacterSubclass.BERSERKER,
                persistent=class_level >= 15,
            ))
    if request.class_id is CharacterClass.SORCERER:
        if (
            subclass_id is CharacterSubclass.DRACONIC_BLOODLINE
            and class_level > 1
        ):
            transforms.append(draconic_resilience_hp_transform(level))
        transforms.extend(
            spell_learning_transform(level, spell_id)
            for spell_id in learned_spell_ids
        )
        if spell_replacement is not None:
            transforms.append(spell_replacement_transform(
                level,
                spell_replacement[0],
                spell_replacement[1],
            ))
        transforms.append(spell_caster_level_reconciliation_transform(level))
    return ResolvedLevelStep(level=level, transforms=tuple(transforms))


_RAGE_ADVANCEMENT_LEVELS = frozenset({1, 3, 6, 9, 12, 16, 17, 20})


def resolve_level_step(entity: Entity, request: ClassLevelRequest) -> ResolvedLevelStep:
    """Resolve one post-birth level against current semantic entity state."""
    ability_scores = {
        ability.name: ability.ability_score.score
        for ability in entity.ability_scores.abilities_list
    }
    step = _resolve(request, tuple(entity.applied_class_levels), ability_scores)
    return ResolvedLevelStep(
        level=step.level,
        transforms=(
            *step.transforms,
            *resolve_origin_level_transforms(
                entity.species,
                entity.species_variant,
                step.level.character_level,
            ),
        ),
    )


def resolve_initial_level_steps(
    origin_state: AppliedOriginState,
    requests: tuple[ClassLevelRequest, ...],
) -> tuple[ResolvedLevelStep, ...]:
    """Resolve an unpublished ordered build without mutating an Entity."""
    ability_scores = dict(origin_state.base_ability_scores)
    for ability, bonus in origin_state.flexible_ability_bonuses:
        ability_scores[ability] += bonus
    previous: list[AppliedClassLevel] = []
    steps: list[ResolvedLevelStep] = []
    for request in requests:
        step = _resolve(request, tuple(previous), ability_scores)
        steps.append(step)
        previous.append(step.level)
        for choice in step.level.choices:
            if not choice.choice_id.endswith(".asi_or_feat"):
                continue
            for value in choice.values:
                if not value.startswith("ability."):
                    continue
                ability_token, amount_token = value.split(":+", 1)
                ability_scores[
                    AbilityName(ability_token.removeprefix("ability."))
                ] += int(amount_token)
    return tuple(steps)


def add_class_level(entity: Entity, request: ClassLevelRequest) -> AppliedClassLevel:
    """Resolve authored content, then delegate mutation/events to Entity."""
    return apply_level(entity, resolve_level_step(entity, request))


__all__ = [
    "add_class_level",
    "resolve_initial_level_steps",
    "resolve_level_step",
]
