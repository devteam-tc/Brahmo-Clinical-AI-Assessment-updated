# BRAHMO CLINICAL AI — ENGINEERING CONVENTIONS (CLAUDE.md)

## 1. System Mission & Architectural Invariants

BRAHMO Clinical AI is an India-specific clinical copilot designed for Indian outpatient practice. It operates under two inviolable architectural boundaries:
1. **Safety Outside the LLM (Law 4):** Medication safety checks are pure lookup/rules over versioned data. Never invoke an LLM or probabilistic model anywhere in a medication safety check path.
2. **Deterministic State Contract (Law 5):** Safety checks must return exactly one of the 8 status states:
   `HIT` · `CHECKED_NO_HIT` · `PARTIAL_COVERAGE` · `UNVERIFIED_INPUT` · `NOT_CHECKED` · `DATA_EXPIRED` · `SOURCE_CONFLICT` · `SERVICE_UNAVAILABLE`.
   **Missing data must never render as "safe."**

## 2. Coding & Verification Standards

- **Zero Silent Ambiguity (Law 6 / Gate G3):** Any uncertain brand, formulation, strength, or unit resolution must be queued into `ambiguity_review_queue` with a structured reason code. Guessing or silently resolving ambiguity is a critical failure.
- **Event-Sourced Regulatory Truth (Law 7):** Drug legality is NEVER a boolean. It derives from effective-dated gazette notifications with supersession graph traversal. Every check output cites notification ID and effective date.
- **Claim-Level Provenance (Law 3 / Gate G6):** Every consequential clinical claim or number must map to source, edition, section, and page anchor (e.g. `[STW-PED-01 v2024.1, FIRST-LINE MANAGEMENT, Page 1]`).
- **Safety Fences (Law 12):** Never calculate patient-specific doses (such as pediatric mg/kg total daily mg). Retrieve and cite dosage guidelines as written.

## 3. Technology Stack & Zero-Dependency Execution

- **Language:** Python 3.10+ (Standard Library only for core engine: `sqlite3`, `csv`, `json`, `re`, `http.server`).
- **Database:** SQLite with numbered migrations and WAL mode enabled (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`).
- **Zero-Dependency Reproducibility:** A clean machine clone must be fully runnable via `python run_all.py` in under 1 minute.
- **Testing:** `python -m unittest discover tests` with 100% pass rate.

## 4. Directory & Module Boundaries

- `config/`: Central configuration. No hardcoded constants or thresholds in module code.
- `db/migrations/`: Numbered, idempotent SQL migration files (`001_...sql` to `006_...sql`).
- `module_a/`: India Drug Master, Normalization, FDC Decomposition, Event-Sourced Regulatory Register, Deterministic Safety Rail.
- `module_b/`: STW chunking (clinical decision units), Hybrid retrieval, Grounded clinical answering, Mini-eval harness.
- `module_c/`: Single end-to-end trace script (`trace.py`).
- `stretch/`: Regulatory Freshness engine (`freshness.py`) and Brand Alias matcher (`alias_matcher.py`).
- `web/`: Lightweight doctor dashboard and REST API.
