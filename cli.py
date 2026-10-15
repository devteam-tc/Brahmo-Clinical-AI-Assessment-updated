"""Command-Line Interface (CLI) for BRAHMO Clinical AI System.
Provides commands for:
- Evaluating draft prescriptions
- Running grounded clinical Q&A
- Inspecting the ambiguity review queue
- Triggering fresh gazette notification ingestion
- Launching the web dashboard
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from db.connection import get_connection
from module_a.safety_rail import DeterministicSafetyRail, PrescriptionItem
from module_b.answering import GroundedAnsweringEngine
from stretch.freshness import RegulatoryFreshnessEngine, NewGazetteNotification

def cmd_check_rx(args):
    conn = get_connection()
    rail = DeterministicSafetyRail(conn)
    # Parse comma separated products
    items = []
    for idx, prod in enumerate(args.products.split(",")):
        items.append(PrescriptionItem(item_no=idx + 1, written_product=prod.strip(), dose_frequency=args.frequency))
    res = rail.evaluate_prescription("CLI-RX", items)
    print(f"\n[*] Overall State:    {res.overall_state}")
    print(f"[*] Highest Severity: {res.highest_severity}")
    print(f"[*] Evidence Note:    {res.summary_evidence}\n")
    if res.cumulative_exposures:
        print("Cumulative Daily Exposures:")
        for c in res.cumulative_exposures:
            print(f"  - {c.ingredient_name}: {c.total_daily_mg:g} mg/day [{'EXCEEDS' if c.exceeds_threshold else 'SAFE'}]")

def cmd_ask(args):
    engine = GroundedAnsweringEngine()
    ans = engine.answer_question(args.question)
    print(f"\n[*] Question: {ans.question_text}")
    print(f"[*] State:    {ans.state}")
    print(f"[*] Citations: {ans.citations}")
    print(f"\n[*] Grounded Answer:\n{ans.answer_text}\n")

def cmd_queue(args):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT queue_id, raw_input, reason_code, confidence, method_tag FROM ambiguity_review_queue ORDER BY queue_id DESC LIMIT 15;")
    rows = c.fetchall()
    print(f"\n--- Latest {len(rows)} Review Queue Items ---")
    for r in rows:
        print(f"ID: {r['queue_id']} | Input: {r['raw_input']} | Reason: {r['reason_code']} | Conf: {r['confidence']:.2f}")

def cmd_web(args):
    from web.app import run_server
    run_server(args.port)

def main():
    parser = argparse.ArgumentParser(description="BRAHMO Clinical AI CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # check-rx
    rx_p = subparsers.add_parser("check-rx", help="Check prescription safety")
    rx_p.add_argument("--products", required=True, help="Comma-separated product names (e.g. 'Dolo 650,Sinarest Tablet')")
    rx_p.add_argument("--frequency", default="1-0-1", help="Dose frequency")
    rx_p.set_defaults(func=cmd_check_rx)

    # ask
    ask_p = subparsers.add_parser("ask", help="Ask grounded clinical question")
    ask_p.add_argument("--question", required=True, help="Clinical question text")
    ask_p.set_defaults(func=cmd_ask)

    # queue
    q_p = subparsers.add_parser("queue", help="Inspect ambiguity review queue")
    q_p.set_defaults(func=cmd_queue)

    # web
    web_p = subparsers.add_parser("web", help="Start web dashboard server")
    web_p.add_argument("--port", type=int, default=8080, help="Server port")
    web_p.set_defaults(func=cmd_web)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
