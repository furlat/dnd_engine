"""Exact, dependency-neutral cause facts for saving-throw rules."""

from collections.abc import Iterator
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.origin_features import OriginCapability
from dnd.core.content.runtime import BehaviorBinding
from dnd.core.base_conditions import BaseCondition
from dnd.core.modifiers import AdvantageModifier
from dnd.types.rolls import AdvantageStatus
from dnd.types.saving_throws import SAVING_THROW_CONTEXT_KEY, SavingThrowEffectTag
from dnd.core.content.saving_throws import SavingThrowContext
from dnd.core.spell_execution import spell_execution_scope
from dnd.core.values import ContextualAdvantageModifier
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Cloudkill, PoisonSpray, StinkingCloud
from dnd.spells.enchantment import CharmPerson, Sleep
from dnd.spells.illusion import Fear, HypnoticPattern


@pytest.fixture(autouse=True)
def _reset_engine() -> Iterator[None]:
    reset_engine_runtime(grid_size=(8, 8))
    yield
    reset_engine_runtime()


def _ref(
    definition_kind: ContentDefinitionKind,
    content_id: str,
    digest_character: str,
) -> ContentRef:
    return ContentRef(
        pack_id="content.srd_5_1_cc",
        definition_kind=definition_kind,
        content_id=content_id,
        content_version=1,
        definition_contract_hash=digest_character * 64,
    )


def test_saving_throw_context_owns_exact_cause_effect_and_rules_facts() -> None:
    cause_ref = _ref(
        ContentDefinitionKind.SPELL,
        "spell.fixture_poison",
        "a",
    )
    condition_ref = _ref(
        ContentDefinitionKind.CONDITION,
        "condition.poisoned",
        "b",
    )

    context = SavingThrowContext(
        cause_ref=cause_ref,
        effect_id="control.fixture.poisoned",
        condition_ref=condition_ref,
        is_magical=True,
        effect_tags=(SavingThrowEffectTag.POISON,),
    )

    assert context.cause_ref == cause_ref
    assert context.effect_id == "control.fixture.poisoned"
    assert context.condition_ref == condition_ref
    assert context.is_magical is True
    assert context.effect_tags == (SavingThrowEffectTag.POISON,)
    assert SavingThrowContext.model_validate_json(
        context.model_dump_json(),
    ) == context


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        (
            {"effect_id": "Poisoned"},
            "effect_id must be a lowercase dotted identifier",
        ),
        (
            {
                "condition_ref": _ref(
                    ContentDefinitionKind.SPELL,
                    "spell.not_a_condition",
                    "c",
                ),
            },
            "condition_ref must identify a condition",
        ),
        (
            {
                "effect_tags": (
                    SavingThrowEffectTag.POISON,
                    SavingThrowEffectTag.POISON,
                ),
            },
            "effect tags must be unique and ordered",
        ),
        (
            {
                "effect_tags": (
                    SavingThrowEffectTag.FEAR,
                    SavingThrowEffectTag.CHARM,
                ),
            },
            "effect tags must be unique and ordered",
        ),
    ),
)
def test_saving_throw_context_rejects_inexact_or_ambiguous_facts(
    updates: dict[str, object],
    message: str,
) -> None:
    payload: dict[str, object] = {
        "cause_ref": _ref(
            ContentDefinitionKind.ACTION,
            "action.fixture",
            "d",
        ),
        "effect_id": "control.fixture.effect",
        "is_magical": False,
    }
    payload.update(updates)

    with pytest.raises(ValidationError, match=message):
        SavingThrowContext.model_validate(payload)


def test_saving_throw_request_propagates_exact_context_to_save_modifiers() -> None:
    source = Entity.create(
        source_entity_uuid=uuid4(),
        name="Exact Cause",
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Exact Saver",
    )
    magical_context = SavingThrowContext(
        cause_ref=_ref(
            ContentDefinitionKind.SPELL,
            "spell.fixture_charm",
            "e",
        ),
        effect_id="control.fixture.charm",
        condition_ref=_ref(
            ContentDefinitionKind.CONDITION,
            "condition.charmed",
            "f",
        ),
        is_magical=True,
        effect_tags=(SavingThrowEffectTag.CHARM,),
    )
    observed: list[SavingThrowContext] = []

    def exact_magic_advantage(
        source_entity_uuid: UUID,
        target_entity_uuid: UUID | None,
        modifier_context: dict[str, object] | None,
    ) -> AdvantageModifier | None:
        typed_context = (
            modifier_context.get(SAVING_THROW_CONTEXT_KEY)
            if modifier_context is not None
            else None
        )
        if not isinstance(typed_context, SavingThrowContext):
            return None
        observed.append(typed_context)
        if (
            typed_context.is_magical
            and SavingThrowEffectTag.CHARM in typed_context.effect_tags
        ):
            return AdvantageModifier(
                name="Exact magical charm advantage",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=target_entity_uuid,
            )
        return None

    wisdom_save = target.saving_throws.get_saving_throw("wisdom")
    wisdom_save.bonus.self_contextual.add_advantage_modifier(
        ContextualAdvantageModifier(
            name="Exact magical charm advantage",
            source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid,
            callable=exact_magic_advantage,
        ),
    )

    request = source.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=10,
        saving_throw_context=magical_context,
    )
    assert request.saving_throw_context == magical_context

    with patch("dnd.core.dice.random.randint", side_effect=(4, 17)):
        _, magical_roll, _ = target.saving_throw(request)

    assert magical_roll.advantage_status is AdvantageStatus.ADVANTAGE
    assert observed
    assert all(context == magical_context for context in observed)

    nonmagical_context = magical_context.model_copy(
        update={"is_magical": False},
    )
    nonmagical_request = source.create_saving_throw_request(
        target_entity_uuid=target.uuid,
        ability_name="wisdom",
        dc=10,
        saving_throw_context=nonmagical_context,
    )
    with patch("dnd.core.dice.random.randint", return_value=11):
        _, nonmagical_roll, _ = target.saving_throw(nonmagical_request)

    assert nonmagical_roll.advantage_status is AdvantageStatus.NONE


