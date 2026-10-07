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

Run package checks with `python -m pytest sdk/python/tests` in an environment with
this package installed. Tests use deterministic mock transports; the separate
acceptance runner exercises real sockets and independent installed clients.
