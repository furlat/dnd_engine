"""Canonical Neurodragon spell-bearing possession definitions.

`SpellGrantingItem` is a reusable runtime mechanism, not an authored content
definition. Durable identity belongs exclusively to the private factories
declared below and to their authenticated `ContentRecipe` values.
"""

from typing import Any, Optional, cast as type_cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from dnd.actions.standard import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.blocks.base_item import (
    UsableItem,
)
from dnd.core.aoe import AoEShape, Cube
from dnd.core.base_actions import (
    BaseAction,
    Cost,
    TargetType,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.item_definitions import (
    ItemDefinition,
    ItemPersistencePolicy,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import (
    ContentDeclaration,
    behavior_identity,
    get_content_declaration,
    item_factory,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.types.rolls import AttackOutcome
from dnd.types.abilities import AbilityName
from dnd.core.events.resolution_events import (
    Damage,
    Range,
    RangeType,
)
from dnd.core.events.events_registry import (
    EventPhase,
)
from dnd.types.damage import DamageType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.abjuration import (
    MageArmor,
)
from dnd.spells.enchantment import HoldPerson
from dnd.spells.evocation import (
    BurningHands,
    Fireball,
    FireBolt,
    MagicMissile,
)
from dnd.spells.illusion import Invisibility
from dnd.spells.transmutation import SpikeGrowth


class SpellGrantingItem(UsableItem):
    """Reusable runtime mechanism for item-backed spell templates.

    This structural class intentionally has no content declaration and is not
    materializable by itself. Authored scroll, wand, and environment roots may
    reuse it while their private factories retain the only durable identities.
    """

    name: str = Field(
        default="Spell Item",
        description="Display name for the spell-bearing item.",
    )
    is_pickable: bool = Field(
        default=True,
        description="Whether the spell-bearing item can be picked up.",
    )
    map_char: str = Field(
        default="\u03c3",
        description="Map glyph for spell-bearing items.",
    )
    is_consumable: bool = Field(
        default=True,
        description="Whether the item is destroyed after its final charge.",
    )
    charges: int = Field(
        default=1,
        description="Current item charges; -1 means unlimited uses.",
    )
    max_charges: int = Field(
        default=1,
        description="Maximum finite charges the item can hold.",
    )
    max_stack: int = Field(
        default=20,
        description="Maximum count for stackable spell items.",
    )
    scroll_cast_level: int = Field(
        default=1,
        description="Minimum cast level used for granted spell variants.",
    )

    def get_use_actions(self, user_entity_uuid: UUID) -> list[BaseAction]:
        """Create item-bound spell variants without spell-slot costs."""
        if self.charges == 0 or not self.use_action_templates:
            return []
        result: list[BaseAction] = []
        source_item_presentation = self.to_item_presentation_state()
        for template in self.use_action_templates:
            template_charge_cost = template.charge_cost
            if (
                self.charges != -1
                and self.charges < template_charge_cost
            ):
                continue

            if isinstance(template, SpellAction):
                cast_level = (
                    0
                    if template.spell_level == 0
                    else max(
                        template.spell_level,
                        template.cast_at_level,
                        self.scroll_cast_level,
                    )
                )
                result.append(template._create_variant(
                    cast_at_level=cast_level,
                    costs=[
                        Cost(
                            name="Use Item",
                            cost_type="actions",
                            cost=1,
                            evaluator=entity_action_economy_cost_evaluator,
                        ),
                    ],
                    source_item_uuid=self.uuid,
                    source_item_presentation=source_item_presentation,
                    source_entity_uuid=user_entity_uuid,
                    template=True,
                    charge_cost=template_charge_cost,
                ))
                continue

            result.append(template.model_copy(
                deep=True,
                update={
                    "uuid": uuid4(),
                    "source_entity_uuid": user_entity_uuid,
                    "source_item_uuid": self.uuid,
                    "source_item_presentation": source_item_presentation,
                    "charge_cost": template_charge_cost,
                },
            ))
        return result


@behavior_identity(
    definition_kind=ContentDefinitionKind.SPELL,
    runtime_behavior_kind=RuntimeBehaviorKind.SPELL,
    pack_id="content.neurodragon",
    content_id="spell.acid_flask",
    version=1,
    descriptor=ContentDescriptorSpec(
        display_name="Acid Flask",
        description=(
            "Throw a flask into a two-by-two area; affected creatures make a "
            "Dexterity save against acid damage."
        ),
        tags=("acid", "consumable", "item_owned", "spell"),
        visibility=ContentVisibility.OBSERVED,
        presentation=ContentPresentation(
            icon_key="spell.acid_flask",
            visual_variant_key="acid_flask",
            vfx_profile="spell.acid_flask",
            ui_group="spells.item_owned",
        ),
        ordering=ContentOrdering(
            sort_group="spells.item_owned",
            sort_order=10,
        ),
    ),
    provenance=ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor="Neurodragon original content baseline: Acid Flask",
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Private item behavior preserved from the original implementation.",
    ),
)
class _AcidFlaskSpell(SpellAction):
    """Item-private thrown acid effect using the spell action pipeline."""

    name: str = Field(
        default="Acid Flask",
        description="Action name for throwing an acid flask.",
    )
    description: str = Field(
        default="Throw a flask of acid (2x2 area, 2d4 acid, DEX DC 11 half)",
        description="Action description shown for acid flask use.",
    )
    semantic_key: str = Field(
        default="content.neurodragon:spell:spell.acid_flask@1",
        description="Exact metadata identity of the item-private behavior.",
    )
    spell_level: int = Field(
        default=0,
        description="The item-backed effect consumes no spell slot.",
    )
    spell_school: str = Field(
        default="evocation",
        description="School label used by the spell action model.",
    )
    target_type: TargetType = Field(
        default=TargetType.POSITION_AOE,
        description="Acid Flask targets a visible area.",
    )
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=40),
        description="Throw range for the acid flask.",
    )
    aoe_shape: Optional[AoEShape] = Field(
        default=None,
        description="Area shape generated for flask splash damage.",
    )
    include_self: bool = Field(
        default=False,
        description="Whether the caster can be included in the splash.",
    )
    valid_target_filter: str = Field(
        default="all",
        description="Target filter used by area target collection.",
    )
    _fixed_dc: int = 11

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.aoe_shape is None:
            self.aoe_shape = Cube(
                source_entity_uuid=self.source_entity_uuid,
                target=self.end_position if self.end_position is not None else (0, 0),
                size_feet=10,
                centered=True,
            )

    def get_range(self) -> Range:
        return self.spell_range

    def _validate(
        self,
        declaration_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        target_pos = self.end_position
        if target_pos is None:
            return declaration_event.cancel(
                status_message="No target position specified",
            )
        if (
            target_pos not in caster.senses.visible
            or not caster.senses.visible[target_pos]
        ):
            return declaration_event.cancel(
                status_message=(
                    f"Target position {target_pos} not in line of sight"
                ),
            )

        distance = caster.distance_to_position(target_pos)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=(
                    f"Target out of range "
                    f"({distance}ft > {self.spell_range.normal}ft)"
                ),
            )
        return type_cast(
            Optional[SpellEvent],
            super()._validate(declaration_event),
        )

    def _apply(
        self,
        execution_event: SpellEvent,
    ) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid
            else None
        )
        if not caster or not target:
            return execution_event.cancel(
                status_message="Caster or target not found",
            )

        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name=AbilityName.DEXTERITY,
            dc=self._fixed_dc,
            parent_event=execution_event.uuid,
        )
        _, save_roll, success = target.saving_throw(save_request)
        save_bonus = target.saving_throw_bonus(
            caster.uuid,
            AbilityName.DEXTERITY,
        ).normalized_score
        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="dexterity",
            save_dc=self._fixed_dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=(
                f"DEX save: {save_roll.total} vs DC {self._fixed_dc} - "
                f"{'Success' if success else 'Failure'}"
            ),
        )

        no_bonus = ModifiableValue.create(
            source_entity_uuid=caster.uuid,
            base_value=0,
            value_name="Acid Flask Damage",
        )
        acid_damage = Damage(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            damage_dice=4,
            dice_numbers=2,
            damage_bonus=no_bonus,
            damage_type=DamageType.ACID,
        )
        damage_dice = acid_damage.get_dice(
            attack_outcome=AttackOutcome.HIT,
        )
        damage_roll = damage_dice.roll
        final_damage = (
            damage_roll.total // 2
            if success
            else damage_roll.total
        )
        if final_damage > 0:
            target.receive_damage(
                amount=final_damage,
                damage_type=DamageType.ACID,
                source_entity_uuid=caster.uuid,
                parent_event=effect_event.uuid,
            )

        save_text = " (saved for half)" if success else ""
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            damages=[acid_damage],
            damage_rolls=[damage_roll],
            total_damage=final_damage,
            status_message=(
                f"Acid Flask deals {final_damage} acid damage to "
                f"{target.name}{save_text}"
            ),
        )


