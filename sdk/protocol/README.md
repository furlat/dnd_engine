# Production player contract

`player-api-v1.schema.json` is exported directly from existing native/player type
owners and the finite `server/protocol.py` envelopes. It has 19 public roots,
312 shared definitions and 1,622 object-field rows. `protocol-identity.json` binds
protocol 1 and player schema 6 to the exact canonical schema digest.

- `openapi.json`: actual HTTP paths, request/response types, identity headers,
  finite errors and SSE record types. Also served at the running host's `/openapi.json`.
- `field-ledger.json`: each reachable field, required/default shape and source owner.
- The Python and TypeScript packages carry the same schema and digest.

Disclosed floor items and visible equipment preserve their native light radii;
equipment also preserves `is_lit`. The dim radius extends beyond the bright
radius. These fields describe already disclosed items, not a registry of hidden
inventory or spell light sources. Portable ignition/extinguishing publish item
after-values so activation follows the same causal player stream.

`PlayerObject.contained_items` is available only for currently visually observed,
accessible storage. `null` means unavailable or no storage; an empty array means
observed empty. Closing a chest or losing its observation clears the contents.
Discovered `action.environment.storage_chest.loot` rows identify one child with
`loot_item_uuid` and the chest with `source_item_uuid`. Submit the original row's
discovery index and its admitted self target through ordinary preview/execute;
there is no separate loot endpoint. Native inventory transfer revalidates source
membership, hand contact and capacity. Loot All retains its existing partial
capacity behavior. Both source contents and controlled inventory update from
the same recorded operation, including fully merged stacks.

`ActionSelection.prefer_safe` defaults to `true`. Set it to `false` to request
the engine's normal movement route. Use the same selection for preview and
execution; `selected_route` reports the actual path and policy, including the
existing fallback when a safe route is unavailable.

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
