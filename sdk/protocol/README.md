# Production player contract

`player-api-v1.schema.json` is exported directly from existing native/player type
owners and the finite `player_server/protocol.py` envelopes. It has 19 public roots,
312 shared definitions and 1,612 object-field rows. `protocol-identity.json` binds
protocol 1 and player schema 4 to the exact canonical schema digest.

- `openapi.json`: actual HTTP paths, request/response types, identity headers,
  finite errors and SSE record types. Also served at the running host's `/openapi.json`.
- `field-ledger.json`: each reachable field, required/default shape and source owner.
- The Python and TypeScript packages carry the same schema and digest.

Regenerate these exports only after a real type-owner change:

```sh
uv run --no-sync python -m devtools.export_player_protocol
```

Then update declarations with `devtools/generate_player_python.py` and
`sdk/player-typescript/tools/generate.mjs`. Their fixed-array adaptation is a
code-generator compatibility step only; runtime validation uses the unchanged
2020-12 schema. Do not edit generated types or introduce a second gameplay model.

The earlier documents in `agent_docs/server-api-v1/` preserve the planning record,
including disclosure and causal semantics. Their design overlays have been removed;
their labelled old captures are not the current API schema. Current end-to-end
examples are exact records produced by `devtools/player_server_acceptance/run.py`.
