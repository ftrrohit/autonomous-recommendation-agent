from datetime import datetime, timezone, timedelta
from typing import Tuple, List
from src.models.schemas import ViewerState

# IST is UTC + 5 hours 30 minutes
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))

class PolicyVerifier:
    """
    Independent deterministic checks.
    Guarantees rules from messaging_policy.md are never violated.
    """

    @staticmethod
    def is_quiet_hours_ist(utc_time: datetime) -> bool:
        """Quiet hours: No messages between 22:00 and 08:00 IST."""
        ist_time = utc_time.astimezone(IST_OFFSET)
        hour = ist_time.hour
        return hour >= 22 or hour < 8

    @staticmethod
    def get_ist_date_str(utc_time: datetime) -> str:
        """Returns YYYY-MM-DD in IST."""
        return utc_time.astimezone(IST_OFFSET).strftime("%Y-%m-%d")

    @classmethod
    def verify_action(
        cls,
        action_type: str,
        viewer_state: ViewerState,
        trigger_time: datetime,
        is_holdout: bool,
        content_titles: List[str] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validates proposed action.
        Returns: (passed: bool, passed_checks: list, failed_checks: list)
        """
        passed_checks = []
        failed_checks = []

        # 1. Holdout rule: No action allowed for holdout arm
        if is_holdout:
            if action_type != "NO_ACTION":
                failed_checks.append("holdout_protection")
                return False, passed_checks, failed_checks
            passed_checks.append("holdout_compliant")
            return True, passed_checks, failed_checks

        # If decision is NO_ACTION, it always passes
        if action_type == "NO_ACTION":
            passed_checks.append("no_action_safe")
            return True, passed_checks, failed_checks

        # 2. Home page rule: must have at least 3 titles
        if action_type == "HOME_PAGE":
            if content_titles and len(content_titles) >= 3:
                passed_checks.append("home_page_min_titles")
                return True, passed_checks, failed_checks
            else:
                failed_checks.append("home_page_requires_at_least_3_titles")
                return False, passed_checks, failed_checks

        # 3. Messaging channels rules (PUSH or WHATSAPP)
        if action_type in ["PUSH", "WHATSAPP"]:
            # Check Quiet Hours (22:00 to 08:00 IST)
            if cls.is_quiet_hours_ist(trigger_time):
                failed_checks.append("quiet_hours_22_to_08_ist")
            else:
                passed_checks.append("quiet_hours_passed")

            # Check Consent
            if action_type == "PUSH":
                if viewer_state.notifications_opt_in:
                    passed_checks.append("push_consent_verified")
                else:
                    failed_checks.append("push_consent_missing")

            if action_type == "WHATSAPP":
                if viewer_state.whatsapp_opt_in:
                    passed_checks.append("whatsapp_consent_verified")
                else:
                    failed_checks.append("whatsapp_consent_missing")

            # Check Frequency Cap: Max 1 message per user per IST day
            current_ist_day = cls.get_ist_date_str(trigger_time)
            if viewer_state.last_message_sent_ist_date == current_ist_day:
                failed_checks.append("frequency_cap_1_per_day_exceeded")
            else:
                passed_checks.append("frequency_cap_passed")

        passed = len(failed_checks) == 0
        return passed, passed_checks, failed_checks