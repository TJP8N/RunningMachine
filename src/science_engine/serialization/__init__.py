"""Serialization module — export workouts to device-compatible formats."""

from science_engine.serialization.garmin import to_garmin_json, to_garmin_json_string

__all__ = ["to_garmin_json", "to_garmin_json_string"]
