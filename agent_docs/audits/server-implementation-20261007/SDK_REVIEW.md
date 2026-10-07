# SDK validation and finite combat evidence — 2026-10-07

The Python SDK's interpreted validation accounted for **808–840 ms** on a real 2.61 MB choices response. Exact-schema compiled validation now takes **11.51–11.93 ms**, with complete strict decoding at **22.62–28.93 ms** across five offline samples. This receipt also preserves the preceding eight finite combat games: **197 commands and 601 records**. Live HTTP reruns and final native/startup reconciliation belong to the main performance receipt.

## Finite combat through actual HTTP and SDK consumption

Eight complete native fights produce **197 commands, 16 subjective streams and 601 records**. Every stream cold-reduces through the existing shared player reducer, with schema/identity/sequence, closed references, own command numbering and foreign HUD authority checks. Every recorded final boundary is terminal. Exact public bytes, command/query correspondence, source fingerprints and the cold replay are under `.runtime/server-recovery/combat-http-20261007/`; `summary.json` contains every sample count and range.

The weapon games use four authored goblins with their ordinary 7 HP. Spell games use one level-7 caster at 56 HP against two level-5 caster recipes at 40 HP each, with initial shortbow grants for the opposition. The Fireball game instead uses six ordinary 7-HP goblins in its actual area. Initial spell grants and ordinary full-caster slots are fixture preconditions. Seed 2 supplies ordinary native dice. There are no mid-command HP/resource refreshes, suppressed damage, effects, logs, senses or capture. Native discovery and ordered previews supply every target. After the selected spells, ordinary bow attacks, Fire Bolt, movement and End Turn finish the games.

All cells below are **observed minimum–maximum milliseconds**, or the single observed value. No action has 100 samples, so no action percentiles are claimed. Command timing starts after discovery and preview; the separate query columns remain part of the interaction cost. Worker time is the complete measured dispatch/capture/public-construction boundary, excluding HTTP and SDK work. Ranged attacks comprise five commands in the ranged fight and 43 opposing bow attacks in spell fights. Each repeated spell has nine previews across three casts; most other action commands have one preview. Only two of the 83 End Turns require discovery; the other 81 directly submit the native End Turn intent.

| Action | Commands | Command consumed | Worker command | Discovery HTTP + SDK | Discovery worker | Preview HTTP + SDK |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Movement | 23 | 56.06–135.21 | 17.77–53.28 | 54.26–1105.41 | 11.31–329.38 | 5.99–17.03 |
| Melee attack | 5 | 35.46–159.03 | 11.27–85.24 | 28.78–56.25 | 8.90–14.00 | 5.77–6.91 |
| Ranged attack | 48 | 39.24–165.47 | 11.60–88.15 | 45.10–375.00 | 10.32–122.32 | 6.03–22.90 |
| Magic Missile A/B/A | 3 | 93.74–110.16 | 18.36–27.73 | 462.15–528.25 | 66.77–129.55 | 5.18–10.82 |
| Scorching Ray A/B/A | 3 | 166.76–196.50 | 65.48–92.25 | 469.88–517.18 | 66.48–127.00 | 4.66–8.84 |
| Fireball, six goblins | 1 | 845.28 | 473.22 | 578.01 | 161.37 | 8.02 |
| Hold Person | 1 | 88.88 | 26.74 | 538.09 | 128.82 | 8.66 |
| Wall of Fire | 1 | 158.69 | 71.29 | 796.41 | 344.97 | 36.93 |
| Conjure Animals, Wolf | 1 | 79.85 | 54.27 | 1097.58 | 247.42 | 10.19 |
| Fire Bolt fallback | 26 | 35.67–119.23 | 7.88–49.27 | 294.27–1075.13 | 48.31–220.96 | 6.57–16.57 |
| Drop concentration | 2 | 88.39–95.93 | 29.50–33.45 | 244.05–1015.77 | 73.35–173.88 | 7.80–10.13 |
| End Turn | 83 | 20.08–103.65 | 4.05–54.49 | 234.45–304.71 | 69.07–103.29 | — |

Magic Missile and Scorching Ray each retain three A/B/A casts and nine ordered application facts. Fireball affects all six goblins and ends that fight. Hold Person records the real paralyzed condition; Wall of Fire records spatial effect and visibility changes before concentration is dropped on the next caster turn. Conjure Animals records the native Wolf and its subsequent AI movement/attack before concentration is dropped. These are finite functional and latency observations, not broad spell distributions or a claim about summon retirement visibility.

The cohort exposes costs beyond End Turn: the one six-goblin Fireball command takes **845.28 ms through consumption / 473.22 ms in the worker**. Caster choices take up to **1,105.41 ms through HTTP/SDK**. The subsequent SDK attribution below identifies most of the Python choices gap; native query and Fireball costs remain independently visible. This combat cohort predates that SDK validator replacement and later native spatial repairs. Its source fingerprints are preserved as a separate measurement epoch.

