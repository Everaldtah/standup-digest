"""
Demo: Creates a team, adds members, submits standup updates, generates digest.
Run the server first: python main.py
Then: python demo.py
"""

import requests

BASE = "http://localhost:8003"
SLUG = "demo-team"


def demo():
    print("=== Standup Digest Demo ===\n")

    # Create team
    r = requests.post(f"{BASE}/teams", json={
        "name": "Platform Engineering",
        "slug": SLUG,
        "digest_email": "team-lead@example.com",
        "timezone": "America/New_York",
        "digest_time": "09:00"
    })
    print(f"Create team: {r.json().get('message', r.json())}")

    # Add members
    members = [
        {"name": "Alice Chen", "email": "alice@example.com"},
        {"name": "Bob Smith", "email": "bob@example.com"},
        {"name": "Carol Johnson", "email": "carol@example.com"},
    ]
    for m in members:
        r = requests.post(f"{BASE}/teams/{SLUG}/members", json=m)
        print(f"Add member: {r.json().get('message', r.json())}")

    # Submit standup updates
    updates = [
        {
            "member_email": "alice@example.com",
            "yesterday": "Completed the OAuth integration for the billing module. Fixed 2 P2 bugs from last sprint.",
            "today": "Starting work on the webhook delivery retry system. Will pair with Bob on the queue design.",
            "blockers": None,
            "mood": 4
        },
        {
            "member_email": "bob@example.com",
            "yesterday": "Reviewed Alice's OAuth PR. Set up Terraform modules for the new staging environment.",
            "today": "Deploying staging env. Need to finish documentation for the new API endpoints.",
            "blockers": "Blocked waiting for DevOps to approve the AWS IAM policy change — submitted ticket 2 days ago, still pending.",
            "mood": 3
        },
        {
            "member_email": "carol@example.com",
            "yesterday": "Wrote integration tests for the payment gateway. Coverage went from 62% to 78%.",
            "today": "Continuing test coverage. Planning to start the performance benchmarking for the new database queries.",
            "blockers": None,
            "mood": 5
        },
    ]

    print("\nSubmitting updates...")
    for u in updates:
        r = requests.post(f"{BASE}/teams/{SLUG}/update", json=u)
        result = r.json()
        blockers_flag = "⚠️ BLOCKER DETECTED" if result.get("blockers_detected") else "✓"
        print(f"  {u['member_email']}: {blockers_flag}")

    # Check missing
    r = requests.get(f"{BASE}/teams/{SLUG}/missing")
    missing = r.json()
    print(f"\nParticipation: all members submitted ({missing['missing_count']} missing)")

    # Generate digest
    print("\nGenerating AI digest (check server logs for email output)...")
    r = requests.post(f"{BASE}/teams/{SLUG}/digest")
    print(f"  {r.json()['message']}")

    import time
    time.sleep(3)

    # Show updates
    r = requests.get(f"{BASE}/teams/{SLUG}/updates")
    data = r.json()
    print(f"\nToday's updates: {data['participation']} submitted")

    print("\nDemo complete!")
    print(f"  View updates: GET {BASE}/teams/{SLUG}/updates")
    print(f"  View digests: GET {BASE}/teams/{SLUG}/digests")
    print(f"  API docs:     {BASE}/docs")


if __name__ == "__main__":
    demo()
