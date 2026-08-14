import assert from "node:assert/strict";
import test from "node:test";

import { SseDecoder } from "../index.js";

test("SSE decoder preserves CRLF when the pair is split across chunks", () => {
  const decoder = new SseDecoder();

  assert.deepEqual(decoder.feed("event: custom\r"), []);
  assert.deepEqual(decoder.feed("\nid: cursor-1\r"), []);
  assert.deepEqual(decoder.feed("\ndata: {\"ok\":true}\r\n\r"), []);
  assert.deepEqual(decoder.feed("\n"), [{
    event: "custom",
    id: "cursor-1",
    data: { ok: true },
  }]);
  assert.deepEqual(decoder.finish(), []);
});
