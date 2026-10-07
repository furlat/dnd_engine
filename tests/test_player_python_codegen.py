"""Static SDK declarations retain JSON array element types without schema edits."""
from devtools.generate_player_python import generator_schema


def test_python_generator_preserves_fixed_array_element_types_without_mutating_wire_schema():
    wire = {'type': 'object', 'properties': {'position': {'type': 'array', 'prefixItems': [
        {'type': 'integer'}, {'type': 'integer'}], 'minItems': 2, 'maxItems': 2},
        'uuid': {'type': 'string', 'format': 'uuid'}, 'variant': {'discriminator': {'propertyName': 'kind'},
            'oneOf': [{'const': 'a'}, {'const': 'b'}]}}}
    generated = generator_schema(wire)
    assert generated['properties']['position'] == {'type': 'array', 'items': [
        {'type': 'integer'}, {'type': 'integer'}], 'minItems': 2, 'maxItems': 2}
    assert wire['properties']['position']['prefixItems'] == [{'type': 'integer'}, {'type': 'integer'}]
    assert generated['properties']['uuid'] == {'type': 'string'}
    assert wire['properties']['uuid']['format'] == 'uuid'
    assert generated['properties']['variant'] == {'oneOf': [{'const': 'a'}, {'const': 'b'}]}
