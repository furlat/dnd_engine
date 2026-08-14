import { SDK_ALIAS_DESCRIPTORS, SDK_ENUM_DESCRIPTORS, SDK_EVENT_CLASSES, SDK_MODEL_DESCRIPTORS, SDK_MODEL_PATHS_BY_NAME, } from "./generated/contracts.generated.js";
export class ContractValidationError extends Error {
    path;
    constructor(path, message) {
        super(`${path}: ${message}`);
        this.name = "ContractValidationError";
        this.path = path;
    }
}
function isRecord(value) {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function isJsonValue(value) {
    if (value === null
        || typeof value === "string"
        || typeof value === "boolean") {
        return true;
    }
    if (typeof value === "number") {
        return Number.isFinite(value);
    }
    if (Array.isArray(value)) {
        return value.every(isJsonValue);
    }
    if (isRecord(value)) {
        return Object.values(value).every(isJsonValue);
    }
    return false;
}
export function assertJsonValue(value, path = "$") {
    if (!isJsonValue(value)) {
        throw new ContractValidationError(path, "value is not valid JSON");
    }
}
function validateDescriptor(value, descriptor, path) {
    switch (descriptor.kind) {
        case "json":
            assertJsonValue(value, path);
            return;
        case "null":
            if (value !== null) {
                throw new ContractValidationError(path, "expected null");
            }
            return;
        case "string":
            if (typeof value !== "string") {
                throw new ContractValidationError(path, "expected string");
            }
            assertLength(value.length, descriptor, path);
            return;
        case "number":
            if (typeof value !== "number" || !Number.isFinite(value)) {
                throw new ContractValidationError(path, "expected finite number");
            }
            assertNumericBounds(value, descriptor, path);
            return;
        case "integer":
            if (typeof value !== "number" || !Number.isSafeInteger(value)) {
                throw new ContractValidationError(path, "expected safe integer");
            }
            assertNumericBounds(value, descriptor, path);
            return;
        case "boolean":
            if (typeof value !== "boolean") {
                throw new ContractValidationError(path, "expected boolean");
            }
            return;
        case "literal":
            if (!Object.is(value, descriptor.value)) {
                throw new ContractValidationError(path, `expected literal ${JSON.stringify(descriptor.value)}`);
            }
            return;
        case "enum": {
            const enumDescriptor = SDK_ENUM_DESCRIPTORS[descriptor.ref];
            if (enumDescriptor === undefined) {
                throw new ContractValidationError(path, `unknown enum ${descriptor.ref}`);
            }
            if (!enumDescriptor.values.some((candidate) => Object.is(candidate, value))) {
                throw new ContractValidationError(path, `invalid ${enumDescriptor.typescript} value`);
            }
            return;
        }
        case "model":
            if (descriptor.ref === "dnd.core.events.Event"
                || descriptor.ref === "server.timeline_contracts.WireEvent") {
                validateServerEvent(value, path);
                return;
            }
            validateModelPath(value, descriptor.ref, path);
            return;
        case "array":
            if (!Array.isArray(value)) {
                throw new ContractValidationError(path, "expected array");
            }
            assertLength(value.length, descriptor, path);
            value.forEach((item, index) => {
                validateDescriptor(item, descriptor.items, `${path}[${index}]`);
            });
            return;
        case "record":
            if (!isRecord(value)) {
                throw new ContractValidationError(path, "expected object record");
            }
            assertLength(Object.keys(value).length, descriptor, path);
            for (const [key, item] of Object.entries(value)) {
                validateDescriptor(item, descriptor.values, `${path}.${key}`);
            }
            return;
        case "tuple":
            if (!Array.isArray(value) || value.length !== descriptor.items.length) {
                throw new ContractValidationError(path, `expected tuple of length ${descriptor.items.length}`);
            }
            descriptor.items.forEach((itemDescriptor, index) => {
                validateDescriptor(value[index], itemDescriptor, `${path}[${index}]`);
            });
            return;
        case "union": {
            const failures = [];
            for (const member of descriptor.items) {
                try {
                    validateDescriptor(value, member, path);
                    return;
                }
                catch (error) {
                    failures.push(error instanceof Error ? error.message : String(error));
                }
            }
            throw new ContractValidationError(path, `value matched no union member (${failures.join("; ")})`);
        }
    }
}
function assertLength(length, descriptor, path) {
    if (descriptor.min_length !== undefined && length < descriptor.min_length) {
        throw new ContractValidationError(path, `expected length >= ${descriptor.min_length}`);
    }
    if (descriptor.max_length !== undefined && length > descriptor.max_length) {
        throw new ContractValidationError(path, `expected length <= ${descriptor.max_length}`);
    }
}
function assertNumericBounds(value, descriptor, path) {
    if (descriptor.minimum !== undefined && value < descriptor.minimum) {
        throw new ContractValidationError(path, `expected value >= ${descriptor.minimum}`);
    }
    if (descriptor.exclusive_minimum !== undefined && value <= descriptor.exclusive_minimum) {
        throw new ContractValidationError(path, `expected value > ${descriptor.exclusive_minimum}`);
    }
    if (descriptor.maximum !== undefined && value > descriptor.maximum) {
        throw new ContractValidationError(path, `expected value <= ${descriptor.maximum}`);
    }
    if (descriptor.exclusive_maximum !== undefined && value >= descriptor.exclusive_maximum) {
        throw new ContractValidationError(path, `expected value < ${descriptor.exclusive_maximum}`);
    }
}
function validateModelPath(value, modelPath, path) {
    if (modelPath === "server.timeline_contracts.WireEvent") {
        validateServerEvent(value, path);
        return;
    }
    const model = SDK_MODEL_DESCRIPTORS[modelPath];
    if (model === undefined) {
        throw new ContractValidationError(path, `unknown model ${modelPath}`);
    }
    if (model.root_model) {
        const root = model.fields.root;
        if (root === undefined) {
            throw new ContractValidationError(path, `${model.typescript} has no root descriptor`);
        }
        validateDescriptor(value, root, path);
        return;
    }
    if (!isRecord(value)) {
        throw new ContractValidationError(path, `expected ${model.typescript} object`);
    }
    const eventClass = SDK_EVENT_CLASSES[modelPath];
    const expectedFields = new Set(Object.keys(model.fields));
    if (eventClass !== undefined) {
        expectedFields.add("wire_type");
    }
    for (const field of expectedFields) {
        if (!(field in value)) {
            throw new ContractValidationError(`${path}.${field}`, "missing required field");
        }
    }
    for (const field of Object.keys(value)) {
        if (!expectedFields.has(field)) {
            throw new ContractValidationError(`${path}.${field}`, "unexpected field");
        }
    }
    for (const [field, descriptor] of Object.entries(model.fields)) {
        validateDescriptor(value[field], descriptor, `${path}.${field}`);
    }
    if (eventClass !== undefined) {
        if (value.wire_type !== modelPath) {
            throw new ContractValidationError(`${path}.wire_type`, `expected ${JSON.stringify(modelPath)}`);
        }
        if (typeof value.event_type !== "string"
            || !eventClass.event_types.includes(value.event_type)) {
            throw new ContractValidationError(`${path}.event_type`, `event type is invalid for ${model.typescript}`);
        }
    }
}
export function decodeModel(name, value) {
    const path = SDK_MODEL_PATHS_BY_NAME[name];
    if (path === undefined) {
        throw new ContractValidationError("$", `unknown SDK model ${String(name)}`);
    }
    validateModelPath(value, path, "$" + String(name));
    return value;
}
export function decodeAlias(name, value) {
    const descriptor = SDK_ALIAS_DESCRIPTORS[name];
    if (descriptor === undefined) {
        throw new ContractValidationError("$", `unknown SDK alias ${String(name)}`);
    }
    validateDescriptor(value, descriptor, "$" + String(name));
    return value;
}
export function validateServerEvent(value, path = "$event") {
    if (!isRecord(value) || typeof value.wire_type !== "string") {
        throw new ContractValidationError(`${path}.wire_type`, "missing event wire discriminator");
    }
    const eventClass = SDK_EVENT_CLASSES[value.wire_type];
    if (eventClass === undefined) {
        throw new ContractValidationError(`${path}.wire_type`, `unregistered event class ${value.wire_type}`);
    }
    validateModelPath(value, eventClass.model, path);
}
export function decodeServerEvent(value) {
    validateServerEvent(value);
    return value;
}
export function isConcreteServerEvent(event) {
    return event.wire_type !== "dnd.core.events.Event";
}
export function parseJson(text) {
    const parsed = JSON.parse(text);
    assertJsonValue(parsed);
    return parsed;
}
//# sourceMappingURL=validation.js.map