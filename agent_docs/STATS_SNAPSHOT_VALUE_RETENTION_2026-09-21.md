# Observed defect: stat reads retain derived values

Discovered while validating the native typing repair on September 21. This is
an actual lifetime/allocation defect, not a type error or harmless test noise.
It remains outside the completed typing/goblin repair. No value-system change
was slipped into that repair.

## Reproduction and result

In the documented uv environment, from the repository root:

```python
from uuid import uuid4
import gc
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from dnd.core.base_object import BaseObject
from dnd.core.values import BaseValue

reset_engine_runtime(grid_size=(8, 8))
actor = Entity.create(uuid4(), config=EntityConfig())
for _ in range(3):
    before = len(BaseValue._registry), len(BaseObject._registry)
    actor.snapshot_entity_stats()
    gc.collect()
    after = len(BaseValue._registry), len(BaseObject._registry)
    print(after[0] - before[0], after[1] - before[1])
reset_engine_runtime()
```

Both the implementing agent and independent root reproduction measured
**35 additional BaseValues and 3 additional BaseObjects per snapshot**, on
each of three consecutive calls. GC does not release them. Registry sizes
start at 430/84 and grow to 465/87, 500/90, then 535/93. Returned stats remain
unchanged. Counts describe this fixture, not every character build.

`Entity.snapshot_entity_stats()` calls `get_max_hp()` and `ac_bonus()`.
`Ability.get_combined_values()` builds a fresh `ModifiableValue` graph and
ability modifier; combining the armor-class values constructs further values.
The derived objects enter strong UUID registries. Construction-discard and
runtime reset have cleanup paths; no ordinary live-entity destruction guarantee
was established. Ordinary evaluation does not end their registry lifetime.
Repeated reads therefore retain objects throughout the active entity's
lifetime. The observations establish retention, not its total gameplay timing or
memory cost; neither has been measured here.

## Why this surfaced in progression tests

A canceled Frenzied child admits and then removes its Raging parent. Completion
facts evaluate stats, which retained 110 derived values and 10 ability modifiers
in that fixture, in addition to the legitimate paid Frenzy cost. All six actual
Raging modifier UUIDs were removed and their destination modifier maps restored.
The four cancellation variants now assert that concrete ownership and resulting
mechanics instead of conflating every globally created value with Rage leakage.
Those test repairs do **not** establish that the independent retention is correct.

The other two progression assertions expected an empty event queue after
hydration. Entity creation had already emitted 64 events; hydration left the
cursor at 64. The corrected assertion compares before and after hydration.

Evidence: `.runtime/native-typing-cleanup-20260921/derived-values-stack.log`,
`derived-stats-registry-retention.log`, `progression-failure-diagnostic.log`, and
`progression-failures-before.log`. All six failures also reproduced against the
complete pre-edit native snapshot.

Any subsequent repair must preserve contextual modifiers and event breakdowns
while distinguishing persistent owned values from evaluation temporaries. A
global registry wipe or a snapshot-specific duplicate AC/HP formula would hide
the ownership problem. Anti-slop and anti-OOP review must precede that separate
design change.
