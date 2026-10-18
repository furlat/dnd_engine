"""Authored NPC spell selections composed through existing source and cost owners."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid5

from dnd.actions import SpellAction, entity_resource_cost_evaluator
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.core.base_actions import Cost
from dnd.core.content.registration import ContentDeclaration, get_content_declaration
from dnd.core.events import EventHandler
from dnd.entity import Entity
from dnd.spells.abjuration import (
    COUNTERSPELL_REACTION_DECLARATION, SHIELD_REACTION_DECLARATION,
    Banishment, GlobeOfInvulnerability, MageArmor, Stoneskin,
    create_counterspell_reaction_handler, create_shield_reaction_handler,
)
from dnd.spells.conjuration import MistyStep
from dnd.spells.evocation import (
    ConeOfCold, Fireball, FireBolt, FireShield, IceStorm, Light, LightningBolt,
    MagicMissile, ShockingGrasp,
)
from dnd.spells.illusion import GreaterInvisibility, MirrorImage
from dnd.spells.reaction_spell_content import COUNTERSPELL_SPELL_DECLARATION, SHIELD_SPELL_DECLARATION
from dnd.spells.transmutation import Fly
from dnd.spells.wall_constructions import WallOfForce
from dnd.types.abilities import AbilityName


MAGE_SPELLS = (FireBolt, Light, MageArmor, MagicMissile, MistyStep, Fireball, Fly,
               GreaterInvisibility, IceStorm, ConeOfCold)
ARCHMAGE_SPELLS = (FireBolt, Light, ShockingGrasp, MageArmor, MagicMissile,
                  MirrorImage, MistyStep, Fly, LightningBolt, Banishment,
                  FireShield, Stoneskin, ConeOfCold, WallOfForce, GlobeOfInvulnerability)


@dataclass(frozen=True, slots=True)
class InnateReactionSpell:
    """A reaction spell an authored creature casts from its own daily innate uses."""

    spell: ContentDeclaration
    reaction: ContentDeclaration
    create_handler: Callable[[UUID], EventHandler]


SHIELD_REACTION_SPELL = InnateReactionSpell(
    SHIELD_SPELL_DECLARATION, SHIELD_REACTION_DECLARATION, create_shield_reaction_handler)
COUNTERSPELL_REACTION_SPELL = InnateReactionSpell(
    COUNTERSPELL_SPELL_DECLARATION, COUNTERSPELL_REACTION_DECLARATION, create_counterspell_reaction_handler)


def _innate_source(entity: Entity, spell_id: str, *, caster_level: int,
                   rank: int, daily_uses: int | None, ability: AbilityName) -> tuple[UUID, str | None]:
    """Install the exact authored source and optional per-spell daily capacity."""
    source = uuid5(entity.uuid, f"innate:{spell_id}:{rank}")
    if entity.content_ref is None:
        raise ValueError("Authored innate casting requires a creature content identity")
    provider = entity.content_ref.content_id
    entity.spellcasting.add_innate_source(source, ability, provider_id=provider,
        provider_level=caster_level, maximum_spell_rank=rank)
    entity.spellcasting.spell_entitlements[source] = (spell_id,)
    resource = None
    if daily_uses is not None:
        if daily_uses < 1:
            raise ValueError("Authored daily spell uses must be positive")
        resource = f"innate.{spell_id}.{rank}"
        entity.action_economy.add_resource_contribution(resource, source,
            maximum=daily_uses, recharge_type=RechargeType.LONG_REST,
            capacity_policy=ResourceCapacityPolicy.MAXIMUM)
    return source, resource


def grant_innate_spell(entity: Entity, spell_type: type[SpellAction], *, caster_level: int = 1,
                       cast_rank: int | None = None, daily_uses: int | None = None,
                       ability: AbilityName = "charisma") -> SpellAction:
    """Register a fixed-rank native cast with its real source and finite uses."""
    declaration = get_content_declaration(spell_type)
    spell_id = declaration.ref.content_id
    # A cast level of 0 is SpellAction's own "cast at the spell's level".
    action = spell_type(source_entity_uuid=entity.uuid, caster_level=caster_level,
        cast_at_level=cast_rank if cast_rank is not None else 0, alt_skip_slot=True, template=True)
    source, resource = _innate_source(entity, spell_id, caster_level=caster_level,
        rank=action.cast_at_level, daily_uses=daily_uses, ability=ability)
    action.spellcasting_source_id = source
    if resource is not None:
        action.alt_extra_costs = [Cost(name=f"{action.name} daily use", cost_type="actions", cost=0,
            resource_name=resource, resource_cost=1, resource_evaluator=entity_resource_cost_evaluator)]
    entity.register_action(action)
    return action


def grant_innate_reaction(entity: Entity, reaction: InnateReactionSpell, *, cast_rank: int,
                          daily_uses: int, caster_level: int = 1,
                          ability: AbilityName = "charisma") -> None:
    """Bind the existing reaction spell handler to its exact fixed-rank daily innate source."""
    spell_id = reaction.spell.ref.content_id
    source, resource = _innate_source(entity, spell_id, caster_level=caster_level,
        rank=cast_rank, daily_uses=daily_uses, ability=ability)
    existing = entity.spellcasting.learned_reaction_spell_handlers.get(spell_id)
    if existing is not None:
        entity.spellcasting.add_learned_reaction_spell_source(spell_id=spell_id,
            source_id=source, handler_uuid=existing.handler_uuid, fixed_cast_rank=cast_rank, resource_name=resource)
        return
    handler = reaction.create_handler(entity.uuid)
    entity.spellcasting.add_learned_reaction_spell_source(spell_id=spell_id,
        source_id=source, handler_uuid=handler.uuid, fixed_cast_rank=cast_rank, resource_name=resource)
    entity.add_event_handler(handler)
