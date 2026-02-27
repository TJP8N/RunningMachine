"""Enumerations and physical constants for the science engine.

All thresholds and constants cite their published research source.
"""

from enum import IntEnum, auto


class Priority(IntEnum):
    """Rule priority tiers — lower value = higher priority.

    SAFETY rules can veto any lower-priority recommendation.
    """

    SAFETY = 0
    DRIVE = 1
    RECOVERY = 2
    OPTIMIZATION = 3
    PREFERENCE = 4


class TrainingPhase(IntEnum):
    """Macrocycle training phases for marathon preparation.

    Follows Pfitzinger & Douglas periodization model.
    """

    BASE = auto()
    BUILD = auto()
    SPECIFIC = auto()
    TAPER = auto()
    RACE = auto()


class SessionType(IntEnum):
    """Individual workout session types ordered by intensity."""

    REST = auto()
    RECOVERY = auto()
    EASY = auto()
    LONG_RUN = auto()
    TEMPO = auto()
    THRESHOLD = auto()
    VO2MAX_INTERVALS = auto()
    MARATHON_PACE = auto()
    RACE_SIMULATION = auto()


class ZoneType(IntEnum):
    """Heart rate / pace zones (Coggan 5-zone model)."""

    ZONE_1 = 1
    ZONE_2 = 2
    ZONE_3 = 3
    ZONE_4 = 4
    ZONE_5 = 5


class IntensityLevel(IntEnum):
    """Training intensity modifiers applied to weekly plans."""

    A_FULL = auto()
    B_MODERATE = auto()
    C_EASY = auto()


class ReadinessLevel(IntEnum):
    """Athlete readiness classification from HRV / subjective data."""

    ELEVATED = auto()
    NORMAL = auto()
    SUPPRESSED = auto()
    VERY_SUPPRESSED = auto()


class RacePriority(IntEnum):
    """Race priority classification for multi-race calendars.

    A = goal race (e.g. marathon), B = supporting race (e.g. half marathon),
    C = tune-up / fun race (e.g. 8K).
    """

    A = auto()
    B = auto()
    C = auto()


class StepType(IntEnum):
    """Workout step types (Garmin-compatible numbering)."""

    WARMUP = 1
    COOLDOWN = 2
    ACTIVE = 3       # Main-set steady-state (interval on Garmin)
    RECOVERY = 4     # Recovery jog between intervals
    REST = 5         # Full stop rest
    REPEAT = 6       # Container for repeat blocks


class DurationType(IntEnum):
    """How a workout step's duration is measured."""

    TIME = auto()
    DISTANCE = auto()
    LAP_BUTTON = auto()


# ---------------------------------------------------------------------------
# Physical constants with literature citations
# ---------------------------------------------------------------------------

# ACWR thresholds — Gabbett (2016), Br J Sports Med 50(5):273-280
ACWR_DANGER_THRESHOLD = 1.5  # Hard veto above this ratio
ACWR_CAUTION_HIGH = 1.3  # Reduce intensity above this
ACWR_OPTIMAL_HIGH = 1.3  # Upper bound of optimal ("sweet spot")
ACWR_OPTIMAL_LOW = 0.8  # Lower bound of optimal
ACWR_UNDERTRAINED = 0.8  # Below this = insufficient stimulus

# EWMA spans for ACWR calculation — Williams et al. (2017)
EWMA_ACUTE_SPAN = 7  # 7-day acute window
EWMA_CHRONIC_SPAN = 28  # 28-day chronic window

# Coggan HR zone boundaries as fraction of LTHR — Coggan & Allen (2010)
ZONE_BOUNDARIES_PCT_LTHR = {
    ZoneType.ZONE_1: (0.0, 0.81),
    ZoneType.ZONE_2: (0.81, 0.90),
    ZoneType.ZONE_3: (0.90, 0.96),
    ZoneType.ZONE_4: (0.96, 1.02),
    ZoneType.ZONE_5: (1.02, 1.20),  # Capped at ~120% LTHR
}

