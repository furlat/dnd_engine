import {compile} from 'json-schema-to-typescript';
import {readFile, writeFile} from 'node:fs/promises';
const schema = JSON.parse(await readFile('../protocol/player-api-v1.schema.json', 'utf8'));
// The generator accepts draft-7 tuple spelling; runtime still validates the original 2020-12 schema.
function adapt(value) {
  if (Array.isArray(value)) { value.forEach(adapt); return; }
  if (!value || typeof value !== 'object') return;
  delete value.discriminator;
  if (value.prefixItems) { value.items = value.prefixItems; delete value.prefixItems; }
  Object.values(value).forEach(adapt);
}
adapt(schema);
delete schema.$schema;
await writeFile('src/contracts.generated.ts', await compile(schema, 'PlayerProtocol', {additionalProperties: false, unreachableDefinitions: true}));
