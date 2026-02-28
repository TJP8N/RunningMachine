"""AIEnduranceBeater — Streamlit MVP Dashboard.

Run with:
    .venv38/Scripts/streamlit run streamlit_app/app.py

Requires the .venv38 environment (Python 3.8+, streamlit installed).
"""

from __future__ import annotations

import io
import zipfile
from datetime import date

import streamlit as st

from science_engine.engine import ScienceEngine
from science_engine.models.decision_trace import RuleStatus
from science_engine.models.enums import DurationType, SessionType, StepType
from science_engine.serialization import to_garmin_json, to_garmin_json_string

from helpers import (
    DAY_NAMES,
    PHASE_LABELS,
    SESSION_COLORS,
    STEP_COLORS,
    STEP_LABELS,
    build_athlete_state,
    build_athlete_state_with_garmin,
    format_duration,
    format_hr_range,
    format_pace_range,
    list_profiles,
    load_profile,
    save_profile,
)

# Conditional Garmin imports — only available when garminconnect is installed
try:
    from garmin_client import (
        GarminClient,
        GarminAuthError,
        GarminMFARequired,
        complete_mfa_login,
        map_daily_metrics,
        map_profile,
    )

    _GARMIN_AVAILABLE = True
except ImportError:
    _GARMIN_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Endurance Beater",
    page_icon="🏃",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Cached engine
# ---------------------------------------------------------------------------


@st.cache_resource
def get_engine() -> ScienceEngine:
    return ScienceEngine()


# ---------------------------------------------------------------------------
# Rendering helpers (must be defined before use in tabs)
# ---------------------------------------------------------------------------


def _render_steps(steps, indent: int = 0):
    """Render workout steps with color-coded bars."""
    for step in steps:
        color = STEP_COLORS.get(step.step_type, "#CCCCCC")
        label = STEP_LABELS.get(step.step_type, step.step_type.name)
        prefix = "&nbsp;" * (indent * 6)

        # Duration display
        if step.step_type == StepType.REPEAT:
            dur_text = f"{step.repeat_count}x"
        elif step.duration_type == DurationType.DISTANCE:
            dur_text = f"{step.duration_value:.1f} km"
        elif step.duration_type == DurationType.TIME and step.duration_value > 0:
            dur_text = format_duration(step.duration_value)
        else:
            dur_text = ""

        pace_text = format_pace_range(step.pace_target_low, step.pace_target_high)
        hr_text = format_hr_range(step.hr_target_low, step.hr_target_high)

        # Build info parts
        parts = [f"<strong>{label}</strong>"]
        if dur_text:
            parts.append(dur_text)
        if pace_text != "--":
            parts.append(pace_text)
        if hr_text != "--":
            parts.append(hr_text)

        info_line = " | ".join(parts)

        # Coaching cue
        cue = ""
        if step.step_notes:
            cue = f'<br><small style="color:#666;">{step.step_notes}</small>'

        st.markdown(
            f'{prefix}<div style="background:{color};padding:6px 12px;'
            f'border-radius:4px;margin:2px 0;display:inline-block;width:100%;">'
            f'{info_line}{cue}</div>',
            unsafe_allow_html=True,
        )

        # Render child steps for REPEAT blocks
        if step.step_type == StepType.REPEAT and step.child_steps:
            _render_steps(step.child_steps, indent=indent + 1)


def _render_trace(trace):
    """Render a DecisionTrace with color-coded rule results."""
    STATUS_ICONS = {
        RuleStatus.FIRED: "🟢",
        RuleStatus.SKIPPED: "🟠",
        RuleStatus.NOT_APPLICABLE: "⚪",
    }

    for rr in trace.rule_results:
        icon = STATUS_ICONS.get(rr.status, "⚪")
        status_label = rr.status.name
        st.markdown(
            f"{icon} **{rr.rule_id}** — _{status_label}_: {rr.explanation}"
        )

    if trace.conflict_resolution_notes:
        st.divider()
        st.markdown(f"**Conflict Resolution:** {trace.conflict_resolution_notes}")


def _bump_widget_version() -> None:
    """Increment widget version counter to force Streamlit to recreate widgets.

    Streamlit caches widget values by key.  When we change profile_data
    programmatically (Garmin pull, profile load), the widgets ignore the new
    ``value=`` parameter because they remember their old state under the same
    key.  By incrementing a version counter embedded in every widget key, we
    force Streamlit to treat them as *new* widgets that read from ``value=``.
    """
    st.session_state["_wv"] = st.session_state.get("_wv", 0) + 1


