"""
Cron-style scheduler to auto-generate digests at configured team times.
Run this alongside the API server: python scheduler.py
"""

import os
import time
import httpx
from datetime import datetime
from database import Database

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TOKEN = os.getenv("API_TOKEN", "dev-token-change-me")

db = Database()


def check_and_trigger_digests():
    now = datetime.now()
    current_time = now.strftime("%H:%M")

    teams_data = db._load_teams()
    for team_id, team in teams_data.items():
        scheduled = team.get("digest_time", "09:00")
        if current_time == scheduled:
            print(f"[{now.isoformat()}] Triggering digest for team: {team_id}")
            try:
                resp = httpx.post(
                    f"{API_BASE}/digest/generate",
                    json={"team_id": team_id},
                    headers={"Authorization": f"Bearer {API_TOKEN}"},
                    timeout=30,
                )
                print(f"  → {resp.status_code}: {resp.json()}")
            except Exception as e:
                print(f"  → Error: {e}")


if __name__ == "__main__":
    print("Standup Digest Scheduler running...")
    while True:
        check_and_trigger_digests()
        time.sleep(60)  # check every minute
