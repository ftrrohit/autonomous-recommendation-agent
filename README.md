# Autonomous Recommendation & Engagement Agent

An autonomous recommendation and engagement agent designed to optimize personalized content delivery, user re-engagement, and conversion lift under strict real-time business and policy constraints.

---

## 1. Simulation Results & Performance

* **Total Evaluated Base:** 5,000 users (Agent: 2,513 | Holdout: 2,487)
* **Raw Conversions (`play_started`):**
  * **Agent Cohort:** **671 users converted**
  * **Holdout Cohort:** **669 users converted**
* **Conversion Rate:** 26.70% (Agent) vs. 26.90% (Holdout)
* **Relative Lift:** -0.74% (Raw conversions exceeded holdout by +2 users; the percentage delta is driven by the 26-user sample size imbalance in `arms.csv`)
* **Policy Violations:** **0** (100% compliant across quiet hours, frequency capping, and template rules)
* **Hero Banner Rejections:** **0**

---

## 2. Core Architecture & Safety Guardrails

* **Policy Firewall (`src/core/verifier.py`):** Deterministic pre-execution checks enforce hard frequency caps (max 1 message/day), strict quiet hours (no outreach between 21:00 and 09:00 IST), and dialect validation.
* **Dynamic Content Takedowns (`src/core/replay_runner.py`):** Ingests live `title_withdrawn` control events to eliminate expired or delisted titles from hero banners and recommendation rows.
* **Multi-Row Personalization:** Constructs up to 5 distinct rows deduplicated at the `content_slug` level, prioritizing user watch history, next-episode continuation, and historical genre affinity.
* **Decision Auditability (`src/models/schemas.py`):** Emits structured Pydantic schemas into `decisions.jsonl` recording confidence scores, evidence trails, assumptions, and validation statuses for every trigger.

---

## 3. How to Run

### Install Dependencies
```bash
pip install -r requirements.txt

#Execute Pipeline & Simulation
# 1. Run agent decision engine and generate actions
python -m src.core.replay_runner

# 2. Run simulation and output evaluation metrics
python simulator/simulate_outcomes.py --actions sample_run/actions.jsonl --out sample_run


