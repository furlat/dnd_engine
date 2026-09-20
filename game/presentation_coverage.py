"""Developer views over loaded presentation owners and actual lineage binding.

No registration, asset access, native event reconstruction, or frame work lives
here. Declared bindings and observed results are deliberately separate records.
"""

from dataclasses import fields
from typing import Any, Iterable, cast, get_args
from uuid import UUID

from dnd.core.condition_types import ConditionCategory
from game.animation_types import AnimationData
from game.body_action import ACCEPTED_SOURCE_STRIP_RECIPES, body_action_limitations, body_cast_limitations
from game.choreography import BoundChoreography, FACT_PRESENTATION, MotionTimeline
from game.condition_animation import persistent_limitations, transition_limitations
from game.player_facts import (
    ActionFact, AttackFact, ConditionChangeFact, PlayerFact, PlayerLineage,
    ShoveFact, SpellFact,
)
from game.player_reduction import STATE_PRESENTATION_KINDS


def _row(family: str, identity: str, owner: str, representation: str,
         status: str, *, binding: str | None = None,
         details: Iterable[str] = ()) -> dict[str, Any]:
    return {"family": family, "identity": identity, "owner": owner,
            "representation": representation, "status": status,
            "binding": binding, "details": list(details)}


def presentation_inventory(data: AnimationData, *, spell_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Enumerate selected metadata. Optional catalog IDs come from the caller.

    A selected binding is not a guarantee that media exist or every possible
    lineage works. Those are observations of the ordinary binder/media loader.
    """
    rows = []
    for model in get_args(get_args(PlayerFact)[0]):
        identity = cast(str, next(field.default for field in fields(model) if field.name == "kind"))
        if identity in STATE_PRESENTATION_KINDS:
            rows.append(_row("fact", identity, "player_reduction", "state", "state_only"))
        else:
            owner, representation = FACT_PRESENTATION.get(identity, ("unassessed", "unassessed"))
            rows.append(_row("fact", identity, owner, representation,
                             "unassessed" if owner == "unassessed" else "declared"))
    for identity in sorted(set(spell_ids) | data.drafts.keys()):
        draft = data.drafts.get(identity)
        if draft is None:
            rows.append(_row("spell", identity, "cast", "cast timeline", "missing_binding",
                             details=("No selected cast draft; child outcomes may still be presented.",)))
            continue
        body_only = draft.projectile is None and draft.area is None
        limitations = body_cast_limitations(draft) if body_only else ()
        rows.append(_row("spell", identity, "body_action" if body_only else "cast", "timeline",
                         "partial" if limitations else "binding_selected", binding=identity, details=limitations))
    for family, recipes in (("attack", data.attack_recipes), ("shove", data.shove_recipes)):
        rows.extend(_row(family, identity, family, "timeline", "binding_selected", binding=identity)
                    for identity in sorted(recipes))
    for identity in sorted(data.body_action_recipes.keys() | data.body_action_bindings.keys()):
        alias = data.body_action_bindings.get(identity)
        selected = alias.source_recipe if alias is not None else identity
        recipe = data.body_action_recipes.get(selected)
        limitations = (() if recipe is None or not (recipe.variants or recipe.projectile is not None)
                       else ("Body action requires a resolved actor-only content recipe.",))
        source_media = body_action_limitations(recipe) if recipe is not None else ()
        accepted_source_media = selected in ACCEPTED_SOURCE_STRIP_RECIPES
        if not accepted_source_media:
            limitations += source_media
        rows.append(_row("action", identity, "body_action", "body timeline",
                         "missing_binding" if recipe is None else "partial" if limitations else "binding_selected",
                         binding=selected if recipe is not None else None, details=limitations))
        if source_media:
            rows.append(_row("action_source_media", identity, "body_action", "source strip",
                             "accepted_omission" if accepted_source_media else "partial", binding=selected,
                             details=(("Existing potion source strip intentionally omitted; body and effect timing remain.",)
                                      if accepted_source_media else source_media)))
    for identity, recipe in sorted(data.condition_recipes.items()):
        limitations = (*persistent_limitations(recipe),
                        *transition_limitations(identity, recipe.application),
                        *transition_limitations(identity, recipe.removal))
        rows.append(_row("condition", identity, "condition", "membership and appearance",
                         "partial" if limitations else "state_only" if recipe.disposition == "state_only"
                         else "binding_selected", binding=identity, details=limitations))
    for identity, rig in sorted(data.rigs.items()):
        rows.append(_row("rig", identity, "body rig", "registered clip mappings", "binding_selected",
                         binding=identity, details=(f"{len(rig.clips)} selected clip mappings; media not audited.",)))
    for identity, rig in sorted(data.creature_rigs.items()):
        rows.append(_row("creature", identity, "body rig", "rig selection",
                         "binding_selected" if rig in data.rigs else "missing_binding", binding=rig))
    rows.extend(_row("world", identity, "world_animation", "received property transition", "binding_selected",
                     binding=identity) for identity in sorted(data.world_animations))
    return rows


def lineage_coverage(lineage: PlayerLineage, *, group: BoundChoreography | None = None,
                     motion: MotionTimeline | None = None) -> list[dict[str, Any]]:
    """Describe received facts and actual cues once, after lineage binding.

    Absence of a cue is merely 'received', not a failure: disclosure, canceled
    parents and linked effects can legitimately suppress independent animation.
    Native categories or private input files are never consulted.
    """
    owners: dict[UUID, str] = {}
    gaps: dict[UUID, list[str]] = {}
    world: set[str] = set()

    def visit_motion(value: MotionTimeline) -> None:
        for reaction in value.reactions:
            visit_group(reaction.choreography)

    def visit_group(value: BoundChoreography) -> None:
        for identity, detail in value.gaps:
            gaps.setdefault(identity, []).append(detail)
        for cues, owner in ((value.nodes, "attack/cast"), (value.conditions, "condition"),
                            (value.equipment, "equipment"), (value.shoves, "shove"),
                            (value.forced_movement, "forced_movement"), (value.damage, "damage"),
                            (value.body_actions, "body_action"), (value.movements, "movement")):
            for cue in cues:
                owners[cue.event_uuid] = owner
        for cue in value.healing:
            owners[cue.event.uuid] = "healing"
        for cue in value.lifecycle:
            owners[cue.event.uuid] = "lifecycle"
        for cue in value.movements:
            visit_motion(cue.timeline)
        for transition in value.world_transitions:
            if transition.field == "trap_state":
                effect = (value.after.senses.spatial_effects.get(transition.identity)
                          if value.after.senses is not None else None)
                if effect is not None:
                    world.add(effect.content_ref.content_id)
            else:
                obj = value.after.objects.get(transition.identity)
                if obj is not None:
                    world.add(obj.item.item_id)

    if group is not None:
        visit_group(group)
    if motion is not None:
        owners[lineage.root.uuid] = "movement"
        visit_motion(motion)
    events = {event.lineage_uuid: event for event in lineage.events}
    result: list[dict[str, Any]] = [
        {"root_uuid": str(lineage.root.uuid), "event_uuid": None, "owner": "world_animation",
         "observed": "bound", "issues": [], "family": "world", "identity": identity}
        for identity in sorted(world)
    ]
    for event in lineage.events:
        fact = event.fact
        if fact is None:
            continue  # No inference about a correctly undisclosed or technical node.
        owner = owners.get(event.uuid)
        # parent_event identifies the emitting phase version. Complete retained
        # nodes are related by stable lineage identity, as in the compositor.
        parent = event.parent_lineage
        parent_owner = None
        while parent is not None and parent in events:
            ancestor = events[parent]
            if ancestor.uuid in owners:
                parent_owner = owners[ancestor.uuid]
                break
            parent = ancestor.parent_lineage
        parent_owned = parent_owner is not None and (
            fact.kind in {"damage", "step", "life"}
            or isinstance(fact, SpellFact) and fact.application_index is not None)
        observed = ("canceled" if event.canceled else "bound" if owner else "parent_owned" if parent_owned
                    else "state_only" if fact.kind in STATE_PRESENTATION_KINDS else "received")
        declared_owner = ("player_reduction" if fact.kind in STATE_PRESENTATION_KINDS
                          else FACT_PRESENTATION.get(fact.kind, ("unassessed", ""))[0])
        evidence = {"root_uuid": str(lineage.root.uuid), "event_uuid": str(event.uuid),
                    "owner": (owner or parent_owner) if parent_owned else (owner or declared_owner),
                    "observed": observed,
                    "issues": [{"code": "binding_gap", "detail": detail}
                               for detail in dict.fromkeys(gaps.get(event.uuid, ()))],
                    "family": "fact", "identity": fact.kind}
        result.append(evidence)
        if isinstance(fact, (SpellFact, ActionFact, AttackFact, ShoveFact)):
            identity = (fact.effect_id or fact.behavior_id) if isinstance(fact, SpellFact) else fact.behavior_id
            if identity is not None:
                result.append({**evidence, "family": fact.kind, "identity": identity})
        elif (isinstance(fact, ConditionChangeFact) and fact.condition.behavior_id is not None
              and fact.condition.category is not ConditionCategory.INTERNAL):
            result.append({**evidence, "family": "condition", "identity": fact.condition.behavior_id})
    return result


def missing_observed_bindings(inventory: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Include requested content absent from the selected maps in a local run.

    This extends a report with disclosed IDs; it neither registers support nor
    claims the observer should have received an independent animation.
    """
    known = {(row["family"], row["identity"]) for row in inventory}
    missing = []
    for row in evidence:
        key = row["family"], row["identity"]
        if row["family"] not in {"spell", "action", "attack", "shove", "condition"} or key in known:
            continue
        known.add(key)
        missing.append(_row(*key, row["owner"], "content binding", "missing_binding",
                            details=("No binding in the selected presentation data. Child/state results remain separate.",)))
    return missing
