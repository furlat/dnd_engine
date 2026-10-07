# Server API planning record

**Implemented contract:** use [sdk/protocol](../../sdk/protocol/README.md) and
[player_server](../../player_server/README.md). Their schemas are exported from
production owners, with no design overlays or alternate serializer. The temporary
`contract_source.py` and `export_contract.py` have been retired. JSON artifacts in
this directory are the frozen preimplementation evidence described below; they do
not override the production export.

2026-10-07, source HEAD `40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`.
This package makes the proposed API shape concrete before server implementation.
It contains **314 shared definitions and 1,612 field rows**, with **19 public roots**.
It is not a new server, SDK, game model hierarchy or combat-log implementation.

Start with [the semantic contract](semantic-contract.md) and
[the upstream combat-log repair](COMBAT_LOG_CONTRACT.md).

| Artifact | Purpose |
|---|---|
| [player-api-v1.schema.json](player-api-v1.schema.json) | Proposed protocol 1/player schema 4; exact nested records, unions, required/optional fields and errors |
| [openapi.json](openapi.json) | HTTP routes, credentials/binding headers, request/response refs and SSE event schemas |
| [field-ledger.json](field-ledger.json) | Every reachable object field once at its defining type; source owner/location, shape, required/default status, disclosure/capture/consumer policy |
| [owner-deltas.json](owner-deltas.json) | Exact changes required in existing type owners; no parallel API gameplay types |
| [source-validators.json](source-validators.json) | Twenty reachable source validator/serializer definitions; ordinary reducer/admission invariants are in the semantic contract |
| [source-parity.json](source-parity.json) | Existing roots and proposed definition differences; the future owner export must replace, not coexist with, the design overlays |
| [capability-captures.json](capability-captures.json) | Current native scenario/capability/variant inventory and capture provenance |
| [current-captured-examples.json](current-captured-examples.json) | Unmodified current fact/log/query examples, explicitly version 3 |
| [current-initialization.json](current-initialization.json) | Full retained current native initialization |
| [proposed-shape-examples.json](proposed-shape-examples.json) | 134 labelled design/captured shape examples; proposed additions are identified and are not claimed as live API output |
| [verification.json](verification.json) | Bounded checks actually performed, tool versions and limits of the evidence |

## What has actually been checked

One headless pass ran the existing native review scenario producers, existing
subjective projection and existing public reducer. **872 of 873 scenarios
completed**, covering **all 28 concrete fact variants** (27 kind tags; damage has
its two stages) and 49 distinct current log payload shapes. The single failing
scenario is `cloud-door-lifecycle`: its fixture's door interaction raises
`ValueError: Item is out of reach`. Its trace is retained. This does not establish
that the old scenario is repaired or that every gameplay behavior is correct.
Other captured door/cloud cases remain in the matrix.

The current initialization and 2 discovery/36 preview captures came through the
existing native session. No images, videos, artwork, HTTP host or SDK project was
created. Captures verify what today's source emits; they do not prove proposed
privacy/index remaps or newly authored duration/handler fields already exist.

A single bounded schema pass checked 131 examples in Python JSON Schema and Node
Ajv, with zero shape failures. Three subsequently completed response examples were
checked specifically in both tools, also with zero failures. All 19 public roots
now have examples. This is shape interoperability evidence, not end-to-end SDK,
causal privacy or future reducer acceptance. Source/native semantic invariants and
the concrete future repair expectations are specified separately.

The two independent reviews accepted the ownership direction. Their concrete
corrections are recorded in the review receipt: required log payload, category/tag
agreement, real spatial enum, explicit privacy omissions, target-child membership,
nullable unknown causes, retained identity and consistent HTTP error policy.
Approval scope is design/ownership, not server runtime completion.

## What implementation does next

Implement the specified changes at the current owners: typed log payloads and
projection/formatting, retained identity and local causal references, passive
condition duration/handler after-values and native route preview. Extract the shared
application without forking it; build the thin server around it. The existing Python
reducer remains the same production path for headless scripts and cold replay.

Generate SDK declarations from the final owner-exported schema once when those
owners exist; there is no preimplementation SDK generation project. Compare that
export with this contract, handle intentional differences explicitly, and retire
`contract_source.py`'s design overlays. Do not retain them as a second serializer.
Then exercise the real HTTP/SSE transport with the opposing Python/TS scripts.
Repeat only targeted checks for an actual change or failure. The human expressly
rejected validation/regeneration loops and additional gate bureaucracy.

The complete implementation remains governed by the
[server plan](../SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md)
and [stream contract](../SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md).
