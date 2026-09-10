"""Retained actor identity and real authored gear resolve to renderer layers."""

from uuid import UUID

import pytest

from dnd.blocks.appearance import AppearanceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.item_types import EquippedVisualPolicy, ItemPresentationState
from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data, resolve_actor_layers
from game.animation_types import AnimationData, RigLayer


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(rig_files=(DATA_ROOT.parent / "rigs/goblin01.json",))


@pytest.fixture
def dagger() -> ItemPresentationState:
    return build_authored_item("weapon.dagger", UUID(int=101)).to_item_presentation_state()


def test_retained_body_identity_and_authored_dagger_supply_layers(
    data: AnimationData, dagger: ItemPresentationState,
) -> None:
    appearance = AppearanceConfig(
        body_category="NakedBody", skin_tint=0xDDAA88,
        head_category="Head22", hair_tint=0x332211,
    )
    resolved = resolve_actor_layers(
        data, appearance, (dagger,), ((WeaponSlot.MELEE_MAIN.value, dagger.item_uuid),),
        WeaponSet.MELEE, rig_id=data.root_rig,
    )
    assert {layer.slot: layer for layer in resolved} == {
        "shadow": RigLayer("shadow", "Shadow", alpha=0.5),
        "body": RigLayer("body", "NakedBody", 0xDDAA88),
        "head": RigLayer("head", "Head22", 0x332211),
        "weapon": RigLayer("weapon", "Melee1", 8952234),
    }
    appearance.skin_tint = 0xFFFFFF
    assert next(layer for layer in resolved if layer.slot == "body").tint == 0xDDAA88


@pytest.mark.parametrize("weapon_set, policy, visible", [
    (WeaponSet.MELEE, EquippedVisualPolicy.VISIBLE, True),
    (WeaponSet.MELEE, EquippedVisualPolicy.HIDDEN, False),
    (WeaponSet.RANGED, EquippedVisualPolicy.VISIBLE, False),
    (WeaponSet.NONE, EquippedVisualPolicy.VISIBLE, False),
])
def test_equipment_visibility_uses_retained_policy_and_active_set(
    data: AnimationData, dagger: ItemPresentationState,
    weapon_set: WeaponSet, policy: EquippedVisualPolicy, visible: bool,
) -> None:
    retained = dagger.model_copy(update={"equipped_visual_policy": policy})
    layers = resolve_actor_layers(
        data, AppearanceConfig(), (retained,),
        ((WeaponSlot.MELEE_MAIN.value, retained.item_uuid),),
        weapon_set, rig_id=data.root_rig,
    )
    assert ("weapon" in {layer.slot for layer in layers}) is visible


def test_fixed_rig_keeps_baked_body_and_gear(
    data: AnimationData, dagger: ItemPresentationState,
) -> None:
    layers = resolve_actor_layers(
        data, AppearanceConfig(skin_tint=0x123456, head_category="Head22"),
        (dagger,), ((WeaponSlot.MELEE_MAIN.value, dagger.item_uuid),),
        WeaponSet.MELEE, rig_id="smallscale.goblin01",
    )
    assert layers == (
        RigLayer("shadow", "Goblin01Shadow", alpha=0.5),
        RigLayer("body", "Goblin01"),
    )


def test_single_target_cast_preserves_absent_application_identity(data: AnimationData) -> None:
    source = CastInput(
        root_event_uuid=str(UUID(int=201)),
        caster=ActorContact(str(UUID(int=101)), (0, 0), "S", 0.5),
        applications=(CastApplication(
            application_id=None,
            target=ActorContact(str(UUID(int=102)), (3, -3), "W", 0.5, hp=20),
            damage_applied=True, damage_total=8, resulting_hp=12,
        ),),
    )
    timeline = compile_cast(data, "spell.fire_bolt", source)
    travel = next(phase for phase in timeline.applications[0].projectile_intervals if phase.name == "travel")
    sample = sample_cast(timeline, (travel.start_ms + travel.end_ms) / 2)
    assert sample.projectiles[0].application_id is None
    assert timeline.source.root_event_uuid == str(UUID(int=201))
    assert sample_cast(timeline, timeline.complete_ms).vitals[0].hp == 12