def _wk(name: str) -> str:
    """Return a versioned widget key like ``age_v0``."""
    v = st.session_state.get("_wv", 0)
    return f"{name}_v{v}"


def _pull_garmin_profile(gc: "GarminClient") -> None:
    """Pull Garmin profile and merge into profile_data for sidebar pre-fill."""
    if not _GARMIN_AVAILABLE:
        return
    try:
        raw = gc.pull_profile()
        st.session_state["garmin_raw_profile"] = raw  # for debug view
        mapped = map_profile(raw)
        if mapped:
            existing = st.session_state.get("profile_data", {})
            merged = {**existing, **mapped}
            st.session_state["profile_data"] = merged
            st.session_state["garmin_profile_fields"] = set(mapped.keys())
            _bump_widget_version()
        # Also extract daily metrics from the same pull
        daily = map_daily_metrics(raw)
        if any(v is not None for v in daily.values()):
            st.session_state["garmin_metrics"] = daily
    except Exception as e:
        st.session_state["garmin_pull_error"] = str(e)


def _get_pdata(key: str, default):
    """Get value from loaded profile data, or return default."""
    return st.session_state.get("profile_data", {}).get(key, default)


# ---------------------------------------------------------------------------
# Sidebar — Athlete Profile
# ---------------------------------------------------------------------------

st.sidebar.title("Athlete Profile")

# --- Demographics ---
with st.sidebar.expander("Demographics", expanded=True):
    name = st.text_input("Name", value=_get_pdata("name", "Runner"), key=_wk("name"))
    age = st.number_input("Age", 16, 99, int(_get_pdata("age", 35)), key=_wk("age"))
    weight_kg = st.number_input(
        "Weight (kg)", 30.0, 200.0, float(_get_pdata("weight_kg", 70.0)),
        step=0.5, key=_wk("weight_kg"),
    )
    sex = st.selectbox(
        "Sex", ["M", "F"],
        index=0 if _get_pdata("sex", "M") == "M" else 1,
        key=_wk("sex"),
    )

# --- Physiology ---
with st.sidebar.expander("Physiology", expanded=True):
    max_hr = st.number_input(
        "Max HR", 120, 230, int(_get_pdata("max_hr", 185)), key=_wk("max_hr"),
    )
    lthr_bpm = st.number_input(
        "LTHR (bpm)", 100, 220, int(_get_pdata("lthr_bpm", 165)), key=_wk("lthr_bpm"),
    )
    col_lt1, col_lt2 = st.columns(2)
    with col_lt1:
        lthr_pace_min = st.number_input(
            "LT pace min", 2, 12, int(_get_pdata("lthr_pace_min", 5)),
            key=_wk("lt_min"),
        )
    with col_lt2:
        lthr_pace_sec = st.number_input(
            "LT pace sec", 0, 59, int(_get_pdata("lthr_pace_sec", 30)),
            key=_wk("lt_sec"),
        )
    vo2max = st.number_input(
        "VO2max", 20.0, 90.0, float(_get_pdata("vo2max", 45.0)),
        step=0.5, key=_wk("vo2max"),
    )
    resting_hr = st.number_input(
        "Resting HR", 30, 100, int(_get_pdata("resting_hr", 50)), key=_wk("rhr"),
    )

# --- Training Plan ---
with st.sidebar.expander("Training Plan", expanded=True):
    total_plan_weeks = st.number_input(
        "Total plan weeks", 4, 52, int(_get_pdata("total_plan_weeks", 16)),
        key=_wk("plan_weeks"),
    )
    current_week = st.number_input(
        "Current week", 1, total_plan_weeks,
        int(min(_get_pdata("current_week", 1), total_plan_weeks)),
        key=_wk("cur_week"),
    )
    day_of_week = st.number_input(
        "Day of week (1=Mon, 7=Sun)", 1, 7,
        int(_get_pdata("day_of_week", date.today().isoweekday())),
        key=_wk("dow"),
    )
    goal_race_date = st.date_input(
        "Goal race date (optional)", value=None,
    )