def test_spell_execution_supplies_exact_magical_save_context_by_default() -> None:
    caster = Entity.create(source_entity_uuid=uuid4())
    target = Entity.create(source_entity_uuid=uuid4())
    spell_ref = _ref(
        ContentDefinitionKind.SPELL,
        "spell.fixture_charm",
        "a",
    )

    with spell_execution_scope(
        source_entity_uuid=caster.uuid,
        damage_type=None,
        cause_ref=spell_ref,
        saving_throw_effect_id="spell.fixture_charm.saving_throw",
        saving_throw_effect_tags=(SavingThrowEffectTag.CHARM,),
    ):
        request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="wisdom",
            dc=12,
        )

    assert request.saving_throw_context == SavingThrowContext(
        cause_ref=spell_ref,
        effect_id="spell.fixture_charm.saving_throw",
        is_magical=True,
        effect_tags=(SavingThrowEffectTag.CHARM,),
    )


def test_bound_condition_builds_exact_repeat_save_context() -> None:
    condition_ref = _ref(
        ContentDefinitionKind.CONDITION,
        "condition.fixture_fear",
        "b",
    )
    owner_uuid = uuid4()
    condition = BaseCondition(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        behavior_binding=BehaviorBinding(
            definition_ref=condition_ref,
            provided_by_ref=condition_ref,
            runtime_owner_uuid=owner_uuid,
        ),
    )

    assert condition.saving_throw_context(
        effect_id="condition.fixture_fear.repeat_save",
        effect_tags=(SavingThrowEffectTag.FEAR,),
        is_magical=True,
    ) == SavingThrowContext(
        cause_ref=condition_ref,
        effect_id="condition.fixture_fear.repeat_save",
        condition_ref=condition_ref,
        is_magical=True,
        effect_tags=(SavingThrowEffectTag.FEAR,),
    )


def test_unbound_condition_cannot_invent_repeat_save_identity() -> None:
    condition = BaseCondition(
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
    )

    with pytest.raises(ValueError, match="exact runtime behavior binding"):
        condition.saving_throw_context(
            effect_id="condition.fixture.repeat_save",
            effect_tags=(),
            is_magical=False,
        )


def test_magical_sleep_immunity_excludes_target_without_charm_proxy() -> None:
    def actor(position: tuple[int, int], faction: str) -> Entity:
        return Entity.create(
            source_entity_uuid=uuid4(),
            config=EntityConfig(
                position=position,
                faction=faction,
                health=HealthConfig(
                    hit_dices=[
                        HitDiceConfig(
                            hit_dice_value=8,
                            hit_dice_count=1,
                            mode="maximums",
                        ),
                    ],
                ),
            ),
        )

    caster = actor((1, 1), "heroes")
    immune_target = actor((2, 1), "monsters")
    ordinary_target = actor((3, 1), "monsters")
    immune_target.add_origin_capability_source(
        OriginCapability.MAGICAL_SLEEP_IMMUNITY,
        uuid4(),
    )
    Entity.update_all_entities_senses()

    sleep = Sleep(
        source_entity_uuid=caster.uuid,
        end_position=(2, 1),
    )
    sleep.hp_pool_rolled = 100
    sleep.hp_pool_remaining = 100

    targets = sleep.get_all_targets()

    assert immune_target.uuid not in targets
    assert ordinary_target.uuid in targets


@pytest.mark.parametrize(
    ("spell_type", "expected_tag"),
    (
        (CharmPerson, SavingThrowEffectTag.CHARM),
        (HypnoticPattern, SavingThrowEffectTag.CHARM),
        (Fear, SavingThrowEffectTag.FEAR),
        (PoisonSpray, SavingThrowEffectTag.POISON),
        (Cloudkill, SavingThrowEffectTag.POISON),
        (StinkingCloud, SavingThrowEffectTag.POISON),
    ),
)
def test_tagged_spell_saves_declare_exact_origin_rule_semantics(
    spell_type: type,
    expected_tag: SavingThrowEffectTag,
) -> None:
    spell = spell_type(source_entity_uuid=uuid4())

    assert spell.saving_throw_effect_tags == (expected_tag,)
