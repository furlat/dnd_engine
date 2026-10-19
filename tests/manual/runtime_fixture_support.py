"""Explicit world presence for tutorial actors created through native factories."""

from dnd.entity import Entity
from dnd.game import Game


def compose_and_deploy(actor: Entity) -> Entity:
    """Commit a fixture actor's creation and deploy it at its configured position."""
    actor.compose_entity()
    Game().deploy_entity(actor, actor.position)
    return actor
