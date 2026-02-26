"""Training debt ledger — tracks missed training for DRIVE rule debt repayment.

Debt decays over time so the system doesn't endlessly chase missed sessions
from weeks ago. The half-life and write-off constants are configurable via
enums.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from science_engine.models.enums import (
    DEBT_HALF_LIFE_WEEKS,
    DEBT_WRITE_OFF_WEEKS,
    SessionType,
)


@dataclass(frozen=True)
class DebtEntry:
    """A single debt record for a missed or shortened session."""

    session_type: SessionType
    missed_duration_min: float  # minutes of training missed
    weeks_ago: int  # how many weeks since the debt was incurred (0 = this week)


@dataclass(frozen=True)
class TrainingDebtLedger:
    """Frozen ledger of accumulated training debt.

    The application layer maintains this between weeks and passes it
    into AthleteState. The science engine reads it but never mutates it.
    """

    entries: tuple[DebtEntry, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0


def apply_debt_decay(entry: DebtEntry) -> float:
    """Apply exponential decay to a debt entry based on its age.

    Uses a half-life model: debt halves every DEBT_HALF_LIFE_WEEKS weeks.
    Debt older than DEBT_WRITE_OFF_WEEKS is written off completely.

    Args:
        entry: A single debt entry.

    Returns:
        The effective (decayed) debt in minutes.
    """
    if entry.weeks_ago >= DEBT_WRITE_OFF_WEEKS:
        return 0.0
    decay_factor = math.pow(0.5, entry.weeks_ago / DEBT_HALF_LIFE_WEEKS)
    return entry.missed_duration_min * decay_factor


def total_effective_debt(ledger: TrainingDebtLedger) -> float:
    """Sum all effective (decayed) debt in the ledger.

    Args:
        ledger: The full debt ledger.

    Returns:
        Total effective debt in minutes.
    """
    return sum(apply_debt_decay(e) for e in ledger.entries)


def debt_by_session_type(ledger: TrainingDebtLedger) -> dict[SessionType, float]:
    """Break down effective debt by session type.

    Args:
        ledger: The full debt ledger.

    Returns:
        Dict mapping SessionType to total effective debt minutes.
    """
    result: dict[SessionType, float] = {}
    for entry in ledger.entries:
        effective = apply_debt_decay(entry)
        if effective > 0.0:
            result[entry.session_type] = result.get(entry.session_type, 0.0) + effective
    return result
