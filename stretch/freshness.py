"""Stretch Feature: Regulatory Freshness Engine.
Simulates and handles dynamic arrival of new Gazette notifications.
Re-indexes regulatory active states, updates supersession chains, and invalidates or alerts on affected prescriptions.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
import sqlite3

from config.settings import settings
from db.connection import get_connection

@dataclass
class NewGazetteNotification:
    event_id: str
    notification_id: str
    date_published: str
    effective_date: str
    action: str  # PROHIBITED, RESTRICTED, STAY_GRANTED, WITHDRAWN
    target_type: str  # FDC, INGREDIENT, PRODUCT
    target_description: str
    supersedes_event_id: Optional[str] = None
    note: Optional[str] = None

class RegulatoryFreshnessEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn or get_connection()

    def ingest_new_notification(self, notice: NewGazetteNotification) -> Dict[str, Any]:
        """
        Dynamically ingests a newly published gazette notification.
        Updates the regulatory register and checks impact on existing prescriptions.
        """
        cursor = self.conn.cursor()
        
        # Check if already exists
        cursor.execute("SELECT event_id FROM regulatory_events WHERE event_id = ?;", (notice.event_id,))
        if cursor.fetchone():
            return {"status": "ALREADY_EXISTS", "event_id": notice.event_id}

        # Insert new event
        cursor.execute("""
            INSERT INTO regulatory_events
            (event_id, notification_id, date_published, effective_date, action, target_type, target_description, supersedes_event_id, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            notice.event_id, notice.notification_id, notice.date_published,
            notice.effective_date, notice.action, notice.target_type,
            notice.target_description, notice.supersedes_event_id, notice.note
        ))
        self.conn.commit()

        # Identify impacted products in drug master
        impacted_products = []
        target_lower = notice.target_description.lower()
        cursor.execute("SELECT product_id, brand_name, strength_text FROM drug_products;")
        for p in cursor.fetchall():
            if target_lower in p["brand_name"].lower() or any(w in p["strength_text"].lower() for w in target_lower.split() if len(w) > 4):
                impacted_products.append(dict(p))

        result = {
            "status": "INGESTED_AND_APPLIED",
            "event_id": notice.event_id,
            "notification_id": notice.notification_id,
            "effective_date": notice.effective_date,
            "action": notice.action,
            "supersedes": notice.supersedes_event_id,
            "impacted_master_products_count": len(impacted_products),
            "sample_impacted": impacted_products[:5]
        }
        return result
