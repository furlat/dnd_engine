# Python player SDK

Python 3.12+. Install this package with `pip install ./sdk/python`, or build a wheel
with `python -m build sdk/python`. Its runtime dependencies are HTTPX and the
compiled `jsonschema-rs` validator; it has no engine, Pygame or artwork dependency.
Types are generated TypedDicts and unions. The validator uses the packaged,
unchanged Draft 2020-12 schema with format validation enabled. `jsonschema-rs`
requires a native wheel (including supported Windows and Linux wheels), or a Rust
toolchain when building it from source. Validation is always enabled.

```python
import asyncio
from pathlib import Path
from uuid import uuid4
from dnd_player import connect, attach, status, Follower, follow, wait_for_cursor

async def main():
    connection = await connect("http://127.0.0.1:8790", "YOUR_SEAT_BEARER")
    task = None
    try:
        current = await status(connection)
        while current["boundary"]["lifecycle"] == "starting":
            await asyncio.sleep(0.1)
            current = await status(connection)
        await attach(connection, {
            "acquisition_id": str(uuid4()),
            "expected_attachment_epoch": current["attachment_epoch"],
        })
        output = Path("recording")
        output.mkdir(exist_ok=True)

        async def consume(packet, raw):
            # Replace with your durable recording / application reducer.
            # Returning successfully allows the follower to acknowledge this record.
            (output / f'{packet["cursor"]["sequence"]:06}.json').write_bytes(raw)

        follower = Follower(connection, consume)
        task = asyncio.create_task(follow(follower))
        current = await status(connection)
        await wait_for_cursor(follower, current["published_cursor"])
        # Run queries/commands concurrently; do not wait for animations here.
        await task
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await connection.http.aclose()

asyncio.run(main())
```

`choices`, `preview`, `submit_command`, `receipt`, `content` and `acknowledge` take
the generated request/value types. A committed receipt's `cursor` is suitable for
`wait_for_cursor`. The complete working action loop is
`devtools/player_server_acceptance/python_player.py`.

One follower invokes consumers serially, validates schema/identity/contiguous
sequence, retains original bytes, and acknowledges only accepted records.
Duplicates on reconnect are ignored; gaps, wrong epochs, consumer failures and
malformed packets fail explicitly. Transport retry is bounded. Command retries
are the caller's explicit decision using the identical numbered payload.
No second reducer, mechanics, target selection or animation clock lives here.

Player schema 7 adds event-associated `WorldUpdate.tile_changes` for already known
tiles. Consumers must apply these fields at each source event; omitted fields
stay unchanged. Reinstall this SDK alongside the server update and implement the
[client reducer handoff](../protocol/README.md#client-handoff-event-associated-tile-field-updates).

Run package checks with `python -m pytest sdk/python/tests` in an environment with
this package installed. Tests use deterministic mock transports; the separate
acceptance runner exercises real sockets and independent installed clients.

## Compact choices and selected previews

Player schema 8 sends response-local `subjects`, `positions` and `target_sets`.
Install the regenerated SDK together with the server update; the handshake rejects
older schema identities. The [protocol migration and client handoff](../protocol/README.md)
explains the wire records and native selection cases.

`all_actions(choices)` yields the original action rows in discovery order.
`action_options(choices, action)` returns the shared primary binding array.
`binding_subject(domains, binding)` and `binding_position(domains, binding)` resolve
its identity/contact/aim; self bindings return `None` for both. Keep creature/object
identity when multiple subjects share a coordinate. Table offsets are lookups;
`binding['index']` is the native selection index.

```python
from dnd_player import (action_options, all_actions, binding_position, choices,
    next_options, preview, preview_positions, selection_for)

reply = await choices(connection, query)
offered = reply['choices']
action = next(row for row in all_actions(offered)
              if row['behavior_id'] == wanted and row['availability_status'] == 'available')
target = action_options(offered, action)[0]
selection = selection_for(action, [target], prefer_safe=False)
result = await preview(connection, {
    'actor_uuid': query['actor_uuid'], 'state_revision': query['state_revision'],
    'discovery_generation': offered['discovery_generation'],
    'correlation_id': str(uuid4()), 'selection': selection,
})
# Continuations resolve against this Preview, never against offered's tables.
continuations = next_options(result['preview'])
landings = preview_positions(result['preview'])
# Store a chosen continuation's native index, or a landing's coordinates,
# in your own ordered selection state. Native Preview checks the complete prefix.
```

`secondary_options(offered, action, primary)` preserves an inherited pool versus
an explicitly empty override. Indices can repeat across different primary branches;
selection order and repeated recipients remain meaningful. `selection_for` copies
only the command prefix and positions, without sorting or deduplicating them.
`binding_path` resolves only a requested normal/safe path. `position_eligibility`
optionally builds a coordinate-to-`(action, binding)` lookup from primary choices,
retaining subject identities and excluding secondary-only options. Build it once
for the current snapshot when needed, rather than on each hover.

Treat shared dictionaries/lists as read-only consumer data and keep UI state
separately. They are ordinary Python values, not runtime-frozen objects. Mutation
changes your own shared view, never the server's retained admission. Helpers do
not mutate or expand the response. The validator does not populate schema defaults;
`binding_value` reads pair-data defaults on demand (`None`, `False`, or an empty
exposure sequence). An explicit empty path remains empty, distinct from an absent
path. Both structural and response-local reference validation run before replies
are returned; malformed indices, branches and availability relationships fail with
`ProtocolError`.

Ground AoE choices contain exact legal aims with `area_preview='deferred'` and
optional declared aiming geometry. They omit per-aim effects. Render supported
geometry from disclosed facts, then request an optional selected Preview for exact
subjective effects. Its `area_preview='computed'` can contain an empty affected
set; that is different from deferred data. `preview_positions(preview, affected=True)`
resolves its affected cells. Commands remain valid without requesting a Preview.
Discard obsolete replies by request correlation, actor/revision/generation and
ordered prefix; a pending query may supersede another while an in-flight reply
still arrives. For movement, use the same `prefer_safe` in Preview and Command and
read the returned `selected_route`.