Three earlier harness attempts are explicitly superseded in `superseded-probe-attempts.json`: a lowercase weapon-slot selector omitted direct attacks, causing an opportunity-only melee game and an unfinished ranged game; an already-running Magic Missile case inherited that selector. Their actual records/results remain on disk. Corrected enum matching and an explicit requested-action assertion precede all eight accepted cases. Each accepted host and worker shuts down cleanly.

The original combat readiness observations include SDK process startup/attachment/consumption and are one sample per different fixture; they are not a ten-start comparison. The runner now records host publication of the first human boundary separately from SDK consumption, and supports a zero-command startup probe. No command latency is invented for that mode.

## Python choices validation attribution

One fresh actual Conjure Animals choices response is saved privately under `.runtime/server-recovery/sdk-choice-profile-20261007/choices-response.json` (2,612,871 bytes; SHA-256 `e91df5ade4a0666bec31ab43f57a46c64bfe4a1be5b613aeca291d26cbb58a4c`). Raw HTTP fetch costs **283.47 ms**, including **266.86 ms worker choices**. Five offline JSON parses cost **15.81–22.44 ms**, while interpreted Draft 2020-12 validation alone costs **808.28–840.09 ms**. A separate cProfile call records 13.34 million calls, including 338,165 validator evolutions and about 76,000 `anyOf` traversals. Profile wall time includes profiler overhead; the five unprofiled samples establish the validation cost.

The Python SDK now pins `jsonschema-rs==0.46.6`, compiling the exact packaged Draft 2020-12 schema with `validate_formats=True` and unknown formats rejected. It retains strict JSON parsing, safe-number bounds, additional-property/union checks and cursor identities. Direct Python-object validation performs a standard finite JSON preflight because the native binding would otherwise convert non-finite floats to null; already-decoded network records avoid re-encoding. The runtime API and generated declarations/schema are unchanged. This introduces a native-wheel dependency; the published CPython ABI3 Windows wheel installs successfully in the existing Windows environment. All **42 Python package tests** pass. The wheel is rebuilt only for the actual dependency change; no schema/type generation runs.

The final after measurement uses the identical saved response bytes and verifies the schema file hash remains `ec447f31521ef25eab9e4ce1c708eef7fed764f2794578f6315dd9a597e80eab`. Five compiled Python validations take **11.51–11.93 ms**; five complete SDK decodes take **22.62–28.93 ms**. The first decode, including lazy compilation, takes **29.28 ms**. These numbers include conversion into the binding's JSON representation and do not include network/native work. `attribution-after.json` contains individual observations and source hashes. No end-to-end improvement is inferred without the parent's live rerun.

For comparison, the existing TypeScript SDK validates the same actual response with Ajv and decodes it in **8.76–14.08 ms** across five warm samples. Its first decode, including validator compilation, takes **289.25 ms**. Separate warm validation samples range **2.20–13.61 ms**, showing initial JIT variation. `typescript.json` preserves all values; neither five-sample set supports percentile claims. No TypeScript implementation change was needed.

The unchanged SDK lifecycle/error tests plus 16 added cases all live in `sdk/python/tests/test_transport.py`: **42 pass in 1.05 s**. Added cases cover unknown fields, malformed and compact UUIDs, oversized integers, invalid union tags/fields, prefix-item lengths and element types, booleans in integer positions, nullable and nonnullable finite behavior, unchanged optional fields, and invalid Python inputs. Existing tests retain safe-integer limits, record size, awaited consumer, ACK/reconnect, duplicate/gap/identity and cancellation coverage. The direct API still returns the supplied valid object; compiled validation neither fills defaults nor removes fields.

The wheel is rebuilt at `.runtime/server-recovery/sdk-choice-profile-20261007/dist/dnd_player_sdk-0.1.0-py3-none-any.whl`. Editable SDK installs succeed in `/home/tommaso/.cache/dnd-engine/venv` and `.runtime/windows/venv`; Windows installs the native dependency from a published wheel. This is an SDK-only runtime dependency change. Root engine `pyproject.toml` / `uv.lock` and generated schema/declarations are unchanged. Dependency metadata and wheel hashes are in `dependency.json`; Windows installation output is in `windows-install.txt`.

An independent anti-slop source review approved the shared validator, explicit format validation and finite-value boundary. The parent independently reviewed the transport patch. Cold replay now also asserts a completed receipt must end in a terminal public packet, and reports `terminal_expected` per stream instead of applying a misleading global false flag. The already completed 601-record cold replay showed all 16 final boundaries terminal; later reruns exercise the strengthened assertion.

Primary dependency references: [jsonschema-rs 0.46.6 package and platform wheels](https://pypi.org/project/jsonschema-rs/0.46.6/) and [upstream implementation](https://github.com/Stranger6667/jsonschema). The SDK imports the established compiled implementation; it introduces no handwritten schema compiler, separate schema or game-state reducer.
