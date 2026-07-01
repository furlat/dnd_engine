"""Execute public NeuroDragon Dev Manual snippets exactly as published."""

from __future__ import annotations

import ast
import contextlib
from dataclasses import dataclass
import io
import re
import shlex
import sys
from types import ModuleType
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_ROOT_CANDIDATES = (
    REPO_ROOT / "webbook" / "src" / "content" / "manual",
    Path("/home/tommaso/Dev/neurodragon_dev_manual/src/content/manual"),
)
MIGRATED_CHAPTERS = {
    "00-neurodragon-dev-manual.mdx": set(),
    "01-runtime-identity-and-registries.mdx": {
        "identity-first-run",
        "runtime-object-lookup",
        "runtime-object-publishing",
        "registry-families",
        "entity-position-lookup",
        "value-subclass-lookup",
    },
    "02-entity-anatomy.mdx": {"entity-first-run", "entity-anatomy-tutorial"},
    "03-values-and-modifiers.mdx": {
        "values-first-run",
        "values-score-and-breakdown",
        "values-static-rule-state",
        "values-contextual-modifiers",
        "values-target-propagation",
    },
    "04-dice-rolls.mdx": {
        "dice-first-run",
        "dice-cached-d20",
        "dice-advantage-disadvantage",
        "dice-roll-state-snapshot",
        "dice-damage-and-critical",
        "dice-expression-validation",
    },
    "05-event-lifecycle.mdx": {
        "event-first-run",
        "event-lineage-phases",
        "event-cancellation",
        "event-parent-child-lineage",
        "event-completion-combat-log",
        "event-passive-observation",
    },
    "06-reactions-to-events.mdx": {
        "reaction-first-run",
        "event-triggered-handler",
        "event-quiet-timing-windows",
        "event-cancel-and-stop",
        "event-d20-result-processor",
        "event-spatial-entry-handler",
        "event-movement-surfaces",
    },
    "07-conditions-and-cleanup.mdx": {
        "condition-first-run",
        "condition-bearing-actor",
        "condition-owned-modifier",
        "condition-owned-handler",
        "condition-subcondition-tree",
        "condition-linked-cleanup",
        "condition-duration-expiry",
    },
    "08-world-model-and-movement.mdx": {
        "world-first-run",
        "world-terrain-costs",
        "world-directional-border",
        "world-entity-spatial-events",
        "world-forced-movement",
        "world-batch-map-creation",
    },
    "09-action-discovery-and-costs.mdx": {
        "action-first-run",
        "action-template-instantiation",
        "action-discovery-menu",
        "action-execute-by-index",
        "action-object-inventory-routing",
        "action-cost-override",
        "action-target-pools",
        "action-safe-movement-path",
    },
    "10-combat-resolution.mdx": {
        "combat-first-run",
        "combat-invalid-attack-costs",
        "combat-hit-damage-healing",
        "combat-critical-damage-dice",
        "combat-voluntary-movement-reaction",
        "combat-videogame-shove-forced-movement",
    },
    "11-equipment-inventory-and-items.mdx": {
        "items-first-run",
        "items-floor-inventory-drop",
        "items-stack-atomic-capacity",
        "items-equipment-hooks",
        "items-loadout-displacement",
        "items-usable-and-environment-actions",
    },
    "12-perception-light-stealth-and-invisibility.mdx": {
        "senses-first-run",
        "senses-geometry-light-filter",
        "senses-special-light",
        "senses-reactive-light-update",
        "senses-stealth-invisibility-filter",
        "senses-subjective-paths",
        "senses-hidden-invisible-layers",
    },
    "13-spellcasting-core.mdx": {
        "spell-first-run",
        "spell-slots-resource-reset",
        "spell-numbers-modifier-composition",
        "spell-discovery-slot-variants",
        "spell-fire-bolt-resolution",
        "spell-magic-missile-multitarget",
        "spell-concentration-linked-cleanup",
    },
    "14-spell-families-and-implemented-spells.mdx": {
        "spell-family-first-run",
        "spell-catalog-runtime-metadata",
        "spell-family-offense",
        "spell-family-recovery-protection",
        "spell-family-mobility-temp-hp",
        "spell-family-spatial-zone",
        "spell-family-condition-effects",
    },
    "15-class-features-factories-and-feats.mdx": {
        "class-first-run",
        "class-factory-playable-actors",
        "class-fighter-resource-actions",
        "class-barbarian-frenzy-cleanup",
        "class-sorcerer-metamagic-overrides",
        "class-lucky-d20-policy",
    },
    "16-monsters-and-preset-actors.mdx": {
        "monster-first-run",
        "monster-base-stat-blocks",
        "monster-goblin-nimble-escape",
        "monster-generic-caster-preset",
        "monster-skeleton-role-presets",
        "monster-mark-target-concentration",
    },
    "17-encounters-turns-and-controllers.mdx": {
        "encounter-first-run",
        "encounter-start-end-state",
        "encounter-turn-round-advance",
        "encounter-advance-until-human",
        "encounter-combat-log-capture",
        "encounter-faction-survival-ending",
    },
    "18-sessions-apis-and-client-payloads.mdx": {
        "client-session-join",
        "client-state-turn-actions",
        "client-execute-indexed-action",
        "client-events-combat-log-cursors",
        "client-spell-catalog-metadata",
    },
    "19-map-editor-and-scenario-authoring.mdx": {
        "map-editor-catalog-scratch-map",
        "map-editor-tile-patches",
        "map-editor-objects-layers",
        "map-editor-object-deletion",
        "map-editor-save-load",
        "map-editor-preset-handoff",
    },
    "20-content-extension-basics.mdx": {
        "content-extension-module-surfaces",
        "content-extension-condition-lifecycle",
        "content-extension-registered-action",
        "content-extension-inventory-item",
        "content-extension-floor-object",
        "content-extension-factories",
    },
    "21-spell-and-feature-extensions.mdx": {
        "spell-feature-module-surfaces",
        "spell-feature-registers-spell",
        "spell-feature-discovery-targets",
        "spell-feature-execute-cleanup",
        "spell-feature-factory-scene",
    },
    "22-playable-scenario-packages.mdx": {
        "scenario-package-surfaces",
        "scenario-package-factory-state",
        "scenario-package-advance-human",
        "scenario-package-execute-action",
        "scenario-package-faction-ending",
    },
    "23-standard-arena-game-modes.mdx": {
        "arena-mode-surfaces",
        "arena-build-standard",
        "arena-select-hero-kit",
        "arena-control-mode",
        "arena-start-join",
        "arena-live-payloads",
    },
    "24-built-in-controllers-and-automated-turns.mdx": {
        "controller-catalogue-surfaces",
        "controller-external-input",
        "controller-pass-turn",
        "controller-melee-attack",
        "controller-melee-move",
        "controller-no-visible-enemy",
        "controller-agent-runner",
    },
    "25-live-replication-streams.mdx": {
        "stream-surface",
        "stream-sync-frame",
        "stream-cursor-replay",
        "stream-live-fanout",
        "stream-completion-before-log",
        "stream-heartbeat-frame",
        "stream-bounded-eviction",
    },
    "26-agent-tactical-interface.mdx": {
        "agent-interface-surface",
        "agent-tactical-snapshot",
        "agent-action-options",
        "agent-tactical-queries",
        "agent-expected-value",
        "agent-execute-choice",
        "agent-base-runner",
    },
    "27-agent-decision-patterns.mdx": {
        "agent-decision-surfaces",
        "agent-bt-priority",
        "agent-melee-fighter-factory",
        "agent-move-and-attack",
        "agent-interrupt-detection",
        "agent-utility-ranking",
        "agent-utility-runner",
    },
}
STRICT_BOOK_EXAMPLE_CHAPTERS = {
    "00-neurodragon-dev-manual.mdx",
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
CODE_FIRST_CHAPTERS = {
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
}
FIRST_RUN_OPEN_PANEL_CHAPTERS = CODE_FIRST_CHAPTERS | {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
}
PROSE_AUDITED_IMPORT_PANEL_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
PLAY_FRAMED_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
LOCAL_SETUP_NAME_AUDITED_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
HELPER_DOCSTRING_AUDITED_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
SOURCE_LINK_AUDITED_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
    "12-perception-light-stealth-and-invisibility.mdx",
    "13-spellcasting-core.mdx",
    "14-spell-families-and-implemented-spells.mdx",
    "15-class-features-factories-and-feats.mdx",
    "16-monsters-and-preset-actors.mdx",
    "17-encounters-turns-and-controllers.mdx",
    "18-sessions-apis-and-client-payloads.mdx",
    "19-map-editor-and-scenario-authoring.mdx",
    "20-content-extension-basics.mdx",
    "21-spell-and-feature-extensions.mdx",
    "22-playable-scenario-packages.mdx",
    "23-standard-arena-game-modes.mdx",
    "24-built-in-controllers-and-automated-turns.mdx",
    "25-live-replication-streams.mdx",
    "26-agent-tactical-interface.mdx",
    "27-agent-decision-patterns.mdx",
}
PUBLIC_MANUAL_FORBIDDEN_PATTERNS = (
    ("hidden test language", re.compile(r"test harness", re.IGNORECASE)),
    ("pytest mention", re.compile(r"\bpytest\b", re.IGNORECASE)),
    ("fixture language", re.compile(r"\bfixture\b", re.IGNORECASE)),
    ("helper language", re.compile(r"\bhelper(s)?\b", re.IGNORECASE)),
    ("private/internal language", re.compile(r"\bprivate\b", re.IGNORECASE)),
    ("behind-the-scenes language", re.compile(r"behind the scenes", re.IGNORECASE)),
    ("engine-book path leak", re.compile(r"\bengine_book\b", re.IGNORECASE)),
    ("parity language", re.compile(r"\bparity\b", re.IGNORECASE)),
    ("test item module leak", re.compile(r"\btest_items\b", re.IGNORECASE)),
    ("note-link language", re.compile(r"\bnotes?\b", re.IGNORECASE)),
    ("copy-instruction wording", re.compile(r"copy the", re.IGNORECASE)),
    ("stale drawer label", re.compile(r"Show imports", re.IGNORECASE)),
    (
        "stale import drawer label",
        re.compile(r"Open imports and scene setup", re.IGNORECASE),
    ),
    (
        "stale setup-panel boilerplate",
        re.compile(r"Each example has a \*\*Code setup:", re.IGNORECASE),
    ),
    (
        "generic setup-panel invitation",
        re.compile(r"Open it to see import paths", re.IGNORECASE),
    ),
    (
        "generic deterministic setup wording",
        re.compile(r"small deterministic setup", re.IGNORECASE),
    ),
    (
        "vague local setup source",
        re.compile(r"\bLocal setup\b", re.IGNORECASE),
    ),
    (
        "setup drawer wording",
        re.compile(r"setup drawer", re.IGNORECASE),
    ),
    (
        "local setup function wording",
        re.compile(r"local setup function", re.IGNORECASE),
    ),
    (
        "chapter-local example-code wording",
        re.compile(r"chapter-local example code", re.IGNORECASE),
    ),
    (
        "source table panel mechanics wording",
        re.compile(
            r"Defined in (?:the|this chapter's) Code setup: imports and scene panels?",
            re.IGNORECASE,
        ),
    ),
    (
        "negation-framed rules-engine wording",
        re.compile(r"not a (?:separate|second) rules? (?:engine|layer)", re.IGNORECASE),
    ),
    (
        "negation-framed value-total wording",
        re.compile(r"does not merely compute the total", re.IGNORECASE),
    ),
    (
        "negation-framed reaction wording",
        re.compile(r"A reaction is not after-the-fact commentary", re.IGNORECASE),
    ),
    (
        "negation-framed class-system wording",
        re.compile(r"not a parallel rules system", re.IGNORECASE),
    ),
    (
        "negation-framed arena wording",
        re.compile(r"not just an encounter", re.IGNORECASE),
    ),
    (
        "negation-framed spell-family wording",
        re.compile(r"not just names in a list", re.IGNORECASE),
    ),
    (
        "negation-framed character-content wording",
        re.compile(r"not as a separate rules island", re.IGNORECASE),
    ),
    (
        "negation-framed action-discovery wording",
        re.compile(r"discovery is not execution", re.IGNORECASE),
    ),
    (
        "negation-framed content-extension wording",
        re.compile(r"rather than a detached runtime mode", re.IGNORECASE),
    ),
    (
        "negation-framed extension-opening wording",
        re.compile(r"Instead of painting the room", re.IGNORECASE),
    ),
    (
        "negation-framed controller wording",
        re.compile(r"controller never replaces the ruleset", re.IGNORECASE),
    ),
    (
        "negation-framed agent-interface wording",
        re.compile(r"without giving it direct control over engine internals", re.IGNORECASE),
    ),
    (
        "negation-framed scoring wording",
        re.compile(r"expected damage without changing the rules", re.IGNORECASE),
    ),
    (
        "negation-framed monster runtime wording",
        re.compile(r"does not travel through a separate monster runtime", re.IGNORECASE),
    ),
    (
        "negation-framed lifecycle wording",
        re.compile(r"not only a label", re.IGNORECASE),
    ),
    (
        "negation-framed visibility wording",
        re.compile(r"not a single global visibility flag", re.IGNORECASE),
    ),
    (
        "hidden-shortcut wording",
        re.compile(r"hidden shortcuts", re.IGNORECASE),
    ),
    ("HTTPX default host leak", re.compile(r"testserver", re.IGNORECASE)),
    ("mocking implementation detail", re.compile(r"unittest\.mock", re.IGNORECASE)),
    ("dice monkey-patch path", re.compile(r"dnd\.core\.dice\.random\.randint")),
    ("local fixed-dice shim", re.compile(r"def fixed_dice")),
    ("local fixed-dice context", re.compile(r"with fixed_dice\(")),
    ("registry opt-out wording", re.compile(r"registry-opt-out", re.IGNORECASE)),
    ("tiny tutorial wording", re.compile(r"\btiny\b", re.IGNORECASE)),
    ("assertion prose wording", re.compile(r"\bassertions?\b", re.IGNORECASE)),
    ("assert flow label", re.compile(r"\bAssert\b")),
    ("small local class wording", re.compile(r"small local classes", re.IGNORECASE)),
    ("small runtime scene wording", re.compile(r"small runtime scene", re.IGNORECASE)),
    (
        "small condition-bearing wording",
        re.compile(r"small condition-bearing", re.IGNORECASE),
    ),
    ("placeholder marker", re.compile(r"\b(?:TODO|TBD|placeholder)\b", re.IGNORECASE)),
)
CHAPTER_FLOW_EXAMPLES = {}
FENCE_RE = re.compile(r"^```(?P<info>[^\n`]*)\n(?P<code>.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
FRONTMATTER_RULES_RE = re.compile(r"^rules:\s*(?P<rules>\[.*\])\s*$", re.MULTILINE)
EXAMPLE_BLOCK_OPEN_RE = re.compile(r"<ExampleBlock\b(?P<attrs>[^>]*)>")
EXAMPLE_BLOCK_ID_RE = re.compile(r'\bid="([^"]+)"')
EXAMPLE_BLOCK_MODE_RE = re.compile(r'\bmode="([^"]+)"')
BOOK_IMPORTS_RE = re.compile(r"<details\s+className=\"book-imports\"(?P<attrs>[^>]*)>")
BOOK_IMPORT_BLOCK_RE = re.compile(
    r"<details\s+className=\"book-imports\"(?P<attrs>[^>]*)>(?P<body>.*?)</details>",
    re.DOTALL,
)
RESULT_AFTER_BODY_RE = re.compile(
    r"\s*<p className=\"example-output-label\">Result</p>\s*"
    r"```text\n(?P<output>.*?)^```",
    re.DOTALL | re.MULTILINE,
)
ASSERT_FREE_BODY_CHAPTERS = {
    "01-runtime-identity-and-registries.mdx",
    "02-entity-anatomy.mdx",
    "03-values-and-modifiers.mdx",
    "04-dice-rolls.mdx",
    "05-event-lifecycle.mdx",
    "06-reactions-to-events.mdx",
    "07-conditions-and-cleanup.mdx",
    "08-world-model-and-movement.mdx",
    "09-action-discovery-and-costs.mdx",
    "10-combat-resolution.mdx",
    "11-equipment-inventory-and-items.mdx",
}


@dataclass(frozen=True)
class CodeFence:
    """A fenced code block extracted from an MDX chapter."""

    chapter_path: Path
    info: str
    code: str
    start_line: int


@dataclass(frozen=True)
class BookExample:
    """One executable public example assembled from one or more code fences."""

    chapter_path: Path
    name: str
    fences: tuple[CodeFence, ...]

    @property
    def id(self) -> str:
        """Return a stable pytest id for this public example."""
        return f"{self.chapter_path.stem}::{self.name}"

    @property
    def source(self) -> str:
        """Return the exact public code for this example, joined in page order."""
        return "\n\n".join(fence.code.rstrip() for fence in self.fences)

    @property
    def locations(self) -> str:
        """Return the public source locations that compose this example."""
        return ", ".join(
            f"{self.chapter_path.name}:{fence.start_line}" for fence in self.fences
        )


@dataclass(frozen=True)
class ExampleBlockSource:
    """One public ExampleBlock region in an MDX chapter."""

    chapter_path: Path
    block_id: str
    attrs: str
    start_line: int
    end_line: int

    @property
    def mode(self) -> str:
        """Return the public example-block display mode."""
        match = EXAMPLE_BLOCK_MODE_RE.search(self.attrs)
        return match.group(1) if match else "standalone"


def manual_root() -> Path:
    """Return the public manual source directory used by the local webbook."""
    for candidate in MANUAL_ROOT_CANDIDATES:
        if candidate.exists():
            return candidate
    candidates = ", ".join(str(path) for path in MANUAL_ROOT_CANDIDATES)
    pytest.fail(f"Could not find the public manual source directory. Tried: {candidates}")


def parse_fence_info(info: str) -> tuple[str, set[str], dict[str, str]]:
    """Parse a Markdown fence info string into language, flags, and options."""
    parts = shlex.split(info)
    if not parts:
        return "", set(), {}

    language = parts[0]
    flags: set[str] = set()
    options: dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            options[key] = value
        else:
            flags.add(part)
    return language, flags, options


def iter_code_fences(chapter_path: Path) -> Iterable[CodeFence]:
    """Yield fenced code blocks from an MDX chapter with their source line."""
    text = chapter_path.read_text(encoding="utf-8")
    for match in FENCE_RE.finditer(text):
        start_line = text.count("\n", 0, match.start()) + 1
        yield CodeFence(
            chapter_path=chapter_path,
            info=match.group("info").strip(),
            code=match.group("code"),
            start_line=start_line,
        )


def iter_book_import_panels(chapter_path: Path) -> Iterable[tuple[int, str, bool]]:
    """Yield import panels with line, raw attributes, and ExampleBlock locality."""
    inside_example_block = False
    for line_number, line in enumerate(
        chapter_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if "<ExampleBlock" in line:
            inside_example_block = True

        match = BOOK_IMPORTS_RE.search(line)
        if match:
            yield line_number, match.group("attrs"), inside_example_block

        if "</ExampleBlock>" in line:
            inside_example_block = False


def iter_book_import_blocks(chapter_path: Path) -> Iterable[tuple[int, str, str]]:
    """Yield full import panel bodies with line and raw attributes."""
    text = chapter_path.read_text(encoding="utf-8")
    for match in BOOK_IMPORT_BLOCK_RE.finditer(text):
        start_line = text.count("\n", 0, match.start()) + 1
        yield start_line, match.group("attrs"), match.group("body")


def book_import_panel_line_ranges(chapter_path: Path) -> list[tuple[int, int]]:
    """Return source-line ranges occupied by collapsed import panels."""
    text = chapter_path.read_text(encoding="utf-8")
    ranges = []
    for match in BOOK_IMPORT_BLOCK_RE.finditer(text):
        start_line = text.count("\n", 0, match.start()) + 1
        end_line = text.count("\n", 0, match.end()) + 1
        ranges.append((start_line, end_line))
    return ranges


def line_in_ranges(line_number: int, ranges: Iterable[tuple[int, int]]) -> bool:
    """Return whether a source line falls inside one of the inclusive ranges."""
    return any(start <= line_number <= end for start, end in ranges)


def iter_example_blocks(chapter_path: Path) -> Iterable[ExampleBlockSource]:
    """Yield public ExampleBlock source regions from an MDX chapter."""
    block_start_line: int | None = None
    block_id: str | None = None
    block_attrs: str | None = None
    for line_number, line in enumerate(
        chapter_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if block_start_line is None:
            match = EXAMPLE_BLOCK_OPEN_RE.search(line)
            if match:
                attrs = match.group("attrs")
                id_match = EXAMPLE_BLOCK_ID_RE.search(attrs)
                assert id_match is not None, (
                    f"{chapter_path.name}:{line_number} opens an ExampleBlock "
                    "without an id."
                )
                block_start_line = line_number
                block_id = id_match.group(1)
                block_attrs = attrs
            continue

        if "</ExampleBlock>" in line:
            assert block_id is not None
            assert block_attrs is not None
            yield ExampleBlockSource(
                chapter_path=chapter_path,
                block_id=block_id,
                attrs=block_attrs,
                start_line=block_start_line,
                end_line=line_number,
            )
            block_start_line = None
            block_id = None
            block_attrs = None

    assert block_start_line is None, (
        f"{chapter_path.name}:{block_start_line} opens an ExampleBlock that "
        "does not close."
    )


def fence_is_inside_block(fence: CodeFence, block: ExampleBlockSource) -> bool:
    """Return whether a code fence begins inside a public ExampleBlock."""
    return block.start_line <= fence.start_line <= block.end_line


def example_block_source(block: ExampleBlockSource) -> str:
    """Return the MDX source occupied by one public ExampleBlock."""
    lines = block.chapter_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[block.start_line - 1 : block.end_line])


def context_before_example_block(block: ExampleBlockSource, line_count: int = 8) -> str:
    """Return nearby prose before an ExampleBlock opens."""
    lines = block.chapter_path.read_text(encoding="utf-8").splitlines()
    start = max(0, block.start_line - line_count - 1)
    end = block.start_line - 1
    return "\n".join(lines[start:end])


def iter_public_manual_text_paths() -> Iterable[Path]:
    """Yield public manual source files covered by prose hygiene checks."""
    root = manual_root()
    yield from sorted(root.glob("*.mdx"))

    src_root = root.parents[1]
    for relative_path in (
        Path("content.config.ts"),
        Path("pages") / "index.astro",
        Path("layouts") / "ManualChapter.astro",
        Path("components") / "ExampleBlock.astro",
        Path("components") / "ManualNav.astro",
    ):
        path = src_root / relative_path
        if path.exists():
            yield path


def line_text_for_match(text: str, match: re.Match[str]) -> tuple[int, str]:
    """Return the one-based line and stripped line text for a regex match."""
    line_number = text.count("\n", 0, match.start()) + 1
    line = text.splitlines()[line_number - 1].strip()
    return line_number, line


def chapter_rule_touchpoints(chapter_path: Path) -> list[str]:
    """Return source-rule touchpoints declared in chapter frontmatter."""
    text = chapter_path.read_text(encoding="utf-8")
    match = FRONTMATTER_RULES_RE.search(text)
    assert match is not None, (
        f"{chapter_path.name} should declare source-rule touchpoints."
    )

    rules = ast.literal_eval(match.group("rules"))
    assert isinstance(rules, list), (
        f"{chapter_path.name} should declare source-rule touchpoints as a list."
    )
    assert all(isinstance(rule, str) and rule.strip() for rule in rules), (
        f"{chapter_path.name} should use non-empty text labels for rule touchpoints."
    )
    return rules


def chapter_title(chapter_path: Path) -> str:
    """Return a chapter title from frontmatter."""
    text = chapter_path.read_text(encoding="utf-8")
    match = re.search(r'^title:\s*"([^"]+)"\s*$', text, re.MULTILINE)
    assert match is not None, f"{chapter_path.name} should declare a title."
    return match.group(1)


def iter_book_examples() -> list[BookExample]:
    """Return executable public examples grouped by chapter and example name."""
    groups: dict[tuple[Path, str], list[CodeFence]] = {}
    for chapter_path in sorted(manual_root().glob("*.mdx")):
        flow_name = CHAPTER_FLOW_EXAMPLES.get(chapter_path.name)
        for fence in iter_code_fences(chapter_path):
            language, flags, options = parse_fence_info(fence.info)
            if language not in {"python", "py"}:
                continue

            if "book-example" in flags:
                name = options.get("name")
                if not name:
                    pytest.fail(
                        f"{chapter_path.name}:{fence.start_line} is marked as a "
                        "book-example but does not declare name=\"...\"."
                    )
            elif flow_name:
                name = flow_name
            else:
                continue

            groups.setdefault((chapter_path, name), []).append(fence)

    return [
        BookExample(chapter_path=chapter_path, name=name, fences=tuple(fences))
        for (chapter_path, name), fences in sorted(
            groups.items(), key=lambda item: (item[0][0].name, item[0][1])
        )
    ]


def reset_engine_globals() -> None:
    """Isolate one public example group from earlier groups in this pytest run."""
    from dnd.core.base_block import BaseBlock
    from dnd.core.base_conditions import BaseCondition
    from dnd.core.base_object import BaseObject
    from dnd.core.events import EventQueue
    from dnd.core.gridmap import GridMap
    from dnd.core.values import BaseValue
    from dnd.entity import Entity
    from dnd.utils import reset_combat_state

    reset_combat_state()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    EventQueue.set_combat_log_callback(None)


def source_has_assertion(source: str) -> bool:
    """Return whether Python source contains at least one assert statement."""
    tree = ast.parse(source)
    return any(isinstance(node, ast.Assert) for node in ast.walk(tree))


def example_body_source(example: BookExample) -> str:
    """Return visible body code for one public example."""
    body_fences = [
        fence.code.rstrip()
        for fence in example.fences
        if parse_fence_info(fence.info)[2].get("part") == "body"
    ]
    return "\n\n".join(body_fences)


def expected_stdout_by_example(chapter_path: Path) -> dict[str, str]:
    """Return page-visible Result transcripts grouped by public example name."""
    expected: dict[str, list[str]] = {}
    for block in iter_example_blocks(chapter_path):
        block_source = example_block_source(block)
        for match in FENCE_RE.finditer(block_source):
            language, flags, options = parse_fence_info(match.group("info").strip())
            if language not in {"python", "py"} or "book-example" not in flags:
                continue
            if options.get("part") != "body":
                continue

            result_match = RESULT_AFTER_BODY_RE.match(block_source, match.end())
            if result_match is None:
                continue
            expected.setdefault(options["name"], []).append(
                result_match.group("output").rstrip("\n")
            )

    return {name: "\n".join(outputs) for name, outputs in expected.items()}


def expected_stdout_for_example(example: BookExample) -> str:
    """Return the exact Result transcript printed by one public example."""
    expected_by_name = expected_stdout_by_example(example.chapter_path)
    assert example.name in expected_by_name, (
        f"{example.id} has no visible Result transcript to verify. "
        f"Fences: {example.locations}"
    )
    return expected_by_name[example.name]


def import_panel_intro_text(body: str) -> str:
    """Return prose between the import-panel summary and first code fence."""
    _, _, after_summary = body.partition("</summary>")
    intro = re.split(r"```(?:python|py)\s+book-example", after_summary, maxsplit=1)[0]
    return re.sub(r"<[^>]+>", "", intro)


def definition_names_in_import_panel(body: str) -> list[str]:
    """Return local function and class names defined in a Code setup panel."""
    code_parts = []
    for match in FENCE_RE.finditer(body):
        language, flags, _ = parse_fence_info(match.group("info").strip())
        if language in {"python", "py"} and "book-example" in flags:
            code_parts.append(match.group("code"))
    source = "\n".join(code_parts)
    return re.findall(r"^(?:def|class)\s+(\w+)", source, flags=re.MULTILINE)


def imported_runtime_names_by_example(chapter_path: Path) -> dict[str, set[str]]:
    """Return dnd/server/ai names imported by each public example."""
    prefixes = ("dnd.", "server.", "ai.")
    imported: dict[str, set[str]] = {}
    for fence in iter_code_fences(chapter_path):
        language, flags, options = parse_fence_info(fence.info)
        if language not in {"python", "py"} or "book-example" not in flags:
            continue

        example_name = options.get("name")
        if not example_name:
            continue

        tree = ast.parse(fence.code)
        names = imported.setdefault(example_name, set())
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(prefixes):
                    for alias in node.names:
                        if alias.name != "*":
                            names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(prefixes):
                        names.add(alias.asname or alias.name.split(".")[0])

    return imported


def imported_runtime_sources_by_chapter(chapter_path: Path) -> dict[str, set[str]]:
    """Return dnd/server/ai names and source modules imported by a chapter."""
    prefixes = ("dnd.", "server.", "ai.")
    imported: dict[str, set[str]] = {}
    for fence in iter_code_fences(chapter_path):
        language, flags, _ = parse_fence_info(fence.info)
        if language not in {"python", "py"} or "book-example" not in flags:
            continue

        tree = ast.parse(fence.code)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(prefixes):
                    for alias in node.names:
                        if alias.name != "*":
                            imported.setdefault(alias.asname or alias.name, set()).add(
                                node.module
                            )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(prefixes):
                        imported.setdefault(
                            alias.asname or alias.name.split(".")[0],
                            set(),
                        ).add(alias.name)

    return imported


def code_surface_section(chapter_path: Path) -> str:
    """Return the bounded source-table section for a technical chapter."""
    text = chapter_path.read_text(encoding="utf-8")
    section_match = re.search(
        r"## Code Surfaces In This Chapter\n(?P<section>.*?)(?=\n## )",
        text,
        re.DOTALL,
    )
    assert section_match, f"{chapter_path.name} has no bounded code-surface section."
    return section_match.group("section")


def code_surface_table_rows(chapter_path: Path) -> list[str]:
    """Return Markdown table rows from a chapter's source-table section."""
    return [
        line
        for line in code_surface_section(chapter_path).splitlines()
        if line.startswith("|")
    ]


def defined_in_chapter_symbols(chapter_path: Path) -> set[str]:
    """Return symbols listed as defined inside the public chapter."""
    symbols: set[str] = set()
    for row in code_surface_table_rows(chapter_path):
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[1] != "Defined in this chapter":
            continue
        symbols.update(re.findall(r"`([A-Za-z_]\w*)`", cells[0]))
    return symbols


def chapter_map_section(chapter_path: Path) -> str:
    """Return the bounded Chapter Map section for a technical chapter."""
    text = chapter_path.read_text(encoding="utf-8")
    section_match = re.search(
        r"## Chapter Map\n(?P<section>.*?)(?=\n## )",
        text,
        re.DOTALL,
    )
    assert section_match, f"{chapter_path.name} has no bounded Chapter Map section."
    return section_match.group("section")


def chapter_map_table_rows(chapter_path: Path) -> list[str]:
    """Return Markdown table rows from a chapter's Chapter Map section."""
    return [
        line
        for line in chapter_map_section(chapter_path).splitlines()
        if line.startswith("|")
    ]


def local_definition_names_by_example(chapter_path: Path) -> dict[str, set[str]]:
    """Return local function/class names defined inside import panels."""
    names_by_example: dict[str, set[str]] = {}
    for _, _, body in iter_book_import_blocks(chapter_path):
        for match in FENCE_RE.finditer(body):
            language, flags, options = parse_fence_info(match.group("info").strip())
            example_name = options.get("name")
            if (
                language not in {"python", "py"}
                or "book-example" not in flags
                or not example_name
            ):
                continue

            tree = ast.parse(match.group("code"))
            names_by_example.setdefault(example_name, set()).update(
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef | ast.ClassDef)
            )

    return names_by_example


def local_definition_names_in_import_panels(chapter_path: Path) -> set[str]:
    """Return all local function/class names declared in import panels."""
    names: set[str] = set()
    for _, _, body in iter_book_import_blocks(chapter_path):
        for match in FENCE_RE.finditer(body):
            language, flags, _ = parse_fence_info(match.group("info").strip())
            if language not in {"python", "py"} or "book-example" not in flags:
                continue

            tree = ast.parse(match.group("code"))
            names.update(
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef | ast.ClassDef)
            )
    return names


def import_panel_intro_text_by_example(chapter_path: Path) -> dict[str, str]:
    """Return prose introductions for each example's import panels."""
    intro_by_example: dict[str, list[str]] = {}
    for _, _, body in iter_book_import_blocks(chapter_path):
        intro = import_panel_intro_text(body)
        for match in FENCE_RE.finditer(body):
            language, flags, options = parse_fence_info(match.group("info").strip())
            example_name = options.get("name")
            if (
                language in {"python", "py"}
                and "book-example" in flags
                and example_name
            ):
                intro_by_example.setdefault(example_name, []).append(intro)

    return {
        example_name: "\n".join(intro_chunks)
        for example_name, intro_chunks in intro_by_example.items()
    }


def visible_name_uses_by_example(chapter_path: Path) -> dict[str, set[str]]:
    """Return Python names loaded by visible example code outside import panels."""
    names_by_example: dict[str, set[str]] = {}
    import_panel_ranges = book_import_panel_line_ranges(chapter_path)
    for fence in iter_code_fences(chapter_path):
        language, flags, options = parse_fence_info(fence.info)
        example_name = options.get("name")
        if (
            language not in {"python", "py"}
            or "book-example" not in flags
            or not example_name
        ):
            continue
        if options.get("part") == "imports":
            continue
        if line_in_ranges(fence.start_line, import_panel_ranges):
            continue

        tree = ast.parse(fence.code)
        names_by_example.setdefault(example_name, set()).update(
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )

    return names_by_example


def test_migrated_chapters_have_expected_book_examples() -> None:
    """Converted chapters expose the exact public examples expected by the book."""
    found_by_chapter: dict[str, set[str]] = {
        chapter_name: set()
        for chapter_name in MIGRATED_CHAPTERS
    }
    for example in iter_book_examples():
        chapter_name = example.chapter_path.name
        if chapter_name in found_by_chapter:
            found_by_chapter[chapter_name].add(example.name)

    assert found_by_chapter == MIGRATED_CHAPTERS


def test_parity_matrix_tracks_public_webbook_examples() -> None:
    """The internal parity matrix names every public MDX example."""
    parity_path = REPO_ROOT / "engine_book" / "parity_matrix.md"
    text = parity_path.read_text(encoding="utf-8")

    assert "## Public Webbook Exact-Snippet Parity" in text
    assert "tests/book_examples/test_public_mdx_snippets.py" in text

    missing: list[str] = []
    for chapter_name, example_names in MIGRATED_CHAPTERS.items():
        if f"`{chapter_name}`" not in text:
            missing.append(chapter_name)
        for example_name in sorted(example_names):
            if f"`{example_name}`" not in text:
                missing.append(f"{chapter_name}::{example_name}")

    assert not missing, (
        "engine_book/parity_matrix.md is missing public webbook parity rows: "
        f"{missing}"
    )


def test_migrated_chapters_track_all_python_fences() -> None:
    """Every public Python fence is enrolled in exact snippet execution."""
    for chapter_name in MIGRATED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        assert chapter_path.exists(), f"Missing migrated chapter: {chapter_name}"
        flow_name = CHAPTER_FLOW_EXAMPLES.get(chapter_name)

        for fence in iter_code_fences(chapter_path):
            language, flags, _ = parse_fence_info(fence.info)
            if language in {"python", "py"}:
                assert "book-example" in flags or flow_name is not None, (
                    f"{chapter_name}:{fence.start_line} is a Python fence but "
                    "is not enrolled in exact book-example execution."
                )


def test_book_import_panels_are_local_collapsed_panels() -> None:
    """Code setup panels stay beside examples; first-run teaching panels may open."""
    for chapter_name in MIGRATED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        first_panel_line = next(
            (panel_line for panel_line, _, _ in iter_book_import_panels(chapter_path)),
            None,
        )
        for line, attrs, inside_example_block in iter_book_import_panels(chapter_path):
            assert inside_example_block, (
                f"{chapter_name}:{line} has a book-imports panel outside an "
                "ExampleBlock."
            )
            allow_open = (
                chapter_name in FIRST_RUN_OPEN_PANEL_CHAPTERS
                and line == first_panel_line
            )
            if allow_open:
                continue
            assert "open" not in attrs.split(), (
                f"{chapter_name}:{line} has a book-imports panel that is open "
                "by default."
            )


def test_book_import_panels_contain_executed_python() -> None:
    """Collapsed Code setup: imports and scene panels must still be part of snippet execution."""
    for chapter_name in MIGRATED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for line, _, body in iter_book_import_blocks(chapter_path):
            assert "<summary>Code setup: imports and scene</summary>" in body, (
                f"{chapter_name}:{line} should label the collapsed import "
                "panel as 'Code setup: imports and scene'."
            )
            assert "```python book-example" in body or "```py book-example" in body, (
                f"{chapter_name}:{line} has a book-imports panel whose code is "
                "not marked for exact book-example execution."
            )


def test_book_examples_begin_with_their_imports_and_scene_panel() -> None:
    """Each executed public example starts with its local Code setup: imports and scene code."""
    for example in iter_book_examples():
        panel_ranges = book_import_panel_line_ranges(example.chapter_path)
        first_fence = example.fences[0]

        assert line_in_ranges(first_fence.start_line, panel_ranges), (
            f"{example.id} begins at {example.chapter_path.name}:"
            f"{first_fence.start_line}, outside its Code setup: imports and scene panel."
        )
        assert re.search(r"^(?:from|import|class|def)\s+", first_fence.code, re.M), (
            f"{example.id} should begin with imports, local definitions, or both."
        )


def test_book_example_fences_declare_import_or_body_part() -> None:
    """Every executed Python fence declares its role in the public snippet."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        panel_ranges = book_import_panel_line_ranges(chapter_path)

        for fence in iter_code_fences(chapter_path):
            language, flags, options = parse_fence_info(fence.info)
            if language not in {"python", "py"} or "book-example" not in flags:
                continue

            expected_part = (
                "imports"
                if line_in_ranges(fence.start_line, panel_ranges)
                else "body"
            )
            assert options.get("part") == expected_part, (
                f"{chapter_name}:{fence.start_line} should declare "
                f'part="{expected_part}" so the exact snippet order is explicit.'
            )


def test_book_examples_join_imports_and_body_in_page_order() -> None:
    """One public example is its import-scene code followed by body code."""
    for example in iter_book_examples():
        parts = [
            parse_fence_info(fence.info)[2]["part"]
            for fence in example.fences
        ]

        assert parts[0] == "imports", (
            f"{example.id} should begin with a Code setup: imports and scene fence."
        )
        assert "body" in parts[1:], (
            f"{example.id} should include visible body code after imports."
        )

        seen_body = False
        for part in parts:
            if part == "body":
                seen_body = True
            if seen_body:
                assert part == "body", (
                    f"{example.id} should keep import-scene code before body code."
                )


def test_book_examples_print_reader_visible_results() -> None:
    """Public tutorial bodies produce transcripts readers can compare."""
    for example in iter_book_examples():
        body_source = example_body_source(example)
        expected_stdout = expected_stdout_for_example(example)
        assert "print(" in body_source, (
            f"{example.id} should print the behavior it teaches. "
            f"Fences: {example.locations}"
        )
        assert expected_stdout.strip(), (
            f"{example.id} should publish a non-empty Result transcript. "
            f"Fences: {example.locations}"
        )


def test_assert_free_chapters_keep_verification_out_of_reader_code() -> None:
    """Polished chapters keep pytest-style verification out of public code."""
    for chapter_name in ASSERT_FREE_BODY_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for example in iter_book_examples():
            if example.chapter_path != chapter_path:
                continue
            assert not source_has_assertion(example.source), (
                f"{example.id} should verify through Result transcript parity, "
                f"not public assert statements. Fences: {example.locations}"
            )


def test_audited_import_panels_explain_their_setup_before_code() -> None:
    """Finished foundation chapters explain panel imports before showing code."""
    for chapter_name in PROSE_AUDITED_IMPORT_PANEL_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for line, _, body in iter_book_import_blocks(chapter_path):
            words = re.findall(r"\w+", import_panel_intro_text(body))
            assert len(words) >= 12, (
                f"{chapter_name}:{line} should explain the Code setup: imports and scene block "
                "before the first executable code fence."
            )


def test_definition_heavy_import_panels_get_fuller_explanations() -> None:
    """Panels with many local definitions explain the tutorial scene first."""
    for chapter_name in PROSE_AUDITED_IMPORT_PANEL_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for line, _, body in iter_book_import_blocks(chapter_path):
            definition_names = definition_names_in_import_panel(body)
            if len(definition_names) < 5:
                continue

            words = re.findall(r"\w+", import_panel_intro_text(body))
            assert len(words) >= 60, (
                f"{chapter_name}:{line} defines {len(definition_names)} local "
                "functions/classes and should explain that setup before code: "
                f"{', '.join(definition_names)}"
            )


def test_import_panels_name_their_local_definitions() -> None:
    """Each local class/function in a panel is explained before the code fence."""
    for chapter_name in PROSE_AUDITED_IMPORT_PANEL_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for line, _, body in iter_book_import_blocks(chapter_path):
            intro = import_panel_intro_text(body)
            missing = sorted(
                name
                for name in set(definition_names_in_import_panel(body))
                if name not in intro
            )

            assert not missing, (
                f"{chapter_name}:{line} defines local tutorial code without "
                f"naming it in the Code setup: imports and scene prose: {missing}"
            )


def test_public_reset_helpers_use_typed_dimensions() -> None:
    """Reset helpers with dimensions keep tutorial signatures explicit."""
    bare_dimension_defaults: list[str] = []
    pattern = re.compile(r"def\s+reset_[^(]+\([^)]*(?:width|height)\s*=")

    for chapter_path in sorted(manual_root().glob("*.mdx")):
        text = chapter_path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            line_number, line = line_text_for_match(text, match)
            bare_dimension_defaults.append(
                f"{chapter_path.name}:{line_number}: {line.strip()}"
            )

    assert not bare_dimension_defaults, (
        "Public reset helpers with width/height defaults should use explicit "
        f"parameter and return annotations: {bare_dimension_defaults}"
    )


def test_all_import_panel_chapters_are_prose_audited() -> None:
    """Every chapter with Code setup: imports and scene panels participates in prose auditing."""
    chapters_with_import_panels = {
        chapter_path.name
        for chapter_path in manual_root().glob("*.mdx")
        if list(iter_book_import_blocks(chapter_path))
    }

    assert chapters_with_import_panels == PROSE_AUDITED_IMPORT_PANEL_CHAPTERS


def test_public_manual_avoids_internal_meta_language() -> None:
    """Public manual files avoid test, private-note, and implementation leaks."""
    for path in iter_public_manual_text_paths():
        text = path.read_text(encoding="utf-8")
        for label, pattern in PUBLIC_MANUAL_FORBIDDEN_PATTERNS:
            match = pattern.search(text)
            assert match is None, (
                f"{path}:{line_text_for_match(text, match)[0]} contains "
                f"{label}: {line_text_for_match(text, match)[1]!r}"
            )


def test_defined_in_chapter_rows_use_reader_facing_descriptions() -> None:
    """Chapter-defined source rows describe the symbol without scaffolding prose."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        chapter_path = manual_root() / chapter_name
        stale_rows = [
            row
            for row in code_surface_table_rows(chapter_path)
            if "| Defined in this chapter | Local " in row
        ]

        assert not stale_rows, (
            f"{chapter_path.name} has source rows that still sound like local "
            f"scaffolding: {stale_rows}"
        )


def test_public_chapters_have_source_rule_touchpoints() -> None:
    """Each chapter declares the D&D-facing rule ideas it is teaching."""
    for chapter_path in sorted(manual_root().glob("*.mdx")):
        assert chapter_rule_touchpoints(chapter_path), (
            f"{chapter_path.name} should have at least one source-rule touchpoint."
        )


def test_orientation_explains_runnable_example_sequence() -> None:
    """The opening chapter tells readers how Code setup: imports and scene and code blocks join."""
    text = (manual_root() / "00-neurodragon-dev-manual.mdx").read_text(
        encoding="utf-8"
    )

    assert "## One Videogame Ruleset" in text
    assert (
        "The local SRD markdown is the source-reference corpus for Dungeons & Dragons"
        in text
    )
    assert "source-rule comparison" in text
    assert re.search(
        r"the\s+public\s+manual\s+teaches\s+the\s+chosen\s+behavior\s+as\s+engine\s+truth",
        text,
    )
    assert "| Relationship | Meaning in this manual |" in text
    assert "| Source vocabulary |" in text
    assert "| SRD-shaped behavior |" in text
    assert "| Engine adaptation |" in text
    assert "| Product extension |" in text
    assert "The documented action is the chosen videogame/BG3-style shove" in text
    assert "Forced movement and voluntary movement stay distinct" in text
    assert "separate melee and ranged sets" in text
    assert "Advantage and disadvantage are represented through the engine value ledger" in text
    assert "Great Weapon Fighting" in text
    assert "## How This Manual Teaches Code" in text
    assert (
        "Each substantial example is one runnable program presented in page order."
        in text
    )
    assert "**Code setup: imports and scene**" in text
    assert (
        "Read the disclosure and body together as one complete snippet."
    ) in text
    assert "The disclosure stays collapsed so the main lesson remains readable" in text
    assert (
        "The chapter source table and the Code setup: imports and scene panel work together"
        in text
    )
    assert "Later chapters sometimes import named scene constructors" in text
    assert "`create_gatehouse_scenario()`" in text
    assert "`create_stream_scene()`" in text
    assert "`create_agent_scene()`" in text
    assert "Those constructors are public tutorial scene surfaces." in text
    assert "construct the live engine objects, expose the setup function" in text
    assert "run actions, inspect state, and observe outcomes" in text
    assert "## The Build Path" in text
    assert "| Developer move | Manual path | Outcome |" in text
    assert "Name live game objects." in text
    assert "Turn D&D timing into runtime behavior." in text
    assert "Offer playable choices." in text
    assert "Author game content." in text
    assert "Assemble a game mode." in text
    assert "Automate tactical play." in text
    assert "## What Each Chapter Gives You" in text
    assert "| Chapter piece | What it gives you |" in text
    assert "Play meaning" in text
    assert "Runtime state" in text
    assert "D&D bridge" in text
    assert "Code surfaces" in text
    assert "Runnable tutorial example" in text
    assert "Next layer" in text
    assert "That rhythm is the manual's teaching contract." in text
    assert re.search(r"First\s+understand\s+the\s+game\s+moment\.", text)
    assert re.search(r"Then\s+identify\s+the\s+runtime\s+state\s+that\s+owns\s+it\.", text)
    assert re.search(r"Then\s+read\s+the\s+code\s+surface\s+and\s+run\s+the\s+tutorial\s+scene\.", text)


def test_high_risk_rule_policy_chapters_explain_srd_relationship() -> None:
    """High-risk policy chapters teach source-rule relationships publicly."""
    expectations = {
        "03-values-and-modifiers.mdx": [
            "The local SRD ability rules provide the familiar shape",
            "Advantage and disadvantage are also stored as signed value state",
            "rule sources inspectable",
        ],
        "04-dice-rolls.mdx": [
            "The local SRD dice rules give the chapter its baseline",
            "Great Weapon Fighting follows the local fighter class source",
            "the chosen videogame rule",
        ],
        "08-world-model-and-movement.mdx": [
            "The local SRD movement rules describe speed",
            "Voluntary movement uses step-movement events",
            "Forced movement uses `FORCED_MOVEMENT`",
            "opportunity attacks for voluntary movement",
        ],
        "10-combat-resolution.mdx": [
            "The local SRD combat rules provide the chapter's core vocabulary",
            "The chosen Shove rule is explicit engine truth.",
            "bonus-action combat choice with passive target resistance",
            "the single public shove surface for this ruleset",
        ],
        "11-equipment-inventory-and-items.mdx": [
            "The local SRD equipment files provide the familiar gear vocabulary",
            "Loadouts are a deliberate videogame adaptation.",
            "Two-handed melee weapons displace conflicting melee off-hand gear",
            "Ranged gear remains a separate set",
        ],
        "17-encounters-turns-and-controllers.mdx": [
            "The local SRD combat rules describe initiative",
            "Encounter ending is the videogame policy point.",
            "`check_deaths()` updates combatant death state",
            "faction survival ends the running encounter",
        ],
    }

    for chapter_name, required_phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        normalized_text = text.replace("\n", " ")
        source_index = text.index("## Source Rule Relationship")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < source_index < map_index < surfaces_index
        else:
            assert source_index < map_index < surfaces_index < first_example_index
        for phrase in required_phrases:
            assert phrase in normalized_text


def test_core_rule_chapters_explain_srd_relationship() -> None:
    """Core rule chapters keep their SRD relationship visible before examples."""
    expectations = {
        "02-entity-anatomy.mdx": [
            "The local SRD creature rules give this chapter its shape",
            "six abilities, hit points, Armor Class",
            "`Entity` is that addressable creature surface",
        ],
        "05-event-lifecycle.mdx": [
            "The local SRD describes procedures such as making attacks",
            "represents those procedures as event lineages",
            "Events are source vocabulary for the videogame engine",
        ],
        "06-reactions-to-events.mdx": [
            "The local SRD reaction rules describe triggered responses",
            "Opportunity attacks and reaction spells",
            "Completion is the observation boundary",
        ],
        "07-conditions-and-cleanup.mdx": [
            "The local SRD condition rules provide names and play effects",
            "Spellcasting and combat rules also define duration",
            "A condition owns the modifiers, handlers, subconditions",
        ],
        "09-action-discovery-and-costs.mdx": [
            "The local SRD combat rules describe actions, bonus actions, reactions",
            "discoverable action templates with costs",
            "The videogame adaptation is the command menu",
        ],
        "12-perception-light-stealth-and-invisibility.mdx": [
            "The local SRD perception and adventuring rules describe light",
            "observer-local state",
            "per-observer knowledge",
        ],
        "13-spellcasting-core.mdx": [
            "The local SRD spellcasting rules define spell slots",
            "spell actions, spellcasting values, slot resources",
            "A spell is a selectable runtime action",
        ],
        "14-spell-families-and-implemented-spells.mdx": [
            "The local SRD spell files provide named spell behavior",
            "groups those spell texts into runtime families",
            "Spell-family coverage is SRD-shaped at the family level",
        ],
        "15-class-features-factories-and-feats.mdx": [
            "The local SRD class files provide feature names",
            "Feat files provide optional character rules",
            "The engine adaptation is the playable recipe",
        ],
        "16-monsters-and-preset-actors.mdx": [
            "The local SRD monster files provide stat-block vocabulary",
            "return ordinary `Entity` actors",
            "Base monsters can be SRD-shaped while preset actors are product content",
        ],
    }

    for chapter_name, required_phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        normalized_text = text.replace("\n", " ")
        source_index = text.index("## Source Rule Relationship")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < source_index < map_index < surfaces_index
        else:
            assert source_index < map_index < surfaces_index < first_example_index
        for phrase in required_phrases:
            assert phrase in normalized_text


def test_product_extension_chapters_explain_srd_relationship() -> None:
    """Product chapters describe how game systems extend SRD-shaped play."""
    expectations = {
        "18-sessions-apis-and-client-payloads.mdx": [
            "The local SRD combat and adventuring rules give this chapter its game material",
            "The product extension is the session and API contract",
            "the engine remains authoritative for action legality and results",
        ],
        "19-map-editor-and-scenario-authoring.mdx": [
            "The local SRD adventuring and combat rules describe tactical spaces",
            "The product extension is the MapEditor boundary",
            "Map authoring owns entity-free spaces",
        ],
        "20-content-extension-basics.mdx": [
            "The local SRD gives repeatable content forms",
            "The product extension is content-pack authoring",
            "composing the existing value, event, condition, item, action, and perception systems",
        ],
        "21-spell-and-feature-extensions.mdx": [
            "The local SRD spell and class rules show features granting magic",
            "The product extension is the authored spell-feature pack",
            "install a lasting effect through normal engine ownership",
        ],
        "22-playable-scenario-packages.mdx": [
            "The local SRD combat and adventuring rules give scenario packages their play ingredients",
            "The product extension is the playable scenario boundary",
            "faction-survival ending into one reusable game mode",
        ],
        "23-standard-arena-game-modes.mdx": [
            "The local SRD combat rules provide the arena's underlying play loop",
            "The product extension is the standard arena package",
            "ready-to-run videogame experience",
        ],
        "24-built-in-controllers-and-automated-turns.mdx": [
            "The local SRD assumes participants choose actions",
            "The product extension is automated turn ownership",
            "automation remains a participant in the ruleset",
        ],
        "25-live-replication-streams.mdx": [
            "The local SRD combat structure creates a shared table record",
            "The product extension is live replication",
            "the engine timeline as the source of truth",
        ],
        "26-agent-tactical-interface.mdx": [
            "The local SRD turn structure asks practical tactical questions",
            "The product extension is the tactical agent interface",
            "route the selected choice back through normal engine execution",
        ],
        "27-agent-decision-patterns.mdx": [
            "The local SRD combat loop creates recognizable tactical priorities",
            "The product extension is the decision-pattern layer",
            "choose the same engine action rows a player or controller can choose",
        ],
    }

    for chapter_name, required_phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        normalized_text = text.replace("\n", " ")
        source_index = text.index("## Source Rule Relationship")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        assert source_index < map_index < surfaces_index < first_example_index
        for phrase in required_phrases:
            assert phrase in normalized_text


def test_identity_chapter_frontloads_dnd_reference_translation() -> None:
    """Chapter 01 explains identity before the first runnable example."""
    text = (manual_root() / "01-runtime-identity-and-registries.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    contract_index = text.index("## The Smallest Runtime Contract")
    addressing_index = text.index("## Identity As Runtime Addressing")
    translation_index = text.index("## How D&D References Become Runtime Identity")
    source_index = text.index("## Source Rule Relationship")
    map_index = text.index("## Chapter Map")
    authoring_index = text.index("## Identity Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_run_index = text.index("## First Run: Create And Inspect Identity")
    first_example_index = text.index('<ExampleBlock id="EB-01-000"')
    focused_object_index = text.index("## A Focused Runtime Object")

    assert play_index < contract_index < addressing_index < translation_index
    assert translation_index < source_index < map_index < authoring_index
    assert authoring_index < surfaces_index < first_run_index
    assert first_run_index < first_example_index < focused_object_index
    assert "Start with one object." in text
    assert '<details className="book-imports" open>' in text
    assert "identity-first-run" in text
    assert 'print("\\n".join(inspection_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "created object: door marker" in text
    assert "uuid type: UUID" in text
    assert "lookup result: same live object" in text
    assert "registry entries: 1" in text
    assert "That is the first runtime promise" in text
    assert "The smallest identity-bearing object in NeuroDragon answers six questions." in text
    assert "| Field or behavior | Meaning |" in text
    assert "`uuid`" in text
    assert "`name`" in text
    assert "Registry publication" in text
    assert "Lookup family" in text
    assert "root object, value, block, entity" in text
    assert "A tabletop rule can speak casually" in text
    assert "The acting creature." in text
    assert "The target creature." in text
    assert "`source_entity_uuid`" in text
    assert "`target_entity_uuid`" in text
    assert re.search(r"same\s+live\s+objects\s+from\s+declaration\s+through\s+effect", text)
    assert "one root object, three registry families" in text
    assert "The local SRD describes creatures, objects, effects, conditions, turns, and combat outcomes" in normalized_text
    assert "Runtime identity is the engine vocabulary" in normalized_text
    assert "UUIDs, typed registries, ownership fields, and lookup APIs" in normalized_text
    assert "The examples build one identity thread in six moves:" in text
    assert "| Example move | What the reader learns |" in text
    assert "First runtime object" in text
    assert "Root object lookup" in text
    assert "Publication control" in text
    assert "Registry-family choice" in text
    assert "Actor position identity" in text
    assert "Value subclass contracts" in text
    assert "Author runtime identity by making every live relationship addressable before rules mutate state." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Name each live object." in text
    assert "Publish state when it joins play." in text
    assert "Choose the lookup family." in text
    assert "Preserve rule ownership." in text
    assert "Preserve rule targets." in text
    assert "Connect actors to the board." in text
    assert "State lookup behavior explicitly." in text
    assert "create the object with stable identity, publish it when it becomes live" in normalized_text
    assert "Concrete marker object used to demonstrate registry behavior." in text
    assert "Small concrete object used to demonstrate registry behavior." not in text


def test_identity_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 01 examples print transcripts instead of only asserting state."""
    text = (manual_root() / "01-runtime-identity-and-registries.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert 'print("\\n".join(inspection_lines))' in text
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(creation_lines))' in text
    assert 'print("\\n".join(movement_lines))' in text
    assert "marker lookup: same live object" in text
    assert "wrong-family lookup: rejected TutorialToken UUID" in text
    assert "before publish: found=False, use_register=False" in text
    assert "after publish: found=True, use_register=True" in text
    assert "value family lookup: tutorial value" in text
    assert "registry sizes: values=1, blocks=1, root=0" in text
    assert "created actor: Hero at (2, 3)" in text
    assert "moved actor: Hero to (4, 5)" in text
    assert "base lookup names: ['static', 'contextual', 'modifiable']" in text
    assert (
        "missing lookup: base=True, contextual=True, modifiable=True, "
        "static=raises ValueError"
    ) in text


def test_entity_chapter_frontloads_creature_translation() -> None:
    """Chapter 02 explains the actor shape before the first runnable example."""
    text = (manual_root() / "02-entity-anatomy.mdx").read_text(encoding="utf-8")
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    ruling_index = text.index("## Ruling Role")
    entity_shape_index = text.index("## What An Entity Is")
    product_loop_index = text.index("## Actor State In The Game Loop")
    translation_index = text.index("## How A D&D Creature Becomes An Entity")
    source_index = text.index("## Source Rule Relationship")
    map_index = text.index("## Chapter Map")
    authoring_index = text.index("## Entity Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_run_index = text.index("## First Run: Create And Inspect An Actor")
    first_example_index = text.index('<ExampleBlock id="EB-02-000"')
    create_hero_index = text.index("## Create A Tutorial Hero")

    assert play_index < ruling_index < entity_shape_index < product_loop_index
    assert product_loop_index < translation_index < source_index < map_index
    assert map_index < authoring_index < surfaces_index < first_run_index
    assert first_run_index < first_example_index < create_hero_index
    assert "`Entity` is the first actor-shaped object stored under that identity" in text
    assert (
        "When later code receives an actor UUID, this is the object graph it opens"
        in text
    )
    assert "Start with one actor." in text
    assert '<details className="book-imports" open>' in text
    assert "entity-first-run" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert "created actor: Aria" in text
    assert "uuid matches source: yes" in text
    assert "hit points: 24" in text
    assert "direct blocks: 10" in text
    assert "map lookup: (1, 2)" in text
    assert "That is the first actor promise" in text
    assert "The entity is also the shape most product systems gather around." in text
    assert "| Product question | Entity-owned answer |" in text
    assert "What can the player do now?" in text
    assert "What can a designer author?" in text
    assert re.search(r"D&D\s+gives\s+the\s+actor\s+vocabulary", text)
    assert "A creature in D&D is a playable idea" in text
    assert "Six ability scores." in text
    assert "Skill and save training." in text
    assert "`Entity.get_hp()` combines it with Constitution" in text
    assert re.search(r"this\s+one\s+entity-owned\s+shape", text)
    assert "The examples build one actor thread in five moves:" in text
    assert "| Example move | Entity surface learned |" in text
    assert "First actor readout." in text
    assert "Create Aria from config." in text
    assert "Read the character sheet." in text
    assert "Inspect combat and presentation state." in text
    assert "Walk the actor tree." in text
    assert "Author an entity by turning one creature concept into an actor-owned state tree." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Choose actor identity and metadata." in text
    assert "Configure ability scores." in text
    assert "Configure training." in text
    assert "Configure durability." in text
    assert "Configure turn resources." in text
    assert "Configure magic and presentation." in text
    assert "Keep the actor inspectable." in text
    assert "define the creature as one entity configuration, place each gameplay region in its owned block" in normalized_text
    assert (
        "That means the Chapter 01 identity thread becomes a playable actor"
        in text
    )
    assert "This Code setup: imports and scene block imports" not in text


def test_entity_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 02 examples print the actor anatomy instead of only asserting."""
    text = (manual_root() / "02-entity-anatomy.mdx").read_text(encoding="utf-8")

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 13
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(actor_lines))' in text
    assert 'print("\\n".join(block_lines))' in text
    assert 'print("\\n".join(ability_lines))' in text
    assert 'print("\\n".join(skill_lines))' in text
    assert 'print("\\n".join(save_lines))' in text
    assert 'print("\\n".join(health_lines))' in text
    assert 'print("\\n".join(resource_lines))' in text
    assert 'print("\\n".join(named_resource_lines))' in text
    assert 'print("\\n".join(spellcasting_lines))' in text
    assert 'print("\\n".join(appearance_lines))' in text
    assert 'print("\\n".join(tree_lookup_lines))' in text
    assert 'print("\\n".join(deep_value_lines))' in text
    assert "actor shell: name=Aria, faction=heroes, weight=180" in text
    assert "direct block count: 10" in text
    assert "required blocks present: True" in text
    assert "strength: score=16, modifier=3" in text
    assert "stealth: ability=dexterity, proficient=True, expert=True" in text
    assert "dexterity save: ability=dexterity, proficient=True" in text
    assert "hit dice count: 2" in text
    assert "level 1 spell slots: 2" in text
    assert "Second Wind after short rest: 1" in text
    assert "spellcasting ability: wisdom" in text
    assert "body: NakedBody2" in text
    assert "block lookup: strength" in text
    assert "deep value count: 80" in text
    assert (
        "sample values: ['Actions', 'Spell Attack Bonus', "
        "'strength Ability Score']"
    ) in text


def test_runtime_foundation_chapters_explain_their_ruling_role() -> None:
    """Runtime foundation chapters each name the ruling-loop question they answer."""
    expectations = {
        "01-runtime-identity-and-registries.mdx": [
            "Runtime identity answers the reference question in the ruling loop.",
            "| Ruling question | Identity answer |",
            "That makes identity the runtime's answer",
        ],
        "02-entity-anatomy.mdx": [
            "The entity answers the actor question in the ruling loop.",
            "| Ruling question | Entity answer |",
            "That makes the entity the actor packet",
        ],
        "03-values-and-modifiers.mdx": [
            "Values answer the current-number question in the ruling loop.",
            "| Ruling question | Value answer |",
            "This makes a value more than a number.",
        ],
        "04-dice-rolls.mdx": [
            "Dice answer the uncertainty question in the ruling loop.",
            "| Ruling question | Dice answer |",
            "This gives the software dungeon master a concrete roll record.",
        ],
        "05-event-lifecycle.mdx": [
            "Events answer the timeline question in the ruling loop.",
            "| Ruling question | Event answer |",
            "That makes events the runtime memory of a ruling.",
        ],
    }
    for chapter_name, phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        ruling_index = text.index("## Ruling Role")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < ruling_index < map_index < surfaces_index
        else:
            assert ruling_index < map_index < surfaces_index < first_example_index
        for phrase in phrases:
            assert phrase in text


def test_values_chapter_frontloads_product_math_bridge() -> None:
    """Chapter 03 explains values as player, designer, client, and agent math."""
    text = (manual_root() / "03-values-and-modifiers.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    ledger_index = text.index("## Values As Rule Ledgers")
    product_loop_index = text.index("## Value State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How A D&D Rule Becomes A Value")
    source_index = text.index("## Source Rule Relationship")
    contract_index = text.index("## The Value And Modifier Contract")
    map_index = text.index("## Chapter Map")
    authoring_index = text.index("## Value Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_run_index = text.index("## First Run: Create And Inspect A Value")
    first_example_index = text.index("<ExampleBlock")
    channels_index = text.index("## Channels: Self, Target, And Context")
    placement_index = text.index("## Modifier Placement Guide")
    score_index = text.index("## Score And Normalized Score")

    assert play_index < ledger_index < product_loop_index
    assert product_loop_index < ruling_index < bridge_index < source_index
    assert source_index < contract_index < map_index < authoring_index
    assert authoring_index < surfaces_index < first_run_index
    assert first_run_index < first_example_index < channels_index
    assert channels_index < placement_index < score_index
    assert '<details className="book-imports" open>' in text
    assert "value: Armor Class" in text
    assert "rule modifiers: Shield +2, Defense Style +1" in text
    assert "final score: 13" in text
    assert "breakdown names: Armor, Shield, Defense Style" in text
    assert "lookup result: same live value" in text
    assert "Values are the game's explainable math layer." in text
    assert "This chapter opens the math inside those actor blocks." in text
    assert (
        "`ModifiableValue` owns the explainable numbers inside that graph"
        in text
    )
    assert "| Product question | Value-owned answer |" in text
    assert "Why is this number what it is?" in text
    assert "How can a designer add a rule safely?" in text
    assert "What can an agent reason about?" in text
    assert "D&D arithmetic becomes inspectable videogame state" in text
    assert "The value owns the calculation surface; the modifier owns one rule contribution." in normalized_text
    assert "| Value responsibility | What it gives the engine |" in text
    assert "| Modifier responsibility | What it gives the value |" in text
    assert "`ModifiableValue.create(...)` creates a base `NumericalModifier` in `self_static`" in normalized_text
    assert "`score`, `normalized_score`, `advantage`, `critical`, `auto_hit`, `resistance`" in normalized_text
    assert "Every modifier carries a readable name plus source and optional target identity." in text
    assert "Contextual modifiers hold a callable that receives source, target, and context" in normalized_text
    assert "Adding a modifier to a channel returns the modifier UUID" in normalized_text
    assert "The examples build one value thread in five moves:" in text
    assert "| Example move | Value surface learned |" in text
    assert "Create an Armor Class ledger." in text
    assert "A base value, named modifiers, final score, value lookup, and visible output." in text
    assert "Create a Strength score and attack bonus." in text
    assert "Aggregate static rule state." in text
    assert "Evaluate high ground." in text
    assert "Attack a blinded target." in text
    assert "Author a value rule by putting each contribution in the channel that owns the relationship." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Identify the owning value." in text
    assert "Choose the channel." in text
    assert "Add named modifiers." in text
    assert "Use context for situational rules." in text
    assert "Export target-facing effects." in text
    assert "Import target state for one calculation." in text
    assert "Preserve readable explanations." in text
    assert "choose the value that owns the relationship, add a named contribution" in normalized_text
    assert "Author the rule where its ownership lives." in text
    assert "| Rule being authored | Put it here | Why this is the right home |" in text
    assert "An actor's ongoing bonus, penalty, cap, resistance" in text
    assert "`self_static`" in text
    assert "The target exports the rule from its own value" in text
    assert "`set_from_target(target_value)`, then `reset_from_target()`" in text
    assert "This placement rule is the safest starting point for new content." in text
    assert "terrain effect, or monster ability should add a" in text
    assert "small rules ledger" not in text
    assert "small high-ground bonus" not in text


def test_values_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 03 examples print value behavior instead of only asserting."""
    text = (manual_root() / "03-values-and-modifiers.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 5
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(score_lines))' in text
    assert 'print("\\n".join(static_lines))' in text
    assert 'print("\\n".join(context_lines))' in text
    assert 'print("\\n".join(target_lines))' in text
    assert "value: Armor Class" in text
    assert "rule modifiers: Shield +2, Defense Style +1" in text
    assert "strength score: raw=16, normalized=3" in text
    assert "combined score: raw=18, normalized=5" in text
    assert "breakdown: STR=3, Base=1, Magic Weapon=1" in text
    assert "movement after grapple: 0" in text
    assert "advantage states: unseen=Advantage, after long range=None" in text
    assert "critical state: Critical Immune" in text
    assert "auto-hit state: Automiss" in text
    assert (
        "fire response: resistance=Resistance, after vulnerability=None, "
        "after immunity=Immunity"
    ) in text
    assert "score without context: 5" in text
    assert "score with high ground: 7" in text
    assert "contextual breakdown contains High Ground: True" in text
    assert "before import: score=5, advantage=None" in text
    assert "during import: score=7, advantage=Advantage" in text
    assert "imported breakdown contains Exposed Target: True" in text
    assert "after reset: score=5, advantage=None" in text


def test_dice_chapter_frontloads_product_roll_bridge() -> None:
    """Chapter 04 explains dice as player, client, log, and agent records before code."""
    text = (manual_root() / "04-dice-rolls.mdx").read_text(encoding="utf-8")
    normalized_text = text.replace("\n", " ")

    first_run_index = text.index("## First Run: Roll And Inspect A D20")
    first_example_index = text.index("<ExampleBlock")
    play_index = text.index("## What This Means In Play")
    records_index = text.index("## Dice And Roll Records")
    product_loop_index = text.index("## Dice State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Dice Become Engine Records")
    source_index = text.index("## Source Rule Relationship")
    contract_index = text.index("## The Dice Expression And Roll Record Contract")
    map_index = text.index("## Chapter Map")
    authoring_index = text.index("## Dice Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    roll_guide_index = text.index("## Roll Record Guide")

    assert play_index < records_index < product_loop_index
    assert product_loop_index < ruling_index < bridge_index < source_index
    assert source_index < contract_index < map_index < authoring_index
    assert authoring_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index < roll_guide_index
    assert '<details className="book-imports" open>' in text
    assert "roll type: Attack" in text
    assert "faces rolled: [13]" in text
    assert "bonus used: 5" in text
    assert "total: 18" in text
    assert "cached result: same roll" in text
    assert "lookup result: registered" in text
    assert "Dice records are the game's uncertainty ledger." in text
    assert (
        "The previous chapter showed how a `ModifiableValue` keeps bonuses and roll"
        in text
    )
    assert "turns uncertain faces into one registered result record" in text
    assert "| Product question | Dice-owned answer |" in text
    assert "What did the player roll?" in text
    assert "What should the client animate or display?" in text
    assert "What can later rule processors read?" in text
    assert "D&D chance becomes inspectable videogame state" in text
    assert "Dice rules have two owners." in text
    assert "`Dice` owns the expression before uncertainty is resolved." in normalized_text
    assert "`DiceRoll` owns the concrete result after the faces are known." in normalized_text
    assert "| Dice expression responsibility | What it gives the engine |" in text
    assert "| Roll record responsibility | What it gives the runtime |" in text
    assert "`count`, `value`, and `roll_type`" in text
    assert "`bonus` points at the `ModifiableValue`" in text
    assert "Reading `Dice.roll` creates and caches one `DiceRoll`" in text
    assert "`roll_uuid` names the result and `dice_uuid` points back" in text
    assert "Source and target UUIDs are copied from the attached value" in text
    assert "The examples build one dice thread in six moves:" in text
    assert "| Example move | Dice surface learned |" in text
    assert "Roll and inspect one d20." in text
    assert "A value bonus, fixed face, total, cache behavior, and lookup identity become visible output." in text
    assert "Roll one cached d20." in text
    assert "Compare advantage and disadvantage." in text
    assert "Capture roll-state flags." in text
    assert "Roll damage and critical damage." in text
    assert "Reject invalid expressions." in text
    assert "Author dice by separating the roll expression from the roll result." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Prepare the bonus value." in text
    assert "Choose the roll category." in text
    assert "Build the dice expression." in text
    assert "Attach damage outcome data." in text
    assert "Read one cached result." in text
    assert "Preserve display and replay data." in text
    assert "Keep walkthroughs deterministic." in text
    assert "prepare the value, choose the roll category, build the expression" in normalized_text
    assert "Author the roll so every part of the ruling has one owner." in text
    assert "| Roll authoring step | Use this surface | Result |" in text
    assert "Prepare the bonus and roll state." in text
    assert "Resolve damage after an attack outcome exists." in text
    assert "Read `Dice.roll` once and pass the cached `DiceRoll` forward." in text
    assert "`RollType.SAVE`" in text
    assert "`RollType.SAVING_THROW`" not in text
    assert "This guide is the dice-layer version of the Chapter 03 placement rule." in text


def test_dice_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 04 examples print dice records instead of only asserting."""
    text = (manual_root() / "04-dice-rolls.mdx").read_text(encoding="utf-8")

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(cached_lines))' in text
    assert 'print("\\n".join(advantage_lines))' in text
    assert 'print("\\n".join(snapshot_lines))' in text
    assert 'print("\\n".join(damage_lines))' in text
    assert 'print("\\n".join(rejection_lines))' in text
    assert "roll type: Attack" in text
    assert "faces rolled: [13]" in text
    assert "dice expression registered: True" in text
    assert "roll record registered: True" in text
    assert "roll record: type=Attack, faces=[13], bonus=5, total=18" in text
    assert "advantage roll: faces=[4, 17], state=Advantage, total=22" in text
    assert "disadvantage roll: faces=[16, 3], state=Disadvantage, total=8" in text
    assert "critical snapshot: Autocrit" in text
    assert "auto-hit snapshot: Autohit" in text
    assert "normal damage: faces=[2, 5], outcome=Hit, bonus=3, total=10" in text
    assert "critical damage: faces=[1, 8, 4], outcome=Crit, bonus=3, total=16" in text
    assert "multi-die check: rejected" in text
    assert "damage without outcome: rejected" in text
    assert "attack with outcome: rejected" in text
    assert "unsupported die size: rejected" in text


def test_event_chapter_frontloads_product_timeline_bridge() -> None:
    """Chapter 05 explains events as player, client, log, and agent timelines."""
    text = (manual_root() / "05-event-lifecycle.mdx").read_text(encoding="utf-8")
    normalized_text = text.replace("\n", " ")

    first_run_index = text.index("## First Run: Create And Inspect A Lineage")
    first_example_index = text.index("<ExampleBlock")
    play_index = text.index("## What This Means In Play")
    records_index = text.index("## Events As Game Occurrence Records")
    product_loop_index = text.index("## Event State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How A Game Moment Becomes An Event Lineage")
    record_contract_index = text.index("## The Event Record And Queue Contract")
    contract_index = text.index("## The Lifecycle Contract")
    guide_index = text.index("## Event Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")

    assert play_index < records_index < product_loop_index
    assert product_loop_index < ruling_index < bridge_index < record_contract_index
    assert record_contract_index < contract_index
    assert contract_index < guide_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index
    assert '<details className="book-imports" open>' in text
    assert "event: Open Door" in text
    assert "type: base_action" in text
    assert "phase history: declaration -> execution -> effect -> completion" in text
    assert "versions stored: 4" in text
    assert "lineages stored: 1" in text
    assert "queue lookup: registered" in text
    assert "Events are the game's timeline ledger." in text
    assert "The previous chapter created stable `DiceRoll` records." in text
    assert re.search(
        r"This\s+chapter\s+gives\s+those\s+records\s+a\s+place\s+in\s+the\s+"
        r"game\s+timeline\.",
        text,
    )
    assert "| Product question | Event-owned answer |" in text
    assert "What did the actor attempt?" in text
    assert "When can rules respond?" in text
    assert "What can tools and agents inspect later?" in text
    assert "D&D timing becomes inspectable videogame state" in text
    assert "Event timing has two owners." in text
    assert "`Event` owns one stored version of a game occurrence." in normalized_text
    assert "`EventQueue` owns the timeline that stores versions" in normalized_text
    assert "| Event record responsibility | What it gives the engine |" in text
    assert "| Queue responsibility | What it gives the runtime |" in text
    assert "`lineage_uuid` connects declaration, execution, effect, completion" in normalized_text
    assert "`parent_event`, `children_events`, and `lineage_children_events`" in normalized_text
    assert "`parent_lineage` and `children_lineages` are filled at completion" in normalized_text
    assert "The queue indexes by UUID, lineage, type, phase, source, target" in normalized_text
    assert "Matching event handlers can inspect, modify, replace, or cancel events" in normalized_text
    assert "Completion versions are stored and can generate logs" in normalized_text
    assert "The examples build one event thread in six moves:" in text
    assert "| Example move | Event surface learned |" in text
    assert "Create and inspect one lineage." in text
    assert "Declaration, execution, effect, completion, queue history, and lineage identity become visible output." in text
    assert "Advance one lineage through phases." in text
    assert "Cancel a locked-door intent." in text
    assert "Connect spell and damage events." in text
    assert "Generate completion narration." in text
    assert "Observe stored versions passively." in text
    assert "Author an event lineage so each phase owns one part of the ruling." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Record player or controller intent." in text
    assert "Apply the state change." in text
    assert "Publish final narration." in text
    assert "Values own rule numbers, dice own roll results, and events own the cause and" in text


def test_runtime_response_and_choice_chapters_explain_their_ruling_role() -> None:
    """Chapters 06-09 continue the ruling-loop spine into playable choices."""
    expectations = {
        "06-reactions-to-events.mdx": [
            "Reactions answer the response-window question in the ruling loop.",
            "| Ruling question | Reaction answer |",
            "This gives the software dungeon master a controlled response layer.",
        ],
        "07-conditions-and-cleanup.mdx": [
            "Conditions answer the ongoing-state question in the ruling loop.",
            "| Ruling question | Condition answer |",
            "This gives the software dungeon master durable memory for game states",
        ],
        "08-world-model-and-movement.mdx": [
            "The world model answers the board-state question in the ruling loop.",
            "| Ruling question | World answer |",
            "This gives the software dungeon master a shared board ledger.",
        ],
        "09-action-discovery-and-costs.mdx": [
            "Actions answer the choice question in the ruling loop.",
            "| Ruling question | Action answer |",
            "This gives the software dungeon master the turn menu.",
        ],
    }
    for chapter_name, phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        ruling_index = text.index("## Ruling Role")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < ruling_index < map_index < surfaces_index
        else:
            assert ruling_index < map_index < surfaces_index < first_example_index
        for phrase in phrases:
            assert phrase in text


def test_event_lifecycle_frontloads_phase_contract() -> None:
    """Chapter 05 teaches phase promises and source surfaces before the first example."""
    text = (manual_root() / "05-event-lifecycle.mdx").read_text(encoding="utf-8")

    first_run_index = text.index("## First Run: Create And Inspect A Lineage")
    first_example_index = text.index("<ExampleBlock")
    contract_index = text.index("## The Lifecycle Contract")
    guide_index = text.index("## Event Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    phases_index = text.index("## The Phases")

    assert contract_index < guide_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index < phases_index
    assert "An event phase is a promise about what the engine is allowed to do" in text
    assert re.search(r"Completion\s+is\s+for\s+final\s+observation", text)
    assert "The event queue is the ledger that makes this contract usable." in text


def test_event_lifecycle_examples_show_reader_visible_output() -> None:
    """Chapter 05 examples print event records instead of only asserting."""
    text = (manual_root() / "05-event-lifecycle.mdx").read_text(encoding="utf-8")

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(phase_lines))' in text
    assert 'print("\\n".join(cancel_lines))' in text
    assert 'print("\\n".join(parent_lines))' in text
    assert 'print("\\n".join(log_lines))' in text
    assert 'print("\\n".join(observed_lines))' in text
    assert "event: Open Door" in text
    assert "phase history: declaration -> execution -> effect -> completion" in text
    assert "history phases: declaration -> execution -> effect -> completion" in text
    assert "unique event versions: 4" in text
    assert "type index contains completion: True" in text
    assert "event: Locked Door" in text
    assert "phase history: declaration -> cancel" in text
    assert "reason: The door is locked" in text
    assert "parent event: Cast Simple Spell" in text
    assert "child event: Spell Damage" in text
    assert "resolved child names: ['Spell Damage']" in text
    assert "top-level log: Hero resolves Training Action" in text
    assert "child logs: ['Hero resolves Training Effect']" in text
    assert "observed phases: declaration -> execution -> effect -> completion" in text
    assert "observed statuses: [None, None, 'Effect resolved', 'Complete']" in text
    assert "callback count: 4" in text


def test_reactions_chapter_frontloads_timing_contract() -> None:
    """Chapter 06 explains timing choices and movement reason before reaction examples."""
    text = (manual_root() / "06-reactions-to-events.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Register And Fire A Handler")
    first_example_index = text.index("<ExampleBlock")
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Reaction State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Timed Rules Become Event Responses")
    surfaces_index = text.index("## The Three Reaction Surfaces")
    dispatch_index = text.index("## The Reaction Dispatch Contract")
    contract_index = text.index("## The Reaction Contract")
    guide_index = text.index("## Reaction Authoring Guide")
    code_surfaces_index = text.index("## Code Surfaces In This Chapter")
    normalized_text = text.replace("\n", " ")

    assert play_index < product_loop_index < ruling_index < bridge_index
    assert bridge_index < surfaces_index
    assert surfaces_index < dispatch_index < contract_index < guide_index
    assert guide_index < code_surfaces_index
    assert code_surfaces_index < first_run_index < first_example_index
    assert '<details className="book-imports" open>' in text
    assert "handler: Alarm Bell" in text
    assert "wrong target status: quiet" in text
    assert "matching event status: Alarm bell rings" in text
    assert "matching event modified: True" in text
    assert "calls recorded: 1" in text
    assert "handler source: alarm" in text
    assert "Reactions are the game's active timing layer." in text
    assert "The previous chapter taught event phases as the timeline of a game occurrence." in text
    assert "which rules may hear a" in text
    assert "specific event version" in text
    assert "| Product question | Reaction-owned answer |" in text
    assert "Why did the outcome change during resolution?" in text
    assert "What can a designer author?" in text
    assert "What can an agent reason about?" in text
    assert "D&D timing becomes active videogame behavior" in text
    assert "| D&D timing idea | Engine response |" in text
    assert "A reaction answers a specific kind of moment." in text
    assert "An `EventHandler` listens for an `EventType` and `EventPhase`" in text
    assert "Result events expose the original roll and the effective roll" in text
    assert "`STEP_MOVEMENT` represents a paid step through a movement path." in text
    assert "`FORCED_MOVEMENT` has its own surface and still updates spatial state" in text
    assert "Reaction dispatch has four owners." in text
    assert "`Trigger` declares which event versions a rule wants to hear." in normalized_text
    assert "`EventHandler` owns the trigger list, enablement flag, and processor callback." in normalized_text
    assert "`SpatialHandler` owns the same processor shape through map positions" in normalized_text
    assert "`EventQueue` stores those handlers, discovers the matching ones" in normalized_text
    assert "| Dispatch owner | What it gives the runtime |" in text
    assert "`Trigger` | Matches `event_type` and `event_phase`" in text
    assert "Processor return value" in text
    assert "`None` leaves the event unchanged" in text
    assert "a canceled event stops later handlers for that pass" in text
    assert "`DECLARATION`, `EXECUTION`, and `EFFECT` are active response windows" in text
    assert "Author a timed rule by choosing the event surface that owns the response" in text
    assert "| Rule being authored | Use this surface | Result |" in text
    assert "A ward changes or cancels an action at a known phase." in text
    assert "A spell zone reacts when an actor enters a cell." in text
    assert "Forced displacement can update space while staying separate" in text
    assert "The examples build one reaction thread in seven moves:" in text
    assert "| Example move | Reaction surface learned |" in text
    assert "Register and fire one handler." in text
    assert "A trigger, handler, matching event, quiet miss, modified result, and handler source become visible output." in text
    assert "Ring an alarm for one matching event." in text
    assert "Keep quiet timing windows quiet." in text
    assert "Cancel a warded action." in text
    assert "Replace a low attack roll." in text
    assert "Trigger thorns by position." in text
    assert "Separate steps from shoves." in text
    assert re.search(
        r"A\s+reaction\s+is\s+a\s+rule\s+answer\s+inside\s+a\s+specific\s+"
        r"timing\s+window",
        text,
    )
    assert "Every reaction rule has four choices:" in text
    assert re.search(
        r"A\s+voluntary\s+step\s+and\s+a\s+forced\s+displacement\s+are\s+"
        r"different\s+event\s+surfaces\.",
        text,
    )
    assert "`STEP_MOVEMENT`" in text
    assert "`FORCED_MOVEMENT`" in text


def test_reactions_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 06 examples print reaction behavior instead of only asserting."""
    text = (manual_root() / "06-reactions-to-events.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(trigger_lines))' in text
    assert 'print("\\n".join(quiet_lines))' in text
    assert 'print("\\n".join(cancel_lines))' in text
    assert 'print("\\n".join(roll_lines))' in text
    assert 'print("\\n".join(spatial_lines))' in text
    assert 'print("\\n".join(movement_lines))' in text
    assert "handler: Alarm Bell" in text
    assert "wrong target status: quiet" in text
    assert "matching event status: Alarm bell rings" in text
    assert "handler source matched: True" in text
    assert "disabled handler calls: 0" in text
    assert "completion event phase: completion" in text
    assert "completion stored: True" in text
    assert "result phase: cancel" in text
    assert "reason: Arcane ward blocks the action" in text
    assert "later handler calls: 0" in text
    assert "original roll: faces=[5], total=9" in text
    assert "effective roll: faces=[14], total=18" in text
    assert "modification handler: Tutorial Focus" in text
    assert "safe cell status: quiet" in text
    assert "watched cell status: Thorns bite" in text
    assert "entries after moved zone: [(2, 2), (3, 3)]" in text
    assert "step event type: step_movement" in text
    assert "forced event type: forced_movement" in text
    assert "forced movement provoked: False" in text


def test_conditions_chapter_frontloads_ownership_contract() -> None:
    """Chapter 07 explains condition ownership before executable examples."""
    text = (manual_root() / "07-conditions-and-cleanup.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Apply And Clean Up A Condition")
    first_example_index = text.index("<ExampleBlock")
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Condition State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Conditions Become Owned Artifacts")
    owner_contract_index = text.index("## The Condition And Block Contract")
    contract_index = text.index("## The Condition Contract")
    guide_index = text.index("## Condition Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    normalized_text = text.replace("\n", " ")

    assert play_index < product_loop_index < ruling_index < bridge_index
    assert bridge_index < owner_contract_index
    assert owner_contract_index < contract_index
    assert contract_index < guide_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index
    assert '<details className="book-imports" open>' in text
    assert "actor: Hero" in text
    assert "condition applied: True" in text
    assert "guard score while active: 12" in text
    assert "owned modifier count: 1" in text
    assert "condition after cleanup: removed" in text
    assert "guard score after cleanup: 10" in text
    assert "Conditions are the game's ongoing-state ledger." in text
    assert "The previous chapter taught timed reactions" in text
    assert "Conditions are the durable ownership layer" in text
    assert "ongoing state real across later rulings" in text
    assert "| Product question | Condition-owned answer |" in text
    assert "Which state is affecting the actor?" in text
    assert "What can a designer author?" in text
    assert "What can an agent reason about?" in text
    assert "D&D status language becomes inspectable videogame state" in text
    assert "Condition ownership has two cooperating owners." in text
    assert "`BaseCondition` owns the runtime artifacts created by one named state." in normalized_text
    assert "`BaseBlock` owns the active condition indexes and the cleanup traversal" in normalized_text
    assert "| Condition responsibility | What it gives the engine |" in text
    assert "| Block responsibility | What it gives the runtime |" in text
    assert "`_apply(...)` returns modifier pairs, event-handler UUIDs" in text
    assert "`modifers_uuids`, `event_handlers_uuids`, `spatial_handler_uuids`" in normalized_text
    assert "`add_linked_condition(...)` records the forward child and sets `parent_link`" in normalized_text
    assert "`active_conditions`, `active_conditions_by_uuid`, and `active_conditions_by_source`" in normalized_text
    assert "`remove_condition(...)` and `_remove_condition_tree(...)` walk same-block children" in normalized_text
    assert "`advance_duration(...)` ticks duration" in text
    assert "The examples build one condition thread in seven moves:" in text
    assert "| Example move | Condition surface learned |" in text
    assert "Apply and clean up Guarded." in text
    assert "A condition-bearing block, active indexes, owned modifier, score change, and cleanup result become visible output." in text
    assert "Create a condition-bearing actor." in text
    assert "Apply Guarded." in text
    assert "Listen while active." in text
    assert "Remove a same-block child tree." in text
    assert "Link two blocks." in text
    assert "Expire by duration." in text
    assert re.search(
        r"A\s+condition\s+turns\s+a\s+named\s+game\s+state\s+into\s+an\s+"
        r"owned\s+runtime\s+package",
        text,
    )
    assert "Every condition rule answers five questions:" in text
    assert "The owning block removes same-block subconditions" in text
    assert "Duration expiry enters the same removal path as explicit removal" in text
    assert "Author a condition as the durable owner of an ongoing game state." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Name the player-visible state." in text
    assert "Install owned value changes." in text
    assert "Install timed rule responses." in text
    assert "Compose same-block states." in text
    assert "Link effects across blocks." in text
    assert "Give the state a lifetime." in text
    assert "ownership precision" in text
    assert "Use a condition when the rule must remain true after the immediate event" in text


def test_conditions_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 07 examples print condition lifecycle instead of only asserting."""
    text = (manual_root() / "07-conditions-and-cleanup.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(actor_lines))' in text
    assert 'print("\\n".join(modifier_lines))' in text
    assert 'print("\\n".join(handler_lines))' in text
    assert 'print("\\n".join(subcondition_lines))' in text
    assert 'print("\\n".join(linked_lines))' in text
    assert 'print("\\n".join(duration_lines))' in text
    assert "actor: Hero" in text
    assert "condition support: True" in text
    assert "guard score: 10" in text
    assert "completion phase: completion" in text
    assert "active condition before cleanup: Guarded" in text
    assert "source index before cleanup: ['Guarded']" in text
    assert "active conditions after cleanup: []" in text
    assert "heard event status: Listening condition heard the action" in text
    assert "quiet event status: quiet" in text
    assert "active before cleanup: ['Focus Blocked', 'Tutorial Stunned']" in text
    assert "subcondition count: 1" in text
    assert "forward before cleanup: owner=True, marked=True" in text
    assert "linked parent recorded: True" in text
    assert "reverse after child cleanup: owner=False, marked=False" in text
    assert "first tick expired: False" in text
    assert "duration after first tick: 1" in text
    assert "second tick expired: True" in text


def test_world_chapter_frontloads_movement_contract() -> None:
    """Chapter 08 explains grid movement ownership before executable examples."""
    text = (manual_root() / "08-world-model-and-movement.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = re.sub(r"\s+", " ", text)

    first_run_index = text.index("## First Run: Build And Measure A Corridor")
    first_example_index = text.index("<ExampleBlock")
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Board State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    ownership_index = text.index("## The Board Ownership Contract")
    tactical_index = text.index("## The Tactical Board")
    map_state_index = text.index("## How Tactical Movement Becomes Map State")
    source_index = text.index("## Source Rule Relationship")
    contract_index = text.index("## The World Movement Contract")
    chapter_map_index = text.index("## Chapter Map")
    guide_index = text.index("## Tactical Board Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    terrain_index = text.index("## Tiles And Terrain Costs")

    assert play_index < product_loop_index < ruling_index < ownership_index
    assert ownership_index < tactical_index < map_state_index < source_index
    assert source_index < contract_index < chapter_map_index < guide_index
    assert guide_index < surfaces_index < first_run_index < first_example_index
    assert first_example_index < terrain_index
    assert '<details className="book-imports" open>' in text
    assert "tile count: 5" in text
    assert "bounds: (0, 0, 4, 0)" in text
    assert "middle tile: Difficult Terrain" in text
    assert "walking route cost: 5" in text
    assert "ignore-terrain route cost: 4" in text
    assert "path: (0, 0) -> (1, 0) -> (2, 0) -> (3, 0) -> (4, 0)" in text
    assert "The world model is the game's tactical truth layer." in text
    assert "The previous chapter taught durable conditions" in text
    assert "own spatial listeners and duration" in text
    assert re.search(
        r"the\s+board\s+those\s+owned\s+spatial\s+rules\s+listen\s+to",
        text,
    )
    assert "| Product question | World-model answer |" in text
    assert "Where can the actor stand?" in text
    assert "Which systems should react?" in text
    assert "What can authoring tools change?" in text
    assert "D&D movement becomes concrete board state" in text
    assert "The board works because each layer owns a precise part of tactical space." in text
    assert "| Owner | Runtime state | What a reader can ask it |" in text
    assert "`Tile` | Position, movement-mode costs, directional borders" in text
    assert "`GridMap` | Tile storage, UUID lookup, bounds, entity indexes" in text
    assert "Movement parent event | `StepMovementEvent` for paid voluntary steps" in text
    assert "`EventQueue` spatial dispatch | Spatial event lifecycle plus position-indexed spatial handlers." in text
    assert (
        "The parent event carries the rules meaning, and spatial events carry the board change."
        in normalized_text
    )
    assert "The examples build one world thread in six moves:" in text
    assert "| Example move | World surface learned |" in text
    assert "Build and measure a corridor." in text
    assert "Tiles, bounds, difficult terrain, movement-mode costs, route cost, and path output become visible." in text
    assert "Measure a corridor with difficult terrain." in text
    assert "Block one edge." in text
    assert "Move one actor by step." in text
    assert "Push one actor by force." in text
    assert "Build a room quietly." in text
    assert "Every movement rule answers five questions:" in text
    assert "The grid updates entity position indexes and emits leave/enter spatial events." in text
    assert re.search(
        r"A\s+voluntary\s+step\s+can\s+pay\s+movement\s+costs\s+and\s+invite\s+"
        r"opportunity-style\s+timing\.",
        text,
    )
    assert re.search(
        r"A\s+forced\s+displacement\s+can\s+push\s+an\s+actor\s+through\s+cells",
        text,
    )
    assert "`GridMap` stores tile positions, bounds, and tile UUID lookup." in text
    assert "Author tactical space as board state first" in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Shape the playable space." in text
    assert "Put terrain costs on cells." in text
    assert "Block one edge without changing a whole cell." in text
    assert "Preserve why movement happened." in text
    assert "Publish what changed on the board." in text
    assert "Opportunity-style rules listen to voluntary" in normalized_text
    assert re.search(
        r"spatial\s+enter\s+and\s+leave\s+events\s+even\s+when\s+the\s+"
        r"creature\s+was\s+pushed\s+or\s+pulled",
        text,
    )
    assert "from dnd.utils import reset_combat_state" not in text


def test_world_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 08 examples print board state instead of only asserting."""
    text = (manual_root() / "08-world-model-and-movement.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(terrain_lines))' in text
    assert 'print("\\n".join(border_lines))' in text
    assert 'print("\\n".join(movement_lines))' in text
    assert 'print("\\n".join(forced_lines))' in text
    assert 'print("\\n".join(batch_lines))' in text
    assert "tile count: 5" in text
    assert "start tile: Stone Floor" in text
    assert "middle tile lookup: True" in text
    assert "walking route cost: 5" in text
    assert "transition before border: True" in text
    assert "transition after border: False" in text
    assert "tile-change completions: 1" in text
    assert "initial position: (0, 0)" in text
    assert "final position: (1, 0)" in text
    assert "left event: position=(0, 0), old=(1, 0)" in text
    assert "spatial parent lineage matches step: True" in text
    assert "forced event type: forced_movement" in text
    assert "target final position: (3, 0)" in text
    assert "spatial parent lineage matches forced movement: True" in text
    assert "tile count after rectangle: 6" in text
    assert "tile-change events during rectangle: 0" in text
    assert "changed tile walkable: False" in text


def test_actions_chapter_frontloads_choice_contract() -> None:
    """Chapter 09 explains the command contract before executable examples."""
    text = (manual_root() / "09-action-discovery-and-costs.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = re.sub(r"\s+", " ", text)

    first_run_index = text.index("## First Run: Print A Turn Menu")
    first_example_index = text.index('<ExampleBlock id="EB-09-000"')
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Command State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    runtime_index = text.index("## The Action Runtime Contract")
    turn_surface_index = text.index("## The Turn Choice Surface")
    player_choice_index = text.index("## How A Player Choice Becomes An Engine Action")
    contract_index = text.index("## The Action Choice Contract")
    source_index = text.index("## Source Rule Relationship")
    chapter_map_index = text.index("## Chapter Map")
    guide_index = text.index("## Action Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    templates_index = text.index("## Templates And Executable Actions")

    assert play_index < product_loop_index < ruling_index < runtime_index
    assert runtime_index < turn_surface_index
    assert turn_surface_index < player_choice_index < contract_index
    assert contract_index < source_index < chapter_map_index < guide_index
    assert guide_index < surfaces_index < first_run_index < first_example_index
    assert first_example_index < templates_index
    assert '<details className="book-imports" open>' in text
    assert "action-first-run" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "actor: Scout" in text
    assert "movement left: 30" in text
    assert "groups: entity=2, position=2, self=4, object=0" in text
    assert "dash row: target=self, cost=1 actions, afford=True" in text
    assert "move row: target 0 -> (5, 6), distance=5" in text
    assert "attack row: Scimitar -> Skeleton, distance=5" in text
    assert "actions after dash: 0" in text
    assert "dash affordable after dash: False" in text
    assert "That is the first action promise" in text
    assert "Action discovery is the game's command-menu layer." in text
    assert "The previous chapter taught the tactical board" in text
    assert "This chapter turns that board" in text
    assert "truth plus actor state into a command menu" in text
    assert "| Product question | Action-owned answer |" in text
    assert "Which buttons should the player see?" in text
    assert "How does a client send intent back?" in text
    assert "What can controllers and agents compare?" in text
    assert "D&D turn options become a stable command contract." in text
    assert "The action layer has a small vocabulary that appears in every command path." in text
    assert "| Runtime object | Owns | Used when |" in text
    assert "`BaseAction` template | Name, source entity, target type" in text
    assert "`Cost` | Action-economy bucket, amount, optional named resource" in text
    assert "`AvailableActionInfo` | Template name, display name, target type" in text
    assert "`AvailableTarget` | Target index, entity UUID, position" in text
    assert "Executable `BaseAction` instance | Fresh UUID, copied template fields" in text
    assert "Registration answers what the actor can do in principle." in normalized_text
    assert "Discovery answers what the actor can do from current state." in normalized_text
    assert "Execution answers what one selected row does after the target index is bound." in normalized_text
    assert "The examples build one command thread in eight moves:" in text
    assert "| Example move | Action surface learned |" in text
    assert "Print a command menu." in text
    assert "A live actor exposes grouped rows, target previews, visible costs" in text
    assert "Instantiate Dash from a template." in text
    assert "Discover a turn menu." in text
    assert "Execute Dash by index." in text
    assert "Pick up and drink a potion." in text
    assert "Override Dash cost." in text
    assert "Filter target pools." in text
    assert "Prefer a safe movement path." in text
    assert re.search(
        r"The\s+action\s+layer\s+turns\s+engine\s+state\s+into\s+"
        r"player-visible\s+choices\.",
        text,
    )
    assert "Every action choice answers five questions:" in text
    assert (
        "`actions`, `bonus_actions`, `reactions`, movement, resources, charges, "
        "and slots."
    ) in text
    assert "Discovery builds the menu." in text
    assert "Execution resolves the selected row." in text
    assert "Author an action as a player-facing command" in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Choose where the choice comes from." in text
    assert "Keep the capability reusable." in text
    assert "Pick the command category and target type." in text
    assert "Produce legal target rows." in text
    assert "Expose cost before execution." in text
    assert "Execute the selected row." in text
    assert "Route item and object use through the same menu." in text
    assert "Apply temporary feature changes." in text
    assert "Discovery and execution own different moments of the command lifecycle." in text
    assert "Discovery builds the current legal menu." in text
    assert "Execution sends the selected row into" in text
    assert "in the collapsed Code setup: imports and scene panel" not in text
    assert "from dnd.utils import reset_combat_state" not in text


def test_actions_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 09 examples print action state instead of only asserting."""
    text = (manual_root() / "09-action-discovery-and-costs.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 8
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(template_lines))' in text
    assert 'print("\\n".join(discovery_lines))' in text
    assert 'print("\\n".join(execute_lines))' in text
    assert 'print("\\n".join(item_lines))' in text
    assert 'print("\\n".join(override_lines))' in text
    assert 'print("\\n".join(target_lines))' in text
    assert 'print("\\n".join(safe_lines))' in text
    assert "non-template rejected: True" in text
    assert "template lookup: True" in text
    assert "instance use_register: False" in text
    assert "entity uuid matches actor: True" in text
    assert "self actions include: ['Dash', 'Disengage', 'Dodge']" in text
    assert "attack row: weapon=Scimitar, targets=['Skeleton']" in text
    assert "dash target index: 0" in text
    assert "dashing condition active: True" in text
    assert "pickup row: target=object, cost=0, distance=5" in text
    assert "drink row: Drink Potion (Potion of Healing), target index=0" in text
    assert "dash override applied: True" in text
    assert "displayed cost type: bonus_actions" in text
    assert "default targets: ['Enemy']" in text
    assert "all targets with dead included: ['Enemy', 'Dead Enemy', 'Ally']" in text
    assert "unsafe path: [(5, 3), (5, 4), (5, 5), (5, 6)]" in text
    assert "safe path: [(5, 3), (5, 4), (4, 5), (5, 6)]" in text
    assert "executed path is safe path: True" in text


def test_combat_chapter_frontloads_resolution_contract() -> None:
    """Chapter 10 explains combat resolution before executable examples."""
    text = (manual_root() / "10-combat-resolution.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = re.sub(r"\s+", " ", text)

    first_run_index = text.index("## First Run: Resolve One Hit")
    first_example_index = text.index('<ExampleBlock id="EB-10-000"')
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Outcome State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    runtime_index = text.index("## The Combat Runtime Contract")
    spine_index = text.index("## The Combat Spine")
    result_index = text.index("## How A Combat Choice Becomes A Result")
    source_index = text.index("## Source Rule Relationship")
    contract_index = text.index("## The Combat Resolution Contract")
    chapter_map_index = text.index("## Chapter Map")
    guide_index = text.index("## Combat Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    validation_index = text.index("## Validation Before Cost Spending")

    assert play_index < product_loop_index < ruling_index < runtime_index
    assert runtime_index < spine_index
    assert spine_index < result_index < contract_index
    assert result_index < source_index < contract_index < chapter_map_index
    assert chapter_map_index < guide_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index
    assert first_example_index < validation_index
    assert '<details className="book-imports" open>' in text
    assert "combat-first-run" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "attack: Blade -> Bone Guard with Scimitar" in text
    assert "outcome: Hit" in text
    assert "damage roll: [4] + 2 = 6" in text
    assert "target hp after hit: 17 -> 11" in text
    assert "actions after attack: 1 -> 0" in text
    assert "healing applied: 3" in text
    assert "completion events: attack=1, damage_roll_result=1, take_damage=1, heal=1" in text
    assert "That is the first combat promise" in text
    assert "Combat resolution is the game's consequence layer." in text
    assert "The previous chapter taught the command menu" in text
    assert "This chapter follows a" in text
    assert "selected combat command" in text
    assert "validated consequence with rolls, HP changes, reactions" in text
    assert "no longer just a" not in text
    assert "| Product question | Combat-owned answer |" in text
    assert "Did the selected command work?" in text
    assert "What should the client narrate?" in text
    assert "What can designers extend?" in text
    assert "D&D combat becomes replayable videogame outcome state." in text
    assert "Combat is a composition of the lower-level surfaces from the previous chapters." in text
    assert "| Runtime surface | Owns | Used when |" in text
    assert "Executable combat action | Actor UUID, target UUID or position" in text
    assert "`AttackEvent` or `ShoveEvent` | Combat-specific payload" in text
    assert "`AttackD20RollResultEvent` and `DiceRoll` | The decisive d20 roll" in text
    assert "`DamageRollResultEvent` | Original and final damage rolls" in text
    assert "`TakeDamageEvent` and `HealEvent` | Damage application, healing application" in text
    assert "`StepMovementEvent` and `ForcedMovementEvent` | Voluntary walking steps" in text
    assert "Action cost application | Action, bonus action, reaction, movement" in text
    assert (
        "A new combat rule can choose the right entry point without inventing a parallel pipeline"
        in normalized_text
    )
    assert "The examples build one combat thread in six moves:" in text
    assert "| Example move | Combat surface learned |" in text
    assert "Resolve one hit." in text
    assert "A deterministic attack prints outcome, damage, HP change" in text
    assert "Swing at a target outside reach." in text
    assert "Land a hit and heal damage." in text
    assert "Force a critical hit." in text
    assert "Walk out of reach." in text
    assert "Shove a target." in text
    assert re.search(
        r"Combat\s+resolution\s+is\s+the\s+engine's\s+answer\s+to\s+the\s+"
        r"player\s+question",
        text,
    )
    assert "Every combat rule answers six questions:" in text
    assert "Attacks compare a d20 roll against AC" in text
    assert "HP, temporary HP, damage taken, healing, dying state, death state" in text
    assert "after successful completion" in text
    assert "Author combat content as an entry into the shared consequence pipeline." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Start from a selected executable action." in text
    assert "Validate before consequence." in text
    assert "Use values and dice for uncertainty." in text
    assert "Change state through owned blocks." in text
    assert "Publish the consequence as events." in text
    assert "Keep movement reason explicit." in text
    assert "Spend costs after success." in text
    assert "Use the standard videogame Shove surface." in text
    assert "bonus action, passive resistance, Strength-scaled forced movement" in text
    assert "Opportunity-style reactions stay tied to voluntary movement" in text
    assert "from dnd.utils import reset_combat_state" not in text


def test_combat_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 10 examples print combat state instead of only asserting."""
    text = (manual_root() / "10-combat-resolution.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(invalid_lines))' in text
    assert 'print("\\n".join(hit_lines))' in text
    assert 'print("\\n".join(crit_lines))' in text
    assert 'print("\\n".join(opportunity_lines))' in text
    assert 'print("\\n".join(shove_lines))' in text
    assert "attack: Blade -> Bone Guard with Scimitar" in text
    assert "event phase: cancel" in text
    assert "reason: Target entity not in reach for Attack" in text
    assert "actions after invalid attack: 1 -> 1" in text
    assert "outcome: Hit" in text
    assert "hp after damage: 17 -> 11" in text
    assert "completion events: attack=1, damage_roll_result=1, take_damage=1, heal=1" in text
    assert "outcome: Crit" in text
    assert "damage dice: [3, 4]" in text
    assert "target hp after crit: 8" in text
    assert "move phase: completion" in text
    assert "mover hp after reaction: 10 -> 4" in text
    assert "opportunity attack completions: 1" in text
    assert "shove phase: completion" in text
    assert "target position after shove: (10, 5)" in text
    assert "forced movement completions: 1" in text
    assert "opportunity attacks created: 0" in text


def test_combat_object_awareness_chapters_explain_their_ruling_role() -> None:
    """Chapters 10-12 continue the ruling-loop spine into playable outcomes."""
    expectations = {
        "10-combat-resolution.mdx": [
            "Combat answers the consequence question in the ruling loop.",
            "| Ruling question | Combat answer |",
            "This gives the software dungeon master the consequence pipeline.",
        ],
        "11-equipment-inventory-and-items.mdx": [
            "Equipment, inventory, and items answer the physical-object question",
            "| Ruling question | Item answer |",
            "This gives the software dungeon master physical continuity.",
        ],
        "12-perception-light-stealth-and-invisibility.mdx": [
            "Perception answers the knowledge question in the ruling loop.",
            "| Ruling question | Perception answer |",
            "This gives the software dungeon master a player-specific view",
        ],
    }
    for chapter_name, phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        ruling_index = text.index("## Ruling Role")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < ruling_index < map_index < surfaces_index
        else:
            assert ruling_index < map_index < surfaces_index < first_example_index
        for phrase in phrases:
            assert phrase in text


def test_items_chapter_frontloads_ownership_contract() -> None:
    """Chapter 11 explains object ownership before executable examples."""
    text = (manual_root() / "11-equipment-inventory-and-items.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Track One Object")
    first_example_index = text.index('<ExampleBlock id="EB-11-000"')
    play_index = text.index("## What This Means In Play")
    product_loop_index = text.index("## Object State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Gear Becomes Item State")
    source_index = text.index("## Source Rule Relationship")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Item Ownership Contract")
    guide_index = text.index("## Item Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    object_surfaces_index = text.index("## Object Surfaces")

    assert play_index < product_loop_index < ruling_index < bridge_index
    assert bridge_index < source_index < map_index
    assert map_index < contract_index < guide_index < surfaces_index
    assert surfaces_index < first_run_index < first_example_index
    assert first_example_index < object_surfaces_index
    assert '<details className="book-imports" open>' in text
    assert "items-first-run" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "item: Silver Key" in text
    assert "floor position: item=(1, 0), map=(1, 0)" in text
    assert "floor fields: owner missing=True, stored missing=True, tile set=True" in text
    assert "inventory contains item: True" in text
    assert "inventory position follows actor: (0, 0)" in text
    assert "map position while carried: None" in text
    assert "drop returned same item: True" in text
    assert "drop position: item=(0, 1), map=(0, 1)" in text
    assert "That is the first item promise" in text
    assert "The previous chapter taught combat consequences" in text
    assert "This chapter gives those consequences physical objects to work with" in text
    assert "combat, action discovery, perception, and client payloads" in text
    assert "Items are the game's physical-object layer." in text
    assert "| Product question | Item-owned answer |" in text
    assert "Where is this object now?" in text
    assert "How do loadouts stay coherent?" in text
    assert "What can the client render?" in text
    assert "D&D gear becomes persistent videogame object state." in text
    assert "| D&D gear idea | Engine behavior |" in text
    assert "A weapon or shield occupies a hand." in text
    assert "Equipment uses `WeaponSlot` values and weapon properties" in text
    assert "The engine keeps one melee set and one ranged set" in text
    assert "The examples build one item thread in six moves:" in text
    assert "| Example move | Item surface learned |" in text
    assert "Track one object through location states." in text
    assert "Floor fields, inventory ownership, actor-following position" in text
    assert "Place a key on the floor, loot it, then drop it." in text
    assert "Merge potion stacks and reject an overweight insert." in text
    assert "Equip sword, shield, and armor, then unequip the sword." in text
    assert "Resolve a two-handed melee conflict while keeping ranged gear parallel." in text
    assert "Drink a potion and open a door." in text
    assert re.search(
        r"Items\s+are\s+runtime\s+objects\s+with\s+one\s+authoritative\s+"
        r"location\s+at\s+a\s+time\.",
        text,
    )
    assert "Every item rule answers six questions:" in text
    assert "The newer equip wins" in text
    assert "`TWO_HANDED` melee weapon" in text
    assert "one melee set and one ranged set" in text
    assert "spends charges after success" in text
    assert "Author an item as one persistent object with one authoritative location." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Choose the physical identity." in text
    assert "Put the item in exactly one location." in text
    assert "Make carried storage atomic." in text
    assert "Equip through slot rules." in text
    assert "Preserve videogame loadouts." in text
    assert "Expose use actions from the object." in text
    assert "Update charges and stacks after success." in text
    assert "Keep map objects inspectable." in text
    assert "Newer melee equips displace conflicting melee gear" in text
    assert "parallel ranged set stays independent" in text
    assert "from dnd.utils import reset_combat_state" not in text


def test_items_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 11 examples print item state instead of only asserting."""
    text = (manual_root() / "11-equipment-inventory-and-items.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(location_lines))' in text
    assert 'print("\\n".join(stack_lines))' in text
    assert 'print("\\n".join(equipment_lines))' in text
    assert 'print("\\n".join(loadout_lines))' in text
    assert 'print("\\n".join(use_lines))' in text
    assert "item: Silver Key" in text
    assert "floor position: item=(1, 0), map=(1, 0)" in text
    assert "inventory position: item=(0, 0), map=None" in text
    assert "drop ownership: in_inventory=False, owner_missing=True" in text
    assert "merge stack count: first=10, second=0" in text
    assert "second consumed: in_inventory=False, unregistered=True" in text
    assert "overweight insert accepted: False" in text
    assert "tight pack after reject: existing=8, incoming=5" in text
    assert "base ac/movement: 12/30" in text
    assert "shield equipped: offhand=True, ac=12->14" in text
    assert "armor equipped: body=True, is_equipped=True, stealth=Disadvantage" in text
    assert "unequip sword: same_item=True, main_empty=True" in text
    assert "greatsword then shield: main=None, off=Shield" in text
    assert "shield then greatsword: main=Greatsword, off=None" in text
    assert "melee plus bow: melee=Shortsword + Shield, ranged=Shortbow" in text
    assert "paired crossbows: melee=Shortsword + Shield" in text
    assert "drink action clone: name=Drink Potion, user_set=True" in text
    assert "after second drink: canceled=False, hp=18, still_carried=False" in text
    assert "door actions: before=['Open Door'], after=['Close Door']" in text


def test_perception_chapter_frontloads_visibility_contract() -> None:
    """Chapter 12 starts with a runnable observer-knowledge example."""
    text = (
        manual_root() / "12-perception-light-stealth-and-invisibility.mdx"
    ).read_text(encoding="utf-8")

    first_run_index = text.index("## First Run: Reveal A Dark Target Cell")
    first_example_index = text.index('<ExampleBlock id="EB-12-000"')
    product_loop_index = text.index("## Awareness State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Senses Become Observer State")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Visibility Contract")
    guide_index = text.index("## Visibility Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < product_loop_index
    assert product_loop_index < ruling_index < bridge_index < map_index
    assert map_index < contract_index < guide_index < surfaces_index
    assert '<details className="book-imports" open>' in text
    assert "senses-first-run" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "observer: Observer" in text
    assert "target cell subscribed: True" in text
    assert "target cell visible before light: False" in text
    assert "target visible before light: False" in text
    assert "target cell visible after light: True" in text
    assert "target visible after light: True" in text
    assert "light update added cell: True" in text
    assert "light update added target: True" in text
    assert "That is the first perception promise" in text
    assert "The previous chapter taught physical object state" in text
    assert (
        "This chapter decides which of those cells, actors, objects, and paths"
        in normalized_text
    )
    assert (
        "whether a specific actor can see, target, remember, or path around them"
        in normalized_text
    )
    assert "Perception is the game's player-knowledge layer." in text
    assert "| Product question | Senses-owned answer |" in text
    assert "What can this player see right now?" in text
    assert "Which targets may appear in the UI?" in text
    assert "Which hidden layer still applies?" in text
    assert "D&D visibility becomes observer-owned videogame state." in text
    assert "| D&D perception idea | Engine behavior |" in text
    assert "Line of sight limits what a creature can inspect." in text
    assert "Effective light resolves bright light, dim light, darkness" in text
    assert "`Hidden` state stores a stealth DC" in text
    assert "`Invisible` state filters ordinary sight" in text
    assert "`senses.entities`, `senses.objects`, `senses.paths`, and `senses.safe_paths`" in text
    assert "The examples build one perception thread in seven moves:" in text
    assert "| Example move | Perception surface learned |" in text
    assert "Reveal a dark subscribed target cell." in text
    assert "Observer-local visible cells, target lists, memory, and light-update events become visible output." in text
    assert "Subscribe to a dark corridor before seeing the far cell." in text
    assert "Swap darkvision, Devil's Sight, and truesight on one observer." in text
    assert "Light a subscribed target cell." in text
    assert "Raise stealth DC, lower it, then turn on invisibility." in text
    assert "Preview a path past an unseen blocker, then reveal it with truesight." in text
    assert "Stack Hidden and Invisible, then reveal only the stealth layer." in text
    assert "Visibility is observer-local game truth." in text
    assert "Every visibility rule answers six questions:" in text
    assert "Field of view subscribes the observer to cells" in text
    assert "Effective light is resolved for that observer" in text
    assert "Perceivability filters visible cells" in text
    assert "`SensoryUpdateEvent` records observer-specific deltas" in text
    assert "Author visibility as observer-local knowledge layered over an objective board." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Start from objective board facts." in text
    assert "Subscribe by geometry first." in text
    assert "Resolve light per observer." in text
    assert "Filter perceivable actors and objects." in text
    assert "Store knowledge on the observer." in text
    assert "Publish observer-specific changes." in text
    assert "Keep concealment layers independent." in text
    assert "Build paths from known state." in text
    assert "Revealing stealth does not automatically remove invisibility" in text
    assert "the same cache a player would see" in text
    assert "from dnd.utils import reset_combat_state" not in text


def test_perception_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 12 examples print observer state instead of only asserting."""
    text = (
        manual_root() / "12-perception-light-stealth-and-invisibility.mdx"
    ).read_text(encoding="utf-8")

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(geometry_lines))' in text
    assert 'print("\\n".join(special_lines))' in text
    assert 'print("\\n".join(reactive_lines))' in text
    assert 'print("\\n".join(stealth_lines))' in text
    assert 'print("\\n".join(path_lines))' in text
    assert 'print("\\n".join(stacked_lines))' in text
    assert "target cell subscribed: True" in text
    assert "subscribed target cell: True" in text
    assert "visible target cell: False" in text
    assert "darkvision far darkness: DARKNESS" in text
    assert "darkvision magical darkness: MAGICAL_DARKNESS" in text
    assert "devil's sight magical darkness: BRIGHT_LIGHT" in text
    assert "before light: target_visible=False, cell_visible=False, cell_seen=False" in text
    assert "after light: target_visible=True, cell_visible=True, cell_seen=True" in text
    assert "light updates: count=2, added_cell=True, added_target=True" in text
    assert "initial ordinary sight: visible=True, passive=10" in text
    assert "high stealth dc: dc=11, perceivable=False" in text
    assert "invisible target: ordinary=False, truesight=True" in text
    assert "before truesight: blocker_visible=False" in text
    assert "after truesight: blocker_visible=True" in text
    assert "before reveal: invisible=True, hidden=True" in text
    assert "after bright reveal: hidden=False, invisible=True" in text
    assert "after reveal visibility: observer_visible=False, truesight_visible=True" in text


def test_spellcasting_chapter_frontloads_spellcasting_contract() -> None:
    """Chapter 13 starts with a runnable discovered-spell cast."""
    text = (manual_root() / "13-spellcasting-core.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Cast A Discovered Spell")
    first_example_index = text.index('<ExampleBlock id="EB-13-000"')
    play_index = text.index("## What This Means In Play")
    spell_state_index = text.index("## Spell State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Spellcasting Becomes Runtime Magic")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Spellcasting Contract")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    guide_index = text.index("## Spell Authoring Guide")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < play_index
    assert play_index < spell_state_index < ruling_index < bridge_index
    assert bridge_index < map_index < contract_index < guide_index
    assert guide_index < surfaces_index
    assert '<details className="book-imports" open>' in text
    assert 'name=spell-first-run part="imports"' in text
    assert 'name=spell-first-run part="body"' in text
    assert "execute_by_index(" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "caster: Pyromancer" in text
    assert "discovered spells: Fire Bolt, Magic Missile (Level 1)" in text
    assert "fire bolt row: level=0, cost=1 actions, targets=1" in text
    assert "event: fire_bolt, phase=completion, outcome=Hit" in text
    assert "attack roll: [12] + 7 = 19" in text
    assert "damage roll: [5, 6] = 11" in text
    assert "target hp: 27 -> 16" in text
    assert "actions: 1 -> 0" in text
    assert "level 1 slots: 1 -> 1" in text
    assert "combat log type: attack" in text
    assert "That is the first spellcasting promise." in text
    assert "The previous chapter taught observer-local knowledge" in text
    assert (
        "This chapter turns that knowledge into magical choices."
        in normalized_text
    )
    assert (
        "once chosen, the spellcasting layer adds slots, caster numbers, spell events"
        in normalized_text
    )
    assert "Spellcasting is the game's magical-action layer" in text
    assert "| Product question | Spell-owned answer |" in text
    assert "Registered spell templates appear through action discovery" in text
    assert "`SpellAction.apply()` creates a `SpellEvent` and any child attack" in text
    assert "Spell rows, slot cost, targets, attack/save results" in text
    assert "| D&D spellcasting idea | Engine behavior |" in text
    assert "The spell class is registered as an action template on the entity." in text
    assert "The cantrip appears as a spell action row with no spell-slot cost." in text
    assert "The chosen slot maps to an `ActionEconomy` value such as `spell_slot_1`." in text
    assert "`SpellAction.apply()` creates a `SpellEvent` and child events" in text
    assert "The caster owns `Concentrating`" in text
    assert "The examples build one spellcasting thread in seven moves:" in text
    assert "| Example move | Spellcasting surface learned |" in text
    assert "Cast a discovered cantrip." in text
    assert "Spend a first-level spell slot and run turn reset." in text
    assert "Compose a spell attack bonus, save DC, damage bonus, and crit policy." in text
    assert "Register Fire Bolt, Magic Missile, and Haste, then discover rows." in text
    assert "Cast Fire Bolt with fixed dice." in text
    assert "Cast Magic Missile into one target." in text
    assert "Cast Haste and remove concentration." in text
    assert "Every spellcasting rule answers seven questions:" in text
    assert "`spell_slot_1` through `spell_slot_9`" in text
    assert "`SpellcastingBlock.spellcasting_ability`" in text
    assert "slot-specific variants for leveled spells" in text
    assert "`SpellAction.apply()` creates a `SpellEvent`" in text
    assert "The caster's `Concentrating` condition links to active spell effects" in text
    assert "**Code setup: imports and scene**" in text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "Author a spell as an action with magic-specific resources" in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Give the actor spellcasting numbers." in text
    assert "Put slot resources on the turn economy." in text
    assert "Register the spell as a template." in text
    assert "Let perception shape target rows." in text
    assert "Resolve the cast through `SpellAction`." in text
    assert "Use child events for target-specific effects." in text
    assert "Scale with caster level or slot level." in text
    assert "Own lasting magic with conditions." in text
    assert "Breaking concentration removes the spell's active effects" in text
    assert "Perception supplies legal targets" in text
    assert "Snippet Start: Imports And Scene" not in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_spellcasting_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 13 examples print spellcasting state instead of only asserting."""
    text = (manual_root() / "13-spellcasting-core.mdx").read_text(
        encoding="utf-8"
    )

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert 'print("\\n".join(readout_lines))' in text
    assert 'print("\\n".join(slot_lines))' in text
    assert 'print("\\n".join(number_lines))' in text
    assert 'print("\\n".join(discovery_lines))' in text
    assert 'print("\\n".join(fire_lines))' in text
    assert 'print("\\n".join(missile_lines))' in text
    assert 'print("\\n".join(haste_lines))' in text
    assert "caster: Pyromancer" in text
    assert "combat log type: attack" in text
    assert "initial slots: level1=2, level2=1" in text
    assert "slots live on spellcasting block: False" in text
    assert "level1 after slot reset: 2" in text
    assert "spell ability: intelligence" in text
    assert "spell attack bonus: 9" in text
    assert "spell crit extra dice: 2" in text
    assert "fire bolt row: category=spell, level=0, cast_at=0" in text
    assert "magic missile scaling: level2=4, level3=5" in text
    assert "haste row: base=Haste, cast_at=3" in text
    assert "event phase: completion, canceled=False, outcome=Hit" in text
    assert "damage roll: [5, 6] -> 11" in text
    assert "targets/projectiles: 3, damage=12" in text
    assert "combat log: multi_entity_action, sub_entries=3" in text
    assert "conditions after cast: caster_concentrating=True, ally_haste=True" in text
    assert "concentration linked to haste: True" in text
    assert "after concentration cleanup: caster_concentrating=False" in text


def test_magic_and_character_chapters_explain_their_ruling_role() -> None:
    """Chapters 13-15 continue the ruling-loop spine into authored content."""
    expectations = {
        "13-spellcasting-core.mdx": [
            "Spellcasting answers the magic-choice question in the ruling loop.",
            "| Ruling question | Spellcasting answer |",
            "This gives the software dungeon master a magic pipeline.",
        ],
        "14-spell-families-and-implemented-spells.mdx": [
            "Spell families answer the magic-effect question in the ruling loop.",
            "| Ruling question | Spell family answer |",
            "This gives the software dungeon master a spell-behavior catalog.",
        ],
        "15-class-features-factories-and-feats.mdx": [
            "Class features answer the character-identity question in the ruling loop.",
            "| Ruling question | Character content answer |",
            "This gives the software dungeon master playable character identity.",
        ],
    }
    for chapter_name, phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        ruling_index = text.index("## Ruling Role")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < ruling_index < map_index < surfaces_index
        else:
            assert ruling_index < map_index < surfaces_index < first_example_index
        for phrase in phrases:
            assert phrase in text


def test_running_game_authoring_chapters_explain_their_ruling_role() -> None:
    """Chapters 16-19 continue the ruling-loop spine into game assembly."""
    expectations = {
        "16-monsters-and-preset-actors.mdx": [
            "Monsters and preset actors answer the encounter-opposition question in the ruling loop.",
            "| Ruling question | Preset actor answer |",
            "This gives the software dungeon master authored opposition and allies.",
        ],
        "17-encounters-turns-and-controllers.mdx": [
            "Encounters answer the playable-time question in the ruling loop.",
            "| Ruling question | Encounter answer |",
            "This gives the software dungeon master the table clock.",
        ],
        "18-sessions-apis-and-client-payloads.mdx": [
            "Sessions and APIs answer the client-contract question in the ruling loop.",
            "| Ruling question | Client contract answer |",
            "This gives the software dungeon master a networked table surface.",
        ],
        "19-map-editor-and-scenario-authoring.mdx": [
            "Map authoring answers the prepared-space question in the ruling loop.",
            "| Ruling question | Authoring answer |",
            "This gives the software dungeon master authored space before initiative.",
        ],
    }
    for chapter_name, phrases in expectations.items():
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        ruling_index = text.index("## Ruling Role")
        map_index = text.index("## Chapter Map")
        surfaces_index = text.index("## Code Surfaces In This Chapter")
        first_example_index = text.index("<ExampleBlock")

        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < ruling_index < map_index < surfaces_index
        else:
            assert ruling_index < map_index < surfaces_index < first_example_index
        for phrase in phrases:
            assert phrase in text


def test_spell_families_chapter_frontloads_family_contract() -> None:
    """Chapter 14 starts with a runnable spell-family comparison."""
    text = (
        manual_root() / "14-spell-families-and-implemented-spells.mdx"
    ).read_text(encoding="utf-8")

    first_run_index = text.index("## First Run: Compare Three Offensive Families")
    first_example_index = text.index('<ExampleBlock id="EB-14-000"')
    play_index = text.index("## What This Means In Play")
    family_state_index = text.index("## Spell Family State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Spell Names Become Runtime Families")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Spell Family Contract")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    guide_index = text.index("## Spell Family Authoring Guide")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < play_index
    assert play_index < family_state_index < ruling_index < bridge_index
    assert bridge_index < map_index < contract_index < guide_index
    assert guide_index < surfaces_index
    assert '<details className="book-imports" open>' in text
    assert 'name=spell-family-first-run part="imports"' in text
    assert 'name=spell-family-first-run part="body"' in text
    assert "ALL_SPELLS[\"Fire Bolt\"]" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "catalog: Fire Bolt -> attack, level=0, school=evocation, target=entity" in text
    assert "catalog: Sacred Flame -> save, level=0, school=evocation, target=entity" in text
    assert "catalog: Magic Missile -> auto-hit" in text
    assert "fire bolt: outcome=Hit, roll=[12]+7=19" in text
    assert "sacred flame: save=dexterity, success=False" in text
    assert "magic missile: targets=3, total_damage=12" in text
    assert "That is the spell-family promise." in text
    assert "Chapter 13 described the spellcasting machinery" in text
    assert "The previous chapter taught how a chosen spell becomes a resolved magical action" in normalized_text
    assert "This chapter teaches how the catalog turns D&D spell names into runtime families" in normalized_text
    assert "reusable behavior patterns for damage, saves, auto-hit darts" in normalized_text
    assert "Spell families are the game's reusable magic-behavior patterns" in text
    assert "| Product question | Spell-family answer |" in text
    assert "whether the spell attacks, forces a save, heals, protects, moves, zones" in text
    assert "Attack families use the caster's spell attack" in text
    assert "Conditions, zones, protections, mirror images" in text
    assert "A new spell can choose an existing family" in text
    assert "Spell cards can show the family, target shape, resource cost" in text
    assert "| D&D spell idea | Runtime family |" in text
    assert "Spell attack actions use caster spell-attack numbers" in text
    assert "Save spells build a saving throw request" in text
    assert "Auto-hit spells create target events directly" in text
    assert "Healing and protection families change hit points" in text
    assert "Teleport, forced movement, and zone families resolve map state" in text
    assert "Condition families attach named conditions and cleanup links" in text
    assert "Catalog dictionaries map display names to spell classes" in text
    assert "The examples build one spell-family thread in seven moves:" in text
    assert "| Example move | Spell-family surface learned |" in text
    assert "Compare attack, save, and auto-hit damage families." in text
    assert "Read representative spells from the catalog." in text
    assert "Resolve Fire Bolt, Sacred Flame, and Magic Missile." in text
    assert "Cast Cure Wounds, Healing Word, Mage Armor, and Lesser Restoration." in text
    assert "Cast Misty Step and False Life." in text
    assert "Cast Spike Growth, enter its area, then remove concentration." in text
    assert "Cast Mirror Image and Sleep." in text
    assert "Every spell family answers seven questions:" in text
    assert "Damage, healing, protection, movement, temporary HP" in text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text
    assert "Entity, self, position, area, or multi-entity targeting" in text
    assert "The caster may make a spell attack, the target may make a save" in text
    assert "Catalog dictionaries map public spell names to spell classes" in text
    assert "fantasy name to implementation" in text
    assert "Author a spell family by choosing the gameplay shape" in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Start with the fantasy verb." in text
    assert "Choose the target shape." in text
    assert "Decide who rolls or resists." in text
    assert "Apply the immediate result." in text
    assert "Own lasting state explicitly." in text
    assert "Pick the cleanup owner." in text
    assert "Register the catalog address." in text
    assert "Teach the family through examples." in text
    assert re.search(r"If\s+a\s+new\s+spell\s+shares\s+an\s+existing\s+family", text)


def test_spell_family_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 14 examples print spell-family transcripts, not assert-only bodies."""
    text = (
        manual_root() / "14-spell-families-and-implemented-spells.mdx"
    ).read_text(encoding="utf-8")

    expected_phrases = [
        "catalog: Fire Bolt -> attack, level=0, school=evocation, target=entity",
        "magic missile: targets=3, total_damage=12, hp=20->8, slot=1->0",
        "catalog size: 109 spells",
        (
            "Power Word Kill: class=PowerWordKill, level=9, "
            "school=enchantment, target=entity, catalog_match=True"
        ),
        "fire bolt: outcome=Hit, roll=[12]+7=19, damage=[5, 6]->11, hp=40->29",
        "sacred flame: save=dexterity, success=False, damage=[4, 5]->9, hp=29->20",
        "cure wounds: hp=5->15, action=1->0, slot1=2",
        "healing word: hp=5->12, bonus=1->0, slot1=1",
        "mage armor: ac=12->15, condition=True, slot1=0",
        "lesser restoration: poisoned=True->False, slot2=0",
        "misty step: position=(1, 1)->(4, 1), bonus=1->0, slot2=1->0",
        "false life: temp_hp=0->7, slot1=1->0",
        "spike growth: zone=True, concentrating=True, positions=49, handlers=1, linked=True",
        "zone entry: position=(5, 3), damage=7, hp=40->33",
        "cleanup: zone=False, concentrating=False",
        "mirror image: duplicates=3, ac=12->21, concentrating=False",
        (
            "sleep selection: selected=['Low HP Goblin', 'Mid HP Goblin'], "
            "remaining_pool=1, undead_selected=False"
        ),
        (
            "sleep apply: low_sleep=True, low_unconscious=True, "
            "mid_sleep=False, remaining_pool=0"
        ),
        "wakeup: low_sleep=False, low_unconscious=False",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert text.count('print("\\n".join(readout_lines))') == 7
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_class_features_chapter_frontloads_character_content_contract() -> None:
    """Chapter 15 starts with a runnable class-factory readout."""
    text = (manual_root() / "15-class-features-factories-and-feats.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Build Three Playable Classes")
    first_example_index = text.index('<ExampleBlock id="EB-15-000"')
    play_index = text.index("## What This Means In Play")
    character_state_index = text.index("## Character State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Character Choices Become Runtime State")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Character Content Contract")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    guide_index = text.index("## Character Content Authoring Guide")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < play_index
    assert play_index < character_state_index < ruling_index < bridge_index
    assert bridge_index < map_index < contract_index < guide_index
    assert guide_index < surfaces_index
    assert '<details className="book-imports" open>' in text
    assert 'name=class-first-run part="imports"' in text
    assert 'name=class-first-run part="body"' in text
    assert "create_fighter(" in text
    assert "create_barbarian(" in text
    assert "create_sorcerer(" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "fighter: hp=44, features=Second Wind Feature, Action Surge Feature, Extra Attack" in text
    assert "fighter resources: second_wind=1/1, action_surge=1/1, extra_attacks=1/1" in text
    assert "fighter buttons: Second Wind=yes, Action Surge=yes" in text
    assert "barbarian: hp=50, features=Rage Feature, Frenzy Feature, Fast Movement" in text
    assert "barbarian buttons: Frenzy=yes, Reckless Attack=yes" in text
    assert "sorcerer resources: sorcery_points=5/5, level3_slots=2" in text
    assert "sorcerer buttons: Quickened=yes, Twinned=yes, Fire Bolt=yes" in text
    assert "That is the character-content promise." in text
    assert "The previous chapter taught spell families" in text
    assert "This chapter decides which actors own those capabilities" in normalized_text
    assert "which class choices grant them" in normalized_text
    assert "the authored character recipe that assembles engine surfaces into a playable identity" in normalized_text
    assert "Class features are the game's character-building layer" in text
    assert "| Product question | Character-content answer |" in text
    assert "Factories attach named class and subclass features" in text
    assert "Class resources live in `ActionEconomy`" in text
    assert "Feature-granted action templates join the same action-discovery surface" in text
    assert "Feature conditions own modifiers, result processors" in text
    assert "Rage, Frenzy, Reckless Attack, Action Surge, and metamagic" in text
    assert "Character sheets and action bars can show class identity" in text
    assert "| D&D character idea | Engine behavior |" in text
    assert "A factory config selects ability growth, hit dice, equipment" in text
    assert "resources store uses such as `rage`, `second_wind`" in text
    assert "The feature registers an action template" in text
    assert "A feature condition owns modifiers for Armor Class" in text
    assert "Event handlers and result processors watch attacks" in text
    assert "Rest routines refill the resources" in text
    assert "The examples build one character-content thread in six moves:" in text
    assert "| Example move | Character-content surface learned |" in text
    assert "Build three classed actors from factory configs." in text
    assert "Create fighter, barbarian, and sorcerer actors from factories." in text
    assert "Spend Second Wind and Action Surge, then short rest." in text
    assert "Enter Berserker Frenzy and remove Rage." in text
    assert "Apply Quickened Spell to Fire Bolt." in text
    assert "Attach Lucky and process d20 results." in text
    assert "Every character-content rule answers seven questions:" in text
    assert "Factory config fields such as level, fighting style" in text
    assert "`rage`, `second_wind`, `action_surge`, `extra_attacks`" in text
    assert "Registered action templates such as `Second Wind`, `Action Surge`" in text
    assert "Event handlers and processors attach to attacks" in text
    assert "Removing the feature condition removes the resource" in text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "Author character content as owned actor state inside the shared ruleset." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Start from the build recipe." in text
    assert "Add limited-use resources." in text
    assert "Turn active features into buttons." in text
    assert "Put passive features in conditions." in text
    assert "Model modes as temporary state." in text
    assert "Choose the timing surface." in text
    assert "Define rest and reset behavior." in text
    assert "Prove ownership removal." in text
    assert re.search(
        r"A\s+fighter\s+action,\s+barbarian\s+mode,\s+sorcerer\s+metamagic",
        text,
    )
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_class_features_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 15 examples print class-feature transcripts, not assert-only bodies."""
    text = (manual_root() / "15-class-features-factories-and-feats.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "fighter: hp=44, features=Second Wind Feature, Action Surge Feature, Extra Attack",
        "fighter resources: second_wind=1/1, action_surge=1/1, extra_attacks=1/1",
        "sorcerer buttons: Quickened=yes, Twinned=yes, Fire Bolt=yes",
        (
            "fighter factory: hp=44, features=yes/yes/yes, "
            "extra_attacks=1, action_surge=1, second_wind_button=yes"
        ),
        "barbarian factory: hp=50, features=yes/yes/yes, rage=3, frenzy_button=yes",
        (
            "sorcerer factory: hp=37, features=yes/yes, "
            "resources=sorcery_points=5, level3_slots=2, buttons=yes/yes/yes"
        ),
        "initial fighter: hp=20, second_wind=1, action_surge=1, buttons=yes/yes",
        "second wind: canceled=no, hp=10->18, resource=0, bonus=0",
        "action surge: canceled=no, actions=1->2, resource=0, condition=yes",
        "short rest: second_wind=1, action_surge=1",
        "initial berserker: rage=3, frenzy_button=yes",
        (
            "after frenzy: canceled=no, rage=2, raging=yes, frenzied=yes, "
            "strike=yes, linked=yes"
        ),
        "after rage cleanup: raging=no, frenzied=no, strike=no",
        "before quickened: sorcery_points=3, alt_cost=none, cost=actions",
        (
            "after quickened: canceled=no, sorcery_points=1, active=yes, "
            "alt_cost=bonus_actions, cost=bonus_actions"
        ),
        "after fire bolt: canceled=no, outcome=Hit, hp=60->56, actions=1, bonus=0",
        "cleanup: active=no, alt_cost=none",
        "lucky attached: active=yes, luck=3, handler=yes",
        "owner low roll: modified=yes, original=4, effective=20, luck=2",
        "ignored rolls: other=yes, acceptable=yes, luck=2",
        "cleanup: active=no, handler=no, resource=no",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_monsters_chapter_frontloads_preset_actor_contract() -> None:
    """Chapter 16 starts with a runnable stat-block actor readout."""
    text = (manual_root() / "16-monsters-and-preset-actors.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Turn Stat Blocks Into Actors")
    first_example_index = text.index('<ExampleBlock id="EB-16-000"')
    play_index = text.index("## What This Means In Play")
    monster_state_index = text.index("## Monster State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Monster Stat Blocks Become Runtime Actors")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Preset Actor Contract")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    guide_index = text.index("## Preset Actor Authoring Guide")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < play_index
    assert play_index < monster_state_index < ruling_index < bridge_index
    assert bridge_index < map_index < contract_index < guide_index
    assert guide_index < surfaces_index
    assert '<details className="book-imports" open>' in text
    assert 'name=monster-first-run part="imports"' in text
    assert 'name=monster-first-run part="body"' in text
    assert "create_goblin(" in text
    assert "create_skeleton(" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "goblin: hp=10, ac=15, dex_mod=2, darkvision=yes" in text
    assert "goblin loadout: melee=Scimitar, ranged=Shortbow" in text
    assert "goblin actions: melee=yes, ranged=yes, nimble_hide=yes" in text
    assert "skeleton: hp=17, type=undead, darkvision=yes, opt_out_darkvision=no" in text
    assert "skeleton traits: bludgeoning=Vulnerability, poison=Immunity" in text
    assert "condition attempts canceled: poisoned=yes, exhaustion=yes" in text
    assert "active blocked conditions: Poisoned=no, Exhaustion=no" in text
    assert "That is the preset-actor promise." in text
    assert "The previous chapter taught authored character identity" in text
    assert "This chapter applies the same recipe idea to opposition and support actors" in normalized_text
    assert "same entity, action, equipment, spell, item, condition, perception, and encounter systems" in normalized_text
    assert "Monster presets are the game's authored opposition layer" in text
    assert "| Product question | Preset-owned answer |" in text
    assert "The preset names the creature, role, faction" in text
    assert "ordinary ability, health, equipment, inventory, action, spell" in text
    assert "monster-specific actions all appear through action discovery" in text
    assert "Role presets choose gear, HP, AC, stats, spell lists" in text
    assert "Marks, cooldowns, concentration, conditions, immunities" in text
    assert "Encounter setup, controllers, action bars, combat logs" in text
    assert "| D&D monster idea | Engine behavior |" in text
    assert "`EntityConfig` sets the actor name, creature type" in text
    assert "Ability, health, movement, proficiency, equipment" in text
    assert "Sense modes, damage resistances, damage immunities" in text
    assert "monster actions become discoverable action rows" in text
    assert "Inventory items and equipped items use the same item ownership" in text
    assert "Role factories choose loadout, spells, features" in text
    assert "targeted, controlled, damaged, healed, moved" in text
    assert "The examples build one preset-actor thread in six moves:" in text
    assert "| Example move | Preset actor surface learned |" in text
    assert "Turn goblin and skeleton stat blocks into actors." in text
    assert "Create goblin and skeleton stat-block actors." in text
    assert "Inspect goblin Nimble Escape." in text
    assert "Create a generic caster preset." in text
    assert "Create skeleton warrior, archer, and warlock roles." in text
    assert "Use Mark Target and remove concentration." in text
    assert "A preset actor is a complete playable entity recipe." in text
    assert "Every preset actor rule answers seven questions:" in text
    assert "ability scores, hit points, equipment" in text
    assert "Standard actions plus attack" in text
    assert "Starting position, faction" in text
    assert "immediately usable by encounters" in text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text
    assert "controllers. Monster presets enter the ordinary actor runtime" in text
    assert "Author a monster or preset actor as a complete entity recipe." in text
    assert "| Authoring step | Use this surface | Result |" in text
    assert "Start from the battlefield role." in text
    assert "Build one live entity." in text
    assert "Install senses and defenses." in text
    assert "Add attacks and special actions." in text
    assert "Put gear and loot in item state." in text
    assert "Own unusual behavior with conditions." in text
    assert "Keep role variants composable." in text
    assert "Leave the actor ready for play." in text
    assert "a prepared entity using the same action, item, spell" in text


def test_monsters_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 16 examples print preset-actor transcripts, not assert-only bodies."""
    text = (manual_root() / "16-monsters-and-preset-actors.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "goblin: hp=10, ac=15, dex_mod=2, darkvision=yes",
        "goblin actions: melee=yes, ranged=yes, nimble_hide=yes",
        "active blocked conditions: Poisoned=no, Exhaustion=no",
        (
            "goblin base: hp=10, ac=15, dex_mod=2, darkvision=yes, "
            "melee=Scimitar, ranged=Shortbow"
        ),
        "goblin actions: melee=yes, ranged=yes, nimble=yes",
        (
            "skeleton traits: bludgeoning=Vulnerability, poison=Immunity, "
            "poisoned_gate=yes, exhaustion_gate=yes"
        ),
        (
            "blocked conditions: poisoned_event=yes, exhaustion_event=yes, "
            "active_poisoned=no, active_exhaustion=no"
        ),
        "standard costs: hide=['actions'], disengage=['actions']",
        "nimble costs: hide=['bonus_actions'], disengage=['bonus_actions']",
        "nimble disengage: canceled=no, actions=1, bonus=0, condition=yes",
        (
            "caster numbers: spellcaster=yes, ability=charisma, cha_mod=4, "
            "prof=3, attack=7, dc=15"
        ),
        "caster durability: hit_dice=5d6, mode=maximums, hp=40, level3_slots=3",
        "caster actions: spells=9/9, dagger=Dagger, attack=yes, shield_handler=yes",
        (
            "caster potions: invisibility=Drink Greater Invisibility Potion, "
            "invisibility_costs=0, haste=Drink Haste Potion, haste_costs=0"
        ),
        "warrior: hp=31, ac=15, melee=Longsword + Wooden Shield, acid=yes, attack=yes",
        (
            "archer: hp=24, ac=13, dex_mod=3, ranged=Shortbow, "
            "melee=Dagger + Dagger, mark=yes"
        ),
        "warlock: hp=17, cha_mod=2, slots=1:2/2:1, melee=Arcane Staff, scroll=yes",
        "role spread: hp_order=31>24>17, warlock_spells=yes, target=Manual Target",
        "mark target: canceled=no, marked=yes, concentrating=yes, cooldown=yes, bonus=0",
        (
            "mark ownership: linked=yes, attacker_advantage=yes, "
            "blocks_invisible=yes, blocks_hidden=yes"
        ),
        (
            "after concentration cleanup: concentrating=no, marked=no, "
            "blocks_invisible=no, blocks_hidden=no, marked_modifier=no"
        ),
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_encounters_chapter_frontloads_running_game_contract() -> None:
    """Chapter 17 starts with a runnable encounter turn and log readout."""
    text = (manual_root() / "17-encounters-turns-and-controllers.mdx").read_text(
        encoding="utf-8"
    )

    first_run_index = text.index("## First Run: Open A Turn And Record An Attack")
    first_example_index = text.index('<ExampleBlock id="EB-17-000"')
    play_index = text.index("## What This Means In Play")
    encounter_state_index = text.index("## Encounter State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Combat Becomes A Running Encounter")
    map_index = text.index("## Chapter Map")
    product_hinge_index = text.index("## How Engine Pieces Become A Running Game")
    contract_index = text.index("## The Running-Game Contract")
    authoring_index = text.index("## Encounter Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    normalized_text = text.replace("\n", " ")

    assert first_run_index < first_example_index < play_index
    assert play_index < encounter_state_index < ruling_index < bridge_index
    assert (
        bridge_index
        < map_index
        < product_hinge_index
        < contract_index
        < authoring_index
        < surfaces_index
    )
    assert '<details className="book-imports" open>' in text
    assert 'name=encounter-first-run part="imports"' in text
    assert 'name=encounter-first-run part="body"' in text
    assert "Encounter.execute_action()" in text
    assert "fixed_dice_faces(12, 4)" in text
    assert 'print("\\n".join(readout_lines))' in text
    assert '<p className="example-output-label">Result</p>' in text
    assert "encounter: Manual Encounter, state=active, active=True" in text
    assert "initiative order: ['Manual Hero', 'Manual Skeleton']" in text
    assert "turn: round=1, index=0, actor=Manual Hero, state=in_progress" in text
    assert "turn budgets: actions=1, bonus=1, movement=30" in text
    assert "visible enemies: ['Manual Skeleton']" in text
    assert "attack event: type=attack, phase=completion, outcome=Hit" in text
    assert "damage: rolls=[4], total=6, hp=17->11" in text
    assert "combat log: entries=2, last_type=attack" in text
    assert "That is the running-game promise." in text
    assert "The previous chapter taught authored opposition" in text
    assert "This chapter puts those actors on the table." in normalized_text
    assert "records completed events, and decides the result of the scene" in normalized_text
    assert "Encounters are the game's running-scene layer" in text
    assert "| Product question | Encounter-owned answer |" in text
    assert "Combatants wrap live entities with controller ownership" in text
    assert "Initiative order, round number, turn index" in text
    assert "waits for a player, Codex, automation, or an explicit pass" in text
    assert "completed top-level events become encounter combat-log entries" in text
    assert "Current actor, round, turn state, action context" in text
    assert "ends by faction survival once only one living side remains" in text
    assert "| D&D combat idea | Engine behavior |" in text
    assert "Live `Entity` objects become encounter combatants" in text
    assert "Initiative rolls populate `initiative_order`" in text
    assert "`round_number`, `current_turn_index`, `start_turn()`" in text
    assert "A `Controller` receives `TurnContext`" in text
    assert "same action and event pipeline used outside encounters" in text
    assert "Completed top-level events generate combat-log entries stored" in text
    assert "faction survival decides whether the encounter is complete" in text
    assert re.search(
        r"the\s+first\s+layer\s+where\s+the\s+engine\s+becomes\s+a\s+playable\s+"
        r"product\s+loop",
        text,
    )
    assert "The examples build one encounter thread in six moves:" in text
    assert "| Example move | Encounter surface learned |" in text
    assert "Open a turn and record an attack." in text
    assert "Start an ordered encounter, then end it manually." in text
    assert "Start and end turns across a round boundary." in text
    assert "Advance through a pass-controlled monster to a human hero." in text
    assert "Execute an attack through the encounter." in text
    assert "Drop one faction and run death checks." in text
    assert "Live `Entity` objects." in text
    assert "Registered actions, spells, items, and monster abilities." in text
    assert "Events and combat logs." in text
    assert "This is the product hinge of the manual." in text
    assert "The encounter is the developer-DM loop" in text
    assert "Every encounter rule answers seven questions:" in text
    assert "Each live `Entity` receives a `CombatantState`" in text
    assert "`start_turn()` refreshes the acting entity" in text
    assert "human/Codex input boundary" in text
    assert "Completed top-level events generate combat-log entries" in text
    assert "faction survival leaves one side alive" in text
    assert "Build an encounter by deciding what the scene needs the runtime table to own." in text
    assert "| Authoring step | Runtime result |" in text
    assert "Choose live actors." in text
    assert "Assign a controller to every actor." in text
    assert "Establish initiative." in text
    assert "Open the scene." in text
    assert "Open turns deliberately." in text
    assert "Route choices through the encounter." in text
    assert "Publish what happened." in text
    assert "Close by state." in text
    assert "prepare actors, attach controllers, start the table" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_encounters_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 17 examples print running-game transcripts, not assert-only bodies."""
    text = (manual_root() / "17-encounters-turns-and-controllers.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "encounter: Manual Encounter, state=active, active=True",
        "initiative order: ['Manual Hero', 'Manual Skeleton']",
        "turn budgets: actions=1, bonus=1, movement=30",
        "attack event: type=attack, phase=completion, outcome=Hit",
        "damage: rolls=[4], total=6, hp=17->11",
        "combat log: entries=2, last_type=attack",
        (
            "started: state=active, active=True, round=1, "
            "turn_state=not_started, order=['Manual Hero', 'Manual Skeleton']"
        ),
        "start callbacks: hero=['Manual Hero'], monster=['Manual Skeleton']",
        "ended: reason=manual scene complete, state=ended, active=False",
        "end callbacks: hero=['Manual Hero'], monster=['Manual Skeleton']",
        (
            "hero turn start: event=Turn Start, state=in_progress, "
            "actor=Manual Hero, round=1, index=0, budgets=1/1/30, "
            "visible=['Manual Skeleton']"
        ),
        (
            "hero turn end: event=Turn End, state=ended, acted=yes, "
            "turn_count=1, callback_actor=Manual Hero"
        ),
        "next actor: actor=Manual Skeleton, index=1, round=1",
        "new round: actor=Manual Hero, index=0, round=2, hero_acted=no, monster_acted=no",
        "advance result: status=waiting_for_human, entity=Manual Hero, round=1, index=1",
        (
            "encounter state: current=Manual Hero, turn_state=in_progress, "
            "monster_turns=1, hero_turns=0"
        ),
        "executed attack: canceled=no, outcome=Hit, damage=6, hp=17->11",
        (
            "combat log capture: entries=2, latest=attack, "
            "listener=(1, 'attack'), since_count=1, since_latest=yes"
        ),
        "death check: hp=17->0, events=1, monster_dead=yes, condition=yes",
        "encounter end: state=ended, active=no, alive=['Manual Hero'], dead=['Manual Skeleton']",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_encounter_chapter_frames_ending_as_engine_dm_policy() -> None:
    """Chapter 17 presents encounter ending as an owned engine rule."""
    text = (manual_root() / "17-encounters-turns-and-controllers.mdx").read_text(
        encoding="utf-8"
    )
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    assert "The engine owns the dungeon-master decision" in prose
    assert "NeuroDragon's encounter policy is faction survival" in prose
    assert "explicit-pass controller examples" in prose
    assert "actor chooses an explicit pass" in prose
    assert "no live dungeon master" not in prose.lower()
    assert "no-action" not in prose.lower()
    assert "no autonomous action" not in prose.lower()


def test_sessions_chapter_frontloads_client_contract() -> None:
    """Chapter 18 explains the client protocol before executable examples."""
    text = (manual_root() / "18-sessions-apis-and-client-payloads.mdx").read_text(
        encoding="utf-8"
    )

    play_index = text.index("## What This Means In Play")
    session_state_index = text.index("## Session State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How A D&D Table Becomes A Client Session")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Client Contract")
    authoring_index = text.index("## Client Surface Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")
    normalized_text = text.replace("\n", " ")

    assert play_index < session_state_index < ruling_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter taught the running encounter" in text
    assert "This chapter exposes that running loop to clients." in normalized_text
    assert "which engine-authored rows they may choose" in normalized_text
    assert "which cursors describe what changed after a command resolves" in normalized_text
    assert "Sessions are the game's client-participation layer" in text
    assert "| Product question | Session-owned answer |" in text
    assert "`PlayerSession` records participant identity" in text
    assert "`GameSession` maps controlled entity UUIDs" in text
    assert "State payloads serialize entities, grid cells, floor objects" in text
    assert "Available-action payloads expose engine-authored action rows" in text
    assert "Execution payloads send session, actor, template name, and target index" in text
    assert "Action results, event cursors, combat-log cursors" in text
    assert "| D&D table idea | Client and runtime behavior |" in text
    assert "`/session/create` creates a `PlayerSession`" in text
    assert "`/game/join` assigns entity UUIDs" in text
    assert "`/state` serializes `APIGameState`" in text
    assert "session ping payloads identify the acting entity and owner" in text
    assert "engine-authored action rows and stable target indices" in text
    assert "`/action/execute` validates session ownership and turn state" in text
    assert "`/events`, `/combat-log`, stream IDs" in text
    assert "`/catalog/spells` exposes spell metadata" in text
    assert "The examples build one client-contract thread in five moves:" in text
    assert "| Example move | Client surface learned |" in text
    assert "Create a session, join the game, and ping turn ownership." in text
    assert "Read state, current turn, and available actions." in text
    assert "Execute the discovered melee attack by target index." in text
    assert "Read events, combat logs, and an SSE frame." in text
    assert "Read spell catalog metadata." in text
    assert "The client contract turns the running encounter into a playable network surface." in text
    assert "Every client-facing rule answers seven questions:" in text
    assert "A `PlayerSession` created by `/session/create`" in text
    assert "A `GameSession` maps entity UUIDs to session UUIDs" in text
    assert "`/entity/{entity_uuid}/available-actions` returns engine-generated action rows" in text
    assert "`/action/execute` sends `session_id`, `entity_uuid`, `template_name`, and `target_index`" in text
    assert "`ActionResult`, `/events`, `/combat-log`, stream IDs" in text
    assert (
        "Expose an encounter to a client by making every screen and command flow from "
        "engine-owned state."
        in normalized_text
    )
    assert "| Authoring step | Runtime result |" in text
    assert "Create a participant identity." in text
    assert "Join the active game." in text
    assert "Render from snapshots." in text
    assert "Show turn ownership." in text
    assert "Build controls from action rows." in text
    assert "Submit the chosen row." in text
    assert "Advance the client from cursors." in text
    assert "Fill menus from catalogs." in text
    assert "join, claim actors, draw the snapshot" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_sessions_chapter_frames_client_authority_positively() -> None:
    """Chapter 18 presents clients as renderers of engine-authored choices."""
    text = (manual_root() / "18-sessions-apis-and-client-payloads.mdx").read_text(
        encoding="utf-8"
    )
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    assert "The engine authors legal action rows and stable target indices" in prose
    assert "preserves the engine-provided target index" in prose
    assert "does not calculate legality" not in prose
    assert "invent targets" not in prose
    assert "inventing its own target binding" not in prose


def test_sessions_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 18 examples print API payload transcripts, not assert-only bodies."""
    text = (manual_root() / "18-sessions-apis-and-client-payloads.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "session created: status=200, type=human, name=Manual Player",
        "join result: success=yes, game_matches=yes, controlled=1",
        "turn ping: my_turn=yes, active=Manual Hero, controlled=1",
        "game status: active=yes, encounter=yes, session_turn=yes",
        "state snapshot: entities=['Manual Hero', 'Manual Skeleton'], current=Manual Hero",
        "turn payload: controller=human, waiting=yes, actions=1",
        (
            "action menu: entity=Manual Hero, "
            "attacks=['Attack_MELEE_MAIN', 'Attack_RANGED_MAIN'], target_index=0"
        ),
        "status echo: session_seen=yes, actions_remaining=1",
        "execute result: success=yes, event=attack_melee_main, turn_continues=yes",
        "hit points: monster=17->11, hero=10",
        "returned state: current=Manual Hero, actions_remaining=0, ended=no",
        "cursors: events=78, logs=2, log_entries=1",
        "event history: route_count=78, total=78, completions=19",
        "combat log: route_count=2, total=2, latest_type=attack",
        "stream cursors: event=78, combat=2",
        "sse frame: id=id: e=78;l=2, event_line=event: combat_log",
        "catalog response: status=200, version=2026-05-03.1, spells=109",
        "fire bolt: category=spell, attack_roll=yes, range=120",
        "magic missile: multi_target=yes",
        "fireball: aoe=sphere, damage_types=['Fire']",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 5
    assert text.count('print("\\n".join(readout_lines))') == 5
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_map_editor_chapter_frontloads_authoring_contract() -> None:
    """Chapter 19 explains scenario authoring before executable examples."""
    text = (manual_root() / "19-map-editor-and-scenario-authoring.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Authoring State In The Game Loop")
    ruling_index = text.index("## Ruling Role")
    bridge_index = text.index("## How D&D Places Become Authoring Documents")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Authoring Contract")
    authoring_index = text.index("## Map Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < ruling_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter taught the client contract for a running encounter" in text
    assert "This chapter uses the same API discipline for preparation." in normalized_text
    assert "An authoring client sends commands too" in normalized_text
    assert "before actors, turns, controllers, initiative, and combat logs enter it" in normalized_text
    assert "Map authoring is the game's prepared-space layer." in text
    assert "| Product question | Authoring-owned answer |" in text
    assert "Scratch and preset map creation define the grid bounds" in text
    assert "Tile patches change terrain, movement cost, light" in text
    assert "Catalog placement creates doors, torches, levers" in text
    assert "Map snapshots and layer payloads expose tiles" in text
    assert "Save documents serialize the entity-free snapshot" in text
    assert "Scenario and arena routes place actors, sessions, controllers" in text
    assert "| D&D place idea | Authoring behavior |" in text
    assert "`/mapeditor/catalog` returns terrain, environment objects" in text
    assert "`/mapeditor/maps` creates a scratch or preset map" in text
    assert "`/mapeditor/map/tiles` paints terrain" in text
    assert "`/mapeditor/map/objects` places doors, torches" in text
    assert "Walkability, visibility, and light routes expose map-wide layers" in text
    assert "`/mapeditor/saves` stores reloadable map documents" in text
    assert "Running modes create actors, controller ownership" in text
    assert "The examples build one authored-room thread in six moves:" in text
    assert "| Example move | Authoring surface learned |" in text
    assert "Choose the palette and open a blank room." in text
    assert "Paint terrain, light, and a directional border." in text
    assert "Place a door and a lit torch, then read objective layers." in text
    assert "Delete placed objects from the authored room." in text
    assert "Save, reload, list, and delete the authored room." in text
    assert "Open a preset arena and move back from play to authoring." in text
    assert "The authoring contract turns map design into a repeatable payload workflow." in text
    assert "Every map-authoring rule answers seven questions:" in text
    assert "`/mapeditor/catalog` returns preset maps" in text
    assert "`/mapeditor/map/tiles` applies terrain, light" in text
    assert "`/mapeditor/map/objects` instantiates catalog objects" in text
    assert "Walkability, visibility-blocker, and light routes" in text
    assert "`/mapeditor/saves` stores reloadable map documents" in text
    assert "Author a scenario space by treating the map as the first playable artifact." in text
    assert "| Authoring step | Runtime result |" in text
    assert "Choose the palette." in text
    assert "Open an authoring document." in text
    assert "Paint tile rules." in text
    assert "Place authored objects." in text
    assert "Inspect objective layers." in text
    assert "Remove or revise placements." in text
    assert "Save the document." in text
    assert "Hand the space to play." in text
    assert "choose stable catalog IDs, open the map document" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_map_editor_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 19 examples print authoring payload transcripts, not assert-only bodies."""
    text = (manual_root() / "19-map-editor-and-scenario-authoring.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "catalog core: presets=yes, tiles=yes, objects=yes, loot=yes",
        "scratch map: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, tiles=12, objects=0",
        "origin tile: name=Floor, light=1",
        "play state: entities=0, encounter=none, entity_route=0",
        "wall patch: name=Wall, walkable=no, visible=no, light=4",
        "border patch: tile=Floor, east_blocks_movement=yes",
        "snapshot: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, tiles=12, objects=0",
        "placed door: name=Door, position=[12, 21], blocks=yes, open=no",
        "placed torch: name=Wall Torch, position=[13, 20], lit=yes",
        "walkability: wall=Wall, door=Door",
        "visibility: wall=Wall, door=Door",
        "light layer: torch_cell=4",
        "delete by uuid: status=200, remaining=['Wall Torch']",
        "delete by position: status=200, remaining=[]",
        "save result: status=200, id=tutorial_room, tiles=12, objects=2",
        "document: schema=1, name=Tutorial Room, placements=['door', 'wall_torch']",
        (
            "loaded map: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, "
            "tiles=12, objects=['Door', 'Wall Torch']"
        ),
        "save list/delete: first=tutorial_room, delete_status=204",
        "preset map: status=200, bounds={'min_x': 0, 'min_y': 0, 'max_x': 14, 'max_y': 14}, tiles=225",
        "preset objects: walls=8, doors=1, potions=2, torches=2, levers=1",
        "preset play state: entities=0, encounter=none",
        "running game: status=200, entities=4, encounter=yes",
        (
            "return to editor: status=200, bounds={'min_x': 0, 'min_y': 0, "
            "'max_x': 1, 'max_y': 1}, entities=0, encounter=none"
        ),
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_content_extension_chapter_frontloads_extension_contract() -> None:
    """Chapter 20 explains content extension structure before examples."""
    text = (manual_root() / "20-content-extension-basics.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Extension State In The Game Loop")
    bridge_index = text.index("## How D&D Content Ideas Become Engine Extensions")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Extension Contract")
    authoring_index = text.index("## Content Extension Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter taught authored spaces" in text
    assert "This chapter teaches authored rules." in normalized_text
    assert "A content pack defines a new tactical rule" in normalized_text
    assert "lasting state, player intent, portable use, actor reuse" in normalized_text
    assert "Content extension is the game's new-rule composition layer." in text
    assert "| Product question | Extension-owned answer |" in text
    assert "A condition owns the modifiers, handlers, duration" in text
    assert "An action template makes the rule visible through action discovery" in text
    assert "A usable item carries the same action template" in text
    assert "Actor and scene factories assemble ordinary entities" in text
    assert "The content returns the same action rows, item-use rows" in text
    assert "Condition removal, item charges, event completion" in text
    assert "| D&D content idea | Extension behavior |" in text
    assert "A `BaseCondition` owns modifiers, event handlers" in text
    assert "A `BaseAction` validates the target" in text
    assert "A `UsableItem` carries action templates through inventory" in text
    assert "An actor factory creates an ordinary `Entity`" in text
    assert "A scene factory places actors, objects, terrain" in text
    assert "Action discovery returns the new action rows" in text
    assert "Condition removal, item charges, action costs" in text
    assert "The examples build one Field Focus content pack in six moves:" in text
    assert "| Example move | Extension surface learned |" in text
    assert "Import the content pack and inspect its public shape." in text
    assert "Apply and remove the custom condition directly." in text
    assert "Register and execute the custom action." in text
    assert "Package the same action in a carried item." in text
    assert "Drop the item as a nearby floor object." in text
    assert "Compose the actor and training scene factories." in text
    assert "The extension contract turns a game idea into content the engine can discover" in text
    assert "Every content-extension rule answers seven questions:" in text
    assert "`dnd.extensions.field_focus` exposes the public condition" in text
    assert "A `BaseCondition` owns modifiers" in text
    assert "A `BaseAction` validates targets" in text
    assert "A `UsableItem` carries action templates" in text
    assert "Discovery, indexed execution, event completion" in text
    assert (
        "Author new content by deciding which runtime surface owns each part of the game "
        "idea."
        in normalized_text
    )
    assert "| Authoring step | Runtime result |" in text
    assert "Name the content pack." in text
    assert "Model lasting state." in text
    assert "Model player intent." in text
    assert "Package portable use." in text
    assert "Attach content to actors." in text
    assert "Compose a teaching scene." in text
    assert "Verify discovery and cleanup." in text
    assert "create the importable module, make the ongoing rule a condition" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "Treat a content pack as a reusable authored bundle inside the shared runtime." in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_content_extension_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 20 examples print content-pack transcripts, not assert-only bodies."""
    text = (manual_root() / "20-content-extension-basics.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "module surfaces: condition=Field Focus, action=Deploy Field Focus, target=self, cost=bonus_actions",
        "condition defaults: movement=+10, armor=+1, field=Bonus feet of movement while focused.",
        "factories: kit=yes, medic=yes, scene=yes",
        "apply event: phase=completion, active=True, modifiers=2",
        "bonuses active: movement=30->40, ac=15->16",
        "after cleanup: active=False, movement=30, ac=15",
        "discovered action: name=Deploy Field Focus, target=self, index=0, cost=bonus_actions",
        "execution: phase=completion, condition=True, bonus_actions=0",
        "after refresh: action_available=False, bonus_actions=1",
        "carried kit: looted=yes, item=Field Kit, charges_start=1",
        "item action: display=Deploy Field Focus (Field Kit), is_item=yes, source_matches=yes",
        "after use: phase=completion, charges=0, condition=True",
        "after refresh: item_action_available=False",
        "floor kit sensed: position=(1, 2), visible=yes",
        "floor action: display=Deploy Field Focus (Field Kit), is_item=yes, source_matches=yes",
        "scene actors: medic=Field Medic, ally=Field Ally, medic_pos=(1, 1), ally_pos=(2, 1)",
        (
            "actions: actor=Deploy Field Focus, carried=Deploy Field Focus (Field Kit), "
            "floor=Deploy Field Focus (Field Kit)"
        ),
        "kits: carried_in_inventory=yes, floor_visible=yes, floor_pos=(1, 2)",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_spell_feature_chapter_frontloads_spell_feature_contract() -> None:
    """Chapter 21 explains feature-granted spell structure before examples."""
    text = (manual_root() / "21-spell-and-feature-extensions.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Spell-Feature State In The Game Loop")
    bridge_index = text.index("## How D&D Feature Magic Becomes A Spell Extension")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Spell-Feature Contract")
    authoring_index = text.index("## Spell-Feature Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter built Field Focus as a content pack" in text
    assert "This chapter takes the same extension discipline into learned magic." in normalized_text
    assert "Instead of adding a portable field kit" in normalized_text
    assert "a character feature that teaches a spell" in normalized_text
    assert "Feature-granted spell content is the game's learned-magic composition layer." in text
    assert "| Product question | Spell-feature-owned answer |" in text
    assert "A feature condition registers the spell template" in text
    assert "Action discovery exposes the spell as a normal spell action" in text
    assert "Target filtering combines self-targeting, ally checks" in text
    assert "Indexed execution creates a `SpellEvent`, validates the chosen target" in text
    assert "The effect condition owns the Armor Class modifier" in text
    assert "Feature cleanup unregisters the spell template" in text
    assert "| D&D feature-magic idea | Extension behavior |" in text
    assert "`AegisTrainingFeature` registers a spell template" in text
    assert "A `SpellAction` such as `AegisSpark` enters action discovery" in text
    assert "`include_self`, `valid_target_filter`, range checks" in text
    assert "Indexed execution creates a `SpellEvent`, validates the selected target" in text
    assert "A `BaseCondition` such as `AegisSparkEffect` owns the Armor Class modifier" in text
    assert "Feature cleanup unregisters the spell template" in text
    assert "Actor and scene factories create trained spell users" in text
    assert "The examples build one Aegis Spark spell-feature pack in five moves:" in text
    assert "| Example move | Spell-feature surface learned |" in text
    assert "Import the spell-feature pack and inspect its public shape." in text
    assert "Let the feature grant and remove the spell template." in text
    assert "Discover the self-or-ally spell targets." in text
    assert "Resolve the spell as a real spell event." in text
    assert "Compose the trained caster scene." in text
    assert "The spell-feature contract turns a learned ability into a normal spell choice." in text
    assert "Every spell-feature extension answers seven questions:" in text
    assert "`dnd.extensions.aegis_spark` exposes the effect condition" in text
    assert "A `BaseCondition` such as `AegisSparkEffect` owns the Armor Class modifier" in text
    assert "A `SpellAction` such as `AegisSpark` defines spell level" in text
    assert "`AegisTrainingFeature` registers the spell template" in text
    assert "Indexed execution creates a `SpellEvent`" in text
    assert "Author feature-granted magic by separating the owner of training" in text
    assert "| Authoring step | Runtime result |" in text
    assert "Name the spell-feature pack." in text
    assert "Model the lingering spell state." in text
    assert "Model the castable spell." in text
    assert "Model the training owner." in text
    assert "Define legal targets through discovery." in text
    assert "Resolve through spell execution." in text
    assert "Compose trained scenes." in text
    assert "make the feature the spell teacher, make the spell the castable choice" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_spell_feature_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 21 examples print spell-feature transcripts, not assert-only bodies."""
    text = (manual_root() / "21-spell-and-feature-extensions.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "module surfaces: spell=Aegis Spark, level=0, school=abjuration, target=entity",
        "target policy: include_self=yes, filter=self_or_allies, range=30",
        "owners: effect_ac=+2, feature=Aegis Training, caster_level=1, scene_factory=yes",
        "feature applied: phase=completion, active=True, template=yes",
        "registered spell: is_spell=yes, template=yes, caster_level=5",
        "feature removed: active=False, template=no",
        "spell row: target=entity, category=spell, level=0, cast=0, cost=actions",
        "valid targets: ['Shield Ally', 'Aegis Warden']",
        "target filter: ally=yes, caster=yes, enemy=no",
        "spell event: type=SpellEvent, phase=completion, canceled=no, spell=aegis_spark",
        "spell levels: base=0, cast=0, target_index=0",
        "ward active: condition=True, ac=11->13, caster_actions=0",
        "after cleanup: condition=False, ac=11",
        "scene actors: caster=Aegis Warden, ally=Shield Ally, enemy=Training Dummy",
        "feature state: active=True, template=yes",
        "spell targets: ['Shield Ally', 'Aegis Warden']",
        "after feature cleanup: template=no, action_available=False",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 5
    assert text.count('print("\\n".join(readout_lines))') == 5
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_playable_scenario_chapter_frontloads_scenario_contract() -> None:
    """Chapter 22 explains playable scenario packages before examples."""
    text = (manual_root() / "22-playable-scenario-packages.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Scenario State In The Game Loop")
    bridge_index = text.index("## How D&D Adventure Rooms Become Scenario Packages")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Scenario Package Contract")
    authoring_index = text.index("## Scenario Package Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert (
        "The previous chapter taught a learned spell feature as reusable authored content"
        in normalized_text
    )
    assert "This chapter packages authored pieces into a playable room." in normalized_text
    assert "map state, actors, controllers, initiative, turn handoff" in normalized_text
    assert "one startable game mode" in normalized_text
    assert "Scenario packages are the game's ready-to-run adventure-room layer." in text
    assert "| Product question | Scenario-owned answer |" in text
    assert "The scenario reset and factory create the tactical arena" in text
    assert "The scenario creates ordinary `Entity` actors" in text
    assert "Scenario controllers bind actors to human input" in text
    assert "The encounter owns initiative order, round number" in text
    assert "Automated turns advance until the next human or Codex-controlled actor" in text
    assert "Indexed action execution runs the normal action and event pipeline" in text
    assert "Death checks and faction survival decide" in text
    assert "| D&D adventure idea | Scenario package behavior |" in text
    assert "create the tactical arena, map state, actor positions" in text
    assert "ordinary `Entity` actors with factions, equipment" in text
    assert "Scenario controllers bind actors to human input" in text
    assert "An `Encounter` receives combatants, rolls or pins initiative" in text
    assert "`advance_until_player()` runs controller-owned turns" in text
    assert "`execute_action()` resolves the selected template and target index" in text
    assert "Combat logs capture completed events" in text
    assert "faction survival ends the scenario" in text
    assert "The examples build one Gatehouse scenario package in five moves:" in text
    assert "| Example move | Scenario surface learned |" in text
    assert "Import the playable scenario package." in text
    assert "Build the running Gatehouse scenario." in text
    assert "Advance to the playable human turn." in text
    assert "Execute the selected player action." in text
    assert "End the scene by faction survival." in text
    assert "The scenario package contract turns authored content into a ready-to-run game mode." in text
    assert "Every playable-scenario rule answers seven questions:" in text
    assert "`dnd.scenarios.gatehouse` exposes the scenario bundle" in text
    assert "A reset routine clears runtime registries" in text
    assert "Scenario-specific controller classes bind actors" in text
    assert "`advance_until_player()` runs automated turns" in text
    assert "`execute_action()` runs indexed intent" in text
    assert "Author a playable scenario by packaging the whole room boundary." in text
    assert "| Authoring step | Runtime result |" in text
    assert "Name the scenario package." in text
    assert "Reset into the scenario space." in text
    assert "Create the actor cast." in text
    assert "Assign controller ownership." in text
    assert "Start the encounter." in text
    assert "Advance to input." in text
    assert "Execute selected intent." in text
    assert "End by scene state." in text
    assert "prepare the package surface, reset the world, build the map and cast" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_playable_scenario_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 22 examples print scenario transcripts, not assert-only bodies."""
    text = (manual_root() / "22-playable-scenario-packages.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "controllers: human=human, pass=pass",
        "package functions: reset=yes, factory=yes, auto_hit=yes, cleanup=yes",
        "encounter: name=Gatehouse Scenario, state=active, turn_state=not_started, round=1",
        "initiative: ['Gatehouse Skeleton', 'Gatehouse Hero'], active=yes",
        "actors: hero=Gatehouse Hero/heroes, monster=Gatehouse Skeleton/monsters",
        "controllers: hero=human, monster=pass, start=['Gatehouse Hero']",
        "senses: hero_sees_monster=yes",
        "advance: status=waiting_for_human, entity=Gatehouse Hero, round=1, index=1",
        "encounter turn: current=Gatehouse Hero, state=in_progress",
        "automated turn: starts=['Gatehouse Skeleton'], ends=['Gatehouse Skeleton']",
        "human context: actor=Gatehouse Hero, visible_enemies=1, sees_monster=yes",
        "execute: event=attack, phase=completion, canceled=no",
        "damage: hp=17->11, log_entries=4, latest=attack",
        "combat log: source_matches=yes, since_latest=yes",
        "death check: hp=17->0, events=1, dead_condition=yes",
        "encounter end: state=ended, active=no, end_callbacks=['Gatehouse Hero']",
        "survivors: alive=['Gatehouse Hero'], dead=['Gatehouse Skeleton']",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 5
    assert text.count('print("\\n".join(readout_lines))') == 5
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_arena_mode_chapter_frontloads_arena_mode_contract() -> None:
    """Chapter 23 explains the arena game-mode contract before examples."""
    text = (manual_root() / "23-standard-arena-game-modes.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Arena State In The Game Loop")
    bridge_index = text.index("## How D&D Arena Play Becomes A Game Mode")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Arena Mode Contract")
    authoring_index = text.index("## Arena Mode Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter taught a small Gatehouse scenario as one startable room" in text
    assert "This chapter studies the standard arena" in normalized_text
    assert "the built-in reference mode" in normalized_text
    assert "class-selected hero kits, monster-side roles, sessions" in normalized_text
    assert "The standard arena is the game's reference playable mode." in text
    assert "| Product question | Arena-owned answer |" in text
    assert "The arena builder creates the standard grid" in text
    assert "The `character_class` choice creates the fighter" in text
    assert "Skeleton warrior, archer, and warlock factories create the monster faction" in text
    assert "Human mode binds the hero to a human controller" in text
    assert "Session routes create a player session" in text
    assert "State, visibility, controlled-entity, actor-detail" in text
    assert "map builders, actor factories, controller policies" in text
    assert "| D&D arena idea | Game-mode behavior |" in text
    assert "`setup_arena_combat()` builds the standard map" in text
    assert "`character_class` selects fighter, sorcerer, or barbarian" in text
    assert "Skeleton warrior, archer, and warlock factories" in text
    assert "Human mode gives the hero to a human controller" in text
    assert "`/simulation/start-human` builds the encounter" in text
    assert "`/session/create` and `/game/join` bind a human session" in text
    assert "`/state`, `/visibility`, actor detail" in text
    assert "map builder, actor factories, controller assignment" in text
    assert "The examples build one standard arena thread in six moves:" in text
    assert "| Example move | Arena surface learned |" in text
    assert "Import the arena mode surface." in text
    assert "Build the standard arena directly." in text
    assert "Select the hero kit." in text
    assert "Switch monster-side control." in text
    assert "Start human mode and join the hero." in text
    assert "Read the live arena payloads." in text
    assert "The arena mode contract turns a reusable combat format" in text
    assert "setup. It is the product boundary" in text
    assert "Every arena-mode rule answers seven questions:" in text
    assert "`setup_arena_combat()` chooses the arena name" in text
    assert "The standard arena builder creates grid, terrain, walls" in text
    assert "The `character_class` selection creates the fighter" in text
    assert "Skeleton actor factories create the monster faction" in text
    assert "Human mode gives the hero to a human controller" in text
    assert "`/simulation/start-human` builds the encounter" in text
    assert "`/entity/{entity_uuid}/available-actions` expose the live board" in text
    assert "Author a reusable arena mode by packaging the complete product assembly." in text
    assert "| Authoring step | Runtime result |" in text
    assert "Build the arena space." in text
    assert "Select the hero kit." in text
    assert "Compose the opposing side." in text
    assert "Choose the control mode." in text
    assert "Start the live loop." in text
    assert "Let the player claim the hero." in text
    assert "Publish playable state." in text
    assert "Reuse the product recipe." in text
    assert "assemble the environment, choose the hero kit, create the opposing faction" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_arena_mode_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 23 examples print arena transcripts, not assert-only bodies."""
    text = (manual_root() / "23-standard-arena-game-modes.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "status: active=False, game=None, sessions=0",
        "surfaces: client=ArenaApiClient, reset=yes, setup=True, joined=True",
        "readers: entity=True, objects=True, actions=True, inventory=True, equipment=True",
        "encounter: name=Arena Combat, state=not_started, combatants=4",
        "actors: hero=Hero/heroes@(2, 7), warrior=(12, 5), archer=(12, 7), warlock=(12, 9)",
        "controllers: hero=human, warrior=external_ai, archer=external_ai, warlock=external_ai",
        "floor objects: walls=8, doors=1, potions=2, torches=2, levers=1",
        "fighter kit: melee=Shortsword+Dagger, ranged=Longbow, features=['Action Surge', 'Second Wind']",
        "sorcerer kit: spells=['Fire Bolt', 'Fireball', 'Magic Missile'], metamagic=['Quickened Spell', 'Twinned Spell']",
        "barbarian kit: melee=Greataxe, actions=['Frenzy', 'Rage']",
        "encounter: name=PvP Arena, monsters=3",
        "controllers: hero=human, monsters=['codex']",
        "monster names: ['Skeleton Archer', 'Skeleton Warlock', 'Skeleton Warrior']",
        "start: status_code=200, status=waiting_for_human, entity=Hero, encounter=Arena Combat/active",
        "game status: active=True, encounter_active=True, active_matches=True, ai_sessions=1, ai_controls=3",
        "ping: status=200, is_my_turn=True, active_entity=Hero",
        "grid: bounds=(0,0)-(14,14), tiles=225",
        "state: encounter=Arena Combat/active, entities=['Hero', 'Skeleton Archer', 'Skeleton Warlock', 'Skeleton Warrior']",
        "visibility: hero_known=True, position=[2, 7], visible_cells=107, sense_modes=[]",
        "hero detail: controlled=Hero, name=Hero, ac_matches=True",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 6
    assert text.count('print("\\n".join(readout_lines))') == 6
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_controller_chapter_frontloads_turn_contract() -> None:
    """Chapter 24 explains controller turn ownership before examples."""
    text = (manual_root() / "24-built-in-controllers-and-automated-turns.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Controller State In The Game Loop")
    bridge_index = text.index("## How D&D Turn Ownership Becomes Controller Choice")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Controller Turn Contract")
    authoring_index = text.index("## Controller Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert (
        bridge_index
        < map_index
        < contract_index
        < authoring_index
        < surfaces_index
        < first_example_index
    )
    assert "The previous chapter taught the standard arena as the built-in reference mode" in text
    assert "This chapter zooms into the turn boundary inside that mode." in normalized_text
    assert "Once the encounter says which actor is active" in normalized_text
    assert "hands one complete turn to an agent runner" in normalized_text
    assert "Controllers are the game's decision-ownership layer." in text
    assert "| Product question | Controller-owned answer |" in text
    assert "`controller_type` identifies human, Codex, external AI, pass" in text
    assert "`TurnContext` carries the actor UUID, budgets" in text
    assert "Human and Codex controllers keep the turn open" in text
    assert "`PassController` makes pass behavior explicit" in text
    assert "`ExternalAIController` waits for an AI session command" in text
    assert "`AIAgentController` runs a bound turn runner once" in text
    assert "The encounter still owns turn start, action execution" in text
    assert "| D&D turn idea | Controller behavior |" in text
    assert "The encounter owns `initiative_order`, `current_turn_index`" in text
    assert "`controller_type` identifies the decision owner" in text
    assert "`TurnContext` carries actor UUID, round and turn indexes" in text
    assert "`advance_until_player()` keeps the turn waiting" in text
    assert "`PassController` returns the pass signal" in text
    assert "External AI controllers receive legal actions through the session API" in text
    assert "`AIAgentController` calls its bound `TurnRunner.run_turn()`" in text
    assert "Controller choices enter the ordinary action/event pipeline" in text
    assert "The examples build one controller-decision thread in seven moves:" in text
    assert "| Example move | Controller surface learned |" in text
    assert "Import the controller catalogue." in text
    assert "Stop for human or Codex input." in text
    assert "Pass as the chosen turn behavior." in text
    assert "Stop for an external AI subprocess." in text
    assert "Delegate a full turn to an agent runner." in text
    assert "The controller turn contract turns initiative ownership" in text
    assert "Every controller rule answers eight questions:" in text
    assert "The encounter owns initiative order" in text
    assert "`controller_type` identifies whether the actor is owned" in text
    assert "`TurnContext` carries the actor UUID" in text
    assert "`advance_until_player()` return `waiting_for_human`" in text
    assert "`ExternalAIController` waits for session-authorized API commands" in text
    assert "`AIAgentController` calls a bound `TurnRunner.run_turn()`" in text
    assert (
        "Author turn ownership by choosing the controller that matches the actor's "
        "decision source."
        in normalized_text
    )
    assert "| Authoring step | Runtime result |" in text
    assert "Identify the active actor owner." in text
    assert "Provide a turn context." in text
    assert "Use outside-input controllers for players." in text
    assert "Use pass controllers for passive actors." in text
    assert "Use external AI for subprocess tactics." in text
    assert "Use agent controllers for full-turn delegation." in text
    assert "Keep execution inside the encounter." in text
    assert "assign one controller per combatant, give each turn a current context" in normalized_text
    assert "<summary>Code setup: imports and scene</summary>" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_controller_chapter_uses_positive_pass_language() -> None:
    """Chapter 24 explains empty controller choices as pass/wait states."""
    text = (manual_root() / "24-built-in-controllers-and-automated-turns.mdx").read_text(
        encoding="utf-8"
    )
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    assert "Pass With An Empty Target List" in prose
    assert "returns the pass signal" in prose
    assert "keeps the turn waiting for that outside owner" in prose
    assert not re.search(r"\bno action\b", prose, re.IGNORECASE)
    assert not re.search(r"\bno visible enem", prose, re.IGNORECASE)
    assert "no autonomous engine action" not in prose.lower()
    assert "no-op" not in prose.lower()


def test_controller_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 24 examples print controller transcripts, not assert-only bodies."""
    text = (
        manual_root() / "24-built-in-controllers-and-automated-turns.mdx"
    ).read_text(encoding="utf-8")

    expected_phrases = [
        "controllers: ['human', 'codex', 'pass', 'ai_agent']",
        "runner: type=RecordingTurnRunner, run_count=0",
        "catalogue functions: pair=True, context=True, encounter=True",
        "human wait: status=waiting_for_human, entity=Controller Hero, current=Controller Hero, turn_state=in_progress, can_continue=False",
        "human action: None",
        "codex wait: status=waiting_for_codex, entity=Controller Hero, current=Controller Hero, turn_state=in_progress, can_continue=False",
        "codex action: None",
        "external ai wait: status=waiting_for_ai, entity=Controller Skeleton, current=Controller Skeleton, turn_state=in_progress, can_continue=False",
        "external ai action: None",
        "pass turn: status=waiting_for_human, next=Controller Hero, monster_turns=1, acted=True",
        "current: actor=Controller Hero, turn_state=in_progress",
        "first delegation: runner=RecordingTurnRunner, run_count=1, monster_turns=1, current=Controller Hero",
        "second delegation: run_count=2, monster_turns=2, current=Controller Hero",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 5
    assert text.count('print("\\n".join(readout_lines))') == 5
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_live_replication_chapter_frontloads_stream_contract() -> None:
    """Chapter 25 explains resumable stream delivery before examples."""
    text = (manual_root() / "25-live-replication-streams.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Stream State In The Game Loop")
    bridge_index = text.index("## How D&D Consequences Become Live Streams")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Live Replication Contract")
    authoring_index = text.index("## Live Replication Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert bridge_index < map_index < contract_index < authoring_index
    assert authoring_index < surfaces_index < first_example_index
    assert "The previous chapter taught turn decision ownership" in text
    assert "This chapter follows what happens after those decisions resolve." in normalized_text
    assert "The encounter and event queue publish durable records" in normalized_text
    assert "without making the client rediscover the whole board" in normalized_text
    assert "Live replication is the game's change-delivery layer." in text
    assert "| Product question | Stream-owned answer |" in text
    assert "`EventQueue` history records typed events" in text
    assert "The active `Encounter` stores combat-log entries" in text
    assert "`make_stream_id()` joins the event cursor and combat-log cursor" in text
    assert "`StreamSyncPayload` gives the client the current cursor pair" in text
    assert "Replay calls return the event and combat-log payloads" in text
    assert "`DndEventStream` listens to event and combat-log callbacks" in text
    assert "`HeartbeatPayload` carries the current cursor pair" in text
    assert "`BoundedSubscription` evicts subscribers" in text
    assert "Rules, turns, and outcomes stay with the encounter and event engine." in text
    assert "| D&D play update | Stream behavior |" in text
    assert "The current cursor pair moves as encounter and event state" in text
    assert "`EventQueue` appends typed engine events" in text
    assert "combat-log narration from completed event chains" in text
    assert "`/events/subscribe` sends a `sync` frame" in text
    assert "`iter_game_events_since()` and `iter_combat_logs_since()` replay missed history" in text
    assert "`DndEventStream` fans out event and combat-log envelopes" in text
    assert "`HeartbeatPayload` carries the latest cursor pair through quiet intervals" in text
    assert "`BoundedSubscription` sends an `evicted` frame" in text
    assert "The examples build one live-replication thread in seven moves:" in text
    assert "| Example move | Stream surface learned |" in text
    assert "Import the live stream surface." in text
    assert "Send a sync frame." in text
    assert "Replay from saved cursors." in text
    assert "Fan out live frames." in text
    assert "Release logs after completion." in text
    assert "Keep idle clients synchronized." in text
    assert "Bound slow subscribers." in text
    assert "The live replication contract turns completed game changes" in text
    assert "Every live-replication rule answers eight questions:" in text
    assert "`EventQueue` records engine events" in text
    assert "`make_stream_id()` joins them as `e=<n>;l=<m>`" in text
    assert "`/events/subscribe` starts with a `sync` frame" in text
    assert "`iter_game_events_since()` and `iter_combat_logs_since()` replay history" in text
    assert "`DndEventStream` listens to event and combat-log callbacks" in text
    assert "Combat-log payloads tied to unfinished event lineages wait" in text
    assert "`HeartbeatPayload` carries current cursors" in text
    assert "`BoundedSubscription` evicts subscribers" in text
    assert "Author live replication by treating every resolved turn as durable history plus a resumable delivery stream." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Keep event history durable." in text
    assert "Keep narration durable." in text
    assert "Join cursors into one stream position." in text
    assert "Start subscribers with a sync frame." in text
    assert "Replay missed history." in text
    assert "Fan out live changes." in text
    assert "Keep quiet clients current." in text
    assert "Bound subscriber pressure." in text
    assert "persist event and combat-log records, expose the current cursor pair" in normalized_text
    assert "Clears stream subscriptions, callbacks" in text
    assert "`reset_live_stream_state`" in text
    assert "stream cleanup before creating actors" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_live_replication_chapter_frames_quiet_periods_positively() -> None:
    """Chapter 25 presents heartbeats as quiet-interval synchronization."""
    text = (manual_root() / "25-live-replication-streams.mdx").read_text(
        encoding="utf-8"
    )
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    assert "`HeartbeatPayload` carries current cursors and optional session state during quiet intervals." in prose
    assert "through quiet intervals" in prose
    assert re.search(r"whose\s+queue\s+has\s+reached\s+capacity", prose)
    assert not re.search(r"\bno action\b", prose, re.IGNORECASE)
    assert "with no remaining capacity" not in prose


def test_live_replication_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 25 examples print stream transcripts, not assert-only bodies."""
    text = (manual_root() / "25-live-replication-streams.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "scene: hero=Stream Hero, monster=Stream Skeleton, encounter=Stream Encounter",
        "stream: id=e=52;l=1, event_cursor=52, combat_log_cursor=1",
        "surfaces: sync=StreamSyncPayload, heartbeat=HeartbeatPayload, subscription=BoundedSubscription, attack=True, parse=True, drain=True",
        "sync frame: id=e=52;l=1, event=sync, starts_with_id=True",
        "sync data: event_cursor=52, combat_log_cursor=1, active_entity=Stream Hero",
        "cursor check: expected=e=52;l=1, monster=Stream Skeleton",
        "saved cursors: event=52, log=1",
        "replay: game_events=26, combat_logs=1, completions=6",
        "cursor range: first_event=52, last_cursor=78, log_cursor=2",
        "payload types: logs_are_combat=True",
        "fanout: total=27, game_events=26, combat_logs=1",
        "latest game: id=e=78;l=2, phase=completion, cursor=78",
        "latest log: id=e=78;l=2, log_cursor=2, within_log=True",
        "ordering: first_log_index=26, last_completion_before_log=25, completions_before_log=6",
        "log_after_completion=True",
        "heartbeat frame: event=heartbeat, server_time=100.0, id=e=52;l=1",
        "heartbeat cursors: event=52, log=1, waiting=True",
        "enqueue: first=True, second=False, evicted=True, envelopes=1",
        "eviction: event=evicted, reason=subscriber_queue_overflow, id=None",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert text.count('print("\\n".join(readout_lines))') == 7
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_agent_tactical_chapter_frontloads_tactical_contract() -> None:
    """Chapter 26 explains the agent tactical interface before examples."""
    text = (manual_root() / "26-agent-tactical-interface.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Agent State In The Game Loop")
    bridge_index = text.index("## How A D&D Turn Becomes Tactical State")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Agent Tactical Contract")
    authoring_index = text.index("## Tactical Interface Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert bridge_index < map_index < contract_index < authoring_index
    assert authoring_index < surfaces_index < first_example_index
    assert "Chapter 25 made a running game readable by clients" in text
    assert re.search(
        r"A\s+local\s+agent\s+receives\s+the\s+active\s+actor's\s+turn\s+as\s+a\s+structured\s+tactical\s+snapshot",
        text,
    )
    assert "The tactical interface is the game's agent-facing decision layer." in text
    assert "| Product question | Agent-facing answer |" in text
    assert "The controlled entity UUID resolves to one live `Entity`" in text
    assert "Visible enemies and allies come from the actor's current senses" in text
    assert "Action economy, movement, spell slots, named resources" in text
    assert "Engine discovery becomes grouped attack, spell, movement" in text
    assert "`TargetOption.index` preserves the exact target row" in text
    assert "Attack data, save data, hit chance, crit chance" in text
    assert "The interface executes the selected template and target index" in text
    assert "`BaseAgent.run_turn()` reads one tactical snapshot" in text
    assert "| D&D decision question | Tactical interface behavior |" in text
    assert "The controlled entity UUID resolves one live actor" in text
    assert "`TacticalState` lists visible enemies and visible allies" in text
    assert "The snapshot carries action economy, movement, spell slots" in text
    assert "Engine action discovery becomes grouped `ActionOption` lists" in text
    assert "Each `TargetOption` preserves the engine target index" in text
    assert "`hit_chance()`, `crit_chance()`, `attack_ev()`, and `action_ev()`" in text
    assert "`LocalGameInterface.execute()` sends the selected template name" in text
    assert "`BaseAgent.run_turn()` reads one snapshot and calls `take_turn()`" in text
    assert "The examples build one agent-controlled turn in seven moves:" in text
    assert "| 1. Import the public tactical surface |" in text
    assert "| 2. Read the actor's snapshot |" in text
    assert "| 3. Inspect legal action rows |" in text
    assert "| 4. Ask tactical questions |" in text
    assert "| 5. Score combat choices |" in text
    assert "| 6. Execute one selected row |" in text
    assert "| 7. Wrap the turn in an agent |" in text
    assert "The agent tactical contract turns a live turn into a structured decision" in text
    assert "Every agent-interface rule answers eight questions:" in text
    assert "The controlled entity UUID selects one live actor" in text
    assert "`TacticalState` includes `me`, visible enemies, and visible allies" in text
    assert "The snapshot carries action economy" in text
    assert "Engine action discovery becomes grouped `ActionOption` lists" in text
    assert "Each `TargetOption` preserves the engine target index" in text
    assert "`AttackData`, `SpellData`, `hit_chance()`" in text
    assert "`LocalGameInterface.execute()` sends entity UUID" in text
    assert "`BaseAgent.run_turn()` reads one `TacticalState`" in text
    assert "Author an agent tactical surface by turning one live turn into a legal choice model." in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Resolve the controlled actor." in text
    assert "Serialize the subjective board." in text
    assert "Carry spendable resources." in text
    assert "Preserve legal choice rows." in text
    assert "Preserve target indexes." in text
    assert "Attach combat math." in text
    assert "Execute through the game." in text
    assert "Wrap repeatable behavior." in text
    assert "read the active actor, publish the actor's subjective view" in normalized_text
    assert "## Tactical Scores Guide Selection" in text
    assert "Combat scores in `TacticalState` are planning estimates" in text
    assert "`hit_chance()`, `crit_chance()`, `attack_ev()`, and `action_ev()` read" in text
    assert "They rank options before the agent chooses." in normalized_text
    assert "The result of the choice still comes from execution." in text
    assert "The score helps the agent choose; the action pipeline decides what happens." in normalized_text
    assert "compare options directly from the tactical snapshot before execution resolves" in normalized_text
    assert "`reset_agent_interface_state()` clears registries" in text
    assert "`reset_agent_interface_state`" in text
    assert re.search(r"its\s+reset\s+surface\s+clears\s+the\s+relevant\s+registries", text)
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_agent_tactical_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 26 examples print tactical transcripts, not assert-only bodies."""
    text = (manual_root() / "26-agent-tactical-interface.mdx").read_text(
        encoding="utf-8"
    )

    expected_phrases = [
        "surface: state=TacticalState, actor=Agent Skeleton, nearest=Training Hero",
        "scoring: hit=True, crit=True, attack_ev=True, action_ev=True",
        "training surfaces: auto_hit=True, cleanup=True, reset=True, agent=FirstAttackAgent",
        "me: name=Agent Skeleton, pos=(2, 2), hp=17, ac=0, faction=monsters",
        "economy: actions=1, movement=30, has_action=True, has_movement=True",
        "enemy: name=Training Hero, pos=(5, 2), distance=15, allies=0",
        "choices: attacks=1, movements=2, self_actions=3, concentrating=False",
        "attack row: template=Attack_MELEE_MAIN, category=attack, target_type=entity, cost=actions:1, can_afford=True",
        "weapon math: slot=MELEE_MAIN, weapon=Shortsword, bonus=4, dice=[(1, 6, 2, 'Piercing')]",
        "target row: index=0, name=Training Hero, ac=0, distance=5, ev=5.40",
        "queries: nearest=Training Hero, weakest=Training Hero, in_25=['Training Hero']",
        "move: template=Move, index=27, position=(5, 2), path_cost=15",
        "distance: before=4, after=1, improved=True",
        "hit math: bonus=4, target_ac=0, normal=0.95, advantage=1.00",
        "crit/ev: crit=0.05, attack_ev=5.40, action_ev=5.40",
        "execute: success=True, template=Attack_MELEE_MAIN, target_index=0, actor_hp=17",
        "target hp: before=10, after=5, changed=True",
        "agent turn: actions_taken=1, actor=Agent Skeleton, target=Training Hero",
        "target hp: before=10, after=5, damaged=True",
        "refreshed economy: actions=0, has_action=False",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert text.count('print("\\n".join(readout_lines))') == 7
    assert "Expected output:" not in text
    for phrase in expected_phrases:
        assert phrase in text


def test_agent_decision_chapter_frontloads_decision_contract() -> None:
    """Chapter 27 explains agent decision patterns before examples."""
    text = (manual_root() / "27-agent-decision-patterns.mdx").read_text(
        encoding="utf-8"
    )
    normalized_text = text.replace("\n", " ")

    play_index = text.index("## What This Means In Play")
    state_index = text.index("## Decision State In The Game Loop")
    bridge_index = text.index("## How D&D Tactical Judgment Becomes Agent Behavior")
    map_index = text.index("## Chapter Map")
    contract_index = text.index("## The Agent Decision Contract")
    authoring_index = text.index("## Decision Pattern Authoring Guide")
    surfaces_index = text.index("## Code Surfaces In This Chapter")
    first_example_index = text.index("<ExampleBlock")

    assert play_index < state_index < bridge_index
    assert bridge_index < map_index < contract_index < authoring_index
    assert authoring_index < surfaces_index < first_example_index
    assert "Chapter 26 gave a local agent the active actor's tactical state" in text
    assert "This chapter turns that state into behavior." in text
    assert "Agent decision patterns are the game's behavior-selection layer." in text
    assert "| Product question | Decision-pattern answer |" in text
    assert "A `TacticalState` snapshot supplies the actor" in text
    assert "Behavior trees store ordered branches" in text
    assert "A composite owns a multi-step plan" in text
    assert "`detect_interrupts()` compares before state, action result, and after state" in text
    assert "Utility scoring evaluates affordable action-target pairs" in text
    assert "Every pattern sends a discovered template name and target index" in text
    assert "`BehaviorTreeAgent` and `UtilityAgent` refresh tactical state" in text
    assert "The engine still validates targets, spends costs" in text
    assert "The decision layer gives designers a language for play style by selecting" in text
    assert re.search(
        r"Behavior\s+remains\s+grounded\s+in\s+the\s+live\s+actor's\s+legal\s+choices\.",
        text,
    )
    assert "| D&D tactical judgment | Agent behavior pattern |" in text
    assert "A behavior tree uses `Selector`, `Sequence`, `Condition`, and `BTAction`" in text
    assert "`BTAction` calls a function that executes through the game interface" in text
    assert "A composite such as `MoveAndAttack` owns a multi-step plan" in text
    assert "`detect_interrupts()` compares before state, action result, and after state" in text
    assert "`UtilityAI` evaluates affordable choices with weighted scorers" in text
    assert "`DamageScorer` and `FocusFireScorer` turn expected damage" in text
    assert "`UtilityAgent` refreshes tactical state, chooses the best positive-scoring option" in text
    assert "Every pattern selects discovered actions and target indexes" in text
    assert "The examples build one behavior-selection thread in seven moves:" in text
    assert "| 1. Import the decision surface |" in text
    assert "| 2. Run priority logic |" in text
    assert "| 3. Use a factory behavior |" in text
    assert "| 4. Chain a named tactic |" in text
    assert "| 5. Detect board changes |" in text
    assert "| 6. Rank action-target pairs |" in text
    assert "| 7. Run a utility agent |" in text
    assert "The agent decision contract turns a tactical snapshot into repeatable" in text
    assert "Every agent-decision rule answers eight questions:" in text
    assert "A `TacticalState` snapshot is the input to every decision pattern" in text
    assert "Behavior trees use `Selector`, `Sequence`, `Condition`, and `BTAction`" in text
    assert "`BTAction` calls a function that executes through `GameInterface`" in text
    assert "A composite such as `MoveAndAttack` owns a named multi-step plan" in text
    assert "`detect_interrupts()` compares before state" in text
    assert "`UtilityAI` evaluates affordable action-target pairs" in text
    assert "`UtilityAgent` refreshes tactical state" in text
    assert "Every pattern chooses discovered actions and target indexes" in text
    assert "Author decision behavior by keeping every pattern grounded in `TacticalState` and discovered engine rows." in normalized_text
    assert "A behavior can prioritize, chain, replan, or score" in normalized_text
    assert "| Authoring step | Runtime result |" in text
    assert "Start from tactical state." in text
    assert "Express ordered priorities." in text
    assert "Put game mutations in actions." in text
    assert "Package named tactics." in text
    assert "Replan after consequences." in text
    assert "Score comparable choices." in text
    assert "Run bounded agent loops." in text
    assert "Execute discovered rows." in text
    assert "read a tactical snapshot, choose a decision style" in normalized_text
    assert "## Utility Scores Express Priority" in text
    assert "Utility scores are decision policy." in text
    assert "Combat resolution belongs to the engine action pipeline." in normalized_text
    assert "returns a ranked list that expresses the agent's current preference" in normalized_text
    assert "That preference becomes real play only when the selected row executes through" in normalized_text
    assert "Scorers choose where the agent points its turn; the engine decides the consequence." in normalized_text
    assert "The selected score is the agent's priority for this turn" in text
    assert "`reset_agent_interface_state()` from the tactical-interface chapter clears registries" in text
    assert "`reset_agent_interface_state`" in text
    assert "Decision scenes reuse the tactical-interface reset surface" in text
    assert "from dnd.utils import reset_combat_state" not in text
    assert "reset_combat_state()" not in text


def test_agent_decision_chapter_examples_show_reader_visible_output() -> None:
    """Chapter 27 examples show the decision consequence a reader should see."""
    text = (manual_root() / "27-agent-decision-patterns.mdx").read_text(
        encoding="utf-8"
    )
    expected_phrases = [
        "surface: actor=Decision Skeleton, nearest=Decision Hero, utility_targets=['Wounded Hero', 'Sturdy Hero']",
        "state rows: attacks=1, movements=2, self_actions=3, spells=0",
        "patterns: bt=True, composite=True, interrupts=True, utility=True, agent=True",
        "training surfaces: auto_hit=True, cleanup=True, reset=True",
        "from dnd.core.dice import fixed_dice_faces",
        "tree: result=success, actor=Decision Skeleton, nearest=Decision Hero",
        "target hp: before=10, after=5, damaged=True",
        "economy: actions=0, has_attack=False",
        "fighter: start=(2, 2), end=(6, 2), target=Decision Hero",
        "economy: actions=0, adjacent=True",
        "composite: success=True, actions_taken=2, description=Moved and attacked",
        "positions: actor=(4, 2), target=(5, 2), adjacent=True",
        "interrupts: ['damage_taken', 'target_died', 'new_enemy', 'condition']",
        "state change: hp=17->16, enemies=1->2, conditions=['Poisoned']",
        "death notice: ['Decision Hero']",
        "utility: options=104, best=Wounded Hero, score=10.40",
        "best breakdown: damage=5.40, focus_fire=5.00",
        "runner-up: target=Sturdy Hero, score=5.40",
        "weakest: Wounded Hero, sturdy_attack=True",
        "agent choice: target=Wounded Hero, score=10.40",
        "weak target hp: before=7, after=2, damaged=True",
        "sturdy target hp: before=10, after=10, unchanged=True",
        "economy: actions=0, scorers=['DamageScorer', 'FocusFireScorer']",
    ]

    assert text.count("<p className=\"example-output-label\">Result</p>\n\n```text") == 7
    assert text.count('print("\\n".join(readout_lines))') == 7
    assert "Expected output:" not in text
    assert "helpers" not in text.lower()
    for phrase in expected_phrases:
        assert phrase in text


def test_landing_page_explains_book_reading_path() -> None:
    """The landing page orients readers from rules to game-facing systems."""
    index_path = manual_root().parents[1] / "pages" / "index.astro"
    text = index_path.read_text(encoding="utf-8")

    assert "Reading Path" in text
    assert "From Table Rules To A Running Videogame" in text
    assert "Rules Become Runtime State" in text
    assert "Play Becomes Consequence" in text
    assert "The Engine Becomes A Game" in text
    assert "Automation Reads The Game" in text
    assert "Each layer keeps the D&D idea visible" in text
    assert "Builder Outcomes" in text
    assert "From Reading To Shipping Game Content" in text
    assert "Author A New Rule" in text
    assert "Assemble A Playable Scene" in text
    assert "Expose The Game To Clients" in text
    assert "Automate Tactical Turns" in text
    assert "same engine-owned choices" in text
    assert "Chapter Contract" in text
    assert "From Play Meaning To Usable Code" in text
    assert "Read The Play Moment" in text
    assert "Find The Runtime Owner" in text
    assert "Use The Code Surface" in text
    assert "visible imports and tutorial scene" in text
    assert "setup, execution, and observed result" in text


def test_play_framed_chapters_keep_player_and_designer_framing() -> None:
    """Public chapters explain player and designer meaning."""
    for chapter_name in PLAY_FRAMED_CHAPTERS:
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")

        assert "## What This Means In Play" in text
        assert re.search(r"\bplayer\b", text, re.IGNORECASE)
        assert re.search(r"\bdesigner\b", text, re.IGNORECASE)


def test_public_technical_chapters_have_chapter_maps_before_sources() -> None:
    """Public chapters map the learning path before naming code surfaces."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        chapter_path = manual_root() / chapter_name
        text = chapter_path.read_text(encoding="utf-8")
        play_index = text.find("## What This Means In Play")
        map_index = text.find("## Chapter Map")
        surface_index = text.find("## Code Surfaces In This Chapter")
        first_example_index = text.find("<ExampleBlock")

        assert play_index != -1, f"{chapter_name} needs player/designer framing."
        assert map_index != -1, f"{chapter_name} needs a Chapter Map."
        assert surface_index != -1, f"{chapter_name} needs a source-table section."
        assert first_example_index != -1, f"{chapter_name} has no ExampleBlock."
        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < play_index < map_index < surface_index, (
                f"{chapter_name} should start with a runnable first example, then "
                "move into play meaning, Chapter Map, and code surfaces."
            )
        else:
            assert play_index < map_index < surface_index < first_example_index, (
                f"{chapter_name} should flow from play meaning to Chapter Map to "
                "code surfaces to executable examples."
            )

        rows = chapter_map_table_rows(chapter_path)
        assert len(rows) >= 5, (
            f"{chapter_name} Chapter Map should contain a real table with at "
            "least three learning-path rows."
        )
        assert re.search(r"\b(?:surface|family)\b", rows[0], re.IGNORECASE), (
            f"{chapter_name} Chapter Map should name the implementation side "
            "of the learning path."
        )


def test_public_technical_chapters_explain_code_surfaces_before_examples() -> None:
    """Public chapters explain code surfaces before examples unless staged code-first."""
    expected_headers = {
        "| Symbol | Import path | What it teaches here |",
        "| Symbol or route | Module or route | What it teaches here |",
    }

    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        first_example_index = text.find("<ExampleBlock")
        surface_index = text.find("## Code Surfaces In This Chapter")

        assert first_example_index != -1, f"{chapter_name} has no ExampleBlock."
        assert surface_index != -1, f"{chapter_name} has no code-surface section."
        if chapter_name in CODE_FIRST_CHAPTERS:
            assert first_example_index < surface_index, (
                f"{chapter_name} should start with a runnable first example "
                "before the reference source table."
            )
        else:
            assert surface_index < first_example_index, (
                f"{chapter_name} should introduce code surfaces before examples."
            )

        section = code_surface_section(manual_root() / chapter_name)
        assert any(header in section for header in expected_headers), (
            f"{chapter_name} needs a source table with a tutorial explanation column."
        )
        assert "| Role |" not in section, (
            f"{chapter_name} uses generic Role wording in the code-surface table."
        )


def test_runtime_imports_used_by_examples_are_introduced() -> None:
    """Every dnd/server/ai import appears with its source module in the table."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        chapter_path = manual_root() / chapter_name
        rows = code_surface_table_rows(chapter_path)
        imported_sources = imported_runtime_sources_by_chapter(chapter_path)
        missing = sorted(
            (name, module)
            for name, modules in imported_sources.items()
            for module in modules
            if not any(f"`{name}`" in row and module in row for row in rows)
        )

        assert not missing, (
            f"{chapter_name} imports runtime names that are not introduced "
            f"with their source module in the Code Surfaces section: {missing}"
        )


def test_code_surface_tables_use_concrete_runtime_paths() -> None:
    """Runtime source tables use concrete module addresses, not wildcard labels."""
    vague_runtime_path = re.compile(r"\b(?:dnd|server|ai)\.[^|`\n]*\*")
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        chapter_path = manual_root() / chapter_name
        for row in code_surface_table_rows(chapter_path):
            assert not vague_runtime_path.search(row), (
                f"{chapter_name} has a vague runtime source-table path: {row}"
            )
            assert "Runtime reset modules" not in row, (
                f"{chapter_name} has a vague runtime source-table label: {row}"
            )


def test_audited_code_surfaces_link_to_repo_source() -> None:
    """Audited source tables turn runtime import paths into branch source links."""
    source_link = re.compile(
        r"\[(`(?:dnd|server|ai)\.[^`]+`)\]"
        r"\(https://github\.com/furlat/dnd_engine/blob/feat-test-readme/"
        r"[^)]+\.py#L\d+\)"
    )
    for chapter_name in SOURCE_LINK_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for row in code_surface_table_rows(chapter_path):
            if not re.search(r"`(?:dnd|server|ai)\.", row):
                continue
            assert source_link.search(row), (
                f"{chapter_name} should link runtime import paths to anchored "
                f"repo source in audited Code Surfaces rows: {row}"
            )


def test_code_surface_source_links_resolve_to_local_lines() -> None:
    """Anchored source links in Code Surfaces rows resolve in this worktree."""
    source_link = re.compile(
        r"https://github\.com/furlat/dnd_engine/blob/feat-test-readme/"
        r"(?P<path>[^)#]+\.py)#L(?P<line>\d+)"
    )
    missing_or_stale: list[str] = []

    for chapter_name in SOURCE_LINK_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for row in code_surface_table_rows(chapter_path):
            if "github.com/furlat/dnd_engine" not in row:
                continue

            for match in source_link.finditer(row):
                local_path = REPO_ROOT / match.group("path")
                line_number = int(match.group("line"))
                if not local_path.exists():
                    missing_or_stale.append(
                        f"{chapter_name}: missing {local_path} from row {row}"
                    )
                    continue

                local_lines = local_path.read_text(encoding="utf-8").splitlines()
                if line_number < 1 or line_number > len(local_lines):
                    missing_or_stale.append(
                        f"{chapter_name}: {local_path}:{line_number} is out of "
                        f"range for row {row}"
                    )
                    continue

                if not local_lines[line_number - 1].strip():
                    missing_or_stale.append(
                        f"{chapter_name}: {local_path}:{line_number} points at "
                        f"a blank line for row {row}"
                    )

    assert not missing_or_stale, "\n".join(missing_or_stale)


def test_ai_code_surface_anchors_point_to_named_symbols() -> None:
    """Agent chapter source-table anchors land on the public symbol line."""
    ai_link = re.compile(
        r"https://github\.com/furlat/dnd_engine/blob/feat-test-readme/"
        r"(?P<path>ai/[^)#]+\.py)#L(?P<line>\d+)"
    )
    audited_chapters = {
        "26-agent-tactical-interface.mdx",
        "27-agent-decision-patterns.mdx",
    }

    for chapter_name in audited_chapters:
        chapter_path = manual_root() / chapter_name
        for row in code_surface_table_rows(chapter_path):
            match = ai_link.search(row)
            if not match:
                continue

            symbol_cell = row.split("|")[1]
            symbols = re.findall(r"`([A-Za-z_]\w*)`", symbol_cell)
            assert symbols, (
                f"{chapter_name} has an AI source link without a named public "
                f"symbol in the first table cell: {row}"
            )

            local_path = REPO_ROOT / match.group("path")
            line_number = int(match.group("line"))
            source_lines = local_path.read_text(encoding="utf-8").splitlines()
            assert 1 <= line_number <= len(source_lines), (
                f"{chapter_name} links outside {match.group('path')}: {row}"
            )
            source_line = source_lines[line_number - 1]
            assert any(
                re.match(rf"(?:class|def)\s+{re.escape(symbol)}\b", source_line)
                for symbol in symbols
            ), (
                f"{chapter_name} AI source link should point at one of "
                f"{symbols}, but {match.group('path')}:{line_number} is "
                f"{source_line!r}."
            )


def test_tutorial_product_code_surface_anchors_point_to_named_symbols() -> None:
    """Tutorial/product helper source links land on the public symbol line."""
    helper_link = re.compile(
        r"https://github\.com/furlat/dnd_engine/blob/feat-test-readme/"
        r"(?P<path>(?:dnd/(?:extensions|scenarios)|server/(?:arena_mode|live_replication))"
        r"[^)#]*\.py)#L(?P<line>\d+)"
    )
    stale_links: list[str] = []

    for chapter_name in SOURCE_LINK_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for row in code_surface_table_rows(chapter_path):
            matches = list(helper_link.finditer(row))
            if not matches:
                continue

            symbol_cell = row.split("|")[1]
            symbols = re.findall(r"`([A-Za-z_]\w*)`", symbol_cell)
            if not symbols:
                stale_links.append(
                    f"{chapter_name}: helper source link without symbol cell: {row}"
                )
                continue

            for match in matches:
                local_path = REPO_ROOT / match.group("path")
                line_number = int(match.group("line"))
                source_lines = local_path.read_text(encoding="utf-8").splitlines()
                if line_number < 1 or line_number > len(source_lines):
                    stale_links.append(
                        f"{chapter_name}: {match.group('path')}:{line_number} "
                        f"is outside the file for row {row}"
                    )
                    continue

                source_line = source_lines[line_number - 1]
                if not any(
                    re.match(rf"(?:class|(?:async\s+)?def)\s+{re.escape(symbol)}\b", source_line)
                    for symbol in symbols
                ):
                    stale_links.append(
                        f"{chapter_name}: helper source link should point at one "
                        f"of {symbols}, but {match.group('path')}:{line_number} "
                        f"is {source_line!r}."
                    )

    assert not stale_links, "\n".join(stale_links)


def test_audited_public_helpers_have_docstrings() -> None:
    """Audited public helper definitions explain themselves in tutorial code."""
    for chapter_name in HELPER_DOCSTRING_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        missing: list[str] = []
        for fence in iter_code_fences(chapter_path):
            language, flags, options = parse_fence_info(fence.info)
            if language not in {"python", "py"} or "book-example" not in flags:
                continue

            tree = ast.parse(fence.code)
            example_name = options.get("name", "<unnamed>")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(node):
                        missing.append(f"{example_name}:{node.name}")

        assert not missing, (
            f"{chapter_name} defines public tutorial helpers without "
            f"docstrings: {missing}"
        )


def test_visible_local_names_used_by_examples_are_introduced() -> None:
    """Visible local tutorial names also appear in the chapter source table."""
    for chapter_name in LOCAL_SETUP_NAME_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        section = code_surface_section(chapter_path)
        definitions_by_example = local_definition_names_by_example(chapter_path)
        visible_uses_by_example = visible_name_uses_by_example(chapter_path)

        missing: dict[str, list[str]] = {}
        for example_name, definition_names in definitions_by_example.items():
            visible_local_names = sorted(
                definition_names & visible_uses_by_example.get(example_name, set())
            )
            names_missing_from_section = [
                name for name in visible_local_names if f"`{name}`" not in section
            ]
            if names_missing_from_section:
                missing[example_name] = names_missing_from_section

        assert not missing, (
            f"{chapter_name} uses visible local tutorial names that are not "
            f"introduced in the Code Surfaces section: {missing}"
        )


def test_all_import_panel_local_definitions_are_introduced() -> None:
    """Every local class/function in import panels appears in the local source row."""
    for chapter_name in LOCAL_SETUP_NAME_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        chapter_defined_symbols = defined_in_chapter_symbols(chapter_path)
        missing = sorted(
            name
            for name in local_definition_names_in_import_panels(chapter_path)
            if name not in chapter_defined_symbols
        )

        assert not missing, (
            f"{chapter_name} defines chapter-local tutorial code in Imports & "
            f"Scene without listing it in a Defined in this chapter source row: {missing}"
        )


def test_defined_in_chapter_symbols_are_import_panel_definitions() -> None:
    """Every local source-table symbol is defined in the public setup code."""
    for chapter_name in LOCAL_SETUP_NAME_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        declared = local_definition_names_in_import_panels(chapter_path)
        listed = defined_in_chapter_symbols(chapter_path)
        extra = sorted(listed - declared)

        assert not extra, (
            f"{chapter_name} lists symbols as Defined in this chapter, but "
            f"they are not defined in Code setup: imports and scene panels: {extra}"
        )


def test_enrolled_import_panels_explain_visible_local_names() -> None:
    """Enrolled Code setup: imports and scene panels name local definitions used by examples."""
    for chapter_name in LOCAL_SETUP_NAME_AUDITED_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        definitions_by_example = local_definition_names_by_example(chapter_path)
        visible_uses_by_example = visible_name_uses_by_example(chapter_path)
        intro_by_example = import_panel_intro_text_by_example(chapter_path)

        for example_name, definition_names in definitions_by_example.items():
            visible_local_names = (
                definition_names & visible_uses_by_example.get(example_name, set())
            )
            intro = intro_by_example.get(example_name, "")
            missing = sorted(
                name for name in visible_local_names if name not in intro
            )

            assert not missing, (
                f"{chapter_name}::{example_name} uses local setup names without "
                f"explaining them in the import-panel prose: {missing}"
            )


def test_public_chapters_do_not_end_on_example_blocks() -> None:
    """Public chapters close with reader-facing prose after the final example."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        lines = [
            line.strip()
            for line in chapter_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert lines, f"{chapter_name} is empty."
        assert lines[-1] != "</ExampleBlock>", (
            f"{chapter_name} ends directly on an ExampleBlock; add closing "
            "reader-facing prose."
        )


def test_public_technical_chapters_have_next_step_bridges() -> None:
    """Public technical chapters close by orienting the reader to the next layer."""
    chapter_paths = sorted(manual_root().glob("*.mdx"))
    technical_paths = [
        chapter_path
        for chapter_path in chapter_paths
        if chapter_path.name in STRICT_BOOK_EXAMPLE_CHAPTERS
        and chapter_path.name != "00-neurodragon-dev-manual.mdx"
    ]

    for index, chapter_path in enumerate(technical_paths):
        text = chapter_path.read_text(encoding="utf-8")
        assert "## What Comes Next" in text, (
            f"{chapter_path.name} needs a closing What Comes Next bridge."
        )
        section = text.split("## What Comes Next", 1)[1]
        words = re.findall(r"\w+", section)
        assert len(words) >= 20, (
            f"{chapter_path.name} needs a meaningful What Comes Next bridge."
        )

        if index < len(technical_paths) - 1:
            next_title = chapter_title(technical_paths[index + 1])
            assert next_title in section, (
                f"{chapter_path.name} What Comes Next should name the next "
                f"chapter title: {next_title!r}."
            )
        else:
            assert "current manual arc" in section, (
                f"{chapter_path.name} should close the current manual arc."
            )


def test_public_technical_chapters_summarize_reader_capabilities() -> None:
    """Examples resolve into concrete reader capabilities before the next bridge."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS - {"00-neurodragon-dev-manual.mdx"}:
        chapter_path = manual_root() / chapter_name
        text = chapter_path.read_text(encoding="utf-8")
        last_example_index = text.rfind("</ExampleBlock>")
        capability_index = text.find("## What You Can Do Now")
        next_index = text.find("## What Comes Next")

        assert last_example_index != -1, f"{chapter_name} has no closing ExampleBlock."
        assert capability_index != -1, (
            f"{chapter_name} needs a What You Can Do Now section."
        )
        assert next_index != -1, f"{chapter_name} needs a What Comes Next section."
        assert last_example_index < capability_index < next_index, (
            f"{chapter_name} should summarize capabilities after examples and "
            "before the next-chapter bridge."
        )

        section = text[capability_index:next_index]
        assert "After this chapter you can:" in section, (
            f"{chapter_name} should introduce the capability summary directly."
        )
        bullets = re.findall(r"^- ", section, re.MULTILINE)
        assert len(bullets) >= 3, (
            f"{chapter_name} should list at least three concrete capabilities."
        )


def test_manual_layout_has_chapter_reading_sequence() -> None:
    """Chapter pages expose previous/next links for continuous reading."""
    layout_path = manual_root().parents[1] / "layouts" / "ManualChapter.astro"
    text = layout_path.read_text(encoding="utf-8")

    assert "chapter-runway" in text
    assert "Chapter reading sequence" in text
    assert "Previous Chapter" in text
    assert "Next Chapter" in text
    assert "`/manual/${previousEntry.id}/`" in text
    assert "`/manual/${nextEntry.id}/`" in text


def test_manual_nav_preserves_chapter_order_across_repeated_parts() -> None:
    """Sidebar grouping must not move later chapters ahead of earlier ones."""
    component_path = manual_root().parents[1] / "components" / "ManualNav.astro"
    text = component_path.read_text(encoding="utf-8")

    assert "new Map" not in text
    assert "groups.at(-1)" in text
    assert "lastGroup?.part === entry.data.part" in text
    assert "groups.push({ part: entry.data.part, entries: [entry] })" in text


def test_manual_layout_renders_source_rule_touchpoints() -> None:
    """Chapter pages render declared D&D-facing rule touchpoints."""
    layout_path = manual_root().parents[1] / "layouts" / "ManualChapter.astro"
    text = layout_path.read_text(encoding="utf-8")

    assert "Source Rule Touchpoints" in text
    assert "entry.data.rules.length > 0" in text
    assert "rules-touchpoints" in text
    assert "entry.data.rules.map" in text


def test_manual_layout_styles_tables_code_and_import_panels() -> None:
    """Manual layout keeps tables, code, and import panels readable."""
    layout_path = manual_root().parents[1] / "layouts" / "ManualChapter.astro"
    text = layout_path.read_text(encoding="utf-8")

    assert ".content :global(table)" in text
    assert "border-collapse: collapse" in text
    assert "tbody tr:nth-child(even) td" in text
    assert "overflow-x: auto" in text
    assert ".content :global(pre)" in text
    assert ".content :global(code)" in text
    assert ".content :global(.example-output-label)" in text
    assert ".content :global(.example-output-label + pre)" in text
    assert ".content :global(.example-output-label + pre code)" in text
    assert ".content :global(th code)" in text
    assert "overflow-wrap: anywhere" in text
    assert ".content :global(details.book-imports)" in text
    assert "border-left: 3px solid var(--accent)" in text
    assert ".content :global(details.book-imports summary:hover)" in text
    assert ".content :global(details.book-imports summary:focus-visible)" in text
    assert 'content: \'+\'' in text
    assert 'content: \'-\'' in text


def test_public_text_transcripts_are_result_panels() -> None:
    """Rendered example transcripts are labeled as results, not anonymous text."""
    result_label = '<p className="example-output-label">Result</p>'

    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        text = (manual_root() / chapter_name).read_text(encoding="utf-8")
        text_fences = text.count("```text")
        result_labels = text.count(result_label)

        assert "Output:" not in text
        assert result_labels == text_fences, (
            f"{chapter_name} has {text_fences} text transcript fences but "
            f"{result_labels} result labels."
        )


def test_public_example_block_ids_are_unique() -> None:
    """Example anchors stay unique across the public manual."""
    seen: dict[str, str] = {}
    duplicates: dict[str, list[str]] = {}
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for block in iter_example_blocks(chapter_path):
            anchor_id = block.block_id.lower()
            location = f"{chapter_name}:{block.start_line}"
            if anchor_id in seen:
                duplicates.setdefault(anchor_id, [seen[anchor_id]]).append(location)
            else:
                seen[anchor_id] = location

    assert not duplicates, f"Duplicate ExampleBlock anchors: {duplicates}"


def test_example_blocks_present_runnable_tutorial_flow() -> None:
    """Example blocks present code as tutorial flow, not anonymous snippets."""
    component_path = manual_root().parents[1] / "components" / "ExampleBlock.astro"
    text = component_path.read_text(encoding="utf-8")

    assert "const anchorId = id.toLowerCase()" in text
    assert "id={anchorId}" in text
    assert "href={`#${anchorId}`}" in text
    assert "aria-label={`Link to ${id}`}" in text
    assert "Runnable Tutorial Example" in text
    assert "Example code order" in text
    assert "Code setup: imports and scene" in text
    assert "Continuing Scene" in text
    assert "Execute" in text
    assert "Observe" in text
    assert "Assert" not in text
    assert "test" not in text.lower()


def test_migrated_chapters_have_no_untracked_python_fences() -> None:
    """Strictly converted chapters cannot contain freestyle Python snippets."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        assert chapter_path.exists(), f"Missing migrated chapter: {chapter_name}"

        for fence in iter_code_fences(chapter_path):
            language, flags, _ = parse_fence_info(fence.info)
            if language in {"python", "py"}:
                assert "book-example" in flags, (
                    f"{chapter_name}:{fence.start_line} is a Python fence but "
                    "is not marked as a book-example."
                )


def test_migrated_example_blocks_contain_executed_python() -> None:
    """Each public example block owns at least one executed Python fence."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        blocks = list(iter_example_blocks(chapter_path))
        fences = list(iter_code_fences(chapter_path))
        for block in blocks:
            owned_fences = [
                fence
                for fence in fences
                if fence_is_inside_block(fence, block)
                and "book-example" in parse_fence_info(fence.info)[1]
            ]
            assert owned_fences, (
                f"{chapter_name}:{block.start_line} ExampleBlock "
                f"{block.block_id!r} does not contain executed Python."
            )


def test_example_blocks_without_import_panels_are_marked_continuing() -> None:
    """Continuing-scene examples must be explicit to readers."""
    continuing_context = re.compile(
        r"\bcontinue|same live entity|created in the first example",
        re.IGNORECASE,
    )

    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        for block in iter_example_blocks(chapter_path):
            source = example_block_source(block)
            if '<details className="book-imports"' in source:
                continue

            context = context_before_example_block(block)
            assert block.mode == "continuing", (
                f"{chapter_name}:{block.start_line} ExampleBlock "
                f"{block.block_id!r} has no Code setup: imports and scene panel and must be "
                'declared with mode="continuing".'
            )
            assert continuing_context.search(context), (
                f"{chapter_name}:{block.start_line} continuing ExampleBlock "
                f"{block.block_id!r} should be introduced by nearby prose that "
                "tells the reader what scene it continues."
            )


def test_book_example_fences_live_inside_example_blocks() -> None:
    """Executed public Python fences stay attached to a visible example block."""
    for chapter_name in STRICT_BOOK_EXAMPLE_CHAPTERS:
        chapter_path = manual_root() / chapter_name
        blocks = list(iter_example_blocks(chapter_path))
        for fence in iter_code_fences(chapter_path):
            language, flags, _ = parse_fence_info(fence.info)
            if language not in {"python", "py"} or "book-example" not in flags:
                continue

            containing_blocks = [
                block for block in blocks if fence_is_inside_block(fence, block)
            ]
            assert len(containing_blocks) == 1, (
                f"{chapter_name}:{fence.start_line} executed Python fence "
                "should belong to exactly one ExampleBlock."
            )


@pytest.mark.parametrize(
    "example",
    iter_book_examples(),
    ids=lambda example: example.id,
)
def test_public_book_example_executes(example: BookExample) -> None:
    """Run one public manual example exactly as it appears in MDX."""
    expected_stdout = expected_stdout_for_example(example)
    reset_engine_globals()
    safe_example_id = re.sub(r"\W+", "_", example.id)
    module_name = f"_book_example_{safe_example_id}"
    module = ModuleType(module_name)
    module.__file__ = str(example.chapter_path)
    sys.modules[module_name] = module
    stdout = io.StringIO()
    try:
        compiled = compile(example.source, filename=example.id, mode="exec")
        with contextlib.redirect_stdout(stdout):
            exec(compiled, module.__dict__)
        actual_stdout = stdout.getvalue().rstrip("\n")
        assert actual_stdout == expected_stdout, (
            f"{example.id} printed a different transcript than the public "
            f"Result panel. Fences: {example.locations}"
        )
    finally:
        sys.modules.pop(module_name, None)
