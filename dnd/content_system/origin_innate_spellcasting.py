"""Source-owned runtime installation for validated origin innate spells."""

from __future__ import annotations

from collections import defaultdict
from typing import cast
from uuid import UUID, uuid5

from dnd.actions import SpellAction
from dnd.blocks.action_economy import RechargeType
from dnd.content_system.character_build_validation import (
    OriginInnateSpellGrantPreview,
)
from dnd.content_system.character_grant_context import (
    BuiltinCharacterGrantContext,
)
from dnd.content_system.character_grant_types import (
    CharacterGrantReceipt,
    LearnedReactionSpellHandle,
)
from dnd.content_system.spell_catalog_composition import (
    SPELL_CATALOG_COMPOSITION_ROWS,
)
from dnd.core.base_actions import (
    Cost,
    block_action_resource_cost_evaluator,
)
from dnd.core.events import AbilityName
from dnd.spells.infernal import (
    HELLISH_REBUKE_SPELL_DECLARATION,
    create_hellish_rebuke_reaction_handler,
)


_SPELL_ROW_BY_REF_KEY = {
    row.declaration.ref.identity_key: row
    for row in SPELL_CATALOG_COMPOSITION_ROWS
}


def innate_spell_resource_name(
    grant: OriginInnateSpellGrantPreview,
) -> str:
    """Return the exact non-slot resource owned by one limited origin spell."""
    return (
        f"origin_innate_spell:{grant.spellcasting_source_id.value}:"
        f"{grant.grant_id}"
    )


def _source_runtime_id(
    character_id: UUID,
    source_id: str,
) -> UUID:
    return uuid5(
        character_id,
        f"dnd-engine:origin-innate-spellcasting:v1:{source_id}",
    )


def _grant_runtime_id(
    character_id: UUID,
    grant_token: str,
) -> UUID:
    return uuid5(character_id, grant_token)


def _remove_origin_innate_spellcasting(
    context: BuiltinCharacterGrantContext,
    receipts: list[CharacterGrantReceipt],
) -> None:
    """Remove a partially installed origin spell surface in reverse order."""
    for receipt in reversed(receipts):
        for action_uuid in reversed(receipt.action_uuids):
            context.entity.unregister_action_by_uuid(action_uuid)
        for handle in reversed(receipt.learned_reaction_spell_handles):
            remove_handler = (
                context.entity.spellcasting.remove_learned_reaction_spell_source(
                    spell_ref=handle.spell_ref,
                    source_id=handle.spellcasting_source_id,
                    handler_uuid=handle.handler_uuid,
                )
            )
            if remove_handler:
                handler = context.entity.event_handlers.get(
                    handle.handler_uuid,
                )
                if handler is not None:
                    context.entity.remove_event_handler(handler)
        for resource_name, source_id in reversed(
            receipt.resource_contribution_ids,
        ):
            context.entity.action_economy.remove_resource_contribution(
                resource_name,
                source_id,
            )
        for source_id in reversed(receipt.spellcasting_source_ids):
            context.entity.spellcasting.remove_source(source_id)


