"""Lightweight Doctor-Facing Clinical AI Dashboard and REST API Server.
Zero external package dependencies: Uses Python standard library http.server.
Provides live interactive evaluation for:
- Prescription Medication Safety Rail (8 states, cumulative exposure, regulatory checks)
- Grounded Clinical Q&A with claim-level citations
- Ambiguity Review Queue Inspector
- Mini-Eval results view
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.connection import get_connection
from module_a.safety_rail import DeterministicSafetyRail, PrescriptionItem
from module_b.answering import GroundedAnsweringEngine

STATIC_DIR = Path(__file__).resolve().parent / "static"

class BrahmoRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path

        if path == "/" or path == "/index.html":
            self._serve_static_file("index.html", "text/html; charset=utf-8")
        elif path == "/api/status":
            self._send_json({
                "status": "HEALTHY",
                "engine": settings.manifest.engine_name,
                "version": settings.manifest.system_version,
                "batch": settings.manifest.drug_master_load_batch,
                "rules": settings.manifest.safety_rule_version,
                "corpus": settings.manifest.corpus_version
            })
        elif path == "/api/review-queue":
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT queue_id, raw_input, cleaned_query, reason_code, confidence, method_tag, status, created_at
                FROM ambiguity_review_queue
                ORDER BY queue_id DESC LIMIT 50;
            """)
            items = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT COUNT(*) FROM ambiguity_review_queue;")
            total_count = cursor.fetchone()[0]
            self._send_json({"total_queued": total_count, "items": items})
        elif path == "/api/eval-results":
            eval_path = settings.output_dir / "mini_eval_results.json"
            if eval_path.exists():
                with open(eval_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data)
            else:
                self._send_json({"status": "NOT_RUN_YET"})
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        conn = get_connection()

        if path == "/api/check-prescription":
            rx_id = data.get("rx_id", "RX-DEMO")
            raw_items = data.get("items", [])
            items = [
                PrescriptionItem(
                    item_no=idx + 1,
                    written_product=it.get("written_product", ""),
                    strength_as_written=it.get("strength_as_written"),
                    dose_frequency=it.get("dose_frequency", "1-0-0"),
                    clinical_note=it.get("clinical_note")
                )
                for idx, it in enumerate(raw_items)
            ]
            rail = DeterministicSafetyRail(conn)
            eval_res = rail.evaluate_prescription(rx_id, items)
            
            resp = {
                "rx_id": eval_res.rx_id,
                "overall_state": eval_res.overall_state,
                "highest_severity": eval_res.highest_severity,
                "items_verified": eval_res.items_verified,
                "summary_evidence": eval_res.summary_evidence,
                "normalization_results": eval_res.normalization_results,
                "safety_checks": [
                    {
                        "check_name": c.check_name,
                        "state": c.state,
                        "severity": c.severity,
                        "evidence": c.evidence
                    }
                    for c in eval_res.individual_checks
                ],
                "cumulative_daily_exposures": [
                    {
                        "ingredient_name": c.ingredient_name,
                        "total_daily_mg": c.total_daily_mg,
                        "max_recommended_daily_mg": c.max_recommended_daily_mg,
                        "exceeds_threshold": c.exceeds_threshold,
                        "is_prn_sos": c.is_prn_sos,
                        "contributing_products": c.contributing_products
                    }
                    for c in eval_res.cumulative_exposures
                ]
            }
            self._send_json(resp)

        elif path == "/api/ask-clinical-question":
            question = data.get("question", "")
            engine = GroundedAnsweringEngine()
            ans = engine.answer_question(question)
            resp = {
                "question": ans.question_text,
                "state": ans.state,
                "answer": ans.answer_text,
                "citations": ans.citations,
                "abstention_reason": ans.abstention_reason,
                "conflict_detected": ans.conflict_detected,
                "is_dose_question": ans.is_dose_question,
                "contains_local_protocol": ans.contains_local_protocol
            }
            self._send_json(resp)
        else:
            self.send_error(404, "Not Found")

    def _serve_static_file(self, filename: str, content_type: str):
        file_path = STATIC_DIR / filename
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: Any):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def run_server(port: int = 8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, BrahmoRequestHandler)
    print(f"[*] BRAHMO Clinical AI Doctor Dashboard running at: http://localhost:{port}/")
    print(f"[*] Press Ctrl+C to terminate.")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server(8080)
