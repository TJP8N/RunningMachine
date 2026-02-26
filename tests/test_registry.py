"""Tests for RuleRegistry — auto-discovery of rules from subdirectories."""

from __future__ import annotations

from science_engine.models.enums import Priority
from science_engine.registry import RuleRegistry


class TestRuleRegistry:
    def test_discover_finds_rules(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        assert len(registry.get_all_rules()) >= 12

    def test_discovers_safety_rule(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        assert registry.get("injury_risk_acwr") is not None

    def test_discovers_optimization_rules(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        rule_ids = registry.rule_ids
        assert "periodization" in rule_ids
        assert "progressive_overload" in rule_ids
        assert "workout_type_selector" in rule_ids
        assert "race_proximity" in rule_ids

    def test_discovers_recovery_rules(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        rule_ids = registry.rule_ids
        assert "hrv_readiness" in rule_ids
        assert "sleep_quality" in rule_ids
        assert "body_battery" in rule_ids

    def test_get_all_sorted_by_priority(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        rules = registry.get_all_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)

    def test_safety_rules_first(self) -> None:
        registry = RuleRegistry()
        registry.discover_rules()
        rules = registry.get_all_rules()
        assert rules[0].priority == Priority.SAFETY

    def test_get_nonexistent_returns_none(self) -> None:
        registry = RuleRegistry()
        assert registry.get("nonexistent_rule") is None

    def test_register_custom_rule(self) -> None:
        from science_engine.rules.base import ScienceRule
        from science_engine.models.athlete_state import AthleteState
        from science_engine.models.recommendation import RuleRecommendation

        class DummyRule(ScienceRule):
            rule_id = "dummy_test"
            version = "0.1"
            priority = Priority.PREFERENCE
            required_data: list[str] = []

            def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
                return None

        registry = RuleRegistry()
        registry.register(DummyRule())
        assert registry.get("dummy_test") is not None
