"""Direct spell-bearing item builders and their reusable runtime mechanism."""

from types import MappingProxyType

from typing import Any, Optional, cast as type_cast
from uuid import UUID, uuid4

from pydantic import Field

from dnd.actions import (
    SpellAction,
    SpellEvent,
    entity_action_economy_cost_evaluator,
)
from dnd.blocks.base_item import UsableItem
from dnd.core.aoe import AoEShape, Cube
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentOrdering,
    ContentPresentation,
    ContentVisibility,
)
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.registration import (
    behavior_identity,
    get_content_declaration,
)
from dnd.core.content.runtime import RuntimeBehaviorKind
from dnd.core.dice import AttackOutcome
from dnd.core.events import (
    Damage,
    EventPhase,
    Range,
    RangeType,
)
from dnd.core.creature_types import DamageType
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.abjuration import MageArmor
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
    materializable by itself. Direct item builders provide authored identity.
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
                action = template._create_variant(
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
                )
                if action.behavior_binding is None:
                    self.bind_dynamic_use_action(action)
                result.append(action)
                continue

            action = template.model_copy(
                deep=True,
                update={
                    "uuid": uuid4(),
                    "source_entity_uuid": user_entity_uuid,
                    "source_item_uuid": self.uuid,
                    "source_item_presentation": source_item_presentation,
                    "charge_cost": template_charge_cost,
                },
            )
            if action.behavior_binding is None:
                self.bind_dynamic_use_action(action)
            result.append(action)
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
                target=self.end_position or (0, 0),
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
        if not target_pos:
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

        distance = caster.senses.get_feet_distance(target_pos)
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
            ability_name="dexterity",
            dc=self._fixed_dc,
            parent_event=execution_event.uuid,
        )
        _, save_roll, success = target.saving_throw(save_request)
        save_bonus = target.saving_throw_bonus(
            caster.uuid,
            "dexterity",
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
        return effect_event.with_updates(
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
SPELL_ITEM_BEHAVIOR_DECLARATIONS_BY_CLASS = MappingProxyType({
    _AcidFlaskSpell: ACID_FLASK_SPELL_DECLARATION,
})


def _direct_scroll(
    source_entity_uuid: UUID,
    *,
    item_id: str,
    display_name: str,
    description: str,
    cast_level: int,
    template: SpellAction,
    variant_id: str,
) -> SpellGrantingItem:
    """Construct one directly identified spell scroll."""
    return SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        item_id=item_id,
        name=display_name,
        description=description,
        visual_item_name=display_name,
        visual_variant_id=variant_id,
        scroll_cast_level=cast_level,
        use_action_templates=[template],
        stack_id=variant_id,
    )


def build_fireball_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 3,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_fireball",
        display_name="Scroll of Fireball",
        description="Casts Fireball without expending a spell slot.",
        cast_level=cast_level,
        template=Fireball(
            source_entity_uuid=uuid4(),
            caster_level=5,
            template=True,
        ),
        variant_id=f"scroll_fireball_l{cast_level}",
    )


def build_magic_missile_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 1,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_magic_missile",
        display_name="Scroll of Magic Missile",
        description="Casts Magic Missile without expending a spell slot.",
        cast_level=cast_level,
        template=MagicMissile(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        ),
        variant_id=f"scroll_magic_missile_l{cast_level}",
    )


def build_hold_person_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 2,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_hold_person",
        display_name="Scroll of Hold Person",
        description="Casts Hold Person without expending a spell slot.",
        cast_level=cast_level,
        template=HoldPerson(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        variant_id=f"scroll_hold_person_l{cast_level}",
    )


def build_mage_armor_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 1,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_mage_armor",
        display_name="Scroll of Mage Armor",
        description="Casts Mage Armor without expending a spell slot.",
        cast_level=cast_level,
        template=MageArmor(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        ),
        variant_id=f"scroll_mage_armor_l{cast_level}",
    )


def build_spike_growth_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 2,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_spike_growth",
        display_name="Scroll of Spike Growth",
        description="Casts Spike Growth without expending a spell slot.",
        cast_level=cast_level,
        template=SpikeGrowth(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        variant_id=f"scroll_spike_growth_l{cast_level}",
    )


def build_fire_bolt_scroll(
    source_entity_uuid: UUID,
    *,
    caster_level: int = 5,
) -> SpellGrantingItem:
    if not 1 <= caster_level <= 20:
        raise ValueError("Fire Bolt scroll caster_level must be between 1 and 20")
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_fire_bolt",
        display_name="Scroll of Fire Bolt",
        description="Casts Fire Bolt without expending a spell slot.",
        cast_level=0,
        template=FireBolt(
            source_entity_uuid=uuid4(),
            caster_level=caster_level,
            template=True,
        ),
        variant_id=f"scroll_fire_bolt_cl{caster_level}",
    )


def build_invisibility_scroll(
    source_entity_uuid: UUID,
    *,
    cast_level: int = 2,
) -> SpellGrantingItem:
    return _direct_scroll(
        source_entity_uuid,
        item_id="spell_item.scroll_invisibility",
        display_name="Scroll of Invisibility",
        description="Casts Invisibility without expending a spell slot.",
        cast_level=cast_level,
        template=Invisibility(
            source_entity_uuid=uuid4(),
            caster_level=3,
            template=True,
        ),
        variant_id=f"scroll_invisibility_l{cast_level}",
    )


def build_wand_of_magic_missiles(
    source_entity_uuid: UUID,
    *,
    charges: int = 3,
) -> SpellGrantingItem:
    return SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        item_id="spell_item.wand_magic_missiles",
        name="Wand of Magic Missiles",
        description="Casts Magic Missile by spending one charge.",
        visual_item_name="Wand of Magic Missiles",
        visual_variant_id="magic_missiles",
        scroll_cast_level=1,
        charges=charges,
        max_charges=charges,
        is_consumable=False,
        is_pickable=True,
        use_action_templates=[MagicMissile(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        )],
    )


def build_wand_of_fire(
    source_entity_uuid: UUID,
    *,
    charges: int = 7,
) -> SpellGrantingItem:
    return SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        item_id="spell_item.wand_fire",
        name="Wand of Fire",
        description="Casts Burning Hands or Fireball at fixed per-spell charge costs.",
        visual_item_name="Wand of Fire",
        visual_variant_id="fire",
        scroll_cast_level=1,
        charges=charges,
        max_charges=charges,
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


def build_acid_flask(source_entity_uuid: UUID) -> SpellGrantingItem:
    return SpellGrantingItem(
        source_entity_uuid=source_entity_uuid,
        item_id="consumable.acid_flask",
        name="Acid Flask",
        description="Throw for a two-by-two 2d4 acid splash.",
        visual_item_name="Acid Flask",
        visual_variant_id="acid_flask",
        scroll_cast_level=0,
        use_action_templates=[_AcidFlaskSpell(
            source_entity_uuid=uuid4(),
            caster_level=1,
            template=True,
        )],
        stack_id="acid_flask",
        map_char="!",
    )
