# RunningMachine

**AI-powered marathon training engine with deterministic, citation-backed science rules, Garmin Connect integration, and structured workout generation.**

RunningMachine is an open-source marathon training system that replaces black-box AI coaching with a transparent, auditable rule engine. Every training decision — session type, intensity, volume, recovery — traces back to published sports science research. The system ingests real-time physiological data from Garmin devices and produces fully structured workouts that push directly to your watch.

## Why RunningMachine?

No existing platform combines full Garmin data exploitation, auditable science, structured workout push, and environmental adjustment into a single system. RunningMachine fills that gap:

- **Every decision is traceable** — each workout prescription includes a full decision trace citing the research that drove it (Gabbett 2016, Plews 2013, Seiler 2007, etc.)
- **Garmin-native** — pulls HRV, sleep, Body Battery, Training Load, and VO2max; pushes step-by-step workouts with pace/HR targets directly to your watch
- **Weather-aware** — adjusts pace targets for heat and humidity using the Ely et al. (2007) model with ability-tier interpolation
- **No black boxes** — the 5-tier priority system (SAFETY > DRIVE > RECOVERY > OPTIMIZATION > PREFERENCE) is fully inspectable

## Architecture

```
AthleteState (frozen)
    |
    v
RuleRegistry ──> [12 ScienceRules]
    |
    v
ConflictResolver (5-tier priority)
    |
    v
WorkoutPrescription + DecisionTrace
    |
    v
WorkoutBuilder ──> StructuredWorkout (Garmin JSON)
    |
    v
GarminClient ──> Push to Watch
```

### Science Rules (12 rules across 5 tiers)

| Tier | Rule | What it does |
|------|------|-------------|
| SAFETY | Injury Risk ACWR | Vetoes training when acute:chronic workload ratio exceeds danger threshold (Gabbett 2016) |
| DRIVE | Minimum Key Session | Guarantees 2 quality sessions per week |
| DRIVE | Training Debt | Tracks and repays skipped sessions with decay (Pfitzinger) |
| DRIVE | Adaptation Demand | Detects volume stagnation and prescribes stimulus bumps |
| DRIVE | Marathon Pace Volume | Ensures cumulative MP time meets phase targets |
| RECOVERY | Asymmetric Readiness (ARR) | Meta-rule: distinguishes expected vs unexpected HRV suppression, requires signal convergence (Stanley 2013, Plews 2013) |
| RECOVERY | HRV Readiness | Suppresses/vetoes intensity on low HRV (Plews 2013, Buchheit 2014) |
| RECOVERY | Sleep Quality | Gates training on sleep score (Fullagar 2015) |
| RECOVERY | Body Battery | 4-tier Garmin Body Battery gating |
| OPTIMIZATION | Progressive Overload | Contextual volume progression with deload weeks (Damsted 2019) |
| OPTIMIZATION | Workout Type Selector | Phase-appropriate session type selection |
| OPTIMIZATION | Race Proximity | Taper and B/C-race adjustments (Mujika 2010) |

### Math Modules

- **Training Load** — Banister TRIMP, EWMA-based ACWR, monotony, strain (Williams 2017)
- **Critical Speed** — Linear CS model with D' (Poole 2016, Smyth 2020)
- **Performance Ceiling** — Daniels-Gilbert + CS convergence with confidence intervals
- **Periodization** — Phase allocation (Base/Build/Specific/Taper/Race) with recovery weeks
- **Heart Rate Zones** — Coggan 5-zone model anchored on LTHR
- **Weather** — Ely et al. (2007) heat model with humidity correction and extreme heat safety cap
- **Adaptive Stimulus Calibration** — VO2max trajectory analysis with limiter identification

## Features

### Structured Workout Generation
Produces Garmin-compatible structured workouts with:
- Step-by-step pace and HR targets per training zone
- Warmup/cooldown segments scaled to session intensity
- Fueling reminders for sessions >60 minutes (Jeukendrup 2011)
- Coaching cues embedded in step notes
- Weather-adjusted pace targets

### Weekly Planning
7-day plans with weekly-aware rules that reason about the shape of the whole week — key session distribution, volume targets, and recovery scheduling.

### Garmin Connect Integration
- **Pull**: HRV, sleep score, Body Battery, VO2max, Training Load, activities
- **Push**: Structured workouts with pace/HR targets to watch
- **Schedule**: APScheduler daemon for automated nightly workout push

