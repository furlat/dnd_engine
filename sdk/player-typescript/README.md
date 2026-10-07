# TypeScript player SDK

Run `npm ci`, `npm test`, then `npm pack` in this directory. Install the resulting
package in a separate client. It uses streaming `fetch` and Ajv, with generated
wire declarations and no engine, UI, renderer or reducer dependency. Node 22+
is used by the acceptance scripts; browser builds need streaming fetch support.

```ts
import {connect, status, attach, createFollower, follow, waitForCursor}
  from '@neurodragon/player-sdk';

const connection = await connect('http://127.0.0.1:8790', seatBearer);
let current = await status(connection);
while (current.boundary.lifecycle === 'starting') {
  await new Promise(resolve => setTimeout(resolve, 100));
  current = await status(connection);
}
await attach(connection, {
  acquisition_id: crypto.randomUUID(),
  expected_attachment_epoch: current.attachment_epoch,
});
const follower = createFollower(connection, async (packet, raw) => {
  await consumeOrRecord(packet, raw); // Your application owns this function.
});
const stop = new AbortController();
const running = follow(follower, {signal: stop.signal});
current = await status(connection);
if (current.published_cursor) await waitForCursor(follower, current.published_cursor);
// Query and issue commands concurrently; rendering must not block consumption.
// stop.abort() closes the follower; await/catch running when ending the client.
```

`choices`, `preview`, `submitCommand`, `receipt`, and `content` use the exported
request/result types. `waitForCursor` accepts a committed receipt's cursor, deadline
and cancellation signal. The working gameplay loop in
`devtools/player_server_acceptance/typescript_player.mjs` demonstrates one command
number per attempt and explicit identical retries.

Consumers are awaited in order before ACK. Raw bytes remain available for durable
recording. Invalid schemas, identities, gaps and consumer failures stop the
follower. Network retry is bounded; gameplay commands are never retried
automatically. Authenticated redirects are rejected. No animation completion,
second event reducer or gameplay implementation is part of the SDK.
