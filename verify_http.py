"""
Live HTTP Endpoint Verification Script for AquaSense AI
Tests frontend static serving and all REST API endpoints over HTTP.
"""

import http.client
import json

HOST = "127.0.0.1"
PORT = 5000

GET_ENDPOINTS = [
    ("/", "Frontend Index Page"),
    ("/style.css", "Frontend CSS Stylesheet"),
    ("/script.js", "Frontend JavaScript"),
    ("/api/health", "Backend Health Check"),
    ("/api/dashboard", "Dashboard Summary (Default Delhi)"),
    ("/api/dashboard?location=Jaipur", "Dashboard for Jaipur"),
    ("/api/locations", "List All Monitored Locations"),
    ("/api/groundwater?latest=true", "Latest Groundwater Records"),
    ("/api/groundwater/history?location=Delhi", "Historical Chart Data"),
    ("/api/risk?location=Delhi", "Risk Assessment Calculation"),
]


def test_get():
    import time
    print("==================================================")
    print(" 1. TESTING GET ENDPOINTS & STATIC ASSETS")
    print("==================================================")
    for path, desc in GET_ENDPOINTS:
        conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
        try:
            conn.request("GET", path)
            res = conn.getresponse()
            content = res.read()
            print(f"[HTTP {res.status}] {path:<40} ({desc})")
            assert res.status == 200, f"Expected 200, got {res.status}"
        finally:
            conn.close()
        time.sleep(0.05)


def test_predict():
    print("\n==================================================")
    print(" 2. TESTING POST /api/predict (MACHINE LEARNING)")
    print("==================================================")
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        body = json.dumps({
            "water_level": 12.4,
            "rainfall": 642.0,
            "temperature": 29.0,
            "humidity": 65.0,
            "extraction_rate": 55.0,
            "recharge_rate": 20.0
        })
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body))
        }
        conn.request("POST", "/api/predict", body, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        assert res.status == 200
        pred = data["data"]
        print(f"[HTTP {res.status}] Forecast: {pred['predicted_groundwater_level']} meters")
        print(f"         Expected Change: {pred['expected_change_formatted']}")
        print(f"         Model Used: {pred['model']}")
        print(f"         Confidence: {pred['confidence_badge']}")
    finally:
        conn.close()


def test_chat():
    print("\n==================================================")
    print(" 3. TESTING POST /api/chat (AI GROUNDWATER ASSISTANT)")
    print("==================================================")
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    try:
        body = json.dumps({"message": "How can I conserve groundwater?"})
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(body))
        }
        conn.request("POST", "/api/chat", body, headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        assert res.status == 200
        print(f"[HTTP {res.status}] Source Engine: {data.get('source')}")
        snippet = data['response'][:110].replace('\n', ' ')
        print(f"         Response Snippet: '{snippet}...'")
    finally:
        conn.close()


if __name__ == "__main__":
    test_get()
    test_predict()
    test_chat()
    print("\n==================================================")
    print("   ALL HTTP VERIFICATION CHECKS PASSED (100%)    ")
    print("==================================================")
