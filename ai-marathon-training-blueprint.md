# AI marathon training system: competitive analysis and architecture blueprint

**No existing platform combines full Garmin data exploitation, auditable science, structured workout push, and environmental adjustment into a single system.** This gap is the strategic opportunity. After analyzing all 10 major competitors, the conclusion is clear: every platform leaves massive amounts of available data on the table, none traces every training decision to published research, and only one (TriDot) adjusts for environmental conditions — with a proprietary black-box approach. A system built on data maximalism, transparent science rules, and the "workout-as-coach" paradigm can demonstrably outperform every competitor for a technically sophisticated marathoner.

This document is structured for direct handoff to a coding agent: it provides exact tool versions, GitHub URLs, API endpoints, architecture patterns, and a prioritized implementation roadmap.

---

## SECTION 1: Deep competitive analysis

### AI Endurance — The DFA alpha-1 pioneer

**Data inputs**: HR, HRV (raw RR intervals from FIT files via chest strap — optical HR insufficient), GPS pace/speed, power (Stryd), cadence, elevation. Does **not** ingest running dynamics, GCT, stride length, temperature, SpO2, respiration, Body Battery, stress, or sleep stages.

**Methodology**: True per-user ML model ("digital twin") updated every 24 hours, correlating historical performances with training inputs across 50,000+ plan variations. Their signature feature is **DFA alpha-1 HRV analysis** — Detrended Fluctuation Analysis where α1 crossing below **0.75** identifies aerobic threshold (VT1) and below **0.50** marks anaerobic threshold (VT2), based on Rogers/Gronwald/Hoos research (Frontiers in Physiology, 2020). They also compute DFA-based readiness during warm-up and track durability (fatigue resistance over time). Performance prediction accuracy is within ~5% with 100+ GPS activities.

**Garmin integration**: Imports via Garmin Connect; provides the alphaHRV Connect IQ app for real-time DFA display. **Pushes structured workouts** with pace/power primary targets and secondary HR targets to Garmin.

**Pricing**: ~$13–26/month depending on plan term.

**Key weakness**: Running sessions prescribed only in 30-minute increments — a half-marathon plan had no long runs over 60 minutes. Requires a chest strap (Polar H10) for core DFA functionality. Cycling-first heritage means running features are less mature. Users on Intervals.icu forums found workouts "hit and miss."

**What to learn from them**: DFA alpha-1 threshold detection from everyday workouts (no lab test) is genuinely novel. However, their philosophy of replacing Garmin's lactate threshold with an independent estimate is misguided for our use case — Garmin's Firstbeat algorithms have direct on-device sensor access and years of refinement that external computation cannot match. DFA alpha-1 is valuable as an *optional enhancement* for athletes with chest straps, not as a replacement for Garmin's LTHR.

### Runna — The polished plan-delivery machine

**Data inputs**: Pace and distance from completed runs only. Plans anchored to a user-input 5K or 10K time. **No physiological data** — no HR, HRV, sleep, or biometric integration for plan adaptation.

**Methodology**: Plans are **human-designed by coaches** (Ben Parker, Steph Davis from Team GB). "AI" monitors progress and surfaces insights but does not generate workouts. Rule-based plan selection based on ability level, race distance, and days per week. Plans don't dynamically adapt week-to-week unless the user manually updates their pace input. Acquired by Strava in 2025; 2 million monthly users.

**Garmin integration**: Pulls basic activity data. **Pushes structured workouts with pace targets per step** to Garmin — this is seamless and widely praised. Workouts include warm-up, intervals with specific paces, recovery, and cooldown.

**Pricing**: $20/month or $120/year.

**Key weakness**: Growing controversy (Feb 2026) about injury rates — physical therapists reporting increased cases from Runna users, likely because default 4-day plans include 2 speed sessions (violating the 80/20 principle). No physiological data integration means the system cannot detect overreaching. Plans are templates, not truly adaptive.

**What to learn from them**: Their UX is the benchmark — setup is effortless, Garmin workout push is flawless, and 4.9 stars across 76K+ ratings proves that simplicity wins at scale. The lesson is that a technically superior system must also nail the "workout on your wrist" delivery experience.

### Garmin Coach and Daily Suggested Workouts (DSW)

**Data inputs**: DSW uses the **deepest physiological data** of any platform: Training Status, Training Load (acute/chronic), Load Focus, VO2max, sleep, recovery hours, HRV Status, Body Battery, stress, Training Readiness. It is the only system with native access to everything the watch measures.

**Methodology**: DSW is powered by **Firstbeat Analytics algorithms** (acquired by Garmin in 2020). Generates rolling 7-day workout suggestions that change daily based on real-time physiological state. Garmin Coach offers structured plans for 5K, 10K, and half marathon only (Jeff Galloway, Greg McMillan, Amy Parkerson-Mitchell) — **no full marathon plans**. DSW adapts daily but lacks long-term periodization.

**Garmin integration**: Native — workouts are generated on-device. No sync delays, works offline.

**Pricing**: Free with compatible watch. Garmin Connect+ ($7/month) adds AI insights but is not required.

**Key weakness**: **No marathon plan in Garmin Coach**. DSW is overprotective — users report excessive recovery runs and maximum long-run suggestions of 1h50 for marathon prep. DSW only looks 7 days ahead with no periodization awareness. Sleep tracking inaccuracy cascades to suboptimal Training Readiness scores. The Firstbeat algorithms are proprietary, but their outputs (LTHR, VO2max, HRV Status, Training Readiness, Training Load) are well-validated and accessible via API — the weakness is that **DSW underutilizes its own data** by lacking long-term periodization, not that the underlying metrics are poor.

**What to learn from them**: DSW's daily adaptation to physiological state (HRV Status, Body Battery, Training Readiness) is the gold standard for responsiveness. The concept of a multi-signal readiness score that gates workout intensity is exactly right. Garmin's heat and altitude acclimation features also show the value of environmental awareness.

### Athletica.ai — The science-forward platform

**Data inputs**: HR, HRV, RHR, pace, power, cadence, GPS, elevation from Garmin Connect. HRV/RHR data also sourced via Intervals.icu pathway (which can pull from WHOOP, Oura, Polar). Imports Garmin Menstrual Cycle Tracking data.

**Methodology**: Built directly on the **HIIT Science textbook** by Paul Laursen and Martin Buchheit, encoding 150+ peer-reviewed publications. **Implements the Critical Speed/Power model** — auto-calculates and refreshes Critical Pace from rolling workout data (switched from FTP to CP model in 2024). Applies **polarized training distribution** (high-volume low-intensity + targeted high-intensity). Features a "Workout Reserve" concept showing remaining capacity relative to CP. Plans include full periodization (base → build → peak → taper). HRV-based readiness uses a traffic-light system (Green/Yellow/Orange/Red).

**Garmin integration**: Pushes structured workouts — HR-guided for sub-threshold work, pace/power targets for threshold+. "Smart Coach" auto-selects the appropriate metric. Workout Reserve available as a Garmin Connect IQ app.

**Pricing**: $20/month or $189/year.

**Key weakness**: Zone calculation bugs — users report incorrect threshold calculations from Garmin data. Critical speed auto-update has produced errors (one user saw CS jump 100 seconds faster overnight). Races can only be scheduled on weekends. Platform stability issues under load. Running power (Stryd) integration was still incomplete as of mid-2025.

**What to learn from them**: **Strongest science foundation** of any competitor. Their explicit implementation of the Critical Speed model from wearable data, polarized training distribution, and traceable methodology (specific textbook chapters) sets the transparency bar. Their architecture — raw data → persistent athlete database → physiological models → training plan logic → AI interpretation — is a sound reference model.

### TrainerRoad — The cycling ML giant

**Data inputs**: Power (from smart trainers/power meters), HR, cadence for cycling. For running: pace, distance, elevation, cadence, HR, power if available. **Run TSS is RPE-based only** — manually entered, not computed. Does not pull wellness data (sleep, HRV, stress, Body Battery).

**Methodology**: ML system trained on **250M+ activities**. Assigns "Progression Levels" (0–10 scale) per training zone. AI FTP Detection eliminates dedicated test requirements. Adaptive Training analyzes cycling workout completion to adjust plan difficulty. For running: adaptations trigger only from missed workouts, **not from running-specific performance analysis**.

**Garmin integration**: Imports activities. **Cannot push swim or run workouts to Garmin** — only cycling outside workouts sync.

**Pricing**: $20/month or $190/year.

**Key weakness**: Running support is rudimentary. No running-specific ML analysis. Cannot push running workouts to Garmin. Criticized for excessive intensity and sweet-spot bias at the expense of polarization.

**What to learn from them**: Progression Levels (granular zone-by-zone fitness tracking) is a compelling concept for tracking adaptation. Their scale and data-driven approach demonstrate the value of large datasets, though their cycling-centric model doesn't translate well to running.

### Humango — The conversational rescheduler

**Data inputs**: HR, sleep, Body Battery/WHOOP recovery data from Garmin and other wearables. Conversational text input for schedule changes.