def _install_origin_innate_spellcasting(
    context: BuiltinCharacterGrantContext,
    receipts: list[CharacterGrantReceipt],
) -> None:
    """Install validated origin sources into the caller-owned receipt list."""
    by_source: dict[
        tuple[str, str],
        list[OriginInnateSpellGrantPreview],
    ] = defaultdict(list)
    for grant in context.preview.origin_innate_spells:
        by_source[
            (
                grant.provider_ref.identity_key,
                grant.spellcasting_source_id.value,
            )
        ].append(grant)

    for source_key in sorted(by_source):
        grants = by_source[source_key]
        exemplar = grants[0]
        if any(
            (
                grant.provider_ref != exemplar.provider_ref
                or grant.spellcasting_source_id
                != exemplar.spellcasting_source_id
                or grant.spellcasting_ability
                != exemplar.spellcasting_ability
                or grant.provider_level != exemplar.provider_level
            )
            for grant in grants
        ):
            raise RuntimeError("origin innate source has conflicting facts")
        source_uuid = _source_runtime_id(
            context.character_id,
            exemplar.spellcasting_source_id.value,
        )
        context.entity.spellcasting.add_innate_source(
            source_uuid,
            cast(AbilityName, exemplar.spellcasting_ability.value),
            provider_ref=exemplar.provider_ref,
            provider_level=exemplar.provider_level,
            maximum_spell_rank=max(
                grant.fixed_cast_rank for grant in grants
            ),
        )
        receipts.append(
            CharacterGrantReceipt(
                grant_id=source_uuid,
                definition_ref=exemplar.provider_ref,
                spellcasting_source_ids=(source_uuid,),
            ),
        )

        for grant in sorted(grants, key=lambda row: row.grant_id):
            row = _SPELL_ROW_BY_REF_KEY.get(grant.spell_ref.identity_key)
            if row is None or row.declaration.ref != grant.spell_ref:
                raise RuntimeError(
                    "Origin innate spell has no exact runtime row: "
                    f"{grant.spell_ref.identity_key}",
                )
            grant_uuid = _grant_runtime_id(
                context.character_id,
                grant.grant_token,
            )
            resource_name = None
            resource_handles: tuple[tuple[str, UUID], ...] = ()
            if grant.uses_per_long_rest is not None:
                resource_name = innate_spell_resource_name(grant)
                context.entity.action_economy.add_resource_contribution(
                    resource_name,
                    grant_uuid,
                    maximum=grant.uses_per_long_rest,
                    recharge_type=RechargeType.LONG_REST,
                )
                resource_handles = ((resource_name, grant_uuid),)

            if row.spell_type is not None:
                spell = row.spell_type(
                    source_entity_uuid=context.entity.uuid,
                    caster_level=grant.provider_level,
                    cast_at_level=grant.fixed_cast_rank,
                    spellcasting_source_id=source_uuid,
                    alt_skip_slot=grant.fixed_cast_rank > 0,
                    alt_extra_costs=(
                        [
                            Cost(
                                name=(
                                    f"{grant.grant_id} long-rest use"
                                ),
                                cost_type="actions",
                                cost=0,
                                resource_name=resource_name,
                                resource_cost=1,
                                resource_evaluator=(
                                    block_action_resource_cost_evaluator
                                ),
                            ),
                        ]
                        if resource_name is not None
                        else []
                    ),
                    template=True,
                )
                if not isinstance(spell, SpellAction):
                    raise TypeError("origin spell row constructed another action")
                try:
                    context.runtime.bind_granted_behavior(
                        spell,
                        provider_ref=grant.provider_ref,
                        runtime_owner_uuid=context.entity.uuid,
                    )
                    context.entity.register_action(spell)
                except Exception:
                    if resource_name is not None:
                        context.entity.action_economy.remove_resource_contribution(
                            resource_name,
                            grant_uuid,
                        )
                    raise
                receipts.append(
                    CharacterGrantReceipt(
                        grant_id=grant_uuid,
                        grant_token=grant.grant_token,
                        definition_ref=grant.spell_ref,
                        action_uuids=(spell.uuid,),
                        resource_contribution_ids=resource_handles,
                    ),
                )
                continue

            if (
                grant.spell_ref
                != HELLISH_REBUKE_SPELL_DECLARATION.ref
            ):
                raise RuntimeError(
                    "Origin innate reaction spell has no source-aware "
                    f"installer: {grant.spell_ref.identity_key}",
                )
            handler = create_hellish_rebuke_reaction_handler(
                context.entity.uuid,
                spellcasting_source_id=source_uuid,
                fixed_cast_rank=grant.fixed_cast_rank,
                resource_name=resource_name,
            )
            try:
                context.runtime.bind_granted_behavior(
                    handler,
                    provider_ref=grant.provider_ref,
                    runtime_owner_uuid=context.entity.uuid,
                )
                context.entity.add_event_handler(handler)
                context.entity.spellcasting.add_learned_reaction_spell_source(
                    spell_ref=grant.spell_ref,
                    source_id=source_uuid,
                    handler_uuid=handler.uuid,
                )
            except Exception:
                if handler.uuid in context.entity.event_handlers:
                    context.entity.remove_event_handler(handler)
                if resource_name is not None:
                    context.entity.action_economy.remove_resource_contribution(
                        resource_name,
                        grant_uuid,
                    )
                raise
            receipts.append(
                CharacterGrantReceipt(
                    grant_id=grant_uuid,
                    grant_token=grant.grant_token,
                    definition_ref=grant.spell_ref,
                    learned_reaction_spell_handles=(
                        LearnedReactionSpellHandle(
                            spell_ref=grant.spell_ref,
                            spellcasting_source_id=source_uuid,
                            handler_uuid=handler.uuid,
                        ),
                    ),
                    resource_contribution_ids=resource_handles,
                ),
            )


def install_origin_innate_spellcasting(
    context: BuiltinCharacterGrantContext,
) -> tuple[CharacterGrantReceipt, ...]:
    """Install every validated origin source, action, reaction, and resource."""
    receipts: list[CharacterGrantReceipt] = []
    try:
        _install_origin_innate_spellcasting(context, receipts)
    except Exception:
        _remove_origin_innate_spellcasting(context, receipts)
        raise
    return tuple(receipts)


__all__ = [
    "innate_spell_resource_name",
    "install_origin_innate_spellcasting",
]