### Performance Ceiling Model
Converging marathon time estimate from:
- Critical Speed extrapolation (60% weight)
- VO2max trajectory projection via Daniels-Gilbert (40% weight)
- Confidence intervals that narrow as data quality improves

### Streamlit MVP Dashboard
Interactive dashboard with Today's Workout, Weekly Plan, Decision Trace, and Performance Ceiling tabs. Garmin Connect integration for pull/push directly from the UI.

## Quick Start

```bash
# Clone
git clone https://github.com/TJP8N/RunningMachine.git
cd RunningMachine

# Create venv (Python 3.8+)
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install with all extras
pip install -e ".[all]"

# Run tests (955 tests)
pytest tests/ -v

# Launch the dashboard
streamlit run streamlit_app/app.py
```

### Install Options

```bash
pip install -e "."              # Engine only
pip install -e ".[ui]"          # + Streamlit dashboard
pip install -e ".[garmin]"      # + Garmin Connect client
pip install -e ".[scheduler]"   # + APScheduler daemon
pip install -e ".[all]"         # Everything
pip install -e ".[dev]"         # + pytest
```

## Testing

```bash
# Full suite (955 tests)
pytest tests/ -v

# Engine only (863 tests)
pytest tests/ --ignore=tests/test_garmin_client -v

# Garmin client (92 tests)
pytest tests/test_garmin_client -v

# Single rule
pytest tests/test_rules/test_asymmetric_readiness.py -v
```

## Project Structure

```
src/science_engine/
  engine.py                     # Main orchestrator
  registry.py                   # Auto-discovers rules
  conflict_resolution/          # 5-tier priority resolver
  models/
    enums.py                    # All constants with citations
    athlete_state.py            # Frozen input dataclass
    recommendation.py           # Rule output
    workout.py                  # Prescription
    structured_workout.py       # Garmin-compatible steps
    weekly_plan.py              # 7-day planning
    training_debt.py            # Debt ledger
    race_calendar.py            # Multi-race support
  math/
    training_load.py            # TRIMP, ACWR, monotony
    critical_speed.py           # CS model
    ceiling.py                  # Performance ceiling
    periodization.py            # Phase allocation
    zones.py                    # HR/pace zones
    weather.py                  # Heat model
  rules/
    safety/                     # Tier 0: injury prevention
    drive/                      # Tier 1: training stimulus
    recovery/                   # Tier 2: readiness gating
    optimization/               # Tier 3: session selection
  workout_builder/              # Structured workout generation
  serialization/                # Garmin JSON export

src/garmin_client/              # Garmin Connect API
scheduler/                      # Nightly push daemon
streamlit_app/                  # MVP dashboard
```

## Research Citations

Every constant and threshold in the codebase cites its source. Key references:

- Gabbett (2016). The training-injury prevention paradox. *Br J Sports Med* 50(5):273-280
- Plews et al. (2013). Training adaptation and HRV in elite endurance athletes. *Int J Sports Physiol Perform* 8(6):688-694
- Stanley et al. (2013). Cardiac parasympathetic reactivation following exercise. *Auton Neurosci* 178:76-85
- Ely et al. (2007). Impact of weather on marathon-running performance. *Med Sci Sports Exerc* 39(3):487-493
- Daniels & Gilbert (1979). Oxygen Power. *NAIA*
- Smyth & Muniz-Pumares (2020). Critical speed and the biomechanics of marathon running. *Med Sci Sports Exerc* 52(7):1606-1615
- Williams et al. (2017). Better approaches to ACWR calculation. *J Sci Med Sport* 20(5):493-497
- Seiler et al. (2007). Autonomic recovery after exercise in trained athletes. *Med Sci Sports Exerc* 39(8):1366-1373
- Le Meur et al. (2013). Evidence of parasympathetic hyperactivity in overreached athletes. *Med Sci Sports Exerc* 45(11):2061-2071
- Bosquet et al. (2007). Effects of tapering on performance: a meta-analysis. *Med Sci Sports Exerc* 39(8):1358-1365
- Damsted et al. (2019). Is there evidence for an association between changes in training load and running-related injuries? *J Orthop Sports Phys Ther*
- Foster (1998). Monitoring training in athletes with reference to overtraining syndrome. *Med Sci Sports Exerc* 30(7):1164-1168
