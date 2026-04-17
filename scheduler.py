"""
Standalone scheduler for daily standup digests.
Run this script directly to generate and send digests on a schedule.

Usage:
    python scheduler.py                    # Run once now
    python scheduler.py --schedule 09:00   # Run daily at 09:00 local time
"""

import asyncio
import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv
from digest import GitHubDigest, send_email_digest, send_slack_digest

load_dotenv()

REPOS = [
    {"owner": os.getenv("REPO_OWNER", ""), "repo": os.getenv("REPO_NAME", ""), "branch": "main"},
]

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
DIGEST_EMAIL_TO = os.getenv("DIGEST_EMAIL_TO", "")


async def run_digest():
    print(f"[{datetime.now().isoformat()}] Generating standup digest...")
    client = GitHubDigest(GITHUB_TOKEN)
    results = []

    for repo_cfg in REPOS:
        if not repo_cfg["owner"] or not repo_cfg["repo"]:
            print("  Skipping unconfigured repo. Set REPO_OWNER and REPO_NAME in .env")
            continue
        activity = await client.get_repo_activity(
            repo_cfg["owner"], repo_cfg["repo"], repo_cfg["branch"], days_back=1
        )
        results.append(activity)
        print(f"  ✓ {repo_cfg['owner']}/{repo_cfg['repo']}: {activity['commit_count']} commits")

    if not results:
        print("No repos configured. Check your .env file.")
        return

    digest_text = client.format_digest(results)
    print("\n" + digest_text)

    if SLACK_WEBHOOK_URL:
        await send_slack_digest(SLACK_WEBHOOK_URL, digest_text)
        print("  ✓ Sent to Slack")

    if SMTP_USER and DIGEST_EMAIL_TO:
        send_email_digest(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, DIGEST_EMAIL_TO, digest_text)
        print(f"  ✓ Sent email to {DIGEST_EMAIL_TO}")


def wait_until(target_time: str):
    """Sleep until the next occurrence of HH:MM."""
    while True:
        now = datetime.now()
        target = now.replace(
            hour=int(target_time.split(":")[0]),
            minute=int(target_time.split(":")[1]),
            second=0, microsecond=0
        )
        if target <= now:
            target = target.replace(day=target.day + 1)
        wait_seconds = (target - now).total_seconds()
        print(f"  Next digest at {target.strftime('%Y-%m-%d %H:%M')} (in {int(wait_seconds // 60)} minutes)")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="standup-digest scheduler")
    parser.add_argument("--schedule", metavar="HH:MM", help="Run daily at this time (e.g. 09:00)")
    args = parser.parse_args()

    if args.schedule:
        print(f"Scheduling daily digest at {args.schedule}...")
        while True:
            wait_until(args.schedule)
            asyncio.run(run_digest())
    else:
        asyncio.run(run_digest())
