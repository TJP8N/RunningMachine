"""RECOVERY meta-rule: Asymmetric Readiness Response (ARR).

Supersedes individual HRV/Sleep/BodyBattery rules when HRV data is available
by distinguishing *expected* post-training suppression from *unexpected*
readiness drops that warrant intervention.

Key innovations over individual rules:
1. Expected/unexpected distinction — low HRV after VO2max intervals is normal.
2. Signal convergence — requires 2+ independent signals to override a key session.
3. Elevated-HRV boost — super-recovered state is exploited when safe.

References:
    Stanley et al. (2013). Cardiac parasympathetic reactivation following
    exercise. Auton Neurosci 178:76-85.

    Plews et al. (2013). Training Adaptation and Heart Rate Variability in
    Elite Endurance Athletes. Int J Sports Physiol Perform 8(6):688-694.

    Le Meur et al. (2013). Evidence of parasympathetic hyperactivity in
    functionally overreached athletes. Med Sci Sports Exerc 45(11):2061-2071.

    Seiler et al. (2007). Autonomic recovery after exercise in trained
    athletes. Med Sci Sports Exerc 39(8):1366-1373.

    Eichner (1993). Infection, immunity, and exercise. Phys Sportsmed
    21(1):125-135.
"""

from __future__ import annotations

from science_engine.math.training_load import calculate_acwr, classify_acwr
from science_engine.models.athlete_state import AthleteState
from science_engine.models.enums import (
    ARR_CONFIDENCE,
    ARR_CONVERGED_INTENSITY_MOD,
    ARR_CONVERGED_VOLUME_MOD,
    ARR_CONVERGENCE_REQUIRED,
    ARR_ELEVATED_HRV_THRESHOLD,
    ARR_ELEVATED_VOLUME_BOOST,
    ARR_EXPECTED_INTENSITY_MOD,
    ARR_EXPECTED_VOLUME_MOD,
    ARR_MODERATE_INTENSITY_MOD,
    ARR_MODERATE_VOLUME_MOD,
    ARR_VETO_INTENSITY_MOD,
    ARR_VETO_VOLUME_MOD,
    BODY_BATTERY_SUPPRESS_THRESHOLD,
    BODY_BATTERY_VETO_THRESHOLD,
    HRV_SUPPRESS_THRESHOLD,
    HRV_VETO_THRESHOLD,
    SLEEP_SUPPRESS_THRESHOLD,
    SLEEP_VETO_THRESHOLD,
    Priority,
    SessionType,
)
from science_engine.models.recommendation import RuleRecommendation
from science_engine.rules.base import ScienceRule

# Tiered recovery windows — Seiler et al. (2007)
# Tier 1: 48h expected window for the hardest session types
_TIER1_48H = frozenset({SessionType.VO2MAX_INTERVALS, SessionType.RACE_SIMULATION})
# Tier 2: 24h expected window for moderately hard sessions
_TIER2_24H = frozenset({
    SessionType.THRESHOLD,
    SessionType.TEMPO,
    SessionType.MARATHON_PACE,
    SessionType.LONG_RUN,
})


class AsymmetricReadinessRule(ScienceRule):
    """Meta-rule that contextualises readiness signals before suppressing.

    At confidence 0.95 this supersedes individual HRV (0.9), Sleep (0.8),
    and Body Battery (0.7) rules when HRV data is available.
    """

    rule_id = "asymmetric_readiness"
    version = "1.0.0"
    priority = Priority.RECOVERY
    required_data = ["hrv_rmssd", "hrv_baseline"]
    is_weekly_aware = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _count_signals(state: AthleteState) -> tuple[int, int]:
        """Count independent suppressed and veto-level signals.

        Body Battery is derived from HRV + sleep (Firstbeat algorithm) so it
        is NOT counted as independent when HRV data is present. Since this
        rule requires HRV, Body Battery never contributes to convergence here.

        Returns:
            (suppressed_count, veto_count) where veto is a subset of suppressed.
        """
        suppressed = 0
        veto = 0

        # Signal 1: HRV
        if state.hrv_baseline <= 0:  # type: ignore[operator]
            return suppressed, veto
        hrv_ratio = state.hrv_rmssd / state.hrv_baseline  # type: ignore[operator]
        if hrv_ratio < HRV_SUPPRESS_THRESHOLD:
            suppressed += 1
            if hrv_ratio < HRV_VETO_THRESHOLD:
                veto += 1

        # Signal 2: Sleep (independent of HRV)
        if state.sleep_score is not None:
            if state.sleep_score < SLEEP_SUPPRESS_THRESHOLD:
                suppressed += 1
                if state.sleep_score < SLEEP_VETO_THRESHOLD:
                    veto += 1

        # Body Battery — only independent when HRV is missing (fallback).
        # Since required_data guarantees HRV, BB is excluded from convergence.

        return suppressed, veto

    @staticmethod
    def _is_expected_suppression(state: AthleteState) -> bool:
        """Determine if current readiness suppression is expected post-training.

        Tiered recovery windows per Seiler et al. (2007):
        - Tier 1 (48h): VO2max intervals, race simulation
        - Tier 2 (24h): threshold, tempo, marathon pace, long run
        - Fallback: high daily load yesterday
        """
        prev = state.previous_day_session_type

        # Tier 2 — 24h window: hard-but-not-extreme sessions
        if prev is not None and prev in _TIER2_24H:
            return True

        # Tier 1 — 24h window (yesterday was VO2max/race sim)
        if prev is not None and prev in _TIER1_48H:
            return True

        # Tier 1 — 48h window: check if 2 days ago was very hard
        # Proxy: daily_loads[-2] > 2× mean daily load
        if len(state.daily_loads) >= 3:
            mean_load = sum(state.daily_loads) / len(state.daily_loads)
            if mean_load > 0 and state.daily_loads[-2] > 2.0 * mean_load:
                return True

        # Fallback — no session type: high load yesterday
        if prev is None and len(state.daily_loads) >= 2:
            mean_load = sum(state.daily_loads) / len(state.daily_loads)
            if mean_load > 0 and state.daily_loads[-1] > 1.5 * mean_load:
                return True

        return False

    # ------------------------------------------------------------------
    # Main evaluation
    # ------------------------------------------------------------------

    def evaluate(self, state: AthleteState) -> RuleRecommendation | None:
        if state.hrv_baseline <= 0:  # type: ignore[operator]
            return None
        hrv_ratio = state.hrv_rmssd / state.hrv_baseline  # type: ignore[operator]

        suppressed, veto = self._count_signals(state)
        converged = suppressed >= ARR_CONVERGENCE_REQUIRED

        # --- Elevated HRV: supercompensation boost ---
        # Le Meur et al. (2013): guard against parasympathetic saturation
        if hrv_ratio >= ARR_ELEVATED_HRV_THRESHOLD and suppressed == 0:
            # Check ACWR is in optimal range
            acwr = state.acwr
            if acwr is None and len(state.daily_loads) >= 7:
                acwr = calculate_acwr(state.daily_loads)
            acwr_class = classify_acwr(acwr) if acwr is not None else "optimal"

            if acwr_class == "optimal":
                return RuleRecommendation(
                    rule_id=self.rule_id,
                    rule_version=self.version,
                    priority=self.priority,
                    recommended_session_type=None,
                    intensity_modifier=1.0,
                    volume_modifier=ARR_ELEVATED_VOLUME_BOOST,
                    veto=False,
                    explanation=(
                        f"HRV ratio {hrv_ratio:.2f} ≥ {ARR_ELEVATED_HRV_THRESHOLD} "
                        f"with ACWR in optimal range — supercompensation detected. "
                        f"Boosting volume to {ARR_ELEVATED_VOLUME_BOOST:.0%}. "
                        f"Ref: Stanley et al. (2013), Le Meur et al. (2013)."
                    ),
                    confidence=ARR_CONFIDENCE,
                )
            # Elevated but ACWR not optimal — no action (saturation guard)
            return None

        # --- No suppression at all → no action ---
        if suppressed == 0:
            return None

        expected = self._is_expected_suppression(state)

        # --- Expected suppression, single signal: mild dampening ---
        if expected and not converged:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=None,
                intensity_modifier=ARR_EXPECTED_INTENSITY_MOD,
                volume_modifier=ARR_EXPECTED_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Readiness suppression expected after hard training. "
                    f"Single signal, mild dampening ({ARR_EXPECTED_INTENSITY_MOD}/"
                    f"{ARR_EXPECTED_VOLUME_MOD}). "
                    f"Ref: Seiler et al. (2007), Stanley et al. (2013)."
                ),
                confidence=ARR_CONFIDENCE,
            )

        # --- Expected + converged: moderate dampening ---
        if expected and converged:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=ARR_MODERATE_INTENSITY_MOD,
                volume_modifier=ARR_MODERATE_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Expected suppression but {suppressed} signals converge "
                    f"— moderate dampening ({ARR_MODERATE_INTENSITY_MOD}/"
                    f"{ARR_MODERATE_VOLUME_MOD}). "
                    f"Ref: Seiler et al. (2007), Plews et al. (2013)."
                ),
                confidence=ARR_CONFIDENCE,
            )

        # --- Unexpected, single signal: moderate dampening ---
        if not expected and not converged:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.EASY,
                intensity_modifier=ARR_MODERATE_INTENSITY_MOD,
                volume_modifier=ARR_MODERATE_VOLUME_MOD,
                veto=False,
                explanation=(
                    f"Unexpected readiness suppression (single signal) "
                    f"— moderate dampening ({ARR_MODERATE_INTENSITY_MOD}/"
                    f"{ARR_MODERATE_VOLUME_MOD}). "
                    f"Ref: Stanley et al. (2013), Plews et al. (2013)."
                ),
                confidence=ARR_CONFIDENCE,
            )

        # --- Unexpected + converged + veto: REST (illness guard) ---
        if not expected and converged and veto >= 1:
            return RuleRecommendation(
                rule_id=self.rule_id,
                rule_version=self.version,
                priority=self.priority,
                recommended_session_type=SessionType.REST,
                intensity_modifier=ARR_VETO_INTENSITY_MOD,
                volume_modifier=ARR_VETO_VOLUME_MOD,
                veto=True,
                explanation=(
                    f"Unexpected multi-signal convergence ({suppressed} signals, "
                    f"{veto} at veto level) — possible illness or severe "
                    f"fatigue. Recommending REST. If you have symptoms of illness "
                    f"(fever, body aches), take complete rest. "
                    f"Ref: Eichner (1993), Plews et al. (2013)."
                ),
                confidence=ARR_CONFIDENCE,
            )

        # --- Unexpected + converged, no veto: strong dampening ---
        return RuleRecommendation(
            rule_id=self.rule_id,
            rule_version=self.version,
            priority=self.priority,
            recommended_session_type=SessionType.EASY,
            intensity_modifier=ARR_CONVERGED_INTENSITY_MOD,
            volume_modifier=ARR_CONVERGED_VOLUME_MOD,
            veto=False,
            explanation=(
                f"Unexpected multi-signal convergence ({suppressed} signals) "
                f"— strong dampening ({ARR_CONVERGED_INTENSITY_MOD}/"
                f"{ARR_CONVERGED_VOLUME_MOD}). "
                f"Ref: Stanley et al. (2013), Plews et al. (2013)."
            ),
            confidence=ARR_CONFIDENCE,
        )
