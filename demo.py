"""
Demo script: Seeds sample data and tests the standup-digest API end-to-end.
Run: python demo.py (server must be running on port 8000)
"""

import requests
import json

BASE = "http://localhost:8000"


def run_demo():
    print("=== Standup Digest Demo ===\n")

    # Create team
    print("1. Creating team 'engineering'...")
    r = requests.post(f"{BASE}/teams", json={
        "name": "engineering",
        "manager_email": "cto@demo.com",
        "digest_time": "09:00",
        "timezone": "UTC"
    })
    print(f"   Status: {r.status_code} — {r.json()}\n")

    # Submit standups
    members = [
        {
            "team_member": "Alice Chen",
            "team_name": "engineering",
            "yesterday": "Completed the OAuth2 integration, merged PR #42",
            "today": "Starting the billing module, writing unit tests",
            "blockers": None
        },
        {
            "team_member": "Bob Martinez",
            "team_name": "engineering",
            "yesterday": "Investigated the slow query on user_events table",
            "today": "Adding indexes, will test performance in staging",
            "blockers": "Need DBA approval for the migration"
        },
        {
            "team_member": "Carol Singh",
            "team_name": "engineering",
            "yesterday": "Deployed hotfix for the session timeout bug",
            "today": "Working on the mobile responsive layout for dashboard",
            "blockers": None
        },
    ]

    print("2. Submitting standups for 3 team members...")
    for m in members:
        r = requests.post(f"{BASE}/standup", json=m)
        print(f"   {m['team_member']}: {r.status_code}")
    print()

    # Fetch standups
    print("3. Fetching today's standups...")
    r = requests.get(f"{BASE}/standups/engineering")
    data = r.json()
    print(f"   Found {len(data['standups'])} entries\n")

    # Trigger digest
    print("4. Triggering digest generation...")
    r = requests.post(f"{BASE}/digest/engineering")
    print(f"   Response: {r.json()}\n")

    print("Health check:")
    r = requests.get(f"{BASE}/health")
    print(f"   {r.json()}")
    print("\n=== Demo complete! ===")
    print("If SMTP is configured, a digest email was sent to cto@demo.com")


if __name__ == "__main__":
    run_demo()