# --- Training History ---
with st.sidebar.expander("Training History", expanded=True):
    avg_weekly_km = st.number_input(
        "Avg weekly km", 0.0, 250.0, float(_get_pdata("avg_weekly_km", 35.0)),
        step=1.0, key=_wk("weekly_km"),
    )

# --- Readiness (optional) ---
with st.sidebar.expander("Readiness (optional)"):
    hrv_rmssd = st.number_input(
        "HRV RMSSD (0 = unknown)", 0.0, 200.0, float(_get_pdata("hrv_rmssd", 0)),
        step=1.0, key=_wk("hrv_rmssd"),
    )
    hrv_baseline = st.number_input(
        "HRV Baseline (0 = unknown)", 0.0, 200.0, float(_get_pdata("hrv_baseline", 0)),
        step=1.0, key=_wk("hrv_base"),
    )
    sleep_score = st.number_input(
        "Sleep score 0-100 (0 = unknown)", 0.0, 100.0, float(_get_pdata("sleep_score", 0)),
        step=1.0, key=_wk("sleep"),
    )
    body_battery = st.number_input(
        "Body Battery 0-100 (0 = unknown)", 0, 100, int(_get_pdata("body_battery", 0)),
        key=_wk("bb"),
    )

# --- Advanced (optional) ---
with st.sidebar.expander("Advanced (optional)"):
    critical_speed = st.number_input(
        "Critical Speed m/s (0 = unknown)",
        0.0, 8.0, float(_get_pdata("critical_speed", 0.0)),
        step=0.01, key=_wk("cs"),
    )
    d_prime = st.number_input(
        "D' meters (0 = unknown)",
        0.0, 1000.0, float(_get_pdata("d_prime", 0.0)),
        step=1.0, key=_wk("dp"),
    )
    temperature = st.number_input(
        "Temperature C (0 = unknown)",
        0.0, 50.0, float(_get_pdata("temperature", 0.0)),
        step=0.5, key=_wk("temp"),
    )


def _collect_profile_from_sidebar() -> dict:
    """Collect all sidebar widget values into a dict."""
    return {
        "name": name,
        "age": age,
        "weight_kg": weight_kg,
        "sex": sex,
        "max_hr": max_hr,
        "lthr_bpm": lthr_bpm,
        "lthr_pace_min": lthr_pace_min,
        "lthr_pace_sec": lthr_pace_sec,
        "vo2max": vo2max,
        "resting_hr": resting_hr,
        "total_plan_weeks": total_plan_weeks,
        "current_week": current_week,
        "day_of_week": day_of_week,
        "goal_race_date": goal_race_date,
        "avg_weekly_km": avg_weekly_km,
        "hrv_rmssd": hrv_rmssd,
        "hrv_baseline": hrv_baseline,
        "sleep_score": sleep_score,
        "body_battery": body_battery,
        "critical_speed": critical_speed,
        "d_prime": d_prime,
        "temperature": temperature,
    }


# --- Profile load/save (after widget definitions so _collect works) ---
with st.sidebar.expander("Load / Save Profile"):
    profiles = list_profiles()
    if profiles:
        selected_profile = st.selectbox("Load profile", ["(none)"] + profiles)
        if st.button("Load") and selected_profile != "(none)":
            loaded = load_profile(selected_profile)
            st.session_state["profile_data"] = loaded
            _bump_widget_version()
            st.rerun()
    else:
        st.caption("No saved profiles yet.")

    save_name = st.text_input("Save as", value="my_profile")
    if st.button("Save Profile"):
        profile = _collect_profile_from_sidebar()
        save_profile(save_name, profile)
        st.success(f"Saved as '{save_name}'")


