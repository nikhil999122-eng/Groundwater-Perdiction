"""
Automated API Test Suite for AquaSense AI
Tests all REST endpoints, DB operations, ML predictions, and AI chat.
"""

import json
from pathlib import Path
import sys
import unittest

# Ensure workspace root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app
from backend.database import init_db


class AquaSenseAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_01_health_check(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "online")
        print("[PASS] test_01_health_check")

    def test_02_get_dashboard(self):
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("water_level", data["data"])
        self.assertIn("rainfall", data["data"])
        print(f"[PASS] test_02_get_dashboard (Delhi level: {data['data']['water_level']}m)")

    def test_03_get_dashboard_specific_location(self):
        res = self.client.get("/api/dashboard?location=Jaipur")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["location"], "Jaipur")
        print(f"[PASS] test_03_get_dashboard_specific_location (Jaipur level: {data['data']['water_level']}m)")

    def test_04_get_locations(self):
        res = self.client.get("/api/locations")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 3)
        print(f"[PASS] test_04_get_locations ({data['count']} locations found)")

    def test_05_get_groundwater_latest(self):
        res = self.client.get("/api/groundwater?latest=true")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["data"]), 3)
        print(f"[PASS] test_05_get_groundwater_latest ({len(data['data'])} records)")

    def test_06_get_groundwater_history(self):
        res = self.client.get("/api/groundwater/history?location=Delhi&months=10")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["data"]), 5)
        print(f"[PASS] test_06_get_groundwater_history ({len(data['data'])} history records)")

    def test_07_post_predict(self):
        payload = {
            "water_level": 12.4,
            "rainfall": 642.0,
            "temperature": 29.0,
            "humidity": 65.0,
            "extraction_rate": 50.0,
            "recharge_rate": 20.0
        }
        res = self.client.post("/api/predict", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        pred = data["data"]
        self.assertIn("predicted_groundwater_level", pred)
        self.assertIn("unit", pred)
        print(f"[PASS] test_07_post_predict (predicted: {pred['predicted_groundwater_level']}m, model: {pred['model']})")

    def test_08_get_risk(self):
        res = self.client.get("/api/risk?location=Delhi&water_level=12.4")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("risk_level", data["data"])
        self.assertIn("score", data["data"])
        print(f"[PASS] test_08_get_risk (Risk: {data['data']['risk_level']}, Score: {data['data']['score']})")

    def test_09_post_chat(self):
        payload = {"message": "How can I conserve groundwater?"}
        res = self.client.post("/api/chat", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIn("response", data)
        self.assertIn("Rainwater Harvesting", data["response"])
        print(f"[PASS] test_09_post_chat (Source: {data.get('source')})")

    def test_10_crud_groundwater(self):
        # 1. Create
        create_payload = {
            "location": "TestCity",
            "state": "TestState",
            "date": "2026-10-01",
            "water_level": 14.5,
            "rainfall": 120.0,
            "temperature": 27.5,
            "humidity": 60.0
        }
        res = self.client.post("/api/groundwater", json=create_payload)
        self.assertEqual(res.status_code, 201)
        created = res.get_json()
        new_id = created["id"]
        print(f"[PASS] test_10_crud: created record ID {new_id}")

        # 2. Read
        res_read = self.client.get(f"/api/groundwater/{new_id}")
        self.assertEqual(res_read.status_code, 200)
        read_data = res_read.get_json()["data"]
        self.assertEqual(read_data["location"], "TestCity")

        # 3. Update
        update_payload = {
            "location": "TestCity",
            "state": "TestState",
            "date": "2026-10-01",
            "water_level": 15.0,
            "rainfall": 130.0,
            "temperature": 28.0,
            "humidity": 62.0,
            "risk_level": "High"
        }
        res_update = self.client.put(f"/api/groundwater/{new_id}", json=update_payload)
        self.assertEqual(res_update.status_code, 200)
        updated_data = res_update.get_json()["data"]
        self.assertEqual(updated_data["water_level"], 15.0)
        print(f"[PASS] test_10_crud: updated record ID {new_id}")

        # 4. Delete
        res_delete = self.client.delete(f"/api/groundwater/{new_id}")
        self.assertEqual(res_delete.status_code, 200)
        print(f"[PASS] test_10_crud: deleted record ID {new_id}")

        # Verify 404 after delete
        res_404 = self.client.get(f"/api/groundwater/{new_id}")
        self.assertEqual(res_404.status_code, 404)
        print("[PASS] test_10_crud passed completely")


if __name__ == "__main__":
    unittest.main()
