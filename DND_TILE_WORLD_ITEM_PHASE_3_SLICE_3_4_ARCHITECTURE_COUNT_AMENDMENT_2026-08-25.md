# Phase 3 Slice 3.4 architecture-count amendment

Status: `APPROVED_FOR_LUNA_IMPLEMENTATION`.

Substantive independently reviewed revision:
`8fefd782f976ba890858fd3acac30e82f597aa57e056a439776a0a690d5ad2cc`

Review verdict: `APPROVED`. This amendment authorizes only the one-line active
architecture expectation repair below.

Date: 2026-08-25

## 1. Governing bind

This amendment changes only the mutation envelope of the approved Phase 3
completion plan:

- approved plan:
  `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_PLAN_2026-08-25.md`;
- approved plan SHA-256:
  `fd0600201666d86ca8a9bab669fd736f0a50e14729f64a8415c0339abd6faedc`;
- independently approved substantive revision:
  `22e45a4b0a27dfa8952d534d08e9beef3922b28594b4bc6ab9314be9d652000b`.

All mechanics, authored rows, test cases, node budgets, stop conditions, and
Slice 3.5 gates in the approved plan remain unchanged.

## 2. Concrete omission and evidence

The approved plan requires adding the active direct catalog identity
`environment.cliff_face` in `dnd/content/items/item_catalog.py`. The existing
active architecture test
`tests/architecture/test_content_ledger_boundary.py::test_content_ledger_has_the_exact_direct_domain_inventory`
asserts the exact direct item inventory count.

After the approved catalog addition, the architecture lane produced:

```text
ContentLedgerKind.ITEM actual: 146
ContentLedgerKind.ITEM expected: 145
1 failed, 40 passed
```

This is not a mechanics regression or permission to remove the catalog row.
The new concrete cliff identity correctly increases the direct item inventory
by exactly one. The plan authorized the cause but omitted its exact active
architecture expectation from the test mutation envelope.

## 3. Sole authorized repair

Add exactly one Slice 3.4 test file to the approved mutation envelope:

```text
tests/architecture/test_content_ledger_boundary.py
```

Inside the existing selector
`test_content_ledger_has_the_exact_direct_domain_inventory`, change only:

```text
ContentLedgerKind.ITEM: 145
```

to:

```text
ContentLedgerKind.ITEM: 146
```

Do not change any other content-family count, selector, production file,
architecture rule, ledger construction, or dependency boundary. Do not add a
compatibility row, alias, dynamic expectation, or new test node.

## 4. Validation and accounting

After the one-line repair:

1. run the exact selector above;
2. run the complete `tests/architecture` lane and require 41 passed;
3. rerun the approved Slice 3.4 focused selectors;
4. rerun the exact 14-module capability lane, spell lane, complete active
   in-process lane, and collect/hash gate required by the approved plan; and
5. include the architecture test's current final raw-byte hash in the final
   Phase 3 manifest. It is already a member of the accepted Slice 3.3
   manifest, so the final union emits it once.

The repair adds no node and renames none. Expected counts remain:

- complete active: 614;
- capability: 321;
- spell: 62; and
- architecture: 41.

The accepted 614-node normalized hash remains
`774c745d442d5db6b8bfb2878309b4eae118e08d264ae4a12370f2a21db05641`
because node identity is unchanged.

## 5. Stop condition

If the one-line count change does not make the exact selector and full
architecture lane green, stop and report. Do not broaden this amendment.
