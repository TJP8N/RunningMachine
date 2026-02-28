"""Conflict resolution strategies for combining rule recommendations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from science_engine.models.enums import Priority, SessionType
from science_engine.models.recommendation import RuleRecommendation


class ResolutionStrategy(ABC):
    """Base class for conflict resolution strategies."""

    @abstractmethod
    def resolve(
        self, recommendations: list[RuleRecommendation]
    ) -> tuple[RuleRecommendation, str]:
        """Resolve conflicting recommendations into a single winner.

        Returns the winning recommendation and a human-readable explanation
        of the resolution logic.
        """
        ...


class HighestPriorityWins(ResolutionStrategy):
    """Resolution strategy: highest-priority rule wins outright.

    Within the same priority tier, the recommendation with the highest
    confidence wins. SAFETY vetoes override everything regardless of
    confidence.

    Priority hierarchy (5-tier):
        0. SAFETY — can veto, overrides all
        1. DRIVE — overrides RECOVERY and below
        2. RECOVERY — overrides OPTIMIZATION and below
        3. OPTIMIZATION — overrides PREFERENCE
        4. PREFERENCE — lowest priority
    """

    def resolve(
        self, recommendations: list[RuleRecommendation]
    ) -> tuple[RuleRecommendation, str]:
        if not recommendations:
            # No rules fired — default to easy run
            default = RuleRecommendation(
                rule_id="default",
                rule_version="1.0",
                priority=Priority.PREFERENCE,
                recommended_session_type=SessionType.EASY,
                explanation="No rules produced recommendations; defaulting to easy run.",
            )
            return default, "No recommendations to resolve."

        # Check for any SAFETY vetoes first
        safety_vetoes = [
            r for r in recommendations if r.priority == Priority.SAFETY and r.veto
        ]
        if safety_vetoes:
            # Pick the veto with highest confidence
            winner = max(safety_vetoes, key=lambda r: r.confidence)
            return winner, (
                f"SAFETY veto from {winner.rule_id}: {winner.explanation}"
            )

        # Group by priority tier and pick the highest (lowest numeric value)
        best_priority = min(r.priority for r in recommendations)
        tier_recs = [r for r in recommendations if r.priority == best_priority]

        # Within the tier, prefer recs that specify a session type, then by confidence
        recs_with_session = [r for r in tier_recs if r.recommended_session_type is not None]
        if recs_with_session:
            winner = max(recs_with_session, key=lambda r: r.confidence)
        else:
            winner = max(tier_recs, key=lambda r: r.confidence)

        # If the winner doesn't specify a session type (e.g. SAFETY "caution"
        # only adjusts volume/intensity), inherit the best session type from
        # any tier.  A None session type means "I don't care about session
        # type" — not "force EASY".
        if winner.recommended_session_type is None:
            all_with_session = [
                r for r in recommendations if r.recommended_session_type is not None
            ]
            if all_with_session:
                best_session_rec = max(all_with_session, key=lambda r: r.confidence)
                winner = RuleRecommendation(
                    rule_id=winner.rule_id,
                    rule_version=winner.rule_version,
                    priority=winner.priority,
                    recommended_session_type=best_session_rec.recommended_session_type,
                    intensity_modifier=winner.intensity_modifier,
                    volume_modifier=winner.volume_modifier,
                    target_duration_min=winner.target_duration_min,
                    target_distance_km=winner.target_distance_km,
                    veto=winner.veto,
                    explanation=winner.explanation,
                    confidence=winner.confidence,
                )

        # Blend same-tier volume/distance info from other recs into the winner
        for rec in tier_recs:
            if rec is not winner:
                if rec.target_distance_km is not None and winner.target_distance_km is None:
                    winner = RuleRecommendation(
                        rule_id=winner.rule_id,
                        rule_version=winner.rule_version,
                        priority=winner.priority,
                        recommended_session_type=winner.recommended_session_type,
                        intensity_modifier=winner.intensity_modifier,
                        volume_modifier=min(winner.volume_modifier, rec.volume_modifier),
                        target_duration_min=winner.target_duration_min,
                        target_distance_km=rec.target_distance_km,
                        veto=winner.veto,
                        explanation=winner.explanation,
                        confidence=winner.confidence,
                    )

        # Apply intensity/volume modifiers from higher-priority non-veto rules
        intensity_mod = winner.intensity_modifier
        volume_mod = winner.volume_modifier
        for rec in recommendations:
            if rec.priority < winner.priority:
                intensity_mod = min(intensity_mod, rec.intensity_modifier)
                volume_mod = min(volume_mod, rec.volume_modifier)

        # If modifiers were reduced by higher-priority rules, create adjusted rec
        if intensity_mod != winner.intensity_modifier or volume_mod != winner.volume_modifier:
            winner = RuleRecommendation(
                rule_id=winner.rule_id,
                rule_version=winner.rule_version,
                priority=winner.priority,
                recommended_session_type=winner.recommended_session_type,
                intensity_modifier=intensity_mod,
                volume_modifier=volume_mod,
                target_duration_min=winner.target_duration_min,
                target_distance_km=winner.target_distance_km,
                veto=winner.veto,
                explanation=winner.explanation + " (modifiers adjusted by higher-priority rules)",
                confidence=winner.confidence,
            )

        notes = (
            f"Winner: {winner.rule_id} (priority={winner.priority.name}, "
            f"confidence={winner.confidence:.2f})"
        )
        return winner, notes
