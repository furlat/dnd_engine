"""SRD origin spells that were absent from the maintained spell inventory."""

from __future__ import annotations

from functools import partial
from types import MappingProxyType
from uuid import UUID

from pydantic import Field

from dnd.actions import SpellAction
from dnd.core.base_actions import (
    ActionEvent,
    TargetType,
    spell_slot_cost_type,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.registration import get_content_declaration
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.dice import AttackOutcome, Dice, RollType
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventType,
    Range,
    RangeType,
    TakeDamageEvent,
    Trigger,
)
from dnd.core.creature_types import DamageType
from dnd.core.saving_throw_types import SavingThrowContext
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.content_metadata import (
    SpellCatalogMetadata,
    attach_spell_catalog_metadata,
    srd_reaction_identity,
    srd_spell_identity,
)


@srd_spell_identity(
    content_id="spell.thaumaturgy",
    display_name="Thaumaturgy",
    description=(
        "Manifest one harmless supernatural sign for up to one minute."
    ),
    school="transmutation",
    level=0,
    source_page=282,
    sort_order=25,
)
class Thaumaturgy(SpellAction):
    """The spell's harmless sign is represented by its causal spell event."""

    name: str = Field(default="Thaumaturgy")
    description: str = Field(
        default="Manifest a harmless supernatural sign.",
    )
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="transmutation")
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
    )


@srd_reaction_identity(
    content_id="reaction.spell.hellish_rebuke",
    display_name="Hellish Rebuke",
    description=(
        "Use a reaction after taking damage to scorch the visible attacker."
    ),
    source_page=250,
    sort_order=25,
)
class HellishRebukeReactionHandler(EventHandler):
    """Exact reaction behavior installed by the learned spell root."""


HELLISH_REBUKE_REACTION_DECLARATION = get_content_declaration(
    HellishRebukeReactionHandler,
)


@srd_spell_identity(
    content_id="spell.hellish_rebuke",
    display_name="Hellish Rebuke",
    description=(
        "React to damage from a visible creature within 60 feet; it makes a "
        "Dexterity save and takes fire damage, or half on a success."
    ),
    school="evocation",
    level=1,
    source_page=250,
    sort_order=185,
    dependencies=(
        ContentDependency(
            relation=ContentDependencyRelation.INSTALLS_HANDLER,
            target_ref=HELLISH_REBUKE_REACTION_DECLARATION.ref,
            phase=ContentDependencyPhase.RUNTIME_REFERENCE,
            notes="Knowing Hellish Rebuke installs its exact reaction.",
        ),
    ),
)
class HellishRebukeLearnedSpell:
    """Non-clickable spell root for the reaction runtime surface."""


HELLISH_REBUKE_SPELL_DECLARATION = get_content_declaration(
    HellishRebukeLearnedSpell,
)
THAUMATURGY_SPELL_DECLARATION = get_content_declaration(Thaumaturgy)
INFERNAL_BEHAVIOR_DECLARATIONS_BY_CLASS = MappingProxyType({
    HellishRebukeReactionHandler: HELLISH_REBUKE_REACTION_DECLARATION,
    HellishRebukeLearnedSpell: HELLISH_REBUKE_SPELL_DECLARATION,
    Thaumaturgy: THAUMATURGY_SPELL_DECLARATION,
})