**Methodology**: LLM-powered (ChatGPT-based) conversational AI coach named "Hugo." Strength is instant replanning — text "I'm stuck at work, give me a 45-minute run" and Hugo rebuilds the week. Includes Recalibration Tests for threshold updates.

**Garmin integration**: Pushes guided workouts with targets. Syncs completed workouts. Integration reported as buggy by multiple users.

**Pricing**: Free tier (basic); $9/month (fitness); ~$30/month (full performance).

**Key weakness**: Multiple App Store reviews cite broken Garmin/Apple Health sync. Triathlete.com concluded it's "less of a coach, and more of a triathlon-savvy assistant." No instructional content, no nutrition plans, no recovery guidance beyond scheduling. Physiological depth is shallow.

**What to learn from them**: The conversational replanning UX is genuinely best-in-class. The ability to instantly reshape a week around real-life constraints (illness, travel, work) without losing training coherence is a feature worth emulating — though implementing it as a rule-engine adjustment rather than an LLM response will produce more reliable results.

### TriDot — The environmental adjustment leader

**Data inputs**: Pace, power, HR, GPS from Garmin and other wearables. Optionally: DNA data from 23andMe/Ancestry (Physiogenomix). Environmental data: temperature, humidity, elevation, wind, terrain.

**Methodology**: Proprietary "FitLogic" engine built on ~20 years of athlete data. Key innovation is **EnviroNorm** — adjusts prescribed paces for anticipated environmental conditions (temperature, humidity, elevation, wind, terrain) AND normalizes completed workout data back to base conditions for apples-to-apples comparison. NTS (Normalized Training Stress) accounts for environment in load calculations. TrainX score measures execution quality. RaceX combines training data with anticipated race-day conditions for pacing.

**Pricing**: $39–249/month. No free tier.

**Key weakness**: Extremely expensive. Historically poor Garmin workout push (improving). Triathlete.com found the experience "did not feel particularly personalized." Scheduled a brick session the Saturday before race day without proper taper. DNA claims lack independent validation.

**What to learn from them**: **EnviroNorm is the single most instructive competitive feature.** Bidirectional environmental adjustment — normalizing completed data AND adjusting prescribed paces — is exactly the right approach. Their decomposition of environmental factors (temp, humidity, wind, elevation, terrain) into a unified adjustment model should be replicated and improved with published research (Ely et al., 2007; Running Writings heat model).

### COROS EvoLab — Analytics without prescription

**Closed COROS ecosystem** (no Garmin integration). EvoLab is an analytics platform, not a prescription engine — it analyzes but doesn't generate training plans. Provides Running Fitness breakdown (Endurance/Threshold/Speed/Sprint), Marathon Level, and stable VO2max estimates. All free with hardware purchase. **Explicitly does not account for environmental conditions.** No HRV-guided daily prescription.

**What to learn from them**: Their 4-way Running Fitness decomposition is a useful concept for identifying athlete-specific weaknesses. Their Training Hub's predictive feature — showing how planned workouts would affect fitness metrics before executing them — is worth replicating.

### Polar — Recovery science depth

**Closed Polar ecosystem** (no Garmin integration). Key innovations: **Nightly Recharge** using ANS (Autonomic Nervous System) charge from HR, HRV, and breathing rate during sleep's first 4 hours. **Training Load Pro** separates load into three dimensions: Cardio Load, Muscle Load, and Perceived Load. FitSpark offers daily suggestions influenced by recovery state.

**What to learn from them**: Three-dimensional training load (cardio + muscular + perceived) is more nuanced than TSS/TRIMP alone. Nightly Recharge's focus on the first 4 hours of sleep (when ANS recovery is most concentrated) is well-grounded in sleep physiology.

### TrainingPeaks and Final Surge — The platform standard

**TrainingPeaks** is the gold standard platform for coach-athlete interaction and structured workout delivery. **Best-in-class Garmin integration** — syncs Body Battery, Stress, Sleep, HRV, Women's Health data. Pushes structured workouts with per-step pace/power/HR targets. TSS/CTL/ATL/TSB model (Banister impulse-response, 1975) is well-documented in published science but rewards volume over quality. **No AI workout generation** — relies on human coaches and purchased plans ($5–200+). Premium: $20/month or $135/year.

**Final Surge** offers the same structured workout push to Garmin for **free** to athletes. No TSS equivalent, no AI features. Simpler than TrainingPeaks but with full workout builder and mobile app. Coach-friendly pricing.

**What to learn from them**: TrainingPeaks' developer API (allowing third-party apps to push workouts, upload activities, and sync metrics) is the model for how an ecosystem platform should work. Their TSS/CTL/ATL/TSB model, despite its limitations, remains the most widely understood training load framework.

---

## SECTION 2: Where every competitor fails

### Data streams universally ignored

**No competitor uses all available Garmin data streams.** The following data is collected by modern Garmin watches but unexploited by every third-party platform analyzed:

- **Running dynamics** (ground contact time, ground contact balance, vertical oscillation, vertical ratio, stride length) — available in FIT files at per-second resolution. Only Garmin's own algorithms use these internally. No third-party builds running-economy models from this data.
- **Per-record temperature** — embedded in FIT file records by watches with a temperature sensor. No competitor builds personal pace-temperature response curves from historical FIT data.
- **SpO2 (pulse oximetry)** — nightly and spot-check measurements available via API. Potentially useful for altitude adaptation and recovery monitoring. Universally ignored.
- **Respiration rate** — continuous 24/7 measurement on newer Garmin watches. Not used by any competitor for training readiness or aerobic threshold correlation.
- **Body Battery granularity** — minute-by-minute stress/recovery metric available via API. Most platforms that acknowledge it use only the daily summary or a binary high/low assessment.
- **Stress score** — minute-by-minute HRV-derived stress data. Available via `get_stress_data(date)` as time-series. Not used as a continuous readiness signal by any third party.

### Well-established science not implemented by anyone

- **Critical speed model**: Only Athletica.ai implements this. Despite being well-validated (Poole et al., 2016; Jones et al., 2019) as superior to lactate threshold for predicting endurance performance, 9 of 10 competitors ignore it entirely. Garmin does not compute critical speed — this is a genuine gap we must fill.
- **Pace-temperature curves from personal data**: TriDot adjusts for environment via EnviroNorm, but no competitor builds a personal pace-temperature response function from the athlete's own historical race and workout data, despite Ely et al. (2007) providing the scientific foundation. Garmin tracks heat acclimation status but does not adjust workout paces for forecast conditions.
- **Cardiac drift quantification for aerobic development tracking**: The rate of HR rise during steady-pace running (cardiac drift) is a well-established marker of aerobic fitness improvement. No competitor systematically calculates drift rates from historical workout data to track aerobic development. Garmin does not compute this.
- **ACWR with exponentially-weighted moving averages**: While Garmin tracks acute/chronic training load internally, it does not expose the ACWR ratio via API, and its internal load model does not implement the validated EWMA approach (Williams et al., 2017) with established injury-risk thresholds. This must be computed from activity data.
- **Running economy modeling from dynamics data**: Garmin collects GCT, vertical oscillation, stride length, and GCT balance at per-second resolution but does not synthesize these into a composite running economy trend metric. No third-party platform does this either.
- **Training debt and stimulus enforcement**: No platform tracks the gap between prescribed and completed training by workout type, or ensures that missed key sessions are rescheduled rather than dropped. Garmin's Training Status detects detraining but does not prescribe corrective action.
- **Garmin metrics that should be consumed, not replicated**: Garmin's Firstbeat-derived LTHR, VO2max, HRV Status, Training Readiness, Training Load, Body Battery, sleep stages, and stress scores are computed on-device with direct sensor access. No third-party computation from exported data can match this fidelity. Every competitor either ignores these metrics or attempts to replicate them independently — both approaches are wrong. The correct strategy is to consume Garmin's metrics as authoritative inputs and compute only what Garmin does not provide.

### The "last mile" integration gap

The final delivery problem — getting a fully informed, science-driven structured workout onto the athlete's watch with all intelligence encoded — is solved by none. The current landscape:

- **Runna and TrainingPeaks** push clean structured workouts with pace targets, but the workouts aren't informed by physiological readiness data.
- **Garmin DSW** uses physiological data but generates generic workouts without long-term periodization.
- **Athletica.ai** has the science and pushes workouts, but suffers from zone calculation bugs and limited environmental adjustment.
- **No platform** pushes a structured workout that simultaneously encodes: (a) pace targets adjusted for today's weather forecast, (b) intensity modified by Garmin's Training Readiness and HRV Status, (c) workout type selected by periodization phase and ACWR guardrails, (d) step notes with fueling cues and form reminders, and (e) a complete decision audit trail.

---

## SECTION 3: Competitive moat strategy

### 3a. Table stakes — Must-have features

These are minimum-viable capabilities without which the system cannot compete:

