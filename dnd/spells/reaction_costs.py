"""Source-aware native payment choices shared by learned reaction spells."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.blocks.action_economy import (
    ActionEconomyChannelCost,
    NamedResourceCost,
    FixedCostCommitError,
)
from dnd.core.base_actions import spell_slot_cost_type
from dnd.core.effect_types import EffectOrigin
from dnd.core.events import Event, EventQueue, EventPhase, ActionCostsCommittedEvent
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class ReactionSpellCost:
    spell_id: str
    base_rank: int
    cast_rank: int
    source_id: UUID | None
    free_grant_id: UUID | None = None
    resource_name: str | None = None


def choose_reaction_spell_cost(
    actor: Entity, spell_id: str, base_rank: int, *, preferred_rank: int | None = None
) -> ReactionSpellCost | None:
    if not actor.action_economy.can_afford("reactions", 1):
        return None
    sources = actor.spellcasting.learned_reaction_spell_source_ids(spell_id)
    grants = [
        grant
        for grant in actor.spellcasting.free_cast_grants.values()
        if grant.spell_id == spell_id
        and grant.source_id in sources
        and grant.cast_rank == base_rank
        and (not grant.outside_encounter_only or actor.active_encounter_uuid is None)
        and (
            grant.resource_name is None
            or actor.action_economy.can_afford_resource(grant.resource_name, 1)
        )
        and spell_id in actor.spellcasting.spell_entitlements.get(grant.source_id, ())
    ]
    if grants:
        grant = min(
            grants, key=lambda row: (row.resource_name is not None, str(row.grant_id))
        )
        return ReactionSpellCost(
            spell_id,
            base_rank,
            base_rank,
            grant.source_id,
            grant.grant_id,
            grant.resource_name,
        )
    rank = actor.get_lowest_spell_slot(
        preferred_rank or base_rank
    ) or actor.get_lowest_spell_slot(base_rank)
    if rank is None:
        return None
    source_id = max(
        sources,
        key=lambda identity: (
            actor.ability_scores.get_ability(
                actor.spellcasting.resolve_spellcasting_ability(identity)
            ).modifier,
            str(identity),
        ),
        default=None,
    )
    return ReactionSpellCost(spell_id, base_rank, rank, source_id)


def commit_reaction_spell_cost(
    actor: Entity, cost: ReactionSpellCost, parent: Event
) -> bool:
    if cost.free_grant_id is not None:
        grant = actor.spellcasting.free_cast_grants.get(cost.free_grant_id)
        if (
            grant is None
            or grant.spell_id != cost.spell_id
            or grant.source_id != cost.source_id
            or grant.cast_rank != cost.cast_rank
            or grant.resource_name != cost.resource_name
        ):
            return False
        if (
            grant.outside_encounter_only
            and actor.active_encounter_uuid is not None
            or cost.spell_id
            not in actor.spellcasting.spell_entitlements.get(cost.source_id, ())
        ):
            return False
    channels = [ActionEconomyChannelCost(cost_type="reactions", amount=1)]
    if cost.free_grant_id is None:
        channels.append(
            ActionEconomyChannelCost(
                cost_type=spell_slot_cost_type(cost.cast_rank), amount=1
            )
        )
    resources = (
        ()
        if cost.resource_name is None
        else (NamedResourceCost(name=cost.resource_name, amount=1),)
    )
    try:
        actor.action_economy.commit_fixed_costs_without_dispatch(
            channel_costs=tuple(channels), resource_costs=resources
        )
    except FixedCostCommitError:
        return False
    origin = EffectOrigin.spell(
        source_id=cost.spell_id,
        source_event_lineage_uuid=str(parent.lineage_uuid),
        source_position=actor.position,
        base_spell_level=cost.base_rank,
        effective_spell_level=cost.cast_rank,
        spellcasting_source_id=cost.source_id,
    )
    committed = EventQueue.publish_committed_phase(
        ActionCostsCommittedEvent(
            source_entity_uuid=actor.uuid,
            target_entity_uuid=actor.uuid,
            action_lineage_uuid=uuid4(),
            effect_origin=origin,
            parent_event=parent.uuid,
            named_resource_costs=tuple(
                (resource.name, resource.amount) for resource in resources
            ),
            phase=EventPhase.EFFECT,
            use_register=False,
        )
    )
    committed.phase_to(EventPhase.COMPLETION)
    return True
