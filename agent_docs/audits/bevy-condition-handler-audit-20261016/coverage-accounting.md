# Coverage accounting — 2026-10-16

Reconciled all **3,203** unique rows from `inventory.json` against the three supplied keyed ledgers and the existing reports. [consolidated-coverage.tsv](consolidated-coverage.tsv) contains one row per original inventory row, preserving original order, source coordinates, owner and expression. No engine, existing report, scanner, inventory or prior ledger was changed. This is evidence reconciliation, not additional source-body reading or native qualification.

## Matching and honest status

Exact matching uses `(kind, path, line, end_line, expression)`; inventory keys have no duplicates. Feature/world has 1,178 exact matching rows; grants has 73, all also present in feature/world (52 close SECOND_WAVE_OWNED and 21 supersede first-wave read mappings). Grants wins those overlaps. Spell integration has 811 exact indexed matches and 37 supplemental function records; supplemental functions stay in its own ledger and are not added to the 3,203 inventory denominator. All other ledger rows match the inventory.

The foundation report and first-wave spell declaration/callback report do not supply keyed TSV rows. Their 949 assigned rows are marked `REPORT_SCOPE_NOT_KEYED`, explicitly disclosing report-scope inference. That status records ownership and the report claim; it does not manufacture a line-by-line read assertion. Core BaseCondition lifecycle rows are assigned to the foundation report under its stated scope; remaining core/engine infrastructure and the 53 feature/world delegated rows now use `ROOT_BOUNDARY_REVIEW`, supported by infrastructure.md. Its review covers all 409 infrastructure rows, overlapping the 91 core BaseCondition rows shared with foundations.md. This is mechanical boundary/support/false-positive classification, not a full-method read claim.

| Status | Rows |
|---|---:|
| CONFIG_AND_EVALUATOR_READ | 38 |
| CONFIG_AND_PROCESSOR_READ | 102 |
| DECLARATION_LIFECYCLE_MAPPED | 112 |
| FALSE_POSITIVE_COLLECTION_REMOVE | 2 |
| INTEGRATION_METHOD_READ | 195 |
| KEYED_SOURCE_REVIEW_REPORTED | 884 |
| REPORT_SCOPE_NOT_KEYED | 949 |
| ROOT_BOUNDARY_REVIEW | 318 |
| SOURCE_SPAN_READ | 603 |

| Report owner | Rows |
|---|---:|
| content-grants.md | 73 |
| features-world.md | 1052 |
| foundations.md | 246 |
| foundations.md; infrastructure.md (shared) | 91 |
| infrastructure.md | 318 |
| spells-integration.md | 811 |
| spells.md | 612 |

## Requested declaration and callback totals

| Inventory category | Total | Report ownership |
|---|---:|---|
| condition_class | 252 | content-grants.md: 3; features-world.md: 112; foundations.md: 30; foundations.md; infrastructure.md shared: 1; spells.md: 106 |
| handler_construction | 153 | content-grants.md: 7; features-world.md: 48; foundations.md: 11; infrastructure.md: 4; spells.md: 83 |
| processor_argument | 153 | content-grants.md: 7; features-world.md: 48; foundations.md: 11; infrastructure.md: 4; spells.md: 83 |
| contextual_modifier_construction | 43 | content-grants.md: 8; features-world.md: 19; foundations.md: 13; spells.md: 3 |
| contextual_callable_argument | 43 | content-grants.md: 8; features-world.md: 19; foundations.md: 13; spells.md: 3 |

The 153 handler constructions and 153 processor arguments are overlapping categories at the same 153 constructor sites, not 306 independent handler behaviors. Likewise 43 contextual constructions and 43 callable argument rows describe overlapping site categories. The scanner now names the required BaseHandler callable `processor_field_declaration`; both output kind columns match the refreshed inventory. It is a field declaration, not an installed default handler. One processor reassignment remains its own indexed category.

## Remaining coverage and report consistency

**No inventory rows lack report ownership. No delegated or infrastructure rows remain pending report evidence.** The **318 ROOT_BOUNDARY_REVIEW rows** have infrastructure.md boundary/support/false-positive classification; their exact coordinates and owners remain in the TSV. The report also jointly covers 91 BaseCondition rows owned by foundations.md, yielding its stated 409 infrastructure rows. These are not 409 full-method reads. The four engine handler sites (actions_functional.py:167/205/211 and entity.py:1031) now have explicit processor/registration-lifetime boundary review. All 252 condition declarations, all 153 handler constructions/processor sites and all 43 contextual construction/callable sites have report evidence or explicitly disclosed report-scope inference.

`spells.md` explicitly left 121 construction, 57 registration/dispatch and 633 interaction rows inventory-only. `spells-integration.md` and its 811 keyed rows close that integration-site limit; the consolidated ledger uses that later evidence. This does not close arbitrary targeting algorithms, metadata internals, numerical balance or complete transitive gameplay/native parity.

Silence: first-wave F3 identifies a Python captured-set distinction, but the current combined design position is fixed-origin Silence with conditional ambiguity only if a real supported footprint-replacement integration case arises. `bevy-exposure.md` narrows this using actual source and existing verbal/nonverbal/shared-membership tests. Do not summarize the early alias warning as a blocker, a movable-Silence requirement, a proven defect or a mandate for an alias-record framework.

All source-read statuses are claims from the named evidence, not independent execution certification. Exact keyed source review, report-scope ownership inference and root mechanical-boundary classification remain distinct. No native semantic parity, unrestricted parallel execution, speedup or complete unindexed-callback closure is claimed.

Refreshed-inventory verification: exact `(kind, path, line, end_line, owner, expression)` set equality, 3,203 distinct rows, unchanged requested category totals. Infrastructure status was updated only to its stated boundary classification; no new source-body inspection was inferred.
