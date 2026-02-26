"""Rule registry with auto-discovery of ScienceRule subclasses."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from science_engine.rules.base import ScienceRule


class RuleRegistry:
    """Discovers and manages all ScienceRule implementations.

    Auto-discovers rules by scanning the rules/ package tree for any
    concrete subclasses of ScienceRule. New rules are added simply by
    placing a .py file in the appropriate subdirectory — no manual
    registration needed.
    """

    def __init__(self) -> None:
        self._rules: dict[str, ScienceRule] = {}

    def discover_rules(self) -> None:
        """Scan the rules package tree and register all ScienceRule subclasses."""
        import science_engine.rules as rules_pkg

        rules_path = Path(rules_pkg.__file__).parent  # type: ignore[arg-type]
        self._scan_package(rules_pkg.__name__, str(rules_path))

    def _scan_package(self, package_name: str, package_path: str) -> None:
        """Recursively import all modules under a package and register rules."""
        for importer, module_name, is_pkg in pkgutil.walk_packages(
            [package_path], prefix=package_name + "."
        ):
            try:
                module = importlib.import_module(module_name)
            except ImportError:
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, ScienceRule)
                    and attr is not ScienceRule
                    and not getattr(attr, "__abstractmethods__", set())
                ):
                    instance = attr()
                    self.register(instance)

    def register(self, rule: ScienceRule) -> None:
        """Register a rule instance by its rule_id."""
        self._rules[rule.rule_id] = rule

    def get(self, rule_id: str) -> ScienceRule | None:
        """Retrieve a rule by its rule_id."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[ScienceRule]:
        """Return all registered rules sorted by priority (lowest value first)."""
        return sorted(self._rules.values(), key=lambda r: r.priority)

    @property
    def rule_ids(self) -> list[str]:
        """List all registered rule IDs."""
        return list(self._rules.keys())
