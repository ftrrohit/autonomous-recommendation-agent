import csv
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from dateutil import parser
from src.models.schemas import ViewerState

class CatalogManager:
    """
    Retrieval engine for titles.
    Filters content strictly by viewer dialect and active availability windows.
    Excludes already-watched titles so rows do not get rejected.
    """

    def __init__(self, catalogue_path: Optional[str] = None):
        self.titles_by_dialect: Dict[str, List[Dict[str, Any]]] = {}
        self.titles_by_id: Dict[str, Dict[str, Any]] = {}
        if catalogue_path:
            self.load_catalogue(catalogue_path)

    def load_catalogue(self, csv_path: str):
        """Loads and indexes titles from data/catalogue.csv."""
        try:
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title_id = row.get("title_id", "").strip()
                    dialect = row.get("dialect", "").strip()
                    if not title_id or not dialect:
                        continue

                    item = {
                        "title_id": title_id,
                        "content_slug": row.get("content_slug", "").strip(),
                        "title": row.get("title", "").strip(),
                        "dialect": dialect,
                        "language": row.get("language", "").strip(),
                        "content_type": row.get("content_type", "").strip(),
                        "genres": row.get("genres", "").strip(),
                        "release_date": row.get("release_date", "").strip(),
                        "available_from": row.get("available_from", "").strip(),
                        "available_until": row.get("available_until", "").strip(),
                        "is_premium": row.get("is_premium", "").strip().lower() == "true",
                        "description": row.get("description", "").strip()
                    }

                    self.titles_by_id[title_id] = item
                    if dialect not in self.titles_by_dialect:
                        self.titles_by_dialect[dialect] = []
                    self.titles_by_dialect[dialect].append(item)
        except FileNotFoundError:
            pass

    def get_candidate_titles(
        self,
        dialect: str,
        current_time: datetime,
        exclude_title_ids: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves active titles matching the dialect, excluding already-consumed titles.
        Ensures availability rules are respected.
        """
        exclude_set = set(exclude_title_ids or [])
        candidates = self.titles_by_dialect.get(dialect, [])
        valid_titles = []

        for item in candidates:
            tid = item["title_id"]
            if tid in exclude_set:
                continue

            if item["available_from"]:
                try:
                    avail_from = parser.isoparse(item["available_from"])
                    if current_time < avail_from:
                        continue
                except Exception:
                    pass

            if item["available_until"]:
                try:
                    avail_until = parser.isoparse(item["available_until"])
                    if current_time > avail_until:
                        continue
                except Exception:
                    pass

            valid_titles.append(item)
            if len(valid_titles) >= limit:
                break

        return valid_titles


class GoalEligibilityEngine:
    """
    Evaluates viewer state against goals.json rules.
    Prunes trap goals (G10, G11) so the agent only considers measurable goals.
    """

    TRAP_GOALS = {"G10", "G11"}

    def __init__(self, goals_path: Optional[str] = None):
        self.goals_definition: List[Dict[str, Any]] = []
        if goals_path:
            self.load_goals(goals_path)

    def load_goals(self, json_path: str):
        """Loads candidate goals from config/goals.json."""
        try:
            with open(json_path, mode="r", encoding="utf-8") as f:
                data = json.load(f)
                self.goals_definition = data.get("goals", [])
        except FileNotFoundError:
            pass

    def get_eligible_goals(
        self,
        state: ViewerState,
        trigger_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Determines which goals the viewer currently qualifies for.
        """
        if state.active_goal_id and state.active_goal_deadline:
            if trigger_time < state.active_goal_deadline:
                return [{"goal_id": state.active_goal_id, "name": "active_goal_retained"}]

        eligible = []

        account_age_days = None
        if state.signup_at:
            account_age_days = (trigger_time - state.signup_at).total_seconds() / 86400.0

        for g in self.goals_definition:
            gid = g.get("goal_id")
            if gid in self.TRAP_GOALS:
                continue

            if gid == "G01":
                if account_age_days is not None and account_age_days <= 7:
                    if len(state.started_plays) == 0:
                        eligible.append(g)

            elif gid == "G02":
                if len(state.completed_episodes) == 0:
                    eligible.append(g)

            elif gid == "G03":
                if account_age_days is not None and account_age_days <= 2:
                    eligible.append(g)

            elif gid == "G04":
                if state.subscription_status == "trial_active":
                    eligible.append(g)

            elif gid == "G05":
                if state.subscription_status == "never":
                    eligible.append(g)

            elif gid == "G06":
                if state.subscription_status == "lapsed":
                    eligible.append(g)

            elif gid == "G08":
                if state.subscription_status == "active":
                    eligible.append(g)

            elif gid == "G09":
                if state.subscription_status == "active":
                    eligible.append(g)

            elif gid == "G12":
                if len(state.started_plays) > 0:
                    eligible.append(g)

        return eligible