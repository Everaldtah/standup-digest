"""
GitHub API client for fetching commits and pull requests.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import requests


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _since_iso(self, hours: int) -> str:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since.isoformat()

    def get_recent_commits(
        self,
        repo: str,
        hours: int = 24,
        authors: Optional[list[str]] = None,
        branch: str = "main",
    ) -> list[dict]:
        """Return commits from `repo` in the past `hours` hours."""
        url = f"{self.BASE_URL}/repos/{repo}/commits"
        params = {"since": self._since_iso(hours), "sha": branch, "per_page": 100}

        resp = self.session.get(url, params=params)
        if resp.status_code == 409:   # empty repo
            return []
        resp.raise_for_status()

        commits = []
        for item in resp.json():
            author_login = (item.get("author") or {}).get("login", "")
            if authors and author_login not in authors:
                continue
            commits.append({
                "sha": item["sha"][:7],
                "message": item["commit"]["message"].split("\n")[0],
                "author": author_login or item["commit"]["author"]["name"],
                "repo": repo,
                "url": item["html_url"],
                "timestamp": item["commit"]["author"]["date"],
            })
        return commits

    def get_recent_prs(
        self,
        repo: str,
        hours: int = 24,
        authors: Optional[list[str]] = None,
    ) -> list[dict]:
        """Return PRs updated in the past `hours` hours."""
        url = f"{self.BASE_URL}/repos/{repo}/pulls"
        params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": 50}

        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        prs = []
        for pr in resp.json():
            updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
            if updated < cutoff:
                break
            author_login = pr["user"]["login"]
            if authors and author_login not in authors:
                continue
            prs.append({
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": author_login,
                "repo": repo,
                "url": pr["html_url"],
                "merged": pr.get("merged_at") is not None,
                "updated_at": pr["updated_at"],
                "labels": [lb["name"] for lb in pr.get("labels", [])],
            })
        return prs

    def get_user_activity_summary(self, username: str, hours: int = 24) -> dict:
        """Fetch a user's public events for a lightweight activity summary."""
        url = f"{self.BASE_URL}/users/{username}/events"
        resp = self.session.get(url, params={"per_page": 30})
        resp.raise_for_status()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        events = []
        for evt in resp.json():
            created = datetime.fromisoformat(evt["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                continue
            events.append({"type": evt["type"], "repo": evt["repo"]["name"]})

        return {
            "username": username,
            "events": events,
            "event_count": len(events),
        }
