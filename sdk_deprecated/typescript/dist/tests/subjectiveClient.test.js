import assert from "node:assert/strict";
import test from "node:test";
import { ContractValidationError, SubjectiveBootstrapUnavailableError, SubjectiveReplicationClient, SubjectiveReplicationHttpError, } from "../index.js";
import { bootstrap } from "./fixtures.js";
const DEFERRED = {
    code: "source_batch_in_flight",
    retryable: true,
    source_stream_id: "stream-a",
    generation_id: "generation-a",
};
test("bootstrapAttempt decodes only the exact typed source-batch deferral", async () => {
    const requests = [];
    const client = new SubjectiveReplicationClient("/api/", {
        fetchImplementation: async (input) => {
            requests.push(String(input));
            return jsonResponse(DEFERRED, 409);
        },
    });
    assert.deepEqual(await client.bootstrapAttempt("session/id"), {
        status: "deferred",
        deferral: DEFERRED,
    });
    assert.deepEqual(requests, [
        "/api/replication/bootstrap?session_id=session%2Fid",
    ]);
    for (const malformed of [
        { code: "source_batch_in_flight" },
        { ...DEFERRED, hidden_lineage: "must-not-pass" },
        { ...DEFERRED, retryable: false },
    ]) {
        const invalid = new SubjectiveReplicationClient("/api", {
            fetchImplementation: async () => jsonResponse(malformed, 409),
        });
        await assert.rejects(() => invalid.bootstrapAttempt("session-a"), ContractValidationError);
    }
});
test("bootstrapAttempt preserves every non-deferral 409 as an HTTP error", async () => {
    const generic = {
        detail: {
            code: "replication_identity_changed",
            message: "explicit encounter is not the runtime subscribed source",
            expected_source_stream_id: null,
            expected_generation_id: null,
            expected_perspective_epoch_id: null,
        },
    };
    for (const payload of [
        { detail: DEFERRED },
        generic,
        { code: "replication_partition_unavailable", retryable: true },
        ["malformed", "conflict"],
        null,
    ]) {
        const client = new SubjectiveReplicationClient("/api", {
            fetchImplementation: async () => jsonResponse(payload, 409),
        });
        await assert.rejects(() => client.bootstrapAttempt("session-a"), (error) => {
            if (!(error instanceof SubjectiveReplicationHttpError))
                return false;
            assert.equal(error.status, 409);
            assert.deepEqual(error.payload, payload);
            return true;
        });
    }
});
test("bootstrap does not retry or erase a generic 409 conflict", async () => {
    const payload = {
        detail: {
            code: "replication_identity_changed",
            message: "explicit encounter is not the runtime subscribed source",
            expected_source_stream_id: null,
            expected_generation_id: null,
            expected_perspective_epoch_id: null,
        },
    };
    let requests = 0;
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            requests += 1;
            return jsonResponse(payload, 409);
        },
    });
    await assert.rejects(() => client.bootstrap("session-a"), (error) => {
        if (!(error instanceof SubjectiveReplicationHttpError))
            return false;
        assert.equal(error.status, 409);
        assert.deepEqual(error.payload, payload);
        return true;
    });
    assert.equal(requests, 1);
});
test("bootstrap retries only the typed deferred result and returns the first ready seed", async () => {
    let requests = 0;
    const seed = bootstrap();
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            requests += 1;
            return requests === 1 ? jsonResponse(DEFERRED, 409) : jsonResponse(seed);
        },
    });
    assert.deepEqual(await client.bootstrap("session-a"), seed);
    assert.equal(requests, 2);
});
test("bootstrap retry is abortable without issuing another request", async () => {
    const controller = new AbortController();
    const reason = new Error("caller stopped bootstrap");
    let requests = 0;
    const client = new SubjectiveReplicationClient("/api", {
        fetchImplementation: async () => {
            requests += 1;
            queueMicrotask(() => controller.abort(reason));
            return jsonResponse(DEFERRED, 409);
        },
    });
    await assert.rejects(() => client.bootstrap("session-a", controller.signal), (error) => error === reason);
    assert.equal(requests, 1);
});
test("bootstrap expiry is typed, monotonic, bounded, and retains the last deferral", async () => {
    const clock = [0, 0, 10_001];
    let requests = 0;
    const client = new SubjectiveReplicationClient("/api", {
        monotonicNow: () => clock.shift() ?? 10_001,
        fetchImplementation: async () => {
            requests += 1;
            return jsonResponse(DEFERRED, 409);
        },
    });
    await assert.rejects(() => client.bootstrap("session-a"), (error) => (error instanceof SubjectiveBootstrapUnavailableError
        && error.lastDeferral?.code === "source_batch_in_flight"));
    assert.equal(requests, 1);
});
function jsonResponse(payload, status = 200) {
    return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
    });
}
//# sourceMappingURL=subjectiveClient.test.js.map