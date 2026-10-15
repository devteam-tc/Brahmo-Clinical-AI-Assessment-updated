# BRAHMO — Clinical AI Senior Engineering Assessment

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/Core%20Gates-100%25%20Passed-brightgreen.svg)]()
[![Reproduction](https://img.shields.io/badge/Fresh%20Machine%20Repro-<35s-success.svg)]()
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-orange.svg)]()

> **BRAHMO Clinical AI** is a dual-engine clinical decision-support platform engineered specifically for Indian outpatient medicine. It combines an isolated, deterministic, zero-LLM medication safety rail with a grounded clinical Q&A engine enforcing claim-level citations and Law 12 safety fences over ICMR Standard Treatment Workflows.

---

## ⚡ Quickstart (Fresh Machine Reproduction in < 35s)

The core engine uses **100% Python Standard Library** (`sqlite3`, `csv`, `json`, `re`, `http.server`). Zero pip packages or virtual environments are required.

To run the complete pipeline (database migrations, data ingestion, automated test suite, seeded demonstration, mini-eval benchmark, and unified trace):

```bash
python run_all.py
```

### Interactive CLI Commands

```bash
# Check any custom prescription safety
python cli.py check-rx --products "Dolo 650,Sinarest Tablet" --frequency "1-0-1"

# Ask any grounded clinical question
python cli.py ask --question "Which analgesic class must be avoided in suspected dengue, and why?"

# Inspect ambiguity review queue items
python cli.py queue

# Launch the interactive doctor web dashboard
python cli.py web --port 8080
# Open browser at: http://localhost:8080/
```

### Run Automated Test Suite

```bash
python -m unittest discover tests
```

---

## 📚 Assessment Deliverables Index

| Document | Description |
|---|---|
| **[SUBMISSION.md](SUBMISSION.md)** | **Primary Submission Document** linking all deliverables, how-to-run, verification metrics, and gate checklist. |
| **[DESIGN.md](DESIGN.md)** | **Architectural Decision Record** opening with system restatement in candidate's words, the 3 riskiest assumptions in starter materials, and 12 formal Decision Records (D-001 to D-012) with rejected alternatives. |
| **[SCALE.md](SCALE.md)** | **1-Page Strain Analysis** at 100× data volume (200k products, 80k stock rows, 1.3k guidelines) and 100 concurrent doctors, with immediate architectural remedies. |
| **[GAPS_REGISTER.md](GAPS_REGISTER.md)** | **Honest Scope Accounting & Discovered Anomalies** (e.g. CDCI Thyronorm 50 mg vs mcg unit typo; Crocin Advance Ibuprofen anomaly; Law 12 dose calculation fence). |
| **[DAY2_QA.md](DAY2_QA.md)** | **Completed Day-2 Q&A Form** with 5 high-value questions covering High Court stay jurisdiction, unit sanity gates, and FOGSI/RSSDI licensing. |
| **[PROMPT_LIBRARY.md](PROMPT_LIBRARY.md)** | **Replayable Prompt Library** containing all prompts used for normalization and grounded reasoning. |
| **[CLAUDE.md](CLAUDE.md)** | **Engineering Conventions & Architectural Invariants** file. |
| **[PART2_PLAN.md](PART2_PLAN.md)** | **5-Week Production Plan** to 100 concurrent doctors executing 100,000 real clinical queries evaluated vs ChatGPT/Claude across all 9 required sections. |

---

## 🔬 Core System Architecture

```text
   upstream: scribe / EHR draft Rx entities + patient-context snapshot
                          │                                   │
                          ▼                                   ▼
      ┌─────────────────────────┐          ┌──────────────────────────────┐
      │   INDIA DRUG MASTER     │          │  GROUNDED CLINICAL Q&A       │
      │ • alias→brand→salt graph│          │ • decision-unit chunks of    │
      │ • FDC decomposition     │          │   Indian sources (ICMR STWs) │
      │ • event-sourced status  │          │ • hybrid retrieval           │
      │ • ambiguity queue       │          │ • claim-level citations      │
      └───────────┬─────────────┘          │ • Law 12 dose fence          │
                  │ salts                  │ • clean abstentions          │
                  ▼                        └──────────────┬───────────────┘
      ┌─────────────────────────┐                         │
      │ DETERMINISTIC SAFETY    │                         │
      │ RAIL (Zero LLM)         │                         ▼
      │ • duplicate active salt │          ┌──────────────────────────────┐
      │ • prohibited FDC (DAG)  │─────────►│  ORCHESTRATION / AUDIT      │
      │ • severe interactions   │ verdicts │ • structured-first routing   │
      │ • cumulative daily dose │          │ • unified JSON trace         │
      │ • 8-state contract      │          └──────────────┬───────────────┘
      └─────────────────────────┘                         │
                                                          ▼
                                      Doctor-Facing Output + Full Replayable Audit Trace
```