# Progressive overload limits — Damsted et al. (2019), J Orthop Sports Phys Ther
MAX_WEEKLY_VOLUME_INCREASE_PCT = 0.10  # Max 10% weekly volume increase
CONSERVATIVE_VOLUME_INCREASE_PCT = 0.05  # 3-5% near peak
EARLY_BASE_VOLUME_INCREASE_PCT = 0.08  # 8% during early base phase

# Recovery week parameters — Pfitzinger & Douglas, Advanced Marathoning
RECOVERY_WEEK_VOLUME_FRACTION = 0.65  # 60-70% of normal volume (midpoint)
RECOVERY_WEEK_INTERVAL = 3  # Every 4th week is a recovery week (3 hard + 1 recovery cycle)

# ---------------------------------------------------------------------------
# Periodization phase allocation constants
# ---------------------------------------------------------------------------
# Minimum viable plan length
MIN_PLAN_WEEKS = 4

# Taper duration — Bosquet et al. (2007), optimal taper = 8-14 days
MIN_TAPER_WEEKS = 2
MAX_TAPER_WEEKS = 3

# Plans > this threshold get MAX_TAPER_WEEKS; otherwise MIN_TAPER_WEEKS
# Mujika & Padilla (2003): longer plans benefit from 3-week taper
TAPER_LONG_PLAN_THRESHOLD = 20

# Specific phase duration bounds
MIN_SPECIFIC_WEEKS = 3
MAX_SPECIFIC_WEEKS = 8  # Diminishing returns beyond 8 weeks

# Plans >= this threshold get a dedicated RACE week
RACE_WEEK_THRESHOLD = 12

# Pace degradation per degree C above 15°C — Ely et al. (2007), Med Sci Sports Exerc
PACE_DEGRADATION_PER_DEGREE_C = 0.003  # 0.3% per degree above 15°C

# TRIMP gender coefficients — Banister (1991)
TRIMP_COEFFICIENT_MALE = 1.92
TRIMP_COEFFICIENT_FEMALE = 1.67
TRIMP_EXPONENT_MALE = 0.64
TRIMP_EXPONENT_FEMALE = 1.92

# ---------------------------------------------------------------------------
# Critical Speed constants
# ---------------------------------------------------------------------------
# Minimum number of distance-time pairs for a valid CS fit
# Poole et al. (2016), J Appl Physiol 120(4):404-410
CS_MIN_DATA_POINTS = 3

# Default marathon race intensity as fraction of CS
# Smyth & Muniz-Pumares (2020), Med Sci Sports Exerc 52(7):1606-1615
CS_MARATHON_PCT_DEFAULT = 0.848

# ---------------------------------------------------------------------------
# Training debt constants
# ---------------------------------------------------------------------------
# Half-life for debt decay in weeks — debt halves every 3 weeks
DEBT_HALF_LIFE_WEEKS = 3

# Debt older than this is written off entirely
DEBT_WRITE_OFF_WEEKS = 6

# ---------------------------------------------------------------------------
# DRIVE tier constants
# ---------------------------------------------------------------------------
# Minimum key (quality) sessions per non-recovery week
MIN_KEY_SESSIONS_PER_WEEK = 2

# Maximum duration extension for debt repayment (minutes)
MAX_DEBT_DURATION_EXTENSION_MIN = 15

# Volume stagnation detection: consecutive weeks within this fraction of each other
STAGNATION_TOLERANCE_PCT = 0.02

# Adaptation demand volume bump range
ADAPTATION_DEMAND_MIN_MODIFIER = 1.05
ADAPTATION_DEMAND_MAX_MODIFIER = 1.08

# Marathon pace minimum cumulative volume targets by phase (minutes)
# Pfitzinger & Douglas (2009): MP running accumulates progressively
MP_VOLUME_TARGETS_MIN = {
    TrainingPhase.BUILD: 60.0,     # 60 min cumulative by end of BUILD
    TrainingPhase.SPECIFIC: 150.0,  # 150 min cumulative by end of SPECIFIC
}

# Threshold for MP deficit that triggers a DRIVE recommendation (minutes)
MP_DEFICIT_THRESHOLD_MIN = 15.0

# Session intensity zones mapped to %LTHR for TRIMP-like calculations
SESSION_INTENSITY_LTHR_PCT = {
    SessionType.REST: 0.0,
    SessionType.RECOVERY: 0.70,
    SessionType.EASY: 0.78,
    SessionType.LONG_RUN: 0.82,
    SessionType.TEMPO: 0.88,
    SessionType.THRESHOLD: 0.95,
    SessionType.VO2MAX_INTERVALS: 1.05,
    SessionType.MARATHON_PACE: 0.88,
    SessionType.RACE_SIMULATION: 0.92,
}

# ---------------------------------------------------------------------------
# HRV readiness constants — Plews et al. (2013), Buchheit (2014)
# ---------------------------------------------------------------------------
HRV_SUPPRESS_THRESHOLD = 0.85   # <85% baseline → suppress intensity
HRV_VETO_THRESHOLD = 0.70       # <70% baseline → veto to RECOVERY
HRV_SUPPRESS_INTENSITY_MOD = 0.80
HRV_SUPPRESS_VOLUME_MOD = 0.85
HRV_VETO_INTENSITY_MOD = 0.50
HRV_VETO_VOLUME_MOD = 0.60

# ---------------------------------------------------------------------------
# Sleep quality constants — Fullagar et al. (2015), Vitale et al. (2019)
# ---------------------------------------------------------------------------
SLEEP_SUPPRESS_THRESHOLD = 60   # <60 → reduce intensity
SLEEP_VETO_THRESHOLD = 40       # <40 → veto to RECOVERY
SLEEP_SUPPRESS_INTENSITY_MOD = 0.80
SLEEP_SUPPRESS_VOLUME_MOD = 0.90
SLEEP_VETO_INTENSITY_MOD = 0.55
SLEEP_VETO_VOLUME_MOD = 0.65

# ---------------------------------------------------------------------------
# Body Battery (Garmin/Firstbeat) — 4-tier thresholds
# ---------------------------------------------------------------------------
BODY_BATTERY_VETO_THRESHOLD = 25
BODY_BATTERY_SUPPRESS_THRESHOLD = 50
BODY_BATTERY_MILD_THRESHOLD = 75
BODY_BATTERY_VETO_INTENSITY_MOD = 0.50
BODY_BATTERY_VETO_VOLUME_MOD = 0.55
BODY_BATTERY_SUPPRESS_INTENSITY_MOD = 0.75
BODY_BATTERY_SUPPRESS_VOLUME_MOD = 0.80
BODY_BATTERY_MILD_INTENSITY_MOD = 0.90
BODY_BATTERY_MILD_VOLUME_MOD = 0.95

# ---------------------------------------------------------------------------
# Race calendar constants — Mujika (2010)
# ---------------------------------------------------------------------------
B_RACE_TAPER_DAYS = 7
B_RACE_RECOVERY_DAYS = 3
C_RACE_EASY_DAY_BEFORE = 1
B_RACE_TAPER_VOLUME_MOD = 0.70
B_RACE_TAPER_INTENSITY_MOD = 0.85
RACE_PROXIMITY_DAY_BEFORE = 1
RACE_PROXIMITY_B_RACE_WINDOW = 7

# ---------------------------------------------------------------------------
# Workout structure — warmup/cooldown defaults (minutes)
# ---------------------------------------------------------------------------
WARMUP_DURATION_MIN = 10
COOLDOWN_DURATION_MIN = 5
QUALITY_WARMUP_DURATION_MIN = 15   # For threshold/VO2max/tempo
QUALITY_COOLDOWN_DURATION_MIN = 10

# ---------------------------------------------------------------------------
# Fueling — Jeukendrup (2011), Sports Med 41(6):431-446
# ---------------------------------------------------------------------------
FUELING_THRESHOLD_DURATION_MIN = 60   # Insert fueling steps for sessions >60 min
FUELING_INTERVAL_MIN = 45             # Gel every ~45 min during long efforts

# ---------------------------------------------------------------------------
# Intensity level modifiers for pace/HR targets
# ---------------------------------------------------------------------------
INTENSITY_B_MODERATE_FACTOR = 0.95   # 5% easier
INTENSITY_C_EASY_FACTOR = 0.85       # 15% easier
