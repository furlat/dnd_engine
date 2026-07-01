"""Tutorial tests for runtime identity and registries."""

from uuid import UUID, uuid4

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.gridmap import GridMap, get_map
from dnd.core.values import BaseValue, ContextualValue, ModifiableValue, StaticValue
from dnd.entity import Entity, EntityConfig


class TutorialMarker(BaseObject):
    """Concrete marker object used to demonstrate registry behavior."""


class TutorialToken(BaseObject):
    """Second concrete object used to demonstrate typed lookup."""


def reset_identity_state() -> None:
    """Clear the global runtime indexes touched by these identity examples."""
    GridMap.reset()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def test_first_runtime_object_prints_inspection_output(capsys) -> None:
    """The first manual example prints the runtime identity it creates."""
    reset_identity_state()

    source_id = uuid4()
    marker = TutorialMarker(source_entity_uuid=source_id, name="door marker")

    source_state = "stored" if marker.source_entity_uuid == source_id else "missing"
    lookup_state = (
        "same live object"
        if TutorialMarker.get(marker.uuid) is marker
        else "different object"
    )

    inspection_lines = [
        f"created object: {marker.name}",
        f"uuid type: {type(marker.uuid).__name__}",
        f"source relationship: {source_state}",
        f"lookup result: {lookup_state}",
        f"registry entries: {len(BaseObject._registry)}",
    ]

    print("\n".join(inspection_lines))

    expected_lines = [
        "created object: door marker",
        "uuid type: UUID",
        "source relationship: stored",
        "lookup result: same live object",
        "registry entries: 1",
    ]
    assert isinstance(marker.uuid, UUID)
    assert inspection_lines == expected_lines
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_registered_object_prints_lookup_contract(capsys) -> None:
    """A tutorial object prints successful and rejected typed lookup."""
    reset_identity_state()
    source_id = uuid4()

    marker = TutorialMarker(
        source_entity_uuid=source_id,
        name="door marker",
    )

    lookup_state = (
        "same live object"
        if TutorialMarker.get(marker.uuid) is marker
        else "different object"
    )

    other_marker_type = TutorialToken(source_entity_uuid=source_id)
    try:
        TutorialMarker.get(other_marker_type.uuid)
    except ValueError as exc:
        assert "is not a TutorialMarker" in str(exc)
        wrong_type_state = "rejected TutorialToken UUID"
        wrong_type_actual = str(exc).rsplit(", but ", 1)[-1]
    else:
        raise AssertionError("TutorialMarker accepted the wrong registry type")

    readout_lines = [
        f"marker lookup: {lookup_state}",
        f"marker name: {marker.name}",
        f"source stored: {marker.source_entity_uuid == source_id}",
        f"wrong-family lookup: {wrong_type_state}",
        f"wrong-family actual: {wrong_type_actual}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "marker lookup: same live object",
        "marker name: door marker",
        "source stored: True",
        "wrong-family lookup: rejected TutorialToken UUID",
        "wrong-family actual: TutorialToken",
    ]
    assert TutorialMarker.get(marker.uuid) is marker
    assert readout_lines == expected_lines
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_pending_object_prints_publication_states(capsys) -> None:
    """A pending tutorial object prints when registry lookup can see it."""
    reset_identity_state()
    source_id = uuid4()

    pending_marker = TutorialMarker(
        source_entity_uuid=source_id,
        name="pending door marker",
        use_register=False,
    )

    before_publish_found = TutorialMarker.get(pending_marker.uuid) is not None

    pending_marker.add_to_register()
    after_publish_found = TutorialMarker.get(pending_marker.uuid) is pending_marker

    pending_marker.remove_from_register()
    after_remove_found = TutorialMarker.get(pending_marker.uuid) is not None

    readout_lines = [
        f"object: {pending_marker.name}",
        f"before publish: found={before_publish_found}, use_register=False",
        f"after publish: found={after_publish_found}, use_register=True",
        f"after remove: found={after_remove_found}, use_register={pending_marker.use_register}",
        f"registry entries: {len(BaseObject._registry)}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "object: pending door marker",
        "before publish: found=False, use_register=False",
        "after publish: found=True, use_register=True",
        "after remove: found=False, use_register=False",
        "registry entries: 0",
    ]
    assert readout_lines == expected_lines
    assert TutorialMarker.get(pending_marker.uuid) is None
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_registry_families_print_separate_lookup_surfaces(capsys) -> None:
    """Objects, values, and blocks print their separate lookup families."""
    reset_identity_state()
    source_id = uuid4()

    value = BaseValue(source_entity_uuid=source_id, name="tutorial value")
    block = BaseBlock(source_entity_uuid=source_id, name="tutorial block")

    readout_lines = [
        f"value family lookup: {BaseValue.get(value.uuid).name}",
        f"root object lookup for value: {BaseObject.get(value.uuid)}",
        f"block family lookup: {BaseBlock.get(block.uuid).name}",
        f"value lookup for block uuid: {BaseValue.get(block.uuid)}",
        (
            "registry sizes: "
            f"values={len(BaseValue._registry)}, "
            f"blocks={len(BaseBlock._registry)}, "
            f"root={len(BaseObject._registry)}"
        ),
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "value family lookup: tutorial value",
        "root object lookup for value: None",
        "block family lookup: tutorial block",
        "value lookup for block uuid: None",
        "registry sizes: values=1, blocks=1, root=0",
    ]
    assert BaseValue.get(value.uuid) is value
    assert BaseObject.get(value.uuid) is None

    assert BaseBlock.get(block.uuid) is block
    assert BaseValue.get(block.uuid) is None
    assert readout_lines == expected_lines
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_entity_creation_prints_actor_position_and_map_lookup(capsys) -> None:
    """Entity creation prints actor, block, position, and map lookup surfaces."""
    reset_identity_state()
    hero_id = uuid4()

    hero = Entity.create(
        source_entity_uuid=hero_id,
        name="Hero",
        config=EntityConfig(position=(2, 3)),
    )

    creation_lines = [
        f"created actor: {hero.name} at {hero.position}",
        f"entity lookup: {Entity.get(hero_id) is hero}",
        f"block lookup: {BaseBlock.get(hero_id) is hero}",
        f"position index count: {len(Entity.get_all_entities_at_position((2, 3)))}",
        f"map position: {get_map().get_entity_position(hero_id)}",
    ]

    print("\n".join(creation_lines))

    expected_creation_lines = [
        "created actor: Hero at (2, 3)",
        "entity lookup: True",
        "block lookup: True",
        "position index count: 1",
        "map position: (2, 3)",
    ]
    assert hero.uuid == hero_id
    assert Entity.get(hero_id) is hero
    assert BaseBlock.get(hero_id) is hero
    assert hero in Entity.get_all_entities_at_position((2, 3))
    assert get_map().get_entity_position(hero_id) == (2, 3)
    assert creation_lines == expected_creation_lines

    Entity.update_entity_position(hero, (4, 5))

    movement_lines = [
        f"moved actor: {hero.name} to {hero.position}",
        f"senses position: {hero.senses.position}",
        f"old cell contains hero: {hero in Entity.get_all_entities_at_position((2, 3))}",
        f"new cell contains hero: {hero in Entity.get_all_entities_at_position((4, 5))}",
        f"map position: {get_map().get_entity_position(hero_id)}",
    ]

    print("\n".join(movement_lines))

    expected_movement_lines = [
        "moved actor: Hero to (4, 5)",
        "senses position: (4, 5)",
        "old cell contains hero: False",
        "new cell contains hero: True",
        "map position: (4, 5)",
    ]
    assert hero.position == (4, 5)
    assert hero.senses.position == (4, 5)
    assert hero not in Entity.get_all_entities_at_position((2, 3))
    assert hero in Entity.get_all_entities_at_position((4, 5))
    assert get_map().get_entity_position(hero_id) == (4, 5)
    assert movement_lines == expected_movement_lines
    assert capsys.readouterr().out.splitlines() == (
        expected_creation_lines + expected_movement_lines
    )


