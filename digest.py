"""
GitHub activity fetcher and digest formatter.
"""

import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx


class GitHubDigest:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_repo_activity(
        self, owner: str, repo: str, branch: str = "main", days_back: int = 1
    ) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

        async with httpx.AsyncClient(timeout=30) as client:
            commits_resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/commits",
                headers=self.headers,
                params={"sha": branch, "since": since, "per_page": 50},
            )
            commits = commits_resp.json() if commits_resp.status_code == 200 else []

            prs_resp = await client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/pulls",
                headers=self.headers,
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 20},
            )
            prs = prs_resp.json() if prs_resp.status_code == 200 else []

        if isinstance(prs, list):
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            prs = [
                p for p in prs
                if isinstance(p, dict) and "updated_at" in p
                and datetime.fromisoformat(p["updated_at"].replace("Z", "+00:00")) >= since_dt
            ]

        contributors: dict[str, int] = {}
        commit_list = []

        if isinstance(commits, list):
            for c in commits:
                if not isinstance(c, dict):
                    continue
                author = (
                    c.get("author", {}) or {}
                ).get("login") or (
                    c.get("commit", {}) or {}
                ).get("author", {}).get("name", "unknown")
                message = (c.get("commit", {}) or {}).get("message", "").split("\n")[0]
                sha = c.get("sha", "")[:7]
                commit_list.append({"sha": sha, "author": author, "message": message})
                contributors[author] = contributors.get(author, 0) + 1

        return {
            "repo": f"{owner}/{repo}",
            "branch": branch,
            "period_days": days_back,
            "commit_count": len(commit_list),
            "commits": commit_list[:20],
            "contributors": contributors,
            "pr_count": len(prs),
            "prs": [
                {
                    "number": p.get("number"),
                    "title": p.get("title", ""),
                    "state": p.get("state", ""),
                    "author": (p.get("user") or {}).get("login", "unknown"),
                }
                for p in prs[:10]
                if isinstance(p, dict)
            ],
        }

    def format_digest(self, activities: list[dict]) -> str:
        now = datetime.now(timezone.utc)
        lines = [
            f"📋 STANDUP DIGEST — {now.strftime('%A, %B %d %Y')}",
            "=" * 50,
            "",
        ]

        total_commits = sum(a.get("commit_count", 0) for a in activities)
        total_prs = sum(a.get("pr_count", 0) for a in activities)
        lines.append(f"📊 Summary: {total_commits} commits · {total_prs} PRs across {len(activities)} repo(s)")
        lines.append("")

        for activity in activities:
            repo = activity.get("repo", "unknown")
            days = activity.get("period_days", 1)
            lines.append(f"🗂  {repo}  (last {days} day{'s' if days > 1 else ''})")
            lines.append("-" * 40)

            contributors = activity.get("contributors", {})
            if contributors:
                sorted_contribs = sorted(contributors.items(), key=lambda x: x[1], reverse=True)
                lines.append(f"👥 Contributors: " + ", ".join(f"{u} ({n})" for u, n in sorted_contribs))

            commits = activity.get("commits", [])
            if commits:
                lines.append(f"\n📝 Commits ({activity.get('commit_count', 0)} total):")
                for c in commits[:10]:
                    lines.append(f"   [{c['sha']}] {c['author']}: {c['message'][:80]}")
                if activity.get("commit_count", 0) > 10:
                    lines.append(f"   ... and {activity['commit_count'] - 10} more")
            else:
                lines.append("   (no commits in this period)")

            prs = activity.get("prs", [])
            if prs:
                lines.append(f"\n🔀 Pull Requests ({activity.get('pr_count', 0)} total):")
                for pr in prs[:5]:
                    icon = "✅" if pr["state"] == "closed" else "🔄"
                    lines.append(f"   {icon} #{pr['number']} {pr['title'][:60]} — @{pr['author']}")

            lines.append("")

        lines.append("─" * 50)
        lines.append("Powered by standup-digest · https://github.com/Everaldtah/standup-digest")
        return "\n".join(lines)


async def send_slack_digest(webhook_url: str, digest_text: str):
    """Post digest to a Slack channel via incoming webhook."""
    payload = {
        "text": f"```{digest_text}```",
        "username": "standup-digest",
        "icon_emoji": ":clipboard:",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()


def send_email_digest(
    host: str, port: int, user: str, password: str, to: str, digest_text: str
):
    """Send digest via SMTP email."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Standup Digest — {datetime.now().strftime('%B %d, %Y')}"
    msg["From"] = user
    msg["To"] = to

    html_body = f"""
    <html><body style="font-family:monospace;background:#f4f4f4;padding:20px">
    <div style="background:white;padding:25px;border-radius:8px;max-width:700px;margin:auto">
    <pre style="white-space:pre-wrap">{digest_text}</pre>
    </div></body></html>
    """

    msg.attach(MIMEText(digest_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(user, to, msg.as_string())