def _rebuke_processor(
    event: Event,
    source_entity_uuid: UUID,
    *,
    spell_ref: ContentRef,
) -> Event | None:
    """Resolve one reaction through a currently owning casting source."""
    if (
        not isinstance(event, TakeDamageEvent)
        or event.get_effective_damage() <= 0
        or event.source_entity_uuid is None
        or event.source_entity_uuid == source_entity_uuid
    ):
        return None
    caster = Entity.get(source_entity_uuid)
    attacker = Entity.get(event.source_entity_uuid)
    if caster is None or attacker is None:
        return None
    source_options = caster.spellcasting.learned_reaction_spell_sources(
        spell_ref.content_id,
    )
    if not source_options:
        return None
    if not caster.action_economy.can_afford("reactions", 1):
        return None
    caster.materialize_navigation(max_distance=60)
    contact = caster.senses.entities.get(attacker.uuid)
    if (
        contact is None
        or not contact.visual
        or caster.senses.get_feet_distance(attacker.position) > 60
    ):
        return None

    selected_source = None
    cast_rank = None
    for source in source_options:
        if source.resource_name is not None:
            if caster.action_economy.can_afford_resource(source.resource_name, 1):
                selected_source = source
                cast_rank = source.fixed_cast_rank
                break
            continue
        available_rank = caster.get_lowest_spell_slot(1)
        if available_rank is not None:
            selected_source = source
            cast_rank = available_rank
            break
    if selected_source is None or cast_rank is None:
        return None

    caster.action_economy.consume("reactions", 1)
    if selected_source.resource_name is not None:
        if not caster.action_economy.consume_resource(
            selected_source.resource_name,
            1,
        ):
            raise RuntimeError("validated innate rebuke resource disappeared")
    else:
        caster.action_economy.consume(spell_slot_cost_type(cast_rank), 1)

    declaration = ActionEvent(
        name="Hellish Rebuke",
        source_entity_uuid=caster.uuid,
        target_entity_uuid=attacker.uuid,
        source_entity_name=caster.name,
        target_entity_name=attacker.name,
        parent_event=event.uuid,
        phase=EventPhase.DECLARATION,
        costs=[],
    )
    execution = declaration.phase_to(EventPhase.EXECUTION)
    effect = execution.phase_to(EventPhase.EFFECT)
    save_request = caster.create_saving_throw_request(
        attacker.uuid,
        "dexterity",
        caster.spell_save_dc(
            spellcasting_source_id=selected_source.source_id,
        ),
        parent_event=effect.uuid,
        saving_throw_context=SavingThrowContext(
            cause_id=spell_ref.content_id,
            effect_id="spell.hellish_rebuke.damage",
            is_magical=True,
        ),
    )
    _, _, saved = attacker.saving_throw(save_request)
    damage_dice = Dice(
        count=2 + max(0, cast_rank - 1),
        value=10,
        bonus=ModifiableValue.create(
            source_entity_uuid=caster.uuid,
            base_value=0,
            value_name="Hellish Rebuke damage",
        ),
        roll_type=RollType.DAMAGE,
        attack_outcome=AttackOutcome.HIT,
    ).roll
    attacker.receive_damage(
        damage_dice.total // 2 if saved else damage_dice.total,
        DamageType.FIRE,
        caster.uuid,
        damage_rolls=[damage_dice],
        parent_event=effect.uuid,
        effect_id="spell.hellish_rebuke.damage",
    )
    effect.phase_to(EventPhase.COMPLETION)
    return event


def create_hellish_rebuke_reaction_handler(
    source_entity_uuid: UUID,
    *,
    handler_uuid: UUID | None = None,
) -> HellishRebukeReactionHandler:
    """Create one Hellish Rebuke handler shared by its casting sources."""
    return HellishRebukeReactionHandler(
        **({} if handler_uuid is None else {"uuid": handler_uuid}),
        name="Hellish Rebuke",
        semantic_key="reaction.spell.hellish_rebuke",
        content_kind=RuntimeBehaviorKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=source_entity_uuid,
            ),
        ],
        event_processor=partial(
            _rebuke_processor,
            spell_ref=HELLISH_REBUKE_SPELL_DECLARATION.ref,
        ),
        player_toggleable=True,
    )


THAUMATURGY_METADATA = SpellCatalogMetadata(
    catalog_id="thaumaturgy",
    description="Manifest a harmless supernatural sign.",
    target_type="self",
    range_type="ranged",
    range_ft=30,
    delivery="none",
    projectile_type=None,
    aoe=None,
    damage_types=(),
    healing=False,
    attack_roll=False,
    saving_throws=(),
    concentration=False,
    ritual=False,
    verbal=True,
    somatic=False,
    material=False,
    classes=("cleric",),
    subclasses=(),
    multi_target=None,
    recommended_asset_tags=("transmutation", "utility"),
)
HELLISH_REBUKE_METADATA = SpellCatalogMetadata(
    catalog_id="hellish_rebuke",
    description="Reaction: scorch a visible creature that damaged you.",
    target_type="entity",
    range_type="ranged",
    range_ft=60,
    delivery="none",
    projectile_type=None,
    aoe=None,
    damage_types=(DamageType.FIRE,),
    healing=False,
    attack_roll=False,
    saving_throws=(),
    concentration=False,
    ritual=False,
    verbal=True,
    somatic=True,
    material=False,
    classes=("warlock",),
    subclasses=(),
    multi_target=None,
    recommended_asset_tags=("evocation", "fire", "reaction"),
)
attach_spell_catalog_metadata(Thaumaturgy, THAUMATURGY_METADATA)


__all__ = [
    "HELLISH_REBUKE_METADATA",
    "HELLISH_REBUKE_REACTION_DECLARATION",
    "HELLISH_REBUKE_SPELL_DECLARATION",
    "INFERNAL_BEHAVIOR_DECLARATIONS_BY_CLASS",
    "HellishRebukeReactionHandler",
    "THAUMATURGY_METADATA",
    "THAUMATURGY_SPELL_DECLARATION",
    "Thaumaturgy",
    "create_hellish_rebuke_reaction_handler",
]