ACID_FLASK_SPELL_DECLARATION = get_content_declaration(_AcidFlaskSpell)
ACID_FLASK_SPELL_REF = ACID_FLASK_SPELL_DECLARATION.ref

FIREBALL_DECLARATION = get_content_declaration(Fireball)
MAGIC_MISSILE_DECLARATION = get_content_declaration(MagicMissile)
HOLD_PERSON_DECLARATION = get_content_declaration(HoldPerson)
MAGE_ARMOR_DECLARATION = get_content_declaration(MageArmor)
SPIKE_GROWTH_DECLARATION = get_content_declaration(SpikeGrowth)
FIRE_BOLT_DECLARATION = get_content_declaration(FireBolt)
INVISIBILITY_DECLARATION = get_content_declaration(Invisibility)
BURNING_HANDS_DECLARATION = get_content_declaration(BurningHands)

SPELL_ITEM_DEPENDENCY_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    FIREBALL_DECLARATION,
    MAGIC_MISSILE_DECLARATION,
    HOLD_PERSON_DECLARATION,
    MAGE_ARMOR_DECLARATION,
    SPIKE_GROWTH_DECLARATION,
    FIRE_BOLT_DECLARATION,
    INVISIBILITY_DECLARATION,
    BURNING_HANDS_DECLARATION,
    ACID_FLASK_SPELL_DECLARATION,
)


def _grants_spell(
    declaration: ContentDeclaration,
) -> ContentDependency:
    return ContentDependency(
        relation=ContentDependencyRelation.GRANTS_SPELL,
        target_ref=declaration.ref,
        phase=ContentDependencyPhase.RUNTIME_REFERENCE,
        notes="The item grants this exact spell behavior as a use action.",
    )


class FireballScrollParameters(BaseModel):
    """Durable cast level for Scroll of Fireball."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 3


class MagicMissileScrollParameters(BaseModel):
    """Durable cast level for Scroll of Magic Missile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 1


class HoldPersonScrollParameters(BaseModel):
    """Durable cast level for Scroll of Hold Person."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 2


class MageArmorScrollParameters(BaseModel):
    """Durable cast level for Scroll of Mage Armor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 1


class SpikeGrowthScrollParameters(BaseModel):
    """Durable cast level for Scroll of Spike Growth."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 2


class InvisibilityScrollParameters(BaseModel):
    """Durable cast level for Scroll of Invisibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cast_level: int = 2


class FireBoltScrollParameters(BaseModel):
    """Durable caster-level scaling for a Fire Bolt scroll."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    caster_level: int = 5


class WandOfMagicMissilesParameters(BaseModel):
    """Durable initial charge count for Wand of Magic Missiles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = 3