# --- Garmin Connect integration ---
with st.sidebar.expander("Garmin Connect"):
    if not _GARMIN_AVAILABLE:
        st.info(
            "Garmin integration is available but not installed. "
            "Run `pip install -e \".[garmin]\"` to enable it."
        )
    elif st.session_state.get("garmin_client") is not None:
        st.success("Connected to Garmin")

        # Show which fields were auto-populated
        garmin_fields = st.session_state.get("garmin_profile_fields", set())
        if garmin_fields:
            _field_labels = {
                "name": "Name", "age": "Age", "sex": "Sex",
                "weight_kg": "Weight", "max_hr": "Max HR",
                "resting_hr": "Resting HR", "vo2max": "VO2max",
                "lthr_bpm": "LTHR", "lthr_pace_min": "LT Pace",
                "avg_weekly_km": "Weekly km", "hrv_rmssd": "HRV",
                "sleep_score": "Sleep", "body_battery": "Body Battery",
            }
            populated = [_field_labels.get(f, f) for f in garmin_fields if f in _field_labels]
            if populated:
                st.caption(f"Auto-filled from Garmin: {', '.join(sorted(populated))}")

        if st.button("Disconnect"):
            st.session_state.pop("garmin_client", None)
            st.session_state.pop("garmin_metrics", None)
            st.session_state.pop("garmin_profile_fields", None)
            st.rerun()

        if st.button("Refresh Garmin Data"):
            try:
                gc = st.session_state["garmin_client"]
                _pull_garmin_profile(gc)
                st.success("Profile and metrics refreshed")
                st.rerun()
            except Exception as e:
                st.error(f"Refresh failed: {e}")

        if st.button("Pull Today's Metrics"):
            try:
                gc = st.session_state["garmin_client"]
                raw = gc.pull_daily_metrics(date.today())
                mapped = map_daily_metrics(raw)
                st.session_state["garmin_metrics"] = mapped
                st.success("Metrics pulled successfully")
                for k, v in mapped.items():
                    if v is not None:
                        st.caption(f"{k}: {v}")
            except Exception as e:
                st.error(f"Failed to pull metrics: {e}")

        # Debug: show raw Garmin data for troubleshooting
        import json as _json

        raw_profile = st.session_state.get("garmin_raw_profile")
        if raw_profile and st.checkbox("Show raw Garmin data", value=False):
            for section, data in raw_profile.items():
                with st.expander(f"raw: {section}"):
                    if data is None:
                        st.caption("(no data)")
                    elif isinstance(data, (list, dict)):
                        # Truncate large lists
                        display = data
                        if isinstance(data, list) and len(data) > 5:
                            display = data[:5]
                            st.caption(f"Showing 5 of {len(data)} items")
                        st.code(_json.dumps(display, indent=2, default=str)[:3000])
                    else:
                        st.code(str(data)[:1000])
    elif st.session_state.get("garmin_mfa_pending"):
        # MFA step: initial login detected MFA, now need the verification code
        st.info("Garmin sent a verification code to your email. Enter it below.")
        mfa_code = st.text_input("MFA Code", key="garmin_mfa_code")
        if st.button("Verify"):
            if not mfa_code:
                st.warning("Enter the code from your email")
            else:
                try:
                    mfa_client = st.session_state.get("garmin_mfa_client")
                    mfa_state = st.session_state.get("garmin_mfa_state")
                    mfa_token_dir = st.session_state.get("garmin_mfa_token_dir")

                    authed = complete_mfa_login(
                        mfa_client, mfa_state, mfa_code, mfa_token_dir
                    )
                    gc = GarminClient.from_garmin(authed, mfa_token_dir)

                    st.session_state["garmin_client"] = gc
                    for k in ("garmin_mfa_pending", "garmin_mfa_client",
                              "garmin_mfa_state", "garmin_mfa_token_dir"):
                        st.session_state.pop(k, None)
                    _pull_garmin_profile(gc)
                    st.success("Connected! Profile data loaded from Garmin.")
                    st.rerun()
                except Exception as e:
                    st.error(f"MFA verification failed: {e}")
        if st.button("Cancel"):
            for k in ("garmin_mfa_pending", "garmin_mfa_client",
                      "garmin_mfa_state", "garmin_mfa_token_dir"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        st.caption(
            "Connect your Garmin account to pull real metrics "
            "(HRV, sleep, body battery) and push workouts directly."
        )
        garmin_email = st.text_input("Email", key="garmin_email")
        garmin_password = st.text_input(
            "Password", type="password", key="garmin_password"
        )
        if st.button("Connect"):
            if not garmin_email or not garmin_password:
                st.warning("Enter email and password")
            else:
                try:
                    gc = GarminClient(
                        email=garmin_email, password=garmin_password
                    )
                    st.session_state["garmin_client"] = gc
                    _pull_garmin_profile(gc)
                    st.success("Connected! Profile data loaded from Garmin.")
                    st.rerun()
                except GarminMFARequired as mfa_exc:
                    # Stash partially-authed client and MFA state
                    st.session_state["garmin_mfa_pending"] = True
                    st.session_state["garmin_mfa_client"] = getattr(mfa_exc, "garmin_client", None)
                    st.session_state["garmin_mfa_state"] = getattr(mfa_exc, "mfa_state", None)
                    st.session_state["garmin_mfa_token_dir"] = getattr(mfa_exc, "token_dir", None)
                    st.rerun()
                except GarminAuthError as e:
                    st.error(f"Auth failed: {e}")
                except Exception as e:
                    st.error(f"Connection error: {e}")


# ---------------------------------------------------------------------------
# Main content — 3 tabs
# ---------------------------------------------------------------------------

st.title("AI Endurance Beater")
st.caption("Science-driven marathon training — powered by deterministic rules")

# Garmin connection status banner
if _GARMIN_AVAILABLE and st.session_state.get("garmin_client"):
    _garmin_label = "Garmin Connected"
    if st.session_state.get("garmin_metrics"):
        _garmin_label += " — metrics loaded"
    st.success(_garmin_label)


def _ensure_garmin_metrics() -> dict | None:
    """Auto-pull today's Garmin metrics if connected and not yet loaded."""
    if not _GARMIN_AVAILABLE:
        return st.session_state.get("garmin_metrics")
    gc = st.session_state.get("garmin_client")
    if gc is None:
        return None
    cached = st.session_state.get("garmin_metrics")
    if cached is not None:
        return cached
    try:
        raw = gc.pull_daily_metrics(date.today())
        mapped = map_daily_metrics(raw)
        st.session_state["garmin_metrics"] = mapped
        return mapped
    except Exception:
        return None


tab_today, tab_week, tab_trace = st.tabs(
    ["Today's Workout", "Weekly Plan", "Decision Trace"]
)

engine = get_engine()

# ---------------------------------------------------------------------------
# Tab 1: Today's Workout
# ---------------------------------------------------------------------------

with tab_today:
    if st.button("Generate Today's Workout", type="primary"):
        profile = _collect_profile_from_sidebar()
        try:
            garmin_m = _ensure_garmin_metrics()
            if garmin_m:
                state = build_athlete_state_with_garmin(profile, garmin_m)
            else:
                state = build_athlete_state(profile)
            workout, trace = engine.prescribe_structured(state)
            st.session_state["last_workout"] = workout
            st.session_state["last_trace"] = trace
        except Exception as e:
            st.error(f"Error generating workout: {e}")

    workout = st.session_state.get("last_workout")
    if workout is not None:
        st.header(workout.workout_title)
        st.markdown(workout.workout_description)

        # Metrics row
        c1, c2, c3 = st.columns(3)
        c1.metric("Duration", format_duration(workout.total_duration_min))
        c2.metric(
            "Distance",
            f"{workout.total_distance_km:.1f} km"
            if workout.total_distance_km
            else "--",
        )
        c3.metric(
            "Session Type",
            workout.prescription.session_type.name.replace("_", " ").title(),
        )

        st.subheader("Workout Steps")
        _render_steps(workout.steps)

        if workout.decision_summary:
            st.info(workout.decision_summary)

        st.divider()
        dl_col, push_col = st.columns(2)
        with dl_col:
            st.download_button(
                "Download Garmin Workout (.json)",
                data=to_garmin_json_string(workout),
                file_name=f"{workout.workout_title[:32].replace(' ', '_')}.json",
                mime="application/json",
            )
        with push_col:
            if _GARMIN_AVAILABLE and st.session_state.get("garmin_client"):
                if st.button("Push to Garmin", key="push_today"):
                    try:
                        gc = st.session_state["garmin_client"]
                        wj = to_garmin_json(workout)
                        wid = gc.upload_and_schedule(wj, date.today())
                        st.success(f"Pushed to Garmin (workout #{wid})")
                    except Exception as e:
                        st.error(f"Push failed: {e}")
    else:
        st.info("Click **Generate Today's Workout** to get started.")

# ---------------------------------------------------------------------------
# Tab 2: Weekly Plan
# ---------------------------------------------------------------------------

with tab_week:
    if st.button("Generate Weekly Plan", type="primary"):
        profile = _collect_profile_from_sidebar()
        try:
            garmin_m = _ensure_garmin_metrics()
            if garmin_m:
                state = build_athlete_state_with_garmin(profile, garmin_m)
            else:
                state = build_athlete_state(profile)
            workouts, plan = engine.prescribe_week_structured(state)
            st.session_state["last_week_workouts"] = workouts
            st.session_state["last_week_plan"] = plan
        except Exception as e:
            st.error(f"Error generating weekly plan: {e}")

    plan = st.session_state.get("last_week_plan")
    week_workouts = st.session_state.get("last_week_workouts")

    if plan is not None and week_workouts is not None:
        # Summary metrics
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Phase", PHASE_LABELS.get(plan.phase, str(plan.phase)))
        mc2.metric("Week", str(plan.week_number))
        mc3.metric("Total Duration", format_duration(plan.total_duration_min))
        mc4.metric("Key Sessions", str(plan.key_session_count))

        if plan.is_recovery_week:
            st.warning("Recovery week — reduced volume and intensity")

        # Weekly zip download + push
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for j, wo in enumerate(week_workouts):
                fname = f"{DAY_NAMES[j]}_{wo.workout_title[:24].replace(' ', '_')}.json"
                zf.writestr(fname, to_garmin_json_string(wo))

        wk_dl_col, wk_push_col = st.columns(2)
        with wk_dl_col:
            st.download_button(
                "Download Weekly Plan (.zip)",
                data=zip_buf.getvalue(),
                file_name=f"week_{plan.week_number}_plan.zip",
                mime="application/zip",
            )
        with wk_push_col:
            if _GARMIN_AVAILABLE and st.session_state.get("garmin_client"):
                from datetime import timedelta

                # Default to next Monday
                today = date.today()
                days_until_monday = (7 - today.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                default_start = today + timedelta(days=days_until_monday)

                week_start = st.date_input(
                    "Week start date", value=default_start, key="week_push_date"
                )
                if st.button("Push Week to Garmin", key="push_week"):
                    try:
                        gc = st.session_state["garmin_client"]
                        jsons = [to_garmin_json(wo) for wo in week_workouts]
                        ids = gc.upload_week(jsons, week_start)
                        st.success(
                            f"Pushed {len(ids)} workouts to Garmin (IDs: {ids})"
                        )
                    except Exception as e:
                        st.error(f"Push failed: {e}")

        # 7-column day grid
        st.subheader("Week at a Glance")
        cols = st.columns(7)
        for i, (col, wo) in enumerate(zip(cols, week_workouts)):
            stype = wo.prescription.session_type
            color = SESSION_COLORS.get(stype, "#CCCCCC")
            label = stype.name.replace("_", " ").title()
            with col:
                st.markdown(
                    f'<div style="background:{color};padding:10px;border-radius:8px;'
                    f'text-align:center;min-height:100px;">'
                    f"<strong>{DAY_NAMES[i]}</strong><br>"
                    f"{label}<br>"
                    f"<small>{format_duration(wo.total_duration_min)}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        # Expandable detail per day
        st.subheader("Daily Details")
        for i, wo in enumerate(week_workouts):
            with st.expander(f"{DAY_NAMES[i]}: {wo.workout_title}"):
                st.markdown(wo.workout_description)
                dc1, dc2 = st.columns(2)
                dc1.metric("Duration", format_duration(wo.total_duration_min))
                dc2.metric(
                    "Distance",
                    f"{wo.total_distance_km:.1f} km"
                    if wo.total_distance_km
                    else "--",
                )
                if wo.steps:
                    _render_steps(wo.steps)
                st.download_button(
                    "Download Garmin Workout (.json)",
                    data=to_garmin_json_string(wo),
                    file_name=f"{DAY_NAMES[i]}_{wo.workout_title[:24].replace(' ', '_')}.json",
                    mime="application/json",
                    key=f"dl_day_{i}",
                )
    else:
        st.info("Click **Generate Weekly Plan** to plan your training week.")

# ---------------------------------------------------------------------------
# Tab 3: Decision Trace
# ---------------------------------------------------------------------------

with tab_trace:
    trace = st.session_state.get("last_trace")
    plan_for_trace = st.session_state.get("last_week_plan")

    if trace is None and plan_for_trace is None:
        st.info("Generate a workout or weekly plan first to see the decision trace.")
    else:
        if trace is not None:
            st.subheader("Single-Day Trace")
            _render_trace(trace)

        if plan_for_trace is not None:
            st.subheader("Weekly Trace")
            for i, day_trace in enumerate(plan_for_trace.traces):
                with st.expander(f"{DAY_NAMES[i]} trace"):
                    _render_trace(day_trace)