- **Structured workout generation** with per-step pace and HR targets, warm-up, intervals, recovery, cooldown, repeat blocks
- **Push to Garmin watch** via the Garmin Connect workout JSON API — workouts must appear on the watch before the athlete runs
- **Training zones** calculated from threshold data (not just age-based defaults)
- **Training log** with automatic Garmin activity sync
- **Basic periodization** — base, build, peak, taper, race phases with appropriate workout type distribution
- **Progressive overload** — systematic weekly volume and intensity progression within safe bounds
- **Long-run prescription** appropriate for marathon-specific preparation (up to 20–22 miles)

### 3b. Differentiators — Features that beat 90% of competitors

- **Critical speed model** auto-calculated from FIT file history using `scipy.optimize.curve_fit()` on the hyperbolic distance-time relationship. Only Athletica does this; doing it with transparent math and published error bounds is superior. Garmin does not compute critical speed — this is our primary independent model.
- **Garmin LTHR as zone foundation** — Training zones derived directly from Garmin's Firstbeat-computed lactate threshold heart rate, accessed via API. Garmin's LTHR detection uses on-device HR-pace coupling analysis with direct sensor access that external computation cannot match. Zones follow Coggan %LTHR boundaries (Z1: <81%, Z2: 81–90%, Z3: 90–96%, Z4: 96–102%, Z5: >102%). Pace zones derived from CS model (which Garmin does not provide) cross-referenced with Garmin's LTHR pace estimate.
- **Garmin readiness signals as primary inputs** — Consume Garmin's HRV Status, Training Readiness, Body Battery, Training Load, and Training Status directly via API as the primary physiological readiness signals. These Firstbeat metrics integrate multiple sensor streams (HR, HRV, SpO2, respiration, skin temperature, accelerometer) with proprietary algorithms validated across millions of users. The system uses Garmin's readiness data to modulate daily intensity rather than attempting to replicate HRV analysis from exported data. DFA alpha-1 via NeuroKit2 remains available as an *optional enhancement* for threshold refinement when chest-strap RR interval data is present.
- **Environmental pace adjustment** using forecast weather data from Open-Meteo (wet-bulb temperature + solar radiation + wind). Apply Ely et al. (2007) pace-temperature curves and the Running Writings heat model to adjust target paces on the day of workout delivery. Garmin tracks heat acclimation but does not adjust prescribed workout paces — this is a genuine gap we fill.
- **ACWR guardrails** with EWMA-based acute (7-day) and chronic (28-day) load tracking computed from activity TRIMP/TSS data. Garmin's internal acute/chronic load is not exposed as a ratio via API. Flag injury risk when ratio exceeds 1.3 or drops below 0.8. Override workout intensity to maintain safe zone.
- **Auditable training decisions** — every workout includes a decision trace linking each parameter to either a Garmin metric (with timestamp and value) or a computed metric (with formula and paper reference).

### 3c. Moat — Capabilities no competitor offers

**Data maximalism.** Ingest and analyze **every** Garmin data stream: second-by-second running dynamics from FIT files (GCT, vertical oscillation, stride length → running economy model), per-record temperature, SpO2 trends, continuous respiration rate, minute-by-minute Body Battery and stress time-series, and full sleep-stage data. Build derived metrics no one else computes:

- **Personal pace-temperature curve**: Regress historical race/workout performance against FIT-embedded temperature to build a personal heat-degradation function. Use this to adjust both prescribed paces (forecast) and normalize completed workout data (actual).
- **Cardiac drift rate index**: For each steady-state run, calculate the rate of HR increase over time at constant pace. Track this over weeks/months as an aerobic development metric.
- **Running economy composite**: Combine GCT, vertical oscillation ratio, stride length, and pace to create a per-run economy score. Track trends and flag when economy degrades (potential fatigue/injury marker).

**Garmin-first data philosophy.** The system treats Garmin's Firstbeat-derived metrics as authoritative for everything Firstbeat computes: LTHR, VO2max, HRV Status, Training Readiness, Training Load (acute/chronic), Body Battery, sleep stages, stress, heat/altitude acclimation, and recovery time. These are consumed directly via the Garmin Connect API and used as primary inputs to the rule engine. The system only computes metrics independently when Garmin does not provide them: critical speed, ACWR ratio, cardiac drift, running economy composite, personal pace-temperature curves, training debt, and ceiling projections. This eliminates an entire class of bugs (threshold miscalculation, HRV processing errors) that plague competitors like Athletica.ai who attempt to replicate Firstbeat's work from exported data.

**The workout-as-coach.** The pre-pushed Garmin structured workout is the primary coaching interface. Every workout encodes:

- **Per-step pace targets** adjusted for today's weather forecast (temperature, humidity, wind)
- **Step notes** (up to ~200 characters) containing: coaching cues ("land under hips, quick turnover"), fueling instructions ("take gel at start of this interval"), session purpose ("building fatigue resistance for miles 18-22")
- **Workout description** containing: session context, weekly training focus, current ACWR status, link to decision audit
- **Fueling reminders** encoded as brief recovery/rest steps with notes (since custom alerts are disabled during structured workouts on Garmin)
- **HR secondary validation** — even when pace is the primary target, HR bounds in the notes help the athlete validate effort

**Adaptive science engine.** Architecture designed so adding new research requires only:

1. Create a new Python file implementing the `ScienceRule` interface
2. Write unit tests for the new rule
3. Register it in the rule registry
4. The engine automatically evaluates it alongside existing rules, with conflict resolution handling priority

This means when a new paper on, say, SmO2-based intensity zones is published, it becomes a new `SmO2IntensityRule` in the `rules/extensions/` directory — no engine rewrite, no existing code changes. The rule set is versioned, so every workout records which science version generated it, enabling backtesting of new rules against historical data.

---

## SECTION 4: Free tools and open-source stack

### 4a. Garmin data access

**python-garminconnect** (v0.2.38, Jan 2026)
GitHub: https://github.com/cyberjunky/python-garminconnect — ~1,800 stars, MIT license, actively maintained. This is the primary data access layer. Exposes **105+ API methods** across 12 categories including: `get_hrv_data(date)`, `get_training_readiness(date)`, `get_body_battery(date)`, `get_stress_data(date)`, `get_sleep_data(date)`, `download_activity(activity_id)` (FIT file download), and — critically — **workout upload methods added in v0.2.37**. Authentication via garth with OAuth tokens persisting ~1 year. Rate limiting is undocumented; use conservative request patterns with delays between calls.

**garth** (v0.6.3, Jan 2026)
GitHub: https://github.com/matin/garth — 733 stars, MIT license, production-stable. The authentication layer that python-garminconnect depends on. Handles OAuth1/OAuth2 via Garmin SSO, supports MFA, auto-refreshes tokens. Also provides standalone typed data access (e.g., `garth.DailyStress.list()`, `garth.SleepData.get()`). **Critical limitation**: Cannot upload FIT workout files (returns 406). Workouts must use the JSON API.

**FIT file reading — fitdecode** (recommended)
GitHub: https://github.com/polyvertex/fitdecode — 193 stars, MIT license. ~20% faster than fitparse, thread-safe, handles chained FIT files. Reads all Garmin data fields including running dynamics, GCT, vertical oscillation, stride length, HRV/RR intervals, temperature, SpO2, and respiration rate from per-second FIT records.

**FIT file writing — garmin-fit-sdk**
GitHub: https://github.com/garmin/fit-python-sdk — 108 stars, official Garmin SDK. The only Python library that can **encode** FIT files. `pip install garmin-fit-sdk`. Use for creating workout FIT files when direct-to-device sideloading is preferred (USB transfer to `/GARMIN/NewFiles/`).

**Bulk export — garminexport**
GitHub: https://github.com/petergardfjall/garminexport — available on PyPI (`pip install garminexport`). Uses garth for auth. `garmin-backup` CLI for incremental backup of all historical FIT files. Essential for initial 13-year data import.

### 4b. Workout generation and push

**The JSON workout API is the primary path.** Structured workouts are created via `POST https://connectapi.garmin.com/workout-service/workout` with a JSON body. Scheduled via `PUT https://connectapi.garmin.com/workout-service/schedule/{workoutId}` with a date. Workouts auto-sync to the watch via Garmin Connect Mobile or Wi-Fi.

The JSON format supports all needed features:

- **Step types**: warmup (1), cooldown (2), interval (3), recovery (4), rest (5), repeat (6), other (7)
- **Target types**: `pace.zone` (with `targetValueLow`/`targetValueHigh` in sec/km), `heart.rate.zone` (BPM range), `cadence` (RPM range), `power.zone`, `no.target`
- **Duration types**: time (milliseconds), distance (meters), lap.button, calories
- **Repeat blocks**: `numberOfIterations` up to 99, with nested `workoutSteps`. Single-level nesting only (no repeats within repeats in practice).
- **Per-step notes**: `stepNotes` field, ~200 characters, displayed as popup on step transition
- **Workout description**: Free text, displayed in workout preview

**Maximum workout complexity**: The Connect API enforces a **50-step limit**. Each child step in a repeat block counts individually. FIT files sideloaded to the watch bypass this limit (tested to 77+ steps). For most marathon workouts, 50 steps is sufficient.

**Key reference implementations:**
- **garmin_planner** (https://github.com/yeekang-0311/garmin_planner) — Python, running-focused, YAML workout definitions with pace targets (`@P($VO2MaxP)`), HR zones (`@H(z2)`), repeat blocks. Schedule workouts to specific dates.
- **garmin-workouts** (https://github.com/mkuthan/garmin-workouts) — Python, YAML-based, import/export/schedule. Cycling-focused but demonstrates the full API workflow.
- **garmin-workouts-mcp** (https://github.com/st3v/garmin-workouts-mcp) — MCP server for AI-assisted workout creation using garth auth. Directly relevant pattern for AI integration.

### 4c. Weather data

**Open-Meteo** (https://open-meteo.com) is the clear choice: completely free, no API key, CC BY 4.0 license. Rate limits: 10,000 calls/day. Provides all critical parameters at **hourly resolution** (15-minute for US/Europe):

- Temperature, humidity, dewpoint, apparent temperature (feels-like)
- **Wet-bulb temperature** — directly available, critical WBGT component
- Solar radiation (GHI, direct, diffuse) — needed for WBGT calculation
- Wind speed/direction/gusts
- UV index, cloud cover, precipitation

**WBGT approximation**: Use the **Liljegren et al. (2008)** method with Open-Meteo's wet-bulb temperature, solar radiation, and wind data. Full formula: `WBGT = 0.7 × Tnwb + 0.2 × Tg + 0.1 × Td` where globe temperature is estimated from solar radiation and wind.

**Pace-temperature research to encode:**
- **Ely et al. (2007)** — top runners slow ~0.9% per 5°C WBGT increase; 300th-place runners ~3.2%
- **Running Writings heat model** — ~+0.4% pace increase per °F above 60°F, +0.2% per 1% humidity above 60%
- **Temperature + dewpoint sum method** — sum > 130 requires 3-4% pace slowdown; > 150 requires 8%+

Historical weather data from ERA5 reanalysis (1940–present) enables building personal pace-temperature curves from FIT file history matched with historical weather for training locations.

Python client: `openmeteo-requests` (v1.7.5) — official, FlatBuffers-based for zero-copy numpy arrays. GitHub: https://github.com/open-meteo/python-requests.

### 4d. Science engine dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| **numpy** | 2.x | Array operations, FIT record processing, rolling calculations |
| **scipy** | 1.14.x | `curve_fit` for critical speed model, `stats` for statistical calculations |
| **pandas** | 2.x | Training data DataFrames, `rolling()` for ACWR, time-series indexing |
| **NeuroKit2** | 0.2.12 | **Optional** — DFA alpha-1 threshold detection from chest-strap RR intervals. Not needed for core functionality since Garmin provides LTHR and HRV Status. GitHub: https://github.com/neuropsychology/NeuroKit (~5K stars, MIT, peer-reviewed in Behavior Research Methods). |
| **scikit-learn** | 1.x | Isolation forests for anomaly detection, gradient-boosted models for personal performance prediction |
| **statsmodels** | 0.14.x | Time-series decomposition, changepoint detection support |

Key function mappings:
- **Critical speed**: `scipy.optimize.curve_fit()` on `t = D / (S - CS)` where CS = critical speed, D' = distance capacity above CS. **This is the primary independent model — Garmin does not compute CS.**
- **ACWR**: `pandas.Series.ewm(span=7).mean() / pandas.Series.ewm(span=28).mean()` computed from activity TRIMP. **Garmin's acute/chronic load is not exposed as a ratio via API.**
- **Cardiac drift**: Linear regression of HR over time during constant-pace segments, computed from FIT file records. **Garmin does not compute this.**
- **Running economy composite**: Weighted combination of GCT, vertical oscillation ratio, stride length at standardized pace from FIT file running dynamics. **Garmin collects the raw dynamics but does not synthesize a composite trend.**
- **Garmin metrics consumed directly via API** (not computed): LTHR, LTHR pace, VO2max, HRV Status (7-day baseline, current status, trend), Training Readiness, Training Load (7-day, 28-day), Body Battery (time-series), stress (time-series), sleep stages/score, recovery time, heat/altitude acclimation status, Training Effect (aerobic/anaerobic per activity).

### 4e. Database and infrastructure

**PostgreSQL 17** via Docker (`postgres:17-alpine`). Entirely sufficient for single-user. Key features: JSONB for flexible workout/activity data with GIN indexing, `JSON_TABLE()` for API response parsing, window functions for CTL/ATL calculations, `generate_series()` for time-bucket aggregations. TimescaleDB is optional but adds negligible overhead via the `timescale/timescaledb-ha:pg17` Docker image.

**FastAPI** with **APScheduler** (v3.10.x) for task scheduling — runs in-process, no Redis/Celery needed. Schedule: daily workout generation at 8 PM, Garmin data sync every 2 hours, weather forecast update every hour, weekly insight analysis batch job.

**Docker Compose** orchestration: `api` (FastAPI + APScheduler), `db` (PostgreSQL), `ollama` (LLM narration service), all with health checks and `restart: unless-stopped`. Named volume for data persistence.

**GitHub Actions** for CI/CD: 2,000 free minutes/month for private repos. Pipeline: ruff lint + format check, mypy type checking, pytest with coverage against a PostgreSQL service container.

---

## SECTION 5: Future-proof science engine architecture

### The Strategy + Registry pattern

The science engine uses a custom lightweight rule engine (~1,000 lines of core Python) following Martin Fowler's explicit recommendation to build domain-specific rule engines rather than adopting general-purpose rule engine libraries (which are either unmaintained, too complex, or too general for a narrow domain of ~20–50 training rules).

Each science rule is a Python class implementing a common `ScienceRule` abstract base class with four required properties and one method:

```python
class ScienceRule(ABC):
    rule_id: str           # e.g., "hrv_readiness"
    version: str           # e.g., "1.2.0" (semver)
    priority: Priority     # SAFETY | DRIVE | RECOVERY | OPTIMIZATION | PREFERENCE
    required_data: list    # Data fields needed; rule skipped if missing
    
    def evaluate(self, state: AthleteState) -> Optional[RuleRecommendation]:
        """Return recommendation or None if rule doesn't apply."""
```

Rules are auto-discovered from `rules/` subdirectories (`safety/`, `recovery/`, `optimization/`, `preference/`, `extensions/`) and registered in a central `RuleRegistry`. The `ScienceEngine` iterates over registered rules sorted by priority, collects `RuleRecommendation` objects, and passes them to a `ConflictResolver`.

### Conflict resolution hierarchy

The priority system uses an `IntEnum` so numeric comparison determines precedence. The design philosophy is **potential-maximization with safety guardrails** — the system's default posture is to drive the hardest training the athlete can productively absorb, with safety constraints acting as circuit breakers rather than the primary voice. This is the opposite of most competitor architectures, which default to caution and must be overridden to train hard.

1. **SAFETY (0)** — Hard constraints that produce vetoes. These are non-negotiable circuit breakers. Example: `InjuryRiskACWRRule` vetoes high-intensity when ACWR > 1.5 (but explicitly permits training in the 1.3–1.5 caution zone with reduced intensity rather than blocking entirely), `RestingHRAlertRule` uses Garmin's resting HR data to flag abnormally elevated resting HR (>10% above 28-day rolling mean for 3+ consecutive days), `OverreachingDetectorRule` identifies functional overreaching from converging Garmin signals (HRV Status declining + Training Readiness persistently low + Training Status "Overreaching" + sleep score degradation persisting >5 days). Safety rules fire only on convergent multi-signal evidence from Garmin's own metrics, never on a single metric in isolation.
2. **DRIVE (1)** — Minimum training stimulus enforcement. These rules ensure the system never becomes overprotective. Example: `MinimumKeySessionRule` guarantees at least 2 key sessions per week (one tempo/threshold, one interval/VO2max) are completed or rescheduled within the same training block — never simply dropped. `TrainingDebtRule` tracks skipped or downgraded key sessions and increases their priority when readiness recovers, ensuring the training block's physiological intent is fulfilled. `AdaptationDemandRule` ensures progressive overload is maintained at a rate consistent with the athlete's current ceiling trajectory. `MarathonPaceVolumeRule` enforces cumulative time-at-marathon-pace targets by phase. DRIVE rules can be overridden only by SAFETY vetoes.
3. **RECOVERY (2)** — Physiological modulators with asymmetric response. Recovery rules consume Garmin's Firstbeat-derived readiness metrics directly and distinguish between expected post-training fatigue and genuine overreaching. Example: `GarminReadinessRule` uses Training Readiness score as the primary readiness gate — suppression within 24–48 hours of a key session is classified as normal acute fatigue and does NOT trigger intensity reduction; only persistent low readiness beyond the expected recovery window (adjusted for workout type and intensity) triggers modification. When recovery rules do fire, they prefer rescheduling key sessions to later in the week over replacing them with easy running. `SleepQualityRule` uses Garmin's sleep score and sleep stages (accessed via API) and gates intensity only on multi-night sleep disruption (3+ nights below baseline), not single poor nights. `BodyBatteryRule` uses the minute-by-minute Body Battery time-series to assess recovery trajectory — a Body Battery that fails to recover above 60 by wake time after 2+ nights signals genuine recovery deficit. `CumulativeFatigueRule` enforces deload weeks but sizes them to the minimum effective recovery (typically 60–70% of prior week volume, not 40–50%).
4. **OPTIMIZATION (3)** — Training prescription. Example: `PeriodizationRule` selects workout type based on current training phase, `ProgressiveOverloadRule` increases volume/intensity, `RaceSpecificityRule` adjusts marathon-pace volume and long-run structure as race approaches.
5. **PREFERENCE (4)** — Athlete constraints. Example: `TimeAvailabilityRule` caps workout duration, `WorkoutVarietyRule` ensures session diversity.

When rules conflict, **the higher-priority rule wins**. Within the same priority tier, the resolver uses the rule with higher `confidence` or blends recommendations (e.g., averaging intensity modifiers). Safety rules with `veto=True` override everything, but DRIVE rules override RECOVERY — meaning the system will reschedule a key session to a recovery day rather than skip it, unless SAFETY explicitly intervenes.

### Decision trace is first-class

Every call to `engine.prescribe(state)` returns both a `WorkoutPrescription` and a `DecisionTrace`. The trace records, for each registered rule: whether it fired, was skipped (missing data), or was not applicable — plus the rule's explanation string and version. This produces a complete narrative: *"Today's easy run was prescribed because: Garmin Training Readiness was 34 (below 50 threshold → recovery mode, Rule:garmin_readiness v1.2.0), ACWR was 1.35 (elevated → reduce intensity, Rule:acwr_guard v1.0.0), periodization is Base Week 4 (→ aerobic focus, Rule:periodization v2.1.0). Pace adjusted +12 sec/km for 82°F forecast (Rule:weather_adjust v1.0.0)."*

The decision trace and input data snapshot are stored in PostgreSQL alongside each generated workout, enabling full reproducibility and backtesting.

### Graceful degradation via required_data

Each rule declares the data fields it needs (e.g., `GarminReadinessRule.required_data = ["garmin_training_readiness", "garmin_hrv_status"]`). If any field is missing (e.g., Garmin API temporarily unavailable), the engine skips that rule and logs "skipped: missing data" in the trace. This means the system produces useful workouts even with partial data — if Garmin's daily metrics haven't synced yet, the engine falls back to ACWR and periodization rules. An athlete with a chest strap gets optional DFA alpha-1 threshold refinement via `DFAThresholdRule`, but all core functionality works from Garmin API data alone.

### Science versioning and backtesting

Each rule has a **semver version** (MAJOR.MINOR.PATCH). A `RuleSetManifest` is a frozen JSON snapshot of all active rules and their versions. Every generated workout stores the manifest hash. To backtest a new rule: the `BacktestRunner` replays the engine day-by-day over historical data with both old and new manifests, and the `BacktestComparator` evaluates metrics (training load distribution, predicted vs. actual performance, rule firing frequency).

Reproducibility is guaranteed by: frozen `AthleteState` dataclasses (immutable inputs), seeded PRNG for variety (`seed = hash(athlete_id + date + manifest_hash)`), and complete input snapshots stored with every workout record.

### Extension points for emerging research

| Area | Readiness | Extension point | Data inputs |
|------|-----------|----------------|-------------|
| **DFA alpha-1 threshold** | Actionable now (optional) | `DFAAlpha1Rule` in `rules/extensions/` | Chest-strap RR intervals, NeuroKit2 |
| **Running power (Stryd)** | Actionable now | `RunningPowerZoneRule` in `rules/extensions/` | Watts, critical power, form power ratio |
| **SmO2 (Moxy, Train.Red)** | 2–4 years | `SmO2IntensityRule` interface defined | SmO2%, total hemoglobin, re-oxygenation rate |
| **CGM** | 3–5 years | Loose `GlucoseAvailabilityRule` interface | Interstitial glucose time-series, CV, time-in-range |
| **Genetics** | 3–5 years | `GeneticRecoveryModifier` interface | Genotype for ACTN3, ACE, selected SNPs |

The extensions directory exists from day one with defined interfaces. When research matures, implementation requires only filling in the `evaluate()` method and writing tests.

### Recommended directory structure

```
science_engine/
├── engine.py                      # ScienceEngine orchestrator
├── registry.py                    # RuleRegistry with auto-discovery
├── models/
│   ├── athlete_state.py           # Frozen dataclass: all inputs
│   ├── recommendation.py          # RuleRecommendation dataclass
│   ├── decision_trace.py          # Full audit record
│   ├── workout.py                 # WorkoutPrescription output
│   └── enums.py                   # Priority enum
├── rules/
│   ├── base.py                    # Abstract ScienceRule base class
│   ├── safety/                    # SAFETY tier rules (convergent Garmin signals)
│   │   ├── overreaching_detector.py  # Convergent: HRV Status + Training Status + sleep
│   │   ├── resting_hr_alert.py       # Garmin resting HR trend
│   │   └── injury_risk_acwr.py       # Computed ACWR (Garmin doesn't expose ratio)
│   ├── drive/                     # DRIVE tier rules — minimum stimulus enforcement
│   │   ├── minimum_key_session.py
│   │   ├── training_debt.py
│   │   ├── adaptation_demand.py
│   │   └── marathon_pace_volume.py
│   ├── recovery/                  # RECOVERY tier rules (consume Garmin Firstbeat metrics)
│   │   ├── garmin_readiness.py    # Training Readiness + HRV Status gate
│   │   ├── body_battery.py        # Body Battery recovery trajectory
│   │   ├── sleep_quality.py       # Garmin sleep score + sleep stages
│   │   └── cumulative_fatigue.py
│   ├── optimization/              # OPTIMIZATION tier rules
│   │   ├── periodization.py
│   │   ├── progressive_overload.py
│   │   ├── workout_type_selector.py
│   │   └── race_specificity.py
│   ├── preference/                # PREFERENCE tier rules
│   │   ├── time_availability.py
│   │   └── workout_variety.py
│   └── extensions/                # Future/optional rules
│       ├── dfa_alpha1.py          # Optional: DFA threshold from chest-strap RR data
│       ├── running_power.py
│       ├── smo2_intensity.py
│       └── genetic_recovery.py
├── conflict_resolution/
│   ├── resolver.py                # Priority hierarchy + blending
│   └── strategies.py              # HighestPriorityWins, WeightedBlend
├── versioning/
│   ├── manifest.py                # RuleSetManifest snapshots
│   └── schema.py                  # DB schema for versions + audits
├── backtesting/
│   ├── runner.py                  # Replay engine over historical data
│   ├── comparator.py              # Compare manifests' outputs
│   └── metrics.py                 # Evaluation metrics
├── periodization/
│   └── state_machine.py           # FSM: Base→Build→Peak→Taper→Race
└── tests/
    ├── test_rules/                # Unit test per rule
    ├── test_engine.py             # Integration tests
    ├── test_conflict_resolution.py
    └── test_backtesting.py
```

---

## SECTION 6: The killer feature — workout-as-coach

### What Garmin structured workouts support

The structured workout is the system's primary coaching interface. On modern Garmin watches (FR265, FR965, Fenix 7/8), structured workouts display:

- **A target gauge** — a colored graphical indicator showing current pace/HR/power relative to the step's target range. Green when in zone, red when out. DC Rainmaker: "It'll give you a nifty graphical gauge for the target."
- **Step transition popups** with vibration/beep alerts and display of the next step's targets and notes
- **Repeat counter** showing current rep (e.g., "Rep 3/5")
- **Step notes** displayed as popups during transitions — the primary text coaching channel

**Critical constraint**: **Custom alerts are disabled during structured workout execution.** Nutrition/hydration reminders, max/min HR alerts, and all other custom alerts do not fire once a structured workout starts. All coaching intelligence must be embedded within the workout structure itself.

### Encoding maximum intelligence

**Per-step notes** (~200 characters visible, displayed on step transition): Use for coaching cues, fueling instructions, RPE guidance, session context. Example: "Marathon pace effort, 7/10 RPE. Focus on hip drive. Take gel at start."

**Workout description** (free text, visible in preview): Embed session purpose, weekly context, current training metrics, and the decision audit summary. Example: "Key W8 session: Building fatigue resistance for miles 18-22. ACWR: 1.15 (green). Garmin Readiness: 72 (green). Adjusted -8 sec/km for 78°F forecast."

**Fueling as workout steps**: Since custom alerts won't fire, encode fueling reminders as brief (15–30 second) recovery or "other" type steps between interval blocks with notes like "Gel + 4oz water now." This consumes step count (50-step API limit) but is the only reliable on-wrist fueling cue.

**Step names as quick identifiers**: The `wkt_step_name` field (~16–20 visible characters) shows prominently during execution. Use descriptive labels: "MP Pace," "Easy Jog," "Strides," "Float," "Gel Break."

**Cadence as dual-purpose target**: When pace is primary and cadence is secondary coaching goal, use step notes for cadence guidance since only one target type per step is allowed. Alternatively, insert brief cadence-target check-in steps between pace-target intervals.

**Connect IQ "Workout Notes" data field**: Third-party data field (installable from Connect IQ store) that displays step notes as a persistent data field rather than a popup, showing current AND next step notes simultaneously. Recommended for all users.

### The delivery pipeline

The complete workout delivery flow:

1. **Evening before** (8 PM via APScheduler): Science engine evaluates `AthleteState` (latest Garmin Training Readiness, HRV Status, Body Battery trajectory, ACWR, sleep score, periodization phase, training debt ledger)
2. **Weather fetch**: Open-Meteo forecast for athlete's location at planned run time
3. **Prescription**: Engine generates `WorkoutPrescription` with pace targets adjusted for forecast weather
4. **Workout construction**: Convert prescription to Garmin Connect JSON format — steps with pace targets, HR validation bounds, step notes with coaching cues and fueling instructions, workout description with session context
5. **Push**: `POST /workout-service/workout` via python-garminconnect, then `PUT /workout-service/schedule/{workoutId}` for tomorrow's date
6. **Auto-sync**: Garmin Connect Mobile pushes the workout to the watch via Bluetooth or Wi-Fi
7. **Execution**: Athlete selects workout, runs with guided targets, receives step-by-step coaching via notes and alerts
8. **Post-run**: System syncs completed activity, downloads FIT file, extracts second-by-second data, updates all models (critical speed, running economy, cardiac drift, pace-temp curve), recalculates ACWR and readiness metrics

---

## SECTION 7: Insight discovery and LLM narration layer

### The problem deterministic rules cannot solve

The science engine evaluates each rule independently against the current athlete state — HRV against its threshold, ACWR against its bands, periodization against its phase calendar. What it cannot do is detect emergent patterns across dimensions that no rule was written to check. With 13+ years of Garmin data spanning HR, HRV, sleep stages, stress, Body Battery, running dynamics, temperature, pace, cadence, and elevation — all at per-second or per-minute granularity — there are combinatorial relationships that no human would think to encode as explicit rules.

Consider a concrete example: GCT balance drifts asymmetric by 1.5% in the 48 hours following any night where deep sleep drops below 45 minutes, but only when weekly volume exceeds 90km. That is a three-variable interaction that would never be written as a rule, yet it could be a reliable early signal for compensatory movement patterns that precede injury. A rule engine will never find this. A statistical model scanning for multivariate correlations across historical data can.

### Statistical insight discovery — the right tool for pattern recognition

LLMs are poor at numerical pattern recognition. They cannot reliably compute correlations, detect regime changes in time series, or identify statistically significant multivariate interactions. The correct approach uses established ML and statistical methods, all implementable with tools already in the stack (scikit-learn, scipy, statsmodels):

**Anomaly detection** via isolation forests on multivariate physiological data. Input features include Garmin's nightly HRV Status, sleep score, sleep stage durations, Body Battery trajectory, resting HR, Training Readiness, stress time-series, and running dynamics from recent workouts. The model learns the athlete's normal physiological signature and flags days where the combination of Garmin signals departs from the learned distribution — even when no single metric breaches its individual threshold.

**Cross-correlation analysis** between lagged variables. Systematically compute correlations between every pair of metrics at multiple time lags (1–7 days). Does a sleep metric at lag-2 predict a running dynamics shift at lag-0? Does Body Battery trajectory in the 12 hours post-workout correlate with next-day HRV recovery? These lagged relationships are invisible to same-day rule evaluation but can reveal athlete-specific recovery dynamics.

**Changepoint detection** using PELT (Pruned Exact Linear Time) or BOCPD (Bayesian Online Changepoint Detection) algorithms. These identify when the athlete's physiological response regime shifts — for example, when the relationship between training load and HRV recovery fundamentally changes due to accumulated fatigue, fitness gain, or external stressors. A regime shift detected across multiple metrics simultaneously is a strong signal that the training plan needs re-evaluation.

**Personal performance prediction** via gradient-boosted models (LightGBM or XGBoost) trained on the athlete's own historical data. Predict which combinations of pre-workout physiological state, training load history, sleep quality, and environmental conditions produce the best subsequent workout performances. Over time, this builds a personal model of optimal training conditions that informs workout scheduling and intensity selection.

**Trend divergence monitoring** compares metrics that normally move together. When critical speed is stable but cardiac drift rate is worsening, it suggests aerobic base erosion masked by neuromuscular fitness. When running economy (GCT + vertical oscillation composite) degrades while pace holds steady, it suggests compensatory effort that is unsustainable. These divergences are computed as rolling correlation breakdowns between paired metrics.

### The LLM as insight narrator — not decision-maker

The problem with statistical insight discovery is not computation but attention. A batch job might identify that cardiac drift has trended 12% worse over three weeks while critical speed remains stable, or that an anomaly cluster appeared in the sleep-to-recovery pipeline. Those findings sit in database tables. Without narration, they go unnoticed.

The LLM (served locally via Ollama on the Unraid server) functions as an **insight narrator and contextualizer**. It receives structured analytical outputs — anomalies detected, correlations discovered, trend divergences flagged — and synthesizes them into a daily or weekly coaching briefing. The briefing connects multiple analytical signals into a coherent narrative with actionable context grounded in the athlete model.

An example output: *"Your aerobic engine is quietly regressing despite pace holding steady — cardiac drift has worsened 12% over three weeks while GCT has increased 4ms on easy runs. This pattern has preceded overreaching episodes twice in your training history (March 2024, November 2023). Consider prioritizing aerobic base work over the next 7–10 days before entering the build phase."*

The critical architectural principle: **the LLM never discovers insights** (the statistical models do that), **never prescribes training responses** (the rule engine does that), and **never makes safety-critical decisions**. It narrates and contextualizes structured data into human-readable coaching intelligence.

### Architecture: the InsightAnalyzer pipeline

**Batch analysis job** (`InsightAnalyzer`): Runs weekly via APScheduler, executing the full suite of statistical models against a rolling data window (typically 4–12 weeks). Produces structured `Insight` objects:

```python
@dataclass(frozen=True)
class Insight:
    insight_id: str                    # Unique identifier
    insight_type: InsightType          # ANOMALY | CORRELATION | TREND_DIVERGENCE | CHANGEPOINT | PREDICTION
    severity: Severity                 # INFO | NOTABLE | WARNING | CRITICAL
    title: str                         # Brief summary, e.g., "Aerobic regression detected"
    evidence: dict                     # Statistical evidence: metrics, p-values, effect sizes
    affected_metrics: list[str]        # Which data streams are involved
    historical_precedents: list[str]   # Past occurrences of similar patterns (if any)
    suggested_action: Optional[str]    # Proposed rule adjustment or training modification
    confidence: float                  # 0.0–1.0 based on statistical significance and sample size
```

**Insight storage**: All insights are persisted in PostgreSQL with full evidence payloads, enabling trend analysis of the insights themselves (are anomalies clustering? are changepoints accelerating?).

**LLM narration**: A separate `InsightNarrator` service passes the week's insights plus the current athlete state, training phase, and upcoming race calendar to the local Ollama model. The prompt is tightly constrained: the model receives only the structured insight data and is instructed to synthesize a coaching briefing without inventing claims beyond what the evidence supports. The output is a markdown briefing stored alongside the insights.

**Rule engine feedback loop**: When an insight reaches WARNING or CRITICAL severity and includes a `suggested_action`, it is routed to the athlete for review as a proposed rule modification. If approved, the suggestion is encoded as a temporary rule override or a permanent new rule in the `extensions/` directory. This keeps the deterministic audit trail intact — no insight-driven training change occurs without explicit approval and formal rule integration.

### Recommended models and resource requirements

For Ollama on the Unraid server (CPU-only inference based on existing hardware constraints): Llama 3.1 8B (Q4_K_M quantization) or Mistral 7B provide adequate narrative synthesis quality at reasonable inference speed. The narration task is not latency-sensitive (briefings are generated overnight), so even 2–3 minute generation times on CPU are acceptable. The statistical models (isolation forests, cross-correlation, PELT) run in seconds on 13 years of daily-granularity data using scikit-learn and scipy.

### Insight engine directory structure

```
insight_engine/
├── analyzer.py                    # InsightAnalyzer orchestrator
├── models/
│   ├── insight.py                 # Insight dataclass
│   └── enums.py                   # InsightType, Severity
├── detectors/
│   ├── anomaly.py                 # Isolation forest on multivariate physio data
│   ├── cross_correlation.py       # Lagged correlation scanner
│   ├── changepoint.py             # PELT / BOCPD regime shift detection
│   ├── trend_divergence.py        # Paired metric correlation breakdown
│   └── performance_predictor.py   # Personal GBM model
├── narrator/
│   ├── narrator.py                # Ollama integration for briefing generation
│   ├── prompts.py                 # Constrained prompt templates
│   └── formatter.py               # Structured data → prompt context
├── feedback/
│   ├── proposal.py                # Rule modification proposals from insights
│   └── approval.py                # Athlete review and approval workflow
└── tests/
    ├── test_detectors/
    ├── test_narrator.py
    └── test_feedback.py
```

---

## SECTION 8: Potential maximization engine

### Design philosophy — the system's job is to make you faster

Most training platforms default to caution. Garmin DSW caps long runs at 1h50. Runna's injury controversy stems from the opposite extreme — no physiological feedback at all. The correct philosophy is neither safety-first nor recklessness, but **potential-maximization with safety guardrails**. The system should drive the hardest training the athlete can productively absorb, with safety constraints acting as circuit breakers that fire on convergent evidence rather than as the primary voice in every decision.

The goal time is an *output* of the system, not an input. Rather than anchoring to an arbitrary target and building backward, the system continuously models the athlete's physiological ceiling from training data and drives toward it. If the data shows the ceiling is 2:48, the system trains for 2:48. If it's 3:05, the system trains for 3:05 and works to raise the ceiling. This eliminates both the risk of capping ambition below actual potential and the risk of pursuing a goal the body cannot currently support.

### The ceiling model

The athlete's current performance ceiling is derived from converging estimates:

**Critical speed extrapolation.** CS from the hyperbolic distance-time model provides the speed at maximal metabolic steady state. Marathon pace sits at a known percentage of CS that varies by fitness level (Smyth & Muniz-Pumares 2020: ~84.8% on average, ~90–93% for well-trained marathoners). The system continuously updates CS from recent race-quality efforts and projects current marathon ceiling = CS × athlete-specific %CS (initially calibrated from historical race data, refined as more data accumulates).

**VO2max trajectory.** Garmin's Firstbeat-derived VO2max estimate — accessed directly via API — provides the primary aerobic capacity trend signal. With on-device sensor access and continuous refinement across workouts, Garmin's VO2max is more reliable than any external calculation. The system tracks the rate of VO2max change over time and projects where it will be at race day given current training trajectory. Cross-referenced with CS progression and actual race/time-trial performance for ceiling model convergence.

**Running economy trend.** The running economy composite (GCT + vertical oscillation ratio + stride length at standardized pace) tracks efficiency changes over time. Improving economy at constant VO2max directly raises the ceiling; degrading economy signals that the ceiling may be lower than VO2max alone suggests.

**Durability profile.** How much performance degrades over duration — specifically, the ratio of second-half to first-half pace in long runs, and cardiac drift rate during 90+ minute efforts. An athlete whose pace fades 8% in the final third of a 30km run has a lower effective marathon ceiling than one who fades 3%, even at identical CS values.

The ceiling model combines these signals into a projected race-day marathon time with confidence intervals. The system reports this as a range (e.g., "current ceiling: 2:52–2:58 at 85% confidence") and updates it weekly.

### Adaptive stimulus calibration

Rather than fixed progression percentages, the system calibrates training stimulus to the gap between current fitness and projected ceiling:

**When the trajectory is on track** (fitness metrics progressing at or above the rate needed to reach the ceiling by race day): maintain current training load and stimulus. No need to push harder if adaptation is occurring at the required rate.

**When the trajectory falls short** (fitness metrics plateauing or progressing too slowly): increase training stimulus within safe bounds. This might mean adding a third key session in a week, extending marathon-pace segments in the long run, increasing interval volume, or raising weekly mileage — whichever dimension the ceiling model identifies as the limiting factor.

**When the trajectory exceeds projections** (fitness improving faster than expected): the system raises the ceiling estimate rather than backing off. The athlete is showing capacity for more, and the system should capitalize on it. It may also bank the surplus by holding stimulus steady, building a buffer against future disruptions (illness, travel, life stress).

**When a safety constraint fires** (genuine overreaching detected from convergent signals): the system applies the minimum effective recovery — not a full reset, but enough to restore productive training. DRIVE tier rules then ensure that key sessions missed during recovery are rescheduled rather than abandoned, preserving the training block's intent.

### Training debt accounting

Every training block has a physiological intent — a set of adaptations it must produce to keep the athlete on trajectory toward the ceiling. When sessions are missed, downgraded, or rescheduled, the intended adaptation does not disappear; it becomes training debt.

The `TrainingDebtRule` maintains a ledger by workout type:

- **Tempo/threshold debt**: Cumulative time at lactate threshold pace that was prescribed but not completed. Repaid by extending threshold segments in subsequent sessions or adding a threshold component to an easy run.
- **VO2max interval debt**: Cumulative work at VO2max intensity that was missed. Repaid by adding reps, extending interval sessions, or substituting a fartlek with VO2max segments.
- **Long-run debt**: If a peak long run is missed, it cannot be trivially rescheduled — the system identifies the next appropriate window and adjusts the build-up accordingly rather than simply skipping to the next planned long run.
- **Marathon-pace debt**: Cumulative time at MP that was prescribed but not completed. This is the most critical debt type in the specific phase — marathon performance depends heavily on neuromuscular familiarity with race pace under fatigue.

Debt has a decay function — old debt matters less than recent debt, because the training window moves forward. Debt older than 3 weeks is discounted by 50%; debt older than 6 weeks is written off. The system never attempts to repay all accumulated debt in a single week (which would spike ACWR), but instead distributes repayment across available sessions within safe load constraints.

### Asymmetric readiness response

A critical flaw in naive readiness-gated training is treating all readiness dips equally. The system implements an asymmetric response model using Garmin's Firstbeat metrics:

**Expected suppression** (Training Readiness drops and HRV Status shows "Low" within 24–48 hours of a key session, with magnitude proportional to session intensity): This is normal acute fatigue. The system classifies it as such using a lookup table of expected recovery timelines by workout type (e.g., VO2max intervals → 36–48hr readiness suppression expected; easy long run → 12–24hr). No intensity reduction is triggered. The planned easy run for the next day proceeds as scheduled.

**Unexpected suppression** (Training Readiness drops without recent training stimulus, or remains below baseline beyond the expected recovery window; Body Battery fails to recover above 60 by wake time): This suggests external stressors (poor sleep, illness onset, psychological stress, travel) or accumulated fatigue beyond normal. The system responds by first checking if a key session is scheduled within the next 48 hours. If yes, it delays rather than cancels — shifting the key session by 1–2 days and inserting an easy day. If the suppression persists beyond 3 days, RECOVERY rules escalate to modify the training week.

**High readiness signal** (Training Readiness above 70 and HRV Status shows "Above Baseline" or "Balanced High"): The system treats this as a readiness signal for high-quality work. If a key session is scheduled within 24 hours, the system may increase the session's intensity or volume within the bounds of the training plan. If no key session is imminent, it notes the readiness surplus for the next scheduling decision.

**Multi-signal convergence requirement**: No single Garmin metric triggers an intensity reduction in isolation. The system requires at least two of the following to converge before overriding a planned key session: (1) Training Readiness below 30 beyond expected recovery window, (2) HRV Status "Low" for 3+ consecutive days, (3) Garmin sleep score below baseline for 2+ nights, (4) Body Battery failing to recover above 50 for 2+ mornings. This prevents the system from being whipsawed by normal biological variability in any single Firstbeat metric.

### Volume ceiling discovery

Rather than prescribing a fixed peak volume (e.g., "80–130 km/week for sub-3:00"), the system discovers the athlete's personal volume ceiling empirically:

**Historical analysis.** From 13+ years of data, identify the highest sustained weekly volumes (4+ consecutive weeks) that produced positive adaptation without subsequent injury or illness. Also identify the volume ranges that preceded injury episodes or performance regression.

**Progressive probing.** During the base phase, increase volume at contextual rates (8–10% early, 3–5% later) and monitor the adaptation response: is cardiac drift improving? Is HRV recovering normally between sessions? Is running economy maintaining or improving? Is sleep quality stable? If all signals are positive, continue increasing. If any signal deteriorates beyond expected post-load fluctuation, hold volume for 2–3 weeks before attempting another increase.

**Individual volume-response curve.** Over time, the system builds a personal dose-response model relating weekly volume to adaptation rate. This curve has diminishing returns and eventually a negative inflection point — the volume above which additional mileage produces diminishing fitness gains and increasing injury risk. The system targets the volume just below this inflection point as the sustainable peak for the training cycle.

### Race-pace confidence scoring

Marathon performance depends not just on physiological capacity but on the athlete's neuromuscular readiness and psychological confidence at race pace under fatigue. The system tracks a **race-pace confidence score** based on:

- **Cumulative time at marathon pace** across the training cycle, weighted toward recent sessions. Minimum threshold: 90–120 minutes of total MP work in the final 10 weeks.
- **Longest continuous MP segment** completed successfully (pace within target range, cardiac drift within acceptable bounds). Target: at least one 45–60 minute sustained MP effort in the specific phase.
- **MP under fatigue**: Time spent at MP in the second half of long runs, when glycogen depletion and muscular fatigue simulate late-race conditions. This is the highest-value MP training.
- **Pace execution accuracy**: How consistently the athlete holds MP targets in structured workouts — standard deviation of actual vs. prescribed pace across MP sessions.

The confidence score is reported alongside the ceiling model. An athlete with a 2:55 ceiling but a confidence score of 62/100 (insufficient MP work under fatigue) is likely to run 3:00–3:05. The system responds by increasing MP prescription priority — adding MP segments to long runs, scheduling dedicated MP tempo sessions, and encoding MP "test" workouts that simulate race conditions.

---

## Prioritized implementation roadmap

### Phase 1: Foundation (weeks 1–3)

Build the data pipeline and prove the core loop works end-to-end.

1. **Garmin authentication and data sync** — garth + python-garminconnect. Implement token persistence, activity list retrieval, FIT file download, and all Firstbeat daily metrics: LTHR (HR and pace), VO2max, HRV Status (baseline + current + trend), Training Readiness, Training Load (7-day + 28-day), Training Status, Body Battery (time-series), stress (time-series), sleep score/stages, recovery time, heat/altitude acclimation.
2. **FIT file parsing** — fitdecode for reading. Extract per-second records: pace, HR, cadence, running dynamics (GCT, vertical oscillation, stride length), temperature, GPS.
3. **Historical data import** — garminexport for bulk FIT backup of 13 years of data. Parse and load into PostgreSQL.
4. **Database schema** — PostgreSQL with tables for: athletes, activities (JSONB for flexible fields), daily_metrics, workouts (with decision_trace JSONB), rule_versions, rule_set_manifests, insights.
5. **Simple workout push** — Create a hardcoded test workout in Garmin JSON format, push via API, verify it appears on the watch with pace targets, step notes, and workout description.

### Phase 2: Science engine core (weeks 4–7)

Implement the rule engine and first set of science rules.

6. **Science engine architecture** — Implement `ScienceRule` ABC, `RuleRegistry`, `ScienceEngine`, `ConflictResolver`, `DecisionTrace`. Full test coverage of the engine itself.
7. **Critical speed model** — Fit from historical race/workout data using `scipy.optimize.curve_fit()`. Compute CS and D' (distance capacity above CS). Derive training zones from CS.
8. **Garmin readiness integration** — Consume Training Readiness, HRV Status (baseline, current, trend), Body Battery (time-series), sleep score/stages, stress (time-series), Training Status, and Training Load directly from Garmin API via python-garminconnect. Store as daily_metrics in PostgreSQL. These Firstbeat metrics are the primary readiness inputs to the rule engine.
9. **Garmin LTHR zone system** — Read Garmin's Firstbeat-computed lactate threshold HR and pace via API. Derive training zones using Coggan %LTHR boundaries. Pace zones derived from CS model cross-referenced with Garmin's LTHR pace. All workout HR targets use Garmin's LTHR as the anchor — no independent threshold calculation.
9. **ACWR calculation** — EWMA-based acute (7-day) and chronic (28-day) workload. Flag zones: <0.8 (undertrained), 0.8–1.3 (safe), 1.3–1.5 (caution), >1.5 (danger). Implement as `InjuryRiskACWRRule` in safety tier.
10. **Periodization FSM** — Base → Build → Peak → Taper → Race → Recovery state machine. Define workout-type distributions per phase (e.g., Base: 80% easy / 10% tempo / 10% intervals).
11. **Progressive overload rule** — Contextual volume progression: 8–10% in early base (low absolute loads, fresh body), tapering to 3–5% as peak volume approaches. Deload every 3rd or 4th week sized to minimum effective recovery (60–70% of prior week, not 40–50%).
12. **DRIVE tier rules** — Implement `MinimumKeySessionRule` (2 key sessions/week guaranteed or rescheduled), `TrainingDebtRule` (track skipped sessions by type, repay when readiness recovers), `AdaptationDemandRule` (progressive overload rate tied to ceiling trajectory), `MarathonPaceVolumeRule` (cumulative MP time targets by phase).

### Phase 3: Environmental adjustment and workout intelligence (weeks 8–10)

12. **Weather integration** — Open-Meteo API integration with `openmeteo-requests`. Fetch forecast for athlete's location and planned run time. Calculate WBGT approximation from wet-bulb temp + solar radiation + wind.
13. **Pace-temperature adjustment** — Implement Ely et al. (2007) curves + Running Writings model. Regress personal pace-temp curve from historical FIT data matched with ERA5 historical weather.
14. **Workout-as-coach** — Full structured workout generation with: weather-adjusted pace targets per step, HR validation bounds in step notes, coaching cues, fueling reminders as dedicated steps, workout description with session context and decision audit summary.
15. **Workout scheduling** — APScheduler generates and pushes next day's workout at 8 PM. Handle weather forecast updates.

### Phase 4: Potential maximization and advanced models (weeks 11–14)

16. **Ceiling model** — Implement converging ceiling estimate from critical speed extrapolation (CS × athlete-specific %CS from historical data), VO2max trajectory projection, running economy trend, and durability profile (second-half fade ratio, cardiac drift rate in 90+ min efforts). Report as a projected race-day time range with confidence intervals, updated weekly.
17. **Adaptive stimulus calibration** — Compare current fitness trajectory against ceiling projection. When trajectory falls short, identify the limiting factor (aerobic capacity, lactate threshold, economy, durability) and increase stimulus in that dimension. When trajectory exceeds projections, raise the ceiling estimate rather than backing off.
18. **Training debt accounting** — Implement the debt ledger by workout type (tempo, VO2max, long-run, marathon-pace). Debt decay function (50% discount at 3 weeks, write-off at 6 weeks). Distribute repayment across available sessions within safe ACWR bounds.
19. **Asymmetric readiness response** — Implement expected vs. unexpected HRV suppression classification using workout-type recovery timelines. Multi-signal convergence requirement (2+ signals must converge before overriding a planned key session). Elevated HRV treated as readiness signal for increased stimulus.
20. **Volume ceiling discovery** — Analyze historical data for highest sustained volumes with positive adaptation. Build personal volume-response curve during base phase through progressive probing with adaptation monitoring.
21. **Race-pace confidence scoring** — Track cumulative MP time, longest continuous MP segment, MP under fatigue (second-half long runs), and pace execution accuracy. Report alongside ceiling model and increase MP prescription priority when score is below threshold.
22. **Cardiac drift index** — Calculate HR rise rate during steady-state segments. Track as an aerobic development metric and durability input.
23. **Running economy composite** — Derive per-run score from GCT, vertical oscillation ratio, stride length, pace. Track trends as ceiling model input.
24. **DFA alpha-1 optional enhancement** — For sessions with chest-strap RR interval data, compute DFA alpha-1 via NeuroKit2 to provide supplementary threshold validation. This is informational — it does not override Garmin's LTHR but provides an additional data point for the athlete's awareness and for the insight engine's anomaly detection.
25. **Taper model** — Implement exponential decay taper (Banister model) sized to the minimum effective recovery that preserves fitness. Maintain intensity and key session frequency through taper.
26. **Backtesting framework** — `BacktestRunner` to replay historical data with current rule set. Compare prescribed training against what was actually done. Validate that the system would have produced better training and a higher ceiling.

### Phase 5: Insight discovery and narration (weeks 15–18)

27. **Insight detectors** — Implement isolation forest anomaly detection, cross-correlation scanner, PELT changepoint detection, and trend divergence monitoring against the accumulated training database.
28. **Personal performance predictor** — Train a gradient-boosted model on historical data to predict workout quality from pre-workout physiological state, sleep, load history, and environment.
29. **Ollama narration service** — Integrate with the existing Ollama instance on Unraid. Implement constrained prompt templates that synthesize weekly insights into coaching briefings grounded in the statistical evidence.
30. **Feedback loop** — Build the proposal/approval workflow for routing insight-driven training suggestions through the rule engine with athlete review.

### Phase 6: Extensions and iteration (ongoing)

31. **Running power rules** (if Stryd available) — `RunningPowerZoneRule` using critical power.
32. **Long-run fuel planning** — Encode marathon-specific long runs with per-mile fueling strategy encoded as workout steps.
33. **Race-day workout** — Generate a race-day Garmin workout with per-mile pace targets adjusted for course profile and weather, with fueling steps at planned aid stations.
34. **Dashboard** — FastAPI + HTMX or similar lightweight frontend showing training trends, readiness status, critical speed progression, ceiling model projections, ACWR, race-pace confidence score, insight briefings, and decision audit logs.

---

This architecture produces a system whose primary directive is to **find and reach the athlete's physiological ceiling**, not merely to keep them healthy or hit an arbitrary time target. Every training decision is traceable to published science. Every Garmin data stream is exploited. Every workout is adjusted for the athlete's physiological state and today's weather. The DRIVE tier ensures the system never becomes overprotective — key sessions are rescheduled rather than abandoned, training debt is tracked and repaid, and progressive overload is calibrated to the gap between current fitness and the projected ceiling. Safety constraints act as circuit breakers on convergent multi-signal evidence, not as the default response to normal training fatigue. The insight discovery layer mines 13+ years of personal data for emergent patterns that no rule was written to detect, while the LLM narrator ensures those findings reach the athlete as actionable coaching intelligence. The result is a system that drives the hardest training the athlete can productively absorb, within reasonable safety limits, and delivers it as a fully-informed structured workout on their wrist before they step out the door. No competitor does all of these things. Most do none of them.
