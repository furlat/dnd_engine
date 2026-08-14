import { ContractValidationError, decodeModel, parseJson } from "./validation.js";
export class SseDecoder {
    buffer = "";
    pendingCarriageReturn = false;
    eventName = "message";
    eventId = null;
    dataLines = [];
    feed(chunk) {
        this.buffer += this.normalizeChunk(chunk);
        return this.drainCompleteLines();
    }
    drainCompleteLines() {
        const messages = [];
        let start = 0;
        while (true) {
            const newline = this.buffer.indexOf("\n", start);
            if (newline < 0) {
                break;
            }
            const line = this.buffer.slice(start, newline);
            start = newline + 1;
            const message = this.consumeLine(line);
            if (message !== null) {
                messages.push(message);
            }
        }
        this.buffer = this.buffer.slice(start);
        return messages;
    }
    finish() {
        if (this.pendingCarriageReturn) {
            this.buffer += "\n";
            this.pendingCarriageReturn = false;
        }
        const messages = this.drainCompleteLines();
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
    normalizeChunk(chunk) {
        let value = chunk;
        let prefix = "";
        if (this.pendingCarriageReturn) {
            prefix = "\n";
            this.pendingCarriageReturn = false;
            if (value.startsWith("\n"))
                value = value.slice(1);
        }
        if (value.endsWith("\r")) {
            value = value.slice(0, -1);
            this.pendingCarriageReturn = true;
        }
        return prefix + value.replaceAll("\r\n", "\n").replaceAll("\r", "\n");
    }
    consumeLine(line) {
        if (line === "") {
            if (this.dataLines.length === 0) {
                this.resetEvent();
                return null;
            }
            const message = {
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
    resetEvent() {
        this.eventName = "message";
        this.eventId = null;
        this.dataLines = [];
    }
}
export function decodeDirectoryEnvelope(message) {
    switch (message.event) {
        case "sync":
            return { event: "sync", id: message.id, data: decodeModel("DirectoryStreamSync", message.data) };
        case "directory_event":
            return { event: "directory_event", id: message.id, data: decodeModel("DirectoryEventRecord", message.data) };
        case "heartbeat":
            return { event: "heartbeat", id: message.id, data: decodeModel("DirectoryStreamHeartbeat", message.data) };
        case "evicted":
            return { event: "evicted", id: message.id, data: decodeModel("EvictedPayload", message.data) };
        default:
            throw new ContractValidationError("$directory_sse.event", `unsupported event ${message.event}`);
    }
}
//# sourceMappingURL=sse.js.map