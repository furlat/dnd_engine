"""Emit one canonical Acid Splash presentation transition as four JSON lines."""

from __future__ import annotations

import asyncio
import sys
from contextlib import redirect_stdout
from typing import NoReturn
from uuid import uuid4

from dnd.actions.standard import (
    SpellEvent,
)
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.runtime import SERVER_CONTENT_SYSTEM_RUNTIME
from dnd.encounters.controllers import Controller
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.dice import fixed_dice_faces
from dnd.encounters.encounter import Encounter
from dnd.entities.entity import Entity
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_RECIPES_BY_ID
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_NAME
from dnd.spells.conjuration import AcidSplash
from server.content_catalog import build_public_content_catalog
from server.event_stream import DndEventStream
from server.player_replication.journal import SubjectiveJournalStore
from server.player_replication.runtime import (
    CanonicalSubjectiveReplicationRuntime,
)
from server.player_replication_contract import (
    DamagePresentationCue,
    SpellPresentationCue,
    SubjectiveFrameDelivery,
    SubjectiveSyncDelivery,
)
from server.replication_perspective import PerspectiveScope
from server.spell_catalog import build_spell_catalog
from server.subjective_authority import ResolvedSubjectiveAuthority
from server.timeline_contracts import CombatLogProjection


def _fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _materialize_actor(
    *,
    name: str,
    position: tuple[int, int],
    faction: str,
    deployment_role_id: str,
) -> Entity:
    runtime_uuid = uuid4()
    return materialize_creature(
        BESTIARY_CREATURE_RECIPES_BY_ID["goblin"],
        runtime_entity_uuid=runtime_uuid,
        display_name=name,
        faction=faction,
        position=position,
        deployment_role=CreatureDeploymentRole(role_id=deployment_role_id),
        possession_mode=CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY,
    )


def _authority(caster: Entity) -> ResolvedSubjectiveAuthority:
    caster_uuid = str(caster.uuid)
    return ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id="transition-sequence-session",
            membership_id="transition-sequence-membership",
            authority_epoch=1,
            projection=CombatLogProjection.SUBJECTIVE,
            controlled_entity_uuids=(caster_uuid,),
            observer_entity_uuids=(caster_uuid,),
            active_observer_uuid=caster_uuid,
        ),
        perspective_epoch_id="transition-sequence-perspective-1",
    )


def _build_production_models() -> tuple[object, object, object, object]:
    if sys.version_info < (3, 12):
        _fail(
            "Acid Splash transition producer requires Python 3.12 or newer; "
            f"received {sys.version_info.major}.{sys.version_info.minor}",
        )

    grid = reset_engine_runtime(grid_size=(4, 2))
    loaded = bootstrap_content_system()
    installed = SERVER_CONTENT_SYSTEM_RUNTIME.install(loaded)
    _require(
        installed is loaded,
        "SERVER_CONTENT_SYSTEM_RUNTIME did not install the exact loaded set",
    )
    content_catalog = build_public_content_catalog(installed)
    spell_catalog = build_spell_catalog()

    caster = _materialize_actor(
        name="Acid Splash Caster",
        position=(0, 0),
        faction="heroes",
        deployment_role_id="tests.transition_sequences.acid_splash_caster",
    )
    target = _materialize_actor(
        name="Acid Splash Target",
        position=(1, 0),
        faction="monsters",
        deployment_role_id="tests.transition_sequences.acid_splash_target",
    )
    Entity.materialize_all_navigation(max_distance=20)
    _require(
        target.uuid in caster.senses.entities,
        "Acid Splash target is not lawfully visible to its caster",
    )

    encounter = Encounter(
        name="Acid Splash transition encounter",
        source_entity_uuid=caster.uuid,
    )
    encounter.add_combatant(
        caster,
        Controller(source_entity_uuid=caster.uuid, name="Caster controller"),
    )
    encounter.add_combatant(
        target,
        Controller(source_entity_uuid=target.uuid, name="Target controller"),
    )

    source_stream = DndEventStream()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=source_stream,
        grid_provider=lambda: grid,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: encounter,
    )
    context = runtime.bind(_authority(caster), encounter=encounter)
    with fixed_dice_faces(20, 1):
        encounter.start_encounter()
    subscription = context.subscribe()
    try:
        sync = asyncio.run(subscription.get())
        _require(
            isinstance(sync, SubjectiveSyncDelivery),
            "first subjective delivery is not the required initial sync",
        )
        bootstrap = context.bootstrap()
        _require(sync.protocol == bootstrap.protocol, "sync protocol changed")
        _require(
            sync.perspective == bootstrap.perspective,
            "sync perspective changed",
        )
        _require(sync.watermarks == bootstrap.watermarks, "sync watermarks changed")

        authored_acid = SPELL_CONTENT_DECLARATIONS_BY_NAME["Acid Splash"]
        acid_declaration = installed.registry.resolve_definition(
            authored_acid.ref,
        )
        _require(
            acid_declaration.ref == authored_acid.ref,
            "installed registry resolved a different Acid Splash definition",
        )
        acid_ref = acid_declaration.ref
        _require(
            any(entry.ref == acid_ref for entry in content_catalog.entries),
            "Acid Splash definition is absent from the public content catalog",
        )
        _require(
            any(entry.content_ref == acid_ref for entry in spell_catalog.spells),
            "Acid Splash definition is absent from the spell catalog",
        )

        action = AcidSplash(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            caster_level=1,
        )
        binding = SERVER_CONTENT_SYSTEM_RUNTIME.bind_granted_behavior(
            action,
            provider_ref=acid_ref,
            runtime_owner_uuid=caster.uuid,
        )
        _require(
            action.behavior_binding == binding,
            "Acid Splash action did not retain its runtime-installed binding",
        )
        _require(
            binding.definition_ref == acid_ref
            and binding.provided_by_ref == acid_ref
            and binding.runtime_owner_uuid == caster.uuid,
            "Acid Splash action binding does not match its production owner",
        )

        hp_before = target.get_hp()
        with fixed_dice_faces(1, 4):
            result = action.apply()
        _require(isinstance(result, SpellEvent), "Acid Splash returned no SpellEvent")
        _require(not result.canceled, "Acid Splash was canceled")
        _require(
            result.application_index is None,
            "Acid Splash result is not the root SpellEvent",
        )
        _require(result.total_damage > 0, "Acid Splash produced no damage")
        _require(target.get_hp() < hp_before, "Acid Splash did not reduce target HP")
        _require(
            result.behavior_binding == binding,
            "root SpellEvent lost the Acid Splash behavior binding",
        )

        delivery = asyncio.run(subscription.get())
        _require(
            isinstance(delivery, SubjectiveFrameDelivery),
            "delivery immediately after Acid Splash is not a subjective frame",
        )
        frame = delivery.frame
        spell_cues = tuple(
            cue
            for cue in frame.presentation
            if isinstance(cue, SpellPresentationCue)
        )
        damage_cues = tuple(
            cue
            for cue in frame.presentation
            if isinstance(cue, DamagePresentationCue)
        )
        _require(len(spell_cues) == 1, "Acid Splash did not emit one spell cue")
        _require(len(damage_cues) == 1, "Acid Splash did not emit one damage cue")
        spell_cue = spell_cues[0]
        damage_cue = damage_cues[0]
        behavior_attributions = tuple(
            attribution
            for attribution in spell_cue.content_attributions
            if attribution.role.value == "behavior"
        )
        _require(
            len(behavior_attributions) == 1,
            "Acid Splash spell cue lacks one behavior attribution",
        )
        cue_attribution = behavior_attributions[0]
        _require(
            cue_attribution.definition_ref == acid_ref
            and cue_attribution.provided_by_ref == acid_ref,
            "Acid Splash spell cue attribution differs from the bound action",
        )
        _require(
            spell_cue.spell_id == "acid_splash"
            and spell_cue.actor_uuid == str(caster.uuid),
            "Acid Splash spell cue lost its catalog or caster identity",
        )
        _require(
            damage_cue.source_uuid == str(caster.uuid)
            and damage_cue.target_uuid == str(target.uuid)
            and damage_cue.applied_amount > 0
            and damage_cue.resulting_hp == target.get_hp(),
            "Acid Splash damage cue differs from the authoritative result",
        )

        partition = context.partition_key
        _require(
            bootstrap.protocol.source_stream_id == frame.source_stream_id
            == partition.source_stream_id,
            "bootstrap and delivery source-stream partitions differ",
        )
        _require(
            bootstrap.protocol.generation_id == frame.generation_id
            == partition.generation_id,
            "bootstrap and delivery generation partitions differ",
        )
        _require(
            bootstrap.perspective.perspective_epoch_id
            == frame.perspective_epoch_id
            == partition.perspective_epoch_id,
            "bootstrap and delivery perspective partitions differ",
        )
        _require(
            bootstrap.perspective.active_observer_uuid == str(caster.uuid)
            and context.perspective.active_observer_uuid == str(caster.uuid),
            "bootstrap and delivery context lost observer identity",
        )
        _require(
            frame.watermarks.observation_cursor
            == bootstrap.watermarks.observation_cursor + 1,
            "Acid Splash delivery is not the contiguous successor observation",
        )
        _require(
            frame.presentation_from_cursor
            == bootstrap.watermarks.presentation_cursor,
            "Acid Splash presentation window is not contiguous",
        )
        return content_catalog, spell_catalog, bootstrap, delivery
    finally:
        context.unsubscribe(subscription)
        runtime.clear_all()
        runtime.stop()
        source_stream.stop()
        reset_engine_runtime()


def main() -> None:
    with redirect_stdout(sys.stderr):
        models = _build_production_models()
    for model in models:
        print(model.model_dump_json())


if __name__ == "__main__":
    main()
