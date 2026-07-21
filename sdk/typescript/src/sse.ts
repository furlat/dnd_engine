import type {
  CombatLogPayload,
  EvictedPayload,
  GameEventPayload,
  HeartbeatPayload,
  JsonValue,
  SessionPingResponse,
  StreamSyncPayload,
} from "./generated/contracts.generated.js";
import { ContractValidationError, decodeModel, parseJson } from "./validation.js";

export interface SseMessage {
  readonly event: string;
  readonly id: string | null;
  readonly data: JsonValue;
}

export type ReplicationSseEnvelope =
  | { readonly event: "sync"; readonly id: string | null; readonly data: StreamSyncPayload }
  | { readonly event: "game_event"; readonly id: string | null; readonly data: GameEventPayload }
  | { readonly event: "combat_log"; readonly id: string | null; readonly data: CombatLogPayload }
  | { readonly event: "heartbeat"; readonly id: string | null; readonly data: HeartbeatPayload }
  | { readonly event: "session"; readonly id: string | null; readonly data: SessionPingResponse }
  | { readonly event: "evicted"; readonly id: string | null; readonly data: EvictedPayload };

export class SseDecoder {
  private buffer = "";
  private eventName = "message";
  private eventId: string | null = null;
  private dataLines: string[] = [];

  feed(chunk: string): SseMessage[] {
    this.buffer += chunk.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
    const messages: SseMessage[] = [];
    while (true) {
      const newline = this.buffer.indexOf("\n");
      if (newline < 0) {
        break;
      }
      const line = this.buffer.slice(0, newline);
      this.buffer = this.buffer.slice(newline + 1);
      const message = this.consumeLine(line);
      if (message !== null) {
        messages.push(message);
      }
    }
    return messages;
  }

  finish(): SseMessage[] {
    const messages: SseMessage[] = [];
    if (this.buffer.length > 0) {
      const message = this.consumeLine(this.buffer);
      this.buffer = "";
      if (message !== null) {
        messages.push(message);
      }
    }
    const finalMessage = this.consumeLine("");
    if (finalMessage !== null) {
      messages.push(finalMessage);
    }
    return messages;
  }

  private consumeLine(line: string): SseMessage | null {
    if (line === "") {
      if (this.dataLines.length === 0) {
        this.resetEvent();
        return null;
      }
      const message: SseMessage = {
        event: this.eventName,
        id: this.eventId,
        data: parseJson(this.dataLines.join("\n")),
      };
      this.resetEvent();
      return message;
    }
    if (line.startsWith(":")) {
      return null;
    }
    const separator = line.indexOf(":");
    const field = separator < 0 ? line : line.slice(0, separator);
    let value = separator < 0 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    switch (field) {
      case "event":
        this.eventName = value;
        break;
      case "id":
        this.eventId = value;
        break;
      case "data":
        this.dataLines.push(value);
        break;
      default:
        break;
    }
    return null;
  }

  private resetEvent(): void {
    this.eventName = "message";
    this.eventId = null;
    this.dataLines = [];
  }
}

export function decodeReplicationEnvelope(message: SseMessage): ReplicationSseEnvelope {
  switch (message.event) {
    case "sync":
      return { event: "sync", id: message.id, data: decodeModel("StreamSyncPayload", message.data) };
    case "game_event":
      return { event: "game_event", id: message.id, data: decodeModel("GameEventPayload", message.data) };
    case "combat_log":
      return { event: "combat_log", id: message.id, data: decodeModel("CombatLogPayload", message.data) };
    case "heartbeat":
      return { event: "heartbeat", id: message.id, data: decodeModel("HeartbeatPayload", message.data) };
    case "session":
      return { event: "session", id: message.id, data: decodeModel("SessionPingResponse", message.data) };
    case "evicted":
      return { event: "evicted", id: message.id, data: decodeModel("EvictedPayload", message.data) };
    default:
      throw new ContractValidationError("$sse.event", `unsupported event ${message.event}`);
  }
}
