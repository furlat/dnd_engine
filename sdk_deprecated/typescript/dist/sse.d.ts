import type { DirectoryEventRecord, DirectoryStreamHeartbeat, DirectoryStreamSync, EvictedPayload, JsonValue } from "./generated/contracts.generated.js";
export interface SseMessage {
    readonly event: string;
    readonly id: string | null;
    readonly data: JsonValue;
}
export type DirectorySseEnvelope = {
    readonly event: "sync";
    readonly id: string | null;
    readonly data: DirectoryStreamSync;
} | {
    readonly event: "directory_event";
    readonly id: string | null;
    readonly data: DirectoryEventRecord;
} | {
    readonly event: "heartbeat";
    readonly id: string | null;
    readonly data: DirectoryStreamHeartbeat;
} | {
    readonly event: "evicted";
    readonly id: string | null;
    readonly data: EvictedPayload;
};
export declare class SseDecoder {
    private buffer;
    private pendingCarriageReturn;
    private eventName;
    private eventId;
    private dataLines;
    feed(chunk: string): SseMessage[];
    private drainCompleteLines;
    finish(): SseMessage[];
    private normalizeChunk;
    private consumeLine;
    private resetEvent;
}
export declare function decodeDirectoryEnvelope(message: SseMessage): DirectorySseEnvelope;
//# sourceMappingURL=sse.d.ts.map