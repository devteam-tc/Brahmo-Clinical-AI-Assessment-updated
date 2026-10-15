-- Migration 006: Audit Trace and Prescription Evaluation History
-- Adheres to Law 8 (Everything replayable), Law 5 (8-state vocabulary), Module C contract

CREATE TABLE IF NOT EXISTS prescription_audit_traces (
    trace_id TEXT PRIMARY KEY,
    rx_id TEXT,
    overall_state TEXT NOT NULL, -- HIT, CHECKED_NO_HIT, PARTIAL_COVERAGE, UNVERIFIED_INPUT, NOT_CHECKED, DATA_EXPIRED, SOURCE_CONFLICT, SERVICE_UNAVAILABLE
    highest_severity TEXT NOT NULL,
    items_count INTEGER NOT NULL,
    trace_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qa_evaluation_traces (
    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_no INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    state TEXT NOT NULL, -- CORRECT, ABSTAINED, WRONG
    citations_json TEXT NOT NULL,
    evaluation_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
