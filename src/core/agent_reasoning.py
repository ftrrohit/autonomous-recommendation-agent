import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from src.models.schemas import ViewerState, DialectInfo

class AIAgentCore:
    """
    Reasoning engine for the 'One User, One Agent' system.
    Evaluates state, selects goals, and proposes actions with structured evidence.
    Includes deterministic fallback logic for fault recovery.
    """

    def __init__(self, model_faults_path: Optional[str] = None):
        self.faults: Dict[str, Dict[str, Any]] = {}
        if model_faults_path:
            self.load_faults(model_faults_path)

    def load_faults(self, jsonl_path: str):
        """Loads prescribed model faults from replay/model_faults.jsonl."""
        try:
            with open(jsonl_path, mode="r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    fault_data = json.loads(line)
                    trigger_event_id = fault_data.get("trigger_event_id")
                    if trigger_event_id:
                        self.faults[trigger_event_id] = fault_data
        except FileNotFoundError:
            pass

    def decide(
        self,
        trigger_event: Dict[str, Any],
        viewer_state: ViewerState,
        dialect_info: DialectInfo,
        eligible_goals: List[Dict[str, Any]],
        candidate_titles: List[Dict[str, Any]],
        is_holdout: bool
    ) -> Dict[str, Any]:
        """
        Executes reasoning for a trigger.
        Handles fault interception, goal selection, and action proposals.
        """
        trigger_id = trigger_event.get("event_id", "")
        event_name = trigger_event.get("event", "")

        # 1. Check for prescribed model faults
        if trigger_id in self.faults:
            fault = self.faults[trigger_id]
            fault_type = fault.get("fault", "")
            if fault_type == "timeout":
                # Fallback to safe NO_ACTION on timeout
                return self._fallback_decision(
                    reason="Model timeout fault encountered; safe fallback executed.",
                    viewer_state=viewer_state,
                    dialect_info=dialect_info
                )
            elif "model_output" in fault:
                # Fault simulation providing malformed/corrupted output
                raw_output = fault["model_output"]
                parsed = self._safe_parse_output(raw_output)
                if parsed:
                    return parsed
                return self._fallback_decision(
                    reason="Malformed model fault output; safe fallback executed.",
                    viewer_state=viewer_state,
                    dialect_info=dialect_info
                )

        # 2. Holdout protection: Never intervene on holdout arm
        if is_holdout:
            return {
                "goal_id": None,
                "goal_deadline": None,
                "action": "NO_ACTION",
                "content": [],
                "confidence": 1.0,
                "evidence": ["User is assigned to randomized holdout arm."],
                "assumptions": ["No interventions allowed for control group baseline."]
            }

        # 3. Select optimal goal from eligible candidates
        selected_goal = None
        if eligible_goals:
            # Prioritize activation goals for new users, then monetization, then engagement
            selected_goal = eligible_goals[0]

        goal_id = selected_goal.get("goal_id") if selected_goal else None
        goal_deadline = None
        if selected_goal:
            window_hours = selected_goal.get("success", {}).get("window_hours", 24)
            trigger_time_str = trigger_event.get("received_at")
            if trigger_time_str:
                from dateutil import parser
                trigger_time = parser.isoparse(trigger_time_str)
                goal_deadline = trigger_time + timedelta(hours=window_hours)

        # 4. Propose intervention based on event and user lifecycle
        action = "NO_ACTION"
        recommended_content = []
        evidence = []
        assumptions = []
        confidence = 0.85

        title_ids = [t["title_id"] for t in candidate_titles]

        if event_name in ["app_open", "login_success"]:
            if len(title_ids) >= 3:
                action = "HOME_PAGE"
                recommended_content = title_ids[:3]
                evidence.append(f"Trigger {event_name} allows homepage personalization.")
                evidence.append(f"Found {len(recommended_content)} active titles in dialect {dialect_info.used}.")
                assumptions.append("Dialect-aligned hero titles maximize session continuation.")
            else:
                action = "NO_ACTION"
                evidence.append("Insufficient candidate titles for home page row; defaulting to NO_ACTION.")
        else:
            action = "NO_ACTION"
            evidence.append(f"Trigger {event_name} requires no direct intervention.")

        return {
            "goal_id": goal_id,
            "goal_deadline": goal_deadline,
            "action": action,
            "content": recommended_content,
            "confidence": confidence,
            "evidence": evidence,
            "assumptions": assumptions
        }

    def _safe_parse_output(self, output: Any) -> Optional[Dict[str, Any]]:
        """Safely parses structured output from model responses."""
        if isinstance(output, dict):
            return output
        if isinstance(output, str):
            try:
                return json.loads(output)
            except Exception:
                return None
        return None

    def _fallback_decision(
        self,
        reason: str,
        viewer_state: ViewerState,
        dialect_info: DialectInfo
    ) -> Dict[str, Any]:
        """Provides deterministic, safe fallback when model/API faults occur."""
        return {
            "goal_id": viewer_state.active_goal_id,
            "goal_deadline": viewer_state.active_goal_deadline,
            "action": "NO_ACTION",
            "content": [],
            "confidence": 0.5,
            "evidence": [reason],
            "assumptions": ["System degraded or timed out; safe NO_ACTION executed to protect user experience."]
        }