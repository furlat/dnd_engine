"""Read-only pixel diagnostic; run from repository root with SDL_VIDEODRIVER=dummy.

Uses existing synthetic rig pixels to isolate composition of an admitted item
modifier and the shipped Stoneskin ramp. No native combined-spell claim.
"""
from dataclasses import replace
from uuid import uuid4
import pygame
from tests.game.test_support_condition_rendering import rig_pixels, RAMP
from game.animation import BodySample
from game.animation_draw import actor_draw_commands
from game.condition_animation import ConditionAppearance, ConditionItemModifier
from game.condition_types import ConditionEquipmentModifier
from game.projection import Camera

pygame.display.init()
pygame.display.set_mode((1, 1))
data, contact, layers, rows = rig_pixels.__wrapped__()
item = uuid4()
layers = tuple(replace(layer, item_uuid=item) if layer.slot == "weapon" else layer for layer in layers)
modifier = ConditionEquipmentModifier(id="hide", slots=("weapon",), alphaMultiplier=0,
    tintRgb=None, saturation=1, brightness=1, priority=70, affectedItemOnly=True)

def draw(ramp, modified):
    condition = ConditionAppearance(body_ramp=ramp,
        item_modifiers=(ConditionItemModifier(item, modifier),) if modified else ())
    commands = actor_draw_commands(data, BodySample(contact.actor_uuid, "Idle", 0, "S"),
        contact, layers, rows, Camera(zoom=1), condition=condition)
    return next(command.surface for command in commands if command.role == "actor")

for ramp in (None, RAMP):
    ordinary, modified = draw(ramp, False), draw(ramp, True)
    print("ramp", ramp is not None, "same_with_modifier",
        pygame.image.tobytes(ordinary, "RGBA") == pygame.image.tobytes(modified, "RGBA"),
        "pixel_before_after", ordinary.get_at((13, 4)), modified.get_at((13, 4)))