class WandOfFireParameters(BaseModel):
    """Durable initial charge count for Wand of Fire."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    charges: int = 7


class EmptySpellItemParameters(BaseModel):
    """Spell items with no authored reconstruction variants."""

    model_config = ConfigDict(extra="forbid", frozen=True)


_POSSESSION_ITEM_DEFINITION = ItemDefinition(
    persistence_policy=ItemPersistencePolicy.POSSESSION,
)


def _spell_item_descriptor(
    *,
    content_id: str,
    display_name: str,
    description: str,
    group: str,
    visual_variant_key: str,
    sort_order: int,
    tags: tuple[str, ...],
    dependencies: tuple[ContentDeclaration, ...],
) -> ContentDescriptorSpec:
    return ContentDescriptorSpec(
        display_name=display_name,
        description=description,
        tags=("item", "neurodragon", *tags),
        visibility=ContentVisibility.PUBLIC,
        presentation=ContentPresentation(
            icon_key=content_id,
            visual_variant_key=visual_variant_key,
            ui_group=f"spell_items.{group}",
        ),
        ordering=ContentOrdering(
            sort_group=f"spell_items.{group}",
            sort_order=sort_order,
        ),
        related_content_refs=tuple(
            declaration.ref
            for declaration in dependencies
        ),
    )


def _srd_spell_scroll_provenance(display_name: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 242, Magic Items A-Z: "
            f"Spell Scroll; implemented variant: {display_name}"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "The existing fixed-spell usable item and cast-level behavior are "
            "preserved; arbitrary spell scrolls, rarity, and all source "
            "restrictions remain future source-completion work."
        ),
    )


def _neurodragon_provenance(display_name: str) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "Neurodragon original content baseline: "
            f"{display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes="Original spell-item mechanics preserved exactly.",
    )


def _scroll(
    context: object,
    *,
    display_name: str,
    description: str,
    cast_level: int,
    template: SpellAction,
    stack_suffix: str,
) -> SpellGrantingItem:
    item_context = ItemBuildContext.model_validate(context)
    return SpellGrantingItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name=display_name,
        description=description,
        visual_item_name=display_name,
        visual_variant_id=stack_suffix,
        scroll_cast_level=cast_level,
        use_action_templates=[template],
        stack_id=stack_suffix,
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_fireball",
    version=1,
    parameters=FireballScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_fireball",
        display_name="Scroll of Fireball",
        description="A consumable scroll that casts Fireball.",
        group="scrolls",
        visual_variant_key="fireball",
        sort_order=10,
        tags=("consumable", "scroll"),
        dependencies=(FIREBALL_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Fireball"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(FIREBALL_DECLARATION),),
)
def _build_scroll_of_fireball(
    context: object,
    parameters: FireballScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Fireball",
        description="Casts Fireball without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=Fireball(
            source_entity_uuid=uuid4(),
            caster_level=5,
            template=True,
        ),
        stack_suffix=f"scroll_fireball_l{parameters.cast_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_magic_missile",
    version=1,
    parameters=MagicMissileScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_magic_missile",
        display_name="Scroll of Magic Missile",
        description="A consumable scroll that casts Magic Missile.",
        group="scrolls",
        visual_variant_key="magic_missile",
        sort_order=20,
        tags=("consumable", "scroll"),
        dependencies=(MAGIC_MISSILE_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Magic Missile"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(MAGIC_MISSILE_DECLARATION),),
)
def _build_scroll_of_magic_missile(
    context: object,
    parameters: MagicMissileScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Magic Missile",
        description="Casts Magic Missile without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=MagicMissile(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        ),
        stack_suffix=f"scroll_magic_missile_l{parameters.cast_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_hold_person",
    version=1,
    parameters=HoldPersonScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_hold_person",
        display_name="Scroll of Hold Person",
        description="A consumable scroll that casts Hold Person.",
        group="scrolls",
        visual_variant_key="hold_person",
        sort_order=30,
        tags=("consumable", "scroll"),
        dependencies=(HOLD_PERSON_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Hold Person"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(HOLD_PERSON_DECLARATION),),
)
def _build_scroll_of_hold_person(
    context: object,
    parameters: HoldPersonScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Hold Person",
        description="Casts Hold Person without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=HoldPerson(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        stack_suffix=f"scroll_hold_person_l{parameters.cast_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_mage_armor",
    version=1,
    parameters=MageArmorScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_mage_armor",
        display_name="Scroll of Mage Armor",
        description="A consumable scroll that casts Mage Armor.",
        group="scrolls",
        visual_variant_key="mage_armor",
        sort_order=40,
        tags=("consumable", "scroll"),
        dependencies=(MAGE_ARMOR_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Mage Armor"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(MAGE_ARMOR_DECLARATION),),
)
def _build_scroll_of_mage_armor(
    context: object,
    parameters: MageArmorScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Mage Armor",
        description="Casts Mage Armor without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=MageArmor(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        ),
        stack_suffix=f"scroll_mage_armor_l{parameters.cast_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_spike_growth",
    version=1,
    parameters=SpikeGrowthScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_spike_growth",
        display_name="Scroll of Spike Growth",
        description="A consumable scroll that casts Spike Growth.",
        group="scrolls",
        visual_variant_key="spike_growth",
        sort_order=50,
        tags=("consumable", "scroll"),
        dependencies=(SPIKE_GROWTH_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Spike Growth"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(SPIKE_GROWTH_DECLARATION),),
)
def _build_scroll_of_spike_growth(
    context: object,
    parameters: SpikeGrowthScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Spike Growth",
        description="Casts Spike Growth without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=SpikeGrowth(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        stack_suffix=f"scroll_spike_growth_l{parameters.cast_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_fire_bolt",
    version=1,
    parameters=FireBoltScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_fire_bolt",
        display_name="Scroll of Fire Bolt",
        description="A consumable scroll with level-scaled Fire Bolt.",
        group="scrolls",
        visual_variant_key="fire_bolt",
        sort_order=60,
        tags=("cantrip", "consumable", "scroll"),
        dependencies=(FIRE_BOLT_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Fire Bolt"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(FIRE_BOLT_DECLARATION),),
)
def _build_scroll_of_fire_bolt(
    context: object,
    parameters: FireBoltScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Fire Bolt",
        description="Casts Fire Bolt without expending a spell slot.",
        cast_level=0,
        template=FireBolt(
            source_entity_uuid=uuid4(),
            caster_level=parameters.caster_level,
            template=True,
        ),
        stack_suffix=f"scroll_fire_bolt_cl{parameters.caster_level}",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.wand_magic_missiles",
    version=1,
    parameters=WandOfMagicMissilesParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.wand_magic_missiles",
        display_name="Wand of Magic Missiles",
        description="A finite-charge wand that casts Magic Missile.",
        group="wands",
        visual_variant_key="magic_missiles",
        sort_order=10,
        tags=("wand",),
        dependencies=(MAGIC_MISSILE_DECLARATION,),
    ),
    provenance=ContentProvenance(
        primary_source_id="wotc.srd_5_1_cc",
        source_anchor=(
            "SRD 5.1 (CC-BY-4.0), p. 249, Magic Items A-Z: "
            "Wand of Magic Missiles"
        ),
        relation=ContentProvenanceRelation.FAITHFUL_IMPLEMENTATION,
        fidelity=ContentFidelity.PARTIAL,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Existing finite-charge casting is preserved; source recharge, "
            "multi-charge upcasting, and destruction behavior are incomplete."
        ),
    ),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(MAGIC_MISSILE_DECLARATION),),
)
def _build_wand_of_magic_missiles(
    context: object,
    parameters: WandOfMagicMissilesParameters,
) -> SpellGrantingItem:
    item_context = ItemBuildContext.model_validate(context)
    return SpellGrantingItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Wand of Magic Missiles",
        description="Casts Magic Missile by spending one charge.",
        visual_item_name="Wand of Magic Missiles",
        visual_variant_id="magic_missiles",
        scroll_cast_level=1,
        charges=parameters.charges,
        max_charges=parameters.charges,
        is_consumable=False,
        is_pickable=True,
        use_action_templates=[
            MagicMissile(
                source_entity_uuid=uuid4(),
                caster_level=1,
                template=True,
            ),
        ],
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.wand_fire",
    version=1,
    parameters=WandOfFireParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.wand_fire",
        display_name="Wand of Fire",
        description=(
            "A finite-charge wand granting Burning Hands and two Fireball "
            "variants."
        ),
        group="wands",
        visual_variant_key="fire",
        sort_order=20,
        tags=("fire", "wand"),
        dependencies=(BURNING_HANDS_DECLARATION, FIREBALL_DECLARATION),
    ),
    provenance=_neurodragon_provenance("Wand of Fire"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(
        _grants_spell(BURNING_HANDS_DECLARATION),
        _grants_spell(FIREBALL_DECLARATION),
    ),
)
def _build_wand_of_fire(
    context: object,
    parameters: WandOfFireParameters,
) -> SpellGrantingItem:
    item_context = ItemBuildContext.model_validate(context)
    return SpellGrantingItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Wand of Fire",
        description=(
            "Casts Burning Hands or Fireball at fixed per-spell charge costs."
        ),
        visual_item_name="Wand of Fire",
        visual_variant_id="fire",
        scroll_cast_level=1,
        charges=parameters.charges,
        max_charges=parameters.charges,
        is_pickable=True,
        is_consumable=False,
        use_action_templates=[
            BurningHands(
                source_entity_uuid=uuid4(),
                caster_level=1,
                template=True,
                charge_cost=1,
            ),
            Fireball(
                source_entity_uuid=uuid4(),
                caster_level=5,
                template=True,
                charge_cost=3,
            ),
            Fireball(
                source_entity_uuid=uuid4(),
                caster_level=7,
                cast_at_level=4,
                template=True,
                charge_cost=4,
            ),
        ],
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="consumable.acid_flask",
    version=1,
    parameters=EmptySpellItemParameters,
    descriptor=_spell_item_descriptor(
        content_id="consumable.acid_flask",
        display_name="Acid Flask",
        description="A throwable consumable that splashes acid over an area.",
        group="consumables",
        visual_variant_key="acid_flask",
        sort_order=10,
        tags=("acid", "consumable", "thrown"),
        dependencies=(ACID_FLASK_SPELL_DECLARATION,),
    ),
    provenance=_neurodragon_provenance("Acid Flask"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(ACID_FLASK_SPELL_DECLARATION),),
)
def _build_acid_flask(
    context: object,
    parameters: EmptySpellItemParameters,
) -> SpellGrantingItem:
    _ = parameters
    item_context = ItemBuildContext.model_validate(context)
    return SpellGrantingItem(
        source_entity_uuid=item_context.source_entity_uuid,
        content_ref=item_context.requested_ref,
        name="Acid Flask",
        description="Throw for a two-by-two 2d4 acid splash.",
        visual_item_name="Acid Flask",
        visual_variant_id="acid_flask",
        scroll_cast_level=0,
        use_action_templates=[
            _AcidFlaskSpell(
                source_entity_uuid=uuid4(),
                caster_level=1,
                template=True,
            ),
        ],
        stack_id="acid_flask",
        map_char="!",
    )


@item_factory(
    pack_id="content.neurodragon",
    content_id="spell_item.scroll_invisibility",
    version=1,
    parameters=InvisibilityScrollParameters,
    descriptor=_spell_item_descriptor(
        content_id="spell_item.scroll_invisibility",
        display_name="Scroll of Invisibility",
        description="A consumable scroll that casts Invisibility.",
        group="scrolls",
        visual_variant_key="invisibility",
        sort_order=70,
        tags=("consumable", "scroll"),
        dependencies=(INVISIBILITY_DECLARATION,),
    ),
    provenance=_srd_spell_scroll_provenance("Scroll of Invisibility"),
    item_definition=_POSSESSION_ITEM_DEFINITION,
    dependencies=(_grants_spell(INVISIBILITY_DECLARATION),),
)
def _build_scroll_of_invisibility(
    context: object,
    parameters: InvisibilityScrollParameters,
) -> SpellGrantingItem:
    return _scroll(
        context,
        display_name="Scroll of Invisibility",
        description="Casts Invisibility without expending a spell slot.",
        cast_level=parameters.cast_level,
        template=Invisibility(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        stack_suffix=f"scroll_invisibility_l{parameters.cast_level}",
    )


FIREBALL_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_fireball,
)
FIREBALL_SCROLL_REF = FIREBALL_SCROLL_DECLARATION.ref
MAGIC_MISSILE_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_magic_missile,
)
MAGIC_MISSILE_SCROLL_REF = MAGIC_MISSILE_SCROLL_DECLARATION.ref
HOLD_PERSON_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_hold_person,
)
HOLD_PERSON_SCROLL_REF = HOLD_PERSON_SCROLL_DECLARATION.ref
MAGE_ARMOR_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_mage_armor,
)
MAGE_ARMOR_SCROLL_REF = MAGE_ARMOR_SCROLL_DECLARATION.ref
SPIKE_GROWTH_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_spike_growth,
)
SPIKE_GROWTH_SCROLL_REF = SPIKE_GROWTH_SCROLL_DECLARATION.ref
FIRE_BOLT_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_fire_bolt,
)
FIRE_BOLT_SCROLL_REF = FIRE_BOLT_SCROLL_DECLARATION.ref
WAND_OF_MAGIC_MISSILES_DECLARATION = get_content_declaration(
    _build_wand_of_magic_missiles,
)
WAND_OF_MAGIC_MISSILES_REF = WAND_OF_MAGIC_MISSILES_DECLARATION.ref
WAND_OF_FIRE_DECLARATION = get_content_declaration(_build_wand_of_fire)
WAND_OF_FIRE_REF = WAND_OF_FIRE_DECLARATION.ref
ACID_FLASK_DECLARATION = get_content_declaration(_build_acid_flask)
ACID_FLASK_REF = ACID_FLASK_DECLARATION.ref
INVISIBILITY_SCROLL_DECLARATION = get_content_declaration(
    _build_scroll_of_invisibility,
)
INVISIBILITY_SCROLL_REF = INVISIBILITY_SCROLL_DECLARATION.ref


def fireball_scroll_recipe(*, cast_level: int = 3) -> ContentRecipe:
    return ContentRecipe.create(
        ref=FIREBALL_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


def magic_missile_scroll_recipe(*, cast_level: int = 1) -> ContentRecipe:
    return ContentRecipe.create(
        ref=MAGIC_MISSILE_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


def hold_person_scroll_recipe(*, cast_level: int = 2) -> ContentRecipe:
    return ContentRecipe.create(
        ref=HOLD_PERSON_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


def mage_armor_scroll_recipe(*, cast_level: int = 1) -> ContentRecipe:
    return ContentRecipe.create(
        ref=MAGE_ARMOR_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


def spike_growth_scroll_recipe(*, cast_level: int = 2) -> ContentRecipe:
    return ContentRecipe.create(
        ref=SPIKE_GROWTH_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


def fire_bolt_scroll_recipe(*, caster_level: int = 5) -> ContentRecipe:
    return ContentRecipe.create(
        ref=FIRE_BOLT_SCROLL_REF,
        parameters={"caster_level": caster_level},
    )


def wand_of_magic_missiles_recipe(*, charges: int = 3) -> ContentRecipe:
    return ContentRecipe.create(
        ref=WAND_OF_MAGIC_MISSILES_REF,
        parameters={"charges": charges},
    )


def wand_of_fire_recipe(*, charges: int = 7) -> ContentRecipe:
    return ContentRecipe.create(
        ref=WAND_OF_FIRE_REF,
        parameters={"charges": charges},
    )


def invisibility_scroll_recipe(*, cast_level: int = 2) -> ContentRecipe:
    return ContentRecipe.create(
        ref=INVISIBILITY_SCROLL_REF,
        parameters={"cast_level": cast_level},
    )


FIREBALL_SCROLL_RECIPE = fireball_scroll_recipe()
MAGIC_MISSILE_SCROLL_RECIPE = magic_missile_scroll_recipe()
HOLD_PERSON_SCROLL_RECIPE = hold_person_scroll_recipe()
MAGE_ARMOR_SCROLL_RECIPE = mage_armor_scroll_recipe()
SPIKE_GROWTH_SCROLL_RECIPE = spike_growth_scroll_recipe()
FIRE_BOLT_SCROLL_RECIPE = fire_bolt_scroll_recipe()
WAND_OF_MAGIC_MISSILES_RECIPE = wand_of_magic_missiles_recipe()
WAND_OF_FIRE_RECIPE = wand_of_fire_recipe()
ACID_FLASK_RECIPE = ContentRecipe.create(
    ref=ACID_FLASK_REF,
    parameters={},
)
INVISIBILITY_SCROLL_RECIPE = invisibility_scroll_recipe()

NEURODRAGON_SPELL_ITEM_DECLARATIONS: tuple[ContentDeclaration, ...] = (
    FIREBALL_SCROLL_DECLARATION,
    MAGIC_MISSILE_SCROLL_DECLARATION,
    HOLD_PERSON_SCROLL_DECLARATION,
    MAGE_ARMOR_SCROLL_DECLARATION,
    SPIKE_GROWTH_SCROLL_DECLARATION,
    FIRE_BOLT_SCROLL_DECLARATION,
    WAND_OF_MAGIC_MISSILES_DECLARATION,
    WAND_OF_FIRE_DECLARATION,
    ACID_FLASK_DECLARATION,
    INVISIBILITY_SCROLL_DECLARATION,
)
