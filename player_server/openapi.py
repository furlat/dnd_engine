"""HTTP documentation over the same exported value schema used by both SDKs."""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from player_server.protocol import public_schema


def result_schema(name: str) -> dict:
    return {'description': name, 'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/' + name}}}}


def document(app: FastAPI) -> dict:
    result = get_openapi(title=app.title, version=app.version, routes=app.routes)
    schema = deepcopy(public_schema())

    def references(value):
        if isinstance(value, dict):
            for key, member in value.items():
                if isinstance(member, str) and member.startswith('#/$defs/'):
                    value[key] = member.replace('#/$defs/', '#/components/schemas/', 1)
                else:
                    references(member)
        elif isinstance(value, list):
            for member in value:
                references(member)

    references(schema)
    result['components'] = {'schemas': schema['$defs'],
        'securitySchemes': {'SeatBearer': {'type': 'http', 'scheme': 'bearer'}}}
    result['security'] = [{'SeatBearer': []}]
    statuses = {value['properties']['http_status']['const']
        for name, value in schema['$defs'].items() if name.startswith('Error')
        and 'http_status' in value.get('properties', {})}
    for path, methods in result['paths'].items():
        for operation in methods.values():
            operation['responses'].pop('422', None)  # The adapter returns the closed 400 error.
            if path == '/health':
                operation['security'] = []
                continue
            operation['responses'].update({str(code): result_schema('ApiError') for code in statuses})
            parameters = operation.setdefault('parameters', [])
            if '{game_id}' in path:
                for name in ('X-Game-Epoch', 'X-Audience-Id'):
                    parameters.append({'name': name, 'in': 'header', 'required': True,
                        'schema': {'type': 'string', 'format': 'uuid'}})
            if path.endswith(('/initialization', '/events', '/ack', '/choices', '/preview', '/commands')):
                parameters.append({'name': 'X-Attachment-Epoch', 'in': 'header', 'required': True,
                    'schema': {'type': 'string', 'format': 'uuid'}})
    return result