---

## 🎯 Verification Matrix: Part 1 Acceptance Gates

| Gate | Assessment Requirement | Achieved Status | Verification Evidence |
|---|---|---|---|
| **G1** | Fresh-machine reproduction < 1 hour | **PASS (32s)** | Single command `python run_all.py` completes entire pipeline in 32s with zero pip installs. |
| **G2** | FDC decomposition accuracy ≥ 95% on held-out key | **PASS (100%)** | 160 real FDCs decomposed with verified salt + strength in `fdc_decomposition_registry`. |
| **G3** | Zero silent resolutions on ambiguous mappings | **PASS (0 silent)** | Uncertain inputs (`Telma`, `Zqtrixon Forte`, ambiguous stock) route to `ambiguity_review_queue` with reason codes. |
| **G4** | All known-bad seeded cases flagged; zero false negatives; unknowns as unknowns | **PASS** | RX01, RX02, RX03, RX07, RX09 flagged (`HIT`); RX04, RX08 rendered as `UNVERIFIED_INPUT`; clean cases verified (`CHECKED_NO_HIT`). |
| **G5** | 100% provenance on data rows and check results | **PASS** | Every row carries `source`, `source_version`, `effective_from`, and `load_batch`; checks cite gazette notification IDs. |
| **G6** | No uncited consequential clinical numbers anywhere | **PASS** | All clinical numbers carry `[DocCode vVersion, Section, PageAnchor]`; unsupported queries cleanly abstain. |
| **G7** | DESIGN.md decisions each carry a why and at least one rejected alternative | **PASS** | 12 formal Decision Records (D-001 to D-012) fully documented with why, rejected alternatives, and implications. |

---

## 📊 Summary of Module Results

### 1. Module A.7 Seeded Prescriptions (10 Cases)
- **RX01:** `HIT` (WARNING) — Duplicate Paracetamol across Dolo 650 + Sinarest Tablet; cumulative daily total: **2,300 mg/day**.
- **RX02:** `HIT` (CRITICAL) — Prohibited FDC Nimesulide + Paracetamol under Gazette Notification `GSR 411(E)` (effective 2023-06-15).
- **RX03:** `HIT` (SEVERE) — Severe Drug-Drug Interaction: Warfarin + Azithromycin (INR elevation & bleeding risk).
- **RX04:** `UNVERIFIED_INPUT` (WARNING) — Ambiguous strength on `Telma` (20, 40, 80 mg exist). Routed to review queue.
- **RX05:** `CHECKED_NO_HIT` (INFO) — Glycomet 500 + Atorva 10 clean verification.
- **RX06:** `CHECKED_NO_HIT` (INFO) — Augmentin 625 Duo + Okacet 10 clean verification.
- **RX07:** `HIT` (WARNING) — Duplicate Paracetamol: Calpol 650 (1,950 mg/day) + Crocin 650 (650 mg SOS) = **2,600 mg/day**.
- **RX08:** `UNVERIFIED_INPUT` (WARNING) — `Zqtrixon Forte` unrecognized brand. Routed to review queue.
- **RX09:** `HIT` (WARNING) — Duplicate Telmisartan across Telma-H 40 and Telma 40 = **80 mg/day** (max daily target).
- **RX10:** `CHECKED_NO_HIT` (INFO) — Pan 40 + Thyronorm 50 clean verification. (Upstream unit typo logged in gaps register).

### 2. Module B.4 Mini-Evaluation Benchmark (11 Questions)
- **Net Benchmark Score: 9 / 9** (+1 for correct, 0 for honest refusal, -1 for hallucination).
- **Correct Answers:** 9 questions correctly answered with claim-level citations.
- **Clean Abstentions:** 2 questions (Q9 Migraine Prophylaxis & Q10 Pulmonary Tuberculosis) cleanly refused due to corpus boundaries.
- **Hallucinations / Wrong:** 0 questions.

---

## 💻 Tech Stack & Standards

- **Core Engine:** Python 3.10+ (Standard Library: `sqlite3`, `csv`, `json`, `re`, `http.server`, `dataclasses`, `unittest`).
- **Database:** SQLite with numbered migrations and WAL mode (`PRAGMA journal_mode=WAL;`).
- **Web UI:** Responsive vanilla HTML5/CSS3/JavaScript (Dark mode, glassmorphism, responsive data tables).
