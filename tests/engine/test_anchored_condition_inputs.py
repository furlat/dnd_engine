"""Attached effects require a supplied identity; fixed-position effects do not."""

from uuid import uuid4

from pydantic import ValidationError
import pytest

from dnd.monsters.traits import LeadershipAura
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spells.abjuration import AntimagicFieldZone
from dnd.spells.conjuration import GuardianOfFaithZone, SpiritGuardiansZone
from dnd.spells.evocation import ContinualFlameCondition, GustOfWindZone


@pytest.mark.parametrize("condition_type", (
    LeadershipAura, AntimagicFieldZone, GuardianOfFaithZone,
    SpiritGuardiansZone, ContinualFlameCondition, GustOfWindZone,
))
def test_attached_condition_requires_an_explicit_nonnull_anchor(
    condition_type: type[SpatialCondition],
) -> None:
    fields = {"source_entity_uuid": uuid4(), "position": (0, 0), "use_register": False}
    with pytest.raises(ValidationError) as missing:
        condition_type.model_validate(fields)
    assert any(error["loc"] == ("anchor_uuid",) and error["type"] == "missing"
               for error in missing.value.errors())
    with pytest.raises(ValidationError) as null:
        condition_type.model_validate({**fields, "anchor_uuid": None})
    assert any(error["loc"] == ("anchor_uuid",) and error["type"] == "uuid_type"
               for error in null.value.errors())
    anchor = uuid4()
    accepted = condition_type.model_validate({**fields, "anchor_uuid": anchor})
    assert accepted.anchor_uuid == anchor
