-- Migration 002: Event-Sourced Regulatory Register
-- Adheres to Law 7 (regulatory truth is event-sourced, never boolean), Section 3 Module A.5

CREATE TABLE IF NOT EXISTS regulatory_events (
    event_id TEXT PRIMARY KEY,
    notification_id TEXT NOT NULL,
    date_published TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    action TEXT NOT NULL, -- PROHIBITED, RESTRICTED, STAY_GRANTED, WITHDRAWN
    target_type TEXT NOT NULL, -- FDC, INGREDIENT, PRODUCT
    target_description TEXT NOT NULL,
    supersedes_event_id TEXT REFERENCES regulatory_events(event_id),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS regulatory_active_state (
    target_canonical_name TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    current_action TEXT NOT NULL,
    active_event_id TEXT NOT NULL REFERENCES regulatory_events(event_id),
    notification_id TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    supersession_chain TEXT NOT NULL,
    last_evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
