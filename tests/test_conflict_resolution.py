"""Tests for ConflictResolver — priority hierarchy and veto logic."""

from science_engine.conflict_resolution.resolver import ConflictResolver
from science_engine.conflict_resolution.strategies import HighestPriorityWins
from science_engine.models.enums import Priority, SessionType
from science_engine.models.recommendation import RuleRecommendation


def _rec(
    rule_id: str,
    priority: Priority,
    session: SessionType = SessionType.EASY,
    veto: bool = False,
    confidence: float = 0.8,
    intensity: float = 1.0,
    volume: float = 1.0,
) -> RuleRecommendation:
    return RuleRecommendation(
        rule_id=rule_id,
        rule_version="1.0",
        priority=priority,
        recommended_session_type=session,
        intensity_modifier=intensity,
        volume_modifier=volume,
        veto=veto,
        explanation=f"Test recommendation from {rule_id}",
        confidence=confidence,
    )


class TestHighestPriorityWins:
    def setup_method(self) -> None:
        self.resolver = ConflictResolver(HighestPriorityWins())

    def test_safety_veto_overrides_everything(self) -> None:
        recs = [
            _rec("safety", Priority.SAFETY, SessionType.EASY, veto=True),
            _rec("opt", Priority.OPTIMIZATION, SessionType.VO2MAX_INTERVALS),
        ]
        winner, notes = self.resolver.resolve(recs)
        assert winner.veto is True
        assert winner.rule_id == "safety"

    def test_higher_priority_wins_without_veto(self) -> None:
        recs = [
            _rec("drive", Priority.DRIVE, SessionType.TEMPO),
            _rec("pref", Priority.PREFERENCE, SessionType.RECOVERY),
        ]
        winner, _ = self.resolver.resolve(recs)
        assert winner.rule_id == "drive"

    def test_same_tier_highest_confidence_wins(self) -> None:
        recs = [
            _rec("opt_a", Priority.OPTIMIZATION, SessionType.TEMPO, confidence=0.7),
            _rec("opt_b", Priority.OPTIMIZATION, SessionType.THRESHOLD, confidence=0.9),
        ]
        winner, _ = self.resolver.resolve(recs)
        assert winner.rule_id == "opt_b"

    def test_empty_recommendations_returns_default(self) -> None:
        winner, _ = self.resolver.resolve([])
        assert winner.recommended_session_type == SessionType.EASY
        assert winner.rule_id == "default"

    def test_safety_intensity_modifier_applied(self) -> None:
        recs = [
            _rec("safety", Priority.SAFETY, intensity=0.75, confidence=0.9),
            _rec("opt", Priority.OPTIMIZATION, SessionType.THRESHOLD),
        ]
        winner, _ = self.resolver.resolve(recs)
        # Safety rule has higher priority, so it wins
        assert winner.rule_id == "safety"

    def test_multiple_vetoes_highest_confidence_wins(self) -> None:
        recs = [
            _rec("veto_a", Priority.SAFETY, veto=True, confidence=0.7),
            _rec("veto_b", Priority.SAFETY, veto=True, confidence=0.95),
        ]
        winner, _ = self.resolver.resolve(recs)
        assert winner.rule_id == "veto_b"