def test_value_subclass_lookup_contracts_print_type_boundaries(capsys) -> None:
    """Value subclass lookup prints accepted, rejected, and missing lookups."""
    reset_identity_state()
    source_id = uuid4()

    static_value = StaticValue(source_entity_uuid=source_id, name="static")
    contextual_value = ContextualValue(source_entity_uuid=source_id, name="contextual")
    modifiable_value = ModifiableValue.create(
        source_entity_uuid=source_id,
        value_name="modifiable",
    )

    assert BaseValue.get(static_value.uuid) is static_value
    assert BaseValue.get(contextual_value.uuid) is contextual_value
    assert BaseValue.get(modifiable_value.uuid) is modifiable_value

    assert StaticValue.get(static_value.uuid) is static_value
    assert ContextualValue.get(contextual_value.uuid) is contextual_value
    assert ModifiableValue.get(modifiable_value.uuid) is modifiable_value

    wrong_family_results = []
    try:
        StaticValue.get(contextual_value.uuid)
    except ValueError as exc:
        assert "is not a StaticValue" in str(exc)
        wrong_family_results.append("StaticValue rejects ContextualValue")
    else:
        raise AssertionError("StaticValue accepted a ContextualValue UUID")

    try:
        ContextualValue.get(static_value.uuid)
    except ValueError as exc:
        assert "is not a ContextualValue" in str(exc)
        wrong_family_results.append("ContextualValue rejects StaticValue")
    else:
        raise AssertionError("ContextualValue accepted a StaticValue UUID")

    try:
        ModifiableValue.get(static_value.uuid)
    except ValueError as exc:
        assert "is not a ModifiableValue" in str(exc)
        wrong_family_results.append("ModifiableValue rejects StaticValue")
    else:
        raise AssertionError("ModifiableValue accepted a StaticValue UUID")

    missing_id = uuid4()
    base_missing = BaseValue.get(missing_id) is None
    contextual_missing = ContextualValue.get(missing_id) is None
    modifiable_missing = ModifiableValue.get(missing_id) is None

    try:
        StaticValue.get(missing_id)
    except ValueError as exc:
        assert "is not a StaticValue" in str(exc)
        static_missing = "raises ValueError"
    else:
        raise AssertionError("StaticValue accepted a missing UUID")

    readout_lines = [
        (
            "base lookup names: "
            f"{[value.name for value in [BaseValue.get(static_value.uuid), BaseValue.get(contextual_value.uuid), BaseValue.get(modifiable_value.uuid)]]}"
        ),
        (
            "typed lookup ok: "
            f"static={StaticValue.get(static_value.uuid) is static_value}, "
            f"contextual={ContextualValue.get(contextual_value.uuid) is contextual_value}, "
            f"modifiable={ModifiableValue.get(modifiable_value.uuid) is modifiable_value}"
        ),
        f"wrong-family rejections: {wrong_family_results}",
        (
            "missing lookup: "
            f"base={base_missing}, "
            f"contextual={contextual_missing}, "
            f"modifiable={modifiable_missing}, "
            f"static={static_missing}"
        ),
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "base lookup names: ['static', 'contextual', 'modifiable']",
        "typed lookup ok: static=True, contextual=True, modifiable=True",
        (
            "wrong-family rejections: ['StaticValue rejects ContextualValue', "
            "'ContextualValue rejects StaticValue', 'ModifiableValue rejects StaticValue']"
        ),
        "missing lookup: base=True, contextual=True, modifiable=True, static=raises ValueError",
    ]
    assert BaseValue.get(missing_id) is None
    assert ContextualValue.get(missing_id) is None
    assert ModifiableValue.get(missing_id) is None
    assert readout_lines == expected_lines
    assert capsys.readouterr().out.splitlines() == expected_lines
