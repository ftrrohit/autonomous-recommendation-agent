import csv
from datetime import datetime
from typing import Dict, Optional, Tuple
from dateutil import parser
from src.models.schemas import ViewerState, DialectInfo

class StateManager:
    """
    Manages durable per-viewer state, ingestion, and conflict resolution.
    Always prioritizes trustworthy server received_at over device clocks.
    """

    def __init__(self, profiles_snapshot_path: Optional[str] = None):
        self.states: Dict[str, ViewerState] = {}
        if profiles_snapshot_path:
            self.load_profiles_snapshot(profiles_snapshot_path)

    def load_profiles_snapshot(self, csv_path: str):
        """Loads baseline viewer profiles from the warehouse export."""
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    user_id = row.get("user_id", "").strip()
                    if not user_id:
                        continue

                    signup_at = None
                    if row.get("signup_at"):
                        try:
                            signup_at = parser.isoparse(row["signup_at"])
                        except Exception:
                            signup_at = None

                    state = ViewerState(
                        user_id=user_id,
                        signup_at=signup_at,
                        subscription_status=row.get("subscription_status", "never").strip(),
                        preferred_dialect=row.get("preferred_dialect", "unknown").strip(),
                        dialect_source="profile_snapshot",
                        notifications_opt_in=(row.get("notifications_opt_in", "").lower() == "true"),
                        whatsapp_opt_in=(row.get("whatsapp_opt_in", "").lower() == "true")
                    )
                    self.states[user_id] = state
        except FileNotFoundError:
            pass

    def get_or_create_state(self, user_id: str) -> ViewerState:
        """Retrieves existing state or initializes a new viewer."""
        if user_id not in self.states:
            self.states[user_id] = ViewerState(user_id=user_id)
        return self.states[user_id]

    def resolve_dialect(self, user_id: str, event_app_dialect: Optional[str]) -> DialectInfo:
        """
        Resolves dialect conflicts between stale profile and live event settings.
        Rule: Live app_dialect overrides warehouse preferred_dialect.
        """
        state = self.get_or_create_state(user_id)
        conflicts = []

        if event_app_dialect and event_app_dialect != "unknown":
            if state.preferred_dialect not in ["unknown", "none", ""] and state.preferred_dialect != event_app_dialect:
                conflicts.append(f"profile:{state.preferred_dialect}")

            # Live app setting wins
            state.preferred_dialect = event_app_dialect
            state.dialect_source = "app_setting"
            return DialectInfo(
                used=event_app_dialect,
                source="app_setting",
                conflicts=conflicts
            )

        # Fallback to profile setting
        dialect_to_use = state.preferred_dialect if state.preferred_dialect != "unknown" else "d1"
        return DialectInfo(
            used=dialect_to_use,
            source=state.dialect_source if state.dialect_source != "none" else "default_fallback",
            conflicts=conflicts
        )

    def update_with_event(self, event_data: dict) -> Tuple[ViewerState, DialectInfo]:
        """
        Ingests an incoming event and updates durable state.
        Uses received_at for all authoritative state transitions.
        """
        user_id = event_data.get("user_id")
        state = self.get_or_create_state(user_id)

        event_name = event_data.get("event")
        props = event_data.get("properties", {}) or {}

        # 1. Update dialect from the app settings feed on every event
        app_dialect = event_data.get("app_dialect")
        dialect_info = self.resolve_dialect(user_id, app_dialect)

        # 2. Ingest telemetry events
        if event_name == "signup_completed":
            if not state.signup_at and event_data.get("received_at"):
                try:
                    state.signup_at = parser.isoparse(event_data["received_at"])
                except Exception:
                    pass

        elif event_name == "purchase_completed":
            is_trial = props.get("is_trial", False)
            state.subscription_status = "trial_active" if is_trial else "active"

        elif event_name == "subscription_renewed":
            state.subscription_status = "active"

        elif event_name == "subscription_lapsed":
            state.subscription_status = "lapsed"

        elif event_name == "play_started":
            title_id = props.get("title_id")
            if title_id and title_id not in state.started_plays:
                state.started_plays.append(title_id)

        elif event_name == "episode_completed":
            episode_id = props.get("episode_id")
            if episode_id and episode_id not in state.completed_episodes:
                state.completed_episodes.append(episode_id)

        elif event_name == "notification_opt_out":
            channel = props.get("channel", "").lower()
            if channel == "push":
                state.notifications_opt_in = False
            elif channel == "whatsapp":
                state.whatsapp_opt_in = False

        return state, dialect_info