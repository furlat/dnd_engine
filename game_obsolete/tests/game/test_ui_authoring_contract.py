"""UI artwork records preserve native selections without creating game rules."""
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from game.ui.media_types import ChoiceRecord


SOURCE = Path(__file__).resolve().parents[2] / 'game/data/ui_choices.json'


def test_existing_facet_choices_still_load_and_configuration_choices_keep_integer_values():
    existing = TypeAdapter(tuple[ChoiceRecord, ...]).validate_json(SOURCE.read_bytes())
    assert all(row.facet is not None and row.field is None for row in existing)
    owner = existing[0].owner.model_dump(mode='json')
    row = ChoiceRecord.model_validate_json(json.dumps({
        'owner': owner, 'facet': None, 'field': 'curse_option', 'value': 1,
        'icon_key': 'choice.curse.test', 'label': 'Curse', 'requirements': {'curse_option': 1},
    }))
    assert type(row.value) is int and row.value == 1
    assert row.requirements == {'curse_option': 1}
    assert ChoiceRecord.model_validate_json(row.model_dump_json()) == row


def test_discovery_value_and_native_enum_survive_without_silent_case_conversion():
    source = json.loads(SOURCE.read_text())[0]
    row = ChoiceRecord.model_validate({**source, 'facet': 'damage_type', 'value': 'radiant',
                                      'field': 'damage_type', 'field_value': 'Radiant'})
    assert row.value == 'radiant' and row.field_value == 'Radiant'
    with pytest.raises(ValidationError, match='configuration field'):
        ChoiceRecord.model_validate({**source, 'facet': None})
    with pytest.raises(ValidationError, match='field_value requires'):
        ChoiceRecord.model_validate({**source, 'field_value': 'Radiant'})
