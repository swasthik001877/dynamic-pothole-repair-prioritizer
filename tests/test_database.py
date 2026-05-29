"""Integration tests for database layer – covers all FIX items."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import unittest
import database as db
from pathlib import Path


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._orig = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name)
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self._orig
        try: os.unlink(self._tmp.name)
        except: pass

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _user(self, role="Citizen"):
        import uuid
        e = f"u{uuid.uuid4().hex[:6]}@t.com"
        return db.create_user("User", e, "pw123", role)

    def _report(self, uid, road="Road A", sev=5, score=50.0):
        return db.create_report(uid,"U","u@t.com",None,"Loc",12.0,74.0,road,sev,None,[],score)

    # ── FIX #1: bcrypt password hashing ───────────────────────────────────────
    def test_password_hashed_not_plaintext(self):
        u = self._user()
        self.assertNotEqual(u["password_hash"], "pw123")
        self.assertGreater(len(u["password_hash"]), 20)

    def test_password_verify_correct(self):
        db.create_user("X","x@t.com","secret123")
        u = db.authenticate_user("x@t.com","secret123")
        self.assertIsNotNone(u)

    def test_password_verify_wrong(self):
        db.create_user("Y","y@t.com","secret123")
        self.assertIsNone(db.authenticate_user("y@t.com","wrong"))

    def test_bcrypt_no_rainbow_table(self):
        """Two users with same password must have different hashes (salted)."""
        db.create_user("A","a1@t.com","samepass")
        db.create_user("B","b1@t.com","samepass")
        conn = db.get_conn()
        hashes = [r[0] for r in conn.execute(
            "SELECT password_hash FROM users WHERE email IN ('a1@t.com','b1@t.com')"
        ).fetchall()]
        conn.close()
        self.assertNotEqual(hashes[0], hashes[1])

    # ── FIX #9: updated_at actually changes on UPDATE ─────────────────────────
    def test_updated_at_changes_on_status_update(self):
        import time
        u = self._user()
        r = self._report(u["id"])
        time.sleep(1.1)
        db.update_report_status(r["id"], "Scheduled")
        updated = db.get_report_by_id(r["id"])
        self.assertNotEqual(updated["updated_at"], r["created_at"])

    def test_updated_at_changes_on_user_update(self):
        import time
        u = self._user()
        orig_updated = db.get_user_by_id(u["id"])["updated_at"]
        time.sleep(1.1)
        db.update_user(u["id"], name="New Name")
        self.assertNotEqual(db.get_user_by_id(u["id"])["updated_at"], orig_updated)

    # ── FIX #4: Duplicate assignment prevention ────────────────────────────────
    def test_duplicate_assignment_raises(self):
        citizen = self._user("Citizen")
        crew    = self._user("Repair Crew")
        r = self._report(citizen["id"])
        db.create_assignment(r["id"], crew["id"])
        with self.assertRaises(ValueError):
            db.create_assignment(r["id"], crew["id"])

    def test_cancelled_allows_new_assignment(self):
        citizen = self._user("Citizen")
        crew    = self._user("Repair Crew")
        r = self._report(citizen["id"])
        db.create_assignment(r["id"], crew["id"])
        asgns = db.get_assignments(crew_id=crew["id"])
        db.update_assignment_status(asgns[0]["id"], "Cancelled")
        # Now should be allowed again
        self.assertFalse(db.has_active_assignment(r["id"]))

    # ── FIX #10: Email validation (DB layer stores lowercase) ─────────────────
    def test_email_stored_lowercase(self):
        u = db.create_user("Z","Z@T.COM","pw123")
        self.assertEqual(u["email"], "z@t.com")

    def test_case_insensitive_auth(self):
        db.create_user("W","w@T.com","pw123")
        self.assertIsNotNone(db.authenticate_user("W@T.COM","pw123"))

    # ── FIX #14: save_image error handling ────────────────────────────────────
    def test_save_image_nonexistent_returns_none(self):
        result = db.save_image("/nonexistent/path/image.jpg")
        self.assertIsNone(result)

    # ── FIX #19: update_report_severity recalculates score ────────────────────
    def test_severity_update_recalculates_score(self):
        u = self._user()
        db.upsert_traffic("Road B", 20000)
        r = self._report(u["id"], road="Road B", sev=3, score=10.0)
        db.update_report_severity(r["id"], 9)
        updated = db.get_report_by_id(r["id"])
        self.assertEqual(updated["severity"], 9)
        self.assertGreater(updated["priority_score"], 10.0)  # must be higher now

    # ── FIX #21: date not imported (no ImportError) ────────────────────────────
    def test_no_unused_date_import(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.py")).read()
        # 'date' should not appear as a standalone import anymore
        self.assertNotIn("from datetime import datetime, date", src)

    # ── FIX #22: Seed data uses real coordinates ───────────────────────────────
    def test_seed_uses_real_coords(self):
        db.seed_sample_data()
        reports = db.get_reports()
        for r in reports:
            # All Mangaluru coords should be roughly 12.8x lat, 74.8x lng
            self.assertGreater(r["latitude"], 12.5)
            self.assertLess(r["latitude"], 13.2)
            self.assertGreater(r["longitude"], 74.5)
            self.assertLess(r["longitude"], 75.2)

    # ── FIX #28: Unresolved → Pending path (DB level) ─────────────────────────
    def test_unresolved_can_be_set_to_pending(self):
        u = self._user()
        r = self._report(u["id"])
        db.update_report_status(r["id"], "Unresolved")
        db.update_report_status(r["id"], "Pending")
        updated = db.get_report_by_id(r["id"])
        self.assertEqual(updated["status"], "Pending")

    # ── FIX #30: Case-insensitive search ──────────────────────────────────────
    def test_search_case_insensitive(self):
        u = self._user()
        db.create_report(u["id"],"U","u@t.com",None,"Near school",12,74,
                         "School Lane",6,None,[],50)
        results_lower = db.get_reports(search="school lane")
        results_upper = db.get_reports(search="SCHOOL LANE")
        results_mixed = db.get_reports(search="School Lane")
        self.assertEqual(len(results_lower), len(results_upper))
        self.assertEqual(len(results_lower), len(results_mixed))
        self.assertGreater(len(results_lower), 0)

    # ── FIX #35: Nearby report detection ──────────────────────────────────────
    def test_nearby_reports_found(self):
        u = self._user()
        # Place a report at exact coords
        db.create_report(u["id"],"U","u@t.com",None,"Loc",12.8698,74.8426,"Road",5,None,[],50)
        # Search within 50m of same spot
        nearby = db.get_nearby_reports(12.8698, 74.8426, radius_m=50)
        self.assertGreater(len(nearby), 0)

    def test_far_report_not_nearby(self):
        u = self._user()
        db.create_report(u["id"],"U","u@t.com",None,"Loc",12.8698,74.8426,"Road",5,None,[],50)
        # 1km away
        nearby = db.get_nearby_reports(12.8788, 74.8426, radius_m=50)
        self.assertEqual(len(nearby), 0)

    # ── Report history (audit log) ─────────────────────────────────────────────
    def test_history_recorded_on_create(self):
        u = self._user()
        r = self._report(u["id"])
        history = db.get_report_history(r["id"])
        self.assertGreater(len(history), 0)
        self.assertEqual(history[0]["action"], "Created")

    def test_history_recorded_on_status_change(self):
        u = self._user()
        r = self._report(u["id"])
        db.update_report_status(r["id"], "Scheduled", actor_id=u["id"], actor_name="Test")
        history = db.get_report_history(r["id"])
        actions = [h["action"] for h in history]
        self.assertIn("Status changed", actions)

    # ── Existing tests ─────────────────────────────────────────────────────────
    def test_create_user(self):
        u = self._user()
        self.assertIsNotNone(u)

    def test_duplicate_email_returns_none(self):
        db.create_user("A","dup@t.com","p")
        self.assertIsNone(db.create_user("A2","dup@t.com","p"))

    def test_deactivate_blocks_login(self):
        u = db.create_user("D","d@t.com","pw123")
        db.deactivate_user(u["id"])
        self.assertIsNone(db.authenticate_user("d@t.com","pw123"))

    def test_reactivate_restores_login(self):
        u = db.create_user("E","e@t.com","pw123")
        db.deactivate_user(u["id"])
        db.reactivate_user(u["id"])
        self.assertIsNotNone(db.authenticate_user("e@t.com","pw123"))

    def test_upsert_traffic(self):
        db.upsert_traffic("Road X", 45000)
        self.assertEqual(db.get_traffic_for_road("Road X")["avg_daily_traffic"], 45000)

    def test_upsert_traffic_update(self):
        db.upsert_traffic("Road X", 45000)
        db.upsert_traffic("Road X", 60000)
        self.assertEqual(db.get_traffic_for_road("Road X")["avg_daily_traffic"], 60000)

    def test_delete_report_cascades(self):
        u = self._user()
        r = self._report(u["id"])
        db.delete_report(r["id"])
        self.assertIsNone(db.get_report_by_id(r["id"]))

    def test_analytics_structure(self):
        a = db.get_analytics()
        for k in ["total","active","fixed","pending","high_priority",
                  "status_dist","monthly","top_roads"]:
            self.assertIn(k, a)

    def test_assignment_completed_fixes_report(self):
        c = self._user("Citizen"); cr = self._user("Repair Crew")
        r = self._report(c["id"])
        db.create_assignment(r["id"], cr["id"])
        a = db.get_assignments(crew_id=cr["id"])[0]
        db.update_assignment_status(a["id"], "Completed")
        self.assertEqual(db.get_report_by_id(r["id"])["status"], "Fixed")

    def test_crew_workload(self):
        c = self._user("Citizen"); cr = self._user("Repair Crew")
        r1 = self._report(c["id"], "R1"); r2 = self._report(c["id"], "R2")
        db.create_assignment(r1["id"], cr["id"])
        db.create_assignment(r2["id"], cr["id"])
        wl = db.get_crew_workload()
        self.assertEqual(wl.get(cr["id"], 0), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
