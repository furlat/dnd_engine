import { type ConcreteServerEvent, type JsonValue, type SdkAliasByName, type SdkAliasName, type SdkModelByName, type SdkModelName, type ServerEvent } from "./generated/contracts.generated.js";
export declare class ContractValidationError extends Error {
    readonly path: string;
    constructor(path: string, message: string);
}
export declare function isJsonValue(value: unknown): value is JsonValue;
export declare function assertJsonValue(value: unknown, path?: string): asserts value is JsonValue;
export declare function decodeModel<Name extends SdkModelName>(name: Name, value: unknown): SdkModelByName[Name];
export declare function decodeAlias<Name extends SdkAliasName>(name: Name, value: unknown): SdkAliasByName[Name];
export declare function validateServerEvent(value: unknown, path?: string): asserts value is ServerEvent;
export declare function decodeServerEvent(value: unknown): ServerEvent;
export declare function isConcreteServerEvent(event: ServerEvent): event is ConcreteServerEvent;
export declare function parseJson(text: string): JsonValue;
//# sourceMappingURL=validation.d.ts.map