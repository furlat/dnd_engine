"""Authored NPC spell selections composed through existing source and cost owners."""

from uuid import UUID, uuid5

from dnd.actions import SpellAction, entity_action_economy_cost_evaluator, entity_resource_cost_evaluator
from dnd.blocks.action_economy import RechargeType, ResourceCapacityPolicy
from dnd.blocks.spellcasting import FreeSpellCastGrant
from dnd.core.base_actions import Cost
from dnd.core.content.registration import get_content_declaration
from dnd.entity import Entity
from dnd.spells.abjuration import (
    Banishment, GlobeOfInvulnerability, MageArmor, Stoneskin,
    create_counterspell_reaction_handler, create_shield_reaction_handler,
)
from dnd.spells.conjuration import MistyStep
from dnd.spells.evocation import (
    ConeOfCold, Fireball, FireBolt, FireShield, IceStorm, Light, LightningBolt,
    MagicMissile, ShockingGrasp,
)
from dnd.spells.illusion import GreaterInvisibility, MirrorImage
from dnd.spells.transmutation import Fly
from dnd.spells.wall_constructions import WallOfForce
from dnd.types.abilities import AbilityName


MAGE_SPELLS = (FireBolt, Light, MageArmor, MagicMissile, MistyStep, Fireball, Fly,
               GreaterInvisibility, IceStorm, ConeOfCold)
MAGE_OMITTED_SPELLS = ("detect_magic", "mage_hand", "prestidigitation", "suggestion")
ARCHMAGE_SPELLS = (FireBolt, Light, ShockingGrasp, MageArmor, MagicMissile,
                  MirrorImage, MistyStep, Fly, LightningBolt, Banishment,
                  FireShield, Stoneskin, ConeOfCold, WallOfForce, GlobeOfInvulnerability)
ARCHMAGE_OMITTED_SPELLS = (
    "mage_hand", "prestidigitation", "detect_magic", "identify", "detect_thoughts",
    "scrying", "teleport", "mind_blank", "time_stop", "disguise_self",
)


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
    action = spell_type(source_entity_uuid=entity.uuid, caster_level=caster_level,
        alt_skip_slot=True, template=True, **({"cast_at_level": cast_rank} if cast_rank is not None else {}))
    source, resource = _innate_source(entity, spell_id, caster_level=caster_level,
        rank=action.cast_at_level, daily_uses=daily_uses, ability=ability)
    action.spellcasting_source_id = source
    action.costs = [cost for cost in action.costs if not cost.cost_type.startswith("spell_slot")]
    if resource is not None:
        if not action.costs:
            action.costs = [Cost(name=action.name, cost_type="actions", cost=0,
                evaluator=entity_action_economy_cost_evaluator)]
        action.costs[0] = action.costs[0].model_copy(update={
            "resource_name": resource, "resource_cost": 1,
            "resource_evaluator": entity_resource_cost_evaluator,
        })
    entity.register_action(action)
    return action


def grant_innate_reaction(entity: Entity, spell_id: str, *, cast_rank: int,
                          daily_uses: int | None = None, caster_level: int = 1,
                          ability: AbilityName = "charisma") -> None:
    """Bind the existing Shield/Counterspell handler to its exact innate cost."""
    factories = {"spell.shield": create_shield_reaction_handler,
                 "spell.counterspell": create_counterspell_reaction_handler}
    factory = factories[spell_id]
    source, resource = _innate_source(entity, spell_id, caster_level=caster_level,
        rank=cast_rank, daily_uses=daily_uses, ability=ability)
    existing = entity.spellcasting.learned_reaction_spell_handlers.get(spell_id)
    handler = factory(entity.uuid) if existing is None else None
    handler_uuid = existing.handler_uuid if existing is not None else handler.uuid
    entity.spellcasting.add_learned_reaction_spell_source(spell_id=spell_id,
        source_id=source, handler_uuid=handler_uuid,
        fixed_cast_rank=cast_rank if resource is not None else None, resource_name=resource)
    if handler is not None:
        entity.add_event_handler(handler)
    if resource is None:
        entity.spellcasting.free_cast_grants[source] = FreeSpellCastGrant(
            grant_id=source, provider_id=entity.content_ref.content_id, source_id=source,
            spell_id=spell_id, cast_rank=cast_rank, label="Innate")
