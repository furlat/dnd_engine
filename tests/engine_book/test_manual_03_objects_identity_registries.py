"""Manual Chapter 03 checks for object identity and registries."""

from uuid import uuid4

from dnd.core.base_block import BaseBlock
from dnd.core.base_object import BaseObject
from dnd.core.values import BaseValue
from dnd.entity import Entity, EntityConfig
from dnd.utils import reset_combat_state


class TutorialObject(BaseObject):
    """Concrete teaching object for registry examples."""


class TutorialToken(BaseObject):
    """Second teaching object for typed lookup examples."""


def reset_identity_state() -> None:
    """Clear the global registries touched by this chapter's examples."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()


def test_base_object_registration_lifecycle() -> None:
    """A BaseObject subclass registers by UUID and can opt out."""
    reset_identity_state()
    source_id = uuid4()

    registered = TutorialObject(
        source_entity_uuid=source_id,
        name="tutorial marker",
    )

    assert TutorialObject.get(registered.uuid) is registered

    transient = TutorialObject(
        source_entity_uuid=source_id,
        name="draft marker",
        use_register=False,
    )

    assert TutorialObject.get(transient.uuid) is None

    transient.add_to_register()
    assert TutorialObject.get(transient.uuid) is transient

    transient.remove_from_register()
    assert TutorialObject.get(transient.uuid) is None


def test_lookup_rejects_the_wrong_tutorial_type() -> None:
    """Subclass lookup raises instead of returning a different object type."""
    reset_identity_state()
    source_id = uuid4()

    other = TutorialToken(source_entity_uuid=source_id)

    try:
        TutorialObject.get(other.uuid)
    except ValueError:
        rejected = True
    else:
        rejected = False

    assert rejected is True


def test_values_and_blocks_use_separate_registry_families() -> None:
    """Values and blocks are looked up through separate registry families."""
    reset_identity_state()
    source_id = uuid4()

    value = BaseValue(source_entity_uuid=source_id, name="tutorial value")
    block = BaseBlock(source_entity_uuid=source_id, name="tutorial block")

    assert BaseValue.get(value.uuid) is value
    assert BaseObject.get(value.uuid) is None

    assert BaseBlock.get(block.uuid) is block
    assert BaseValue.get(block.uuid) is None


def test_entity_registers_as_actor_block_and_positioned_object() -> None:
    """Entity creation fills actor, block, and position lookup surfaces."""
    reset_identity_state()
    hero_id = uuid4()

    hero = Entity.create(
        source_entity_uuid=hero_id,
        name="Hero",
        config=EntityConfig(position=(2, 3)),
    )

    assert hero.uuid == hero_id
    assert hero.name == "Hero"
    assert Entity.get(hero_id) is hero
    assert BaseBlock.get(hero_id) is hero
    assert hero in Entity.get_all_entities_at_position((2, 3))

    Entity.update_entity_position(hero, (4, 5))

    assert hero.position == (4, 5)
    assert hero.senses.position == (4, 5)
    assert hero not in Entity.get_all_entities_at_position((2, 3))
    assert hero in Entity.get_all_entities_at_position((4, 5))
