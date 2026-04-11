"""
Standup scheduler — APScheduler wrapper for daily digest jobs.
"""

import os
import uuid
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StandupScheduler:
    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._scheduler = None
        self._init_scheduler()

    def _init_scheduler(self):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            self._scheduler = BackgroundScheduler()
            self._scheduler.start()
            logger.info("APScheduler started")
        except ImportError:
            logger.warning("APScheduler not installed — scheduling disabled")

    def add_daily_job(
        self,
        github_token: str,
        repos: list[str],
        team_members: list[str],
        hour: int,
        slack_webhook: str | None,
        webhook_url: str | None,
    ) -> str:
        job_id = str(uuid.uuid4())[:8]

        job_meta = {
            "id": job_id,
            "repos": repos,
            "hour": hour,
            "slack_webhook": slack_webhook,
            "webhook_url": webhook_url,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._jobs[job_id] = job_meta

        if self._scheduler:
            def _run():
                self._execute_job(github_token, repos, team_members, slack_webhook, webhook_url)

            self._scheduler.add_job(
                _run,
                trigger="cron",
                hour=hour,
                minute=0,
                id=job_id,
            )
            logger.info(f"Scheduled job {job_id} at hour={hour}")

        return job_id

    def _execute_job(self, github_token, repos, team_members, slack_webhook, webhook_url):
        from github_client import GitHubClient
        from digest_generator import DigestGenerator

        gh = GitHubClient(token=github_token)
        gen = DigestGenerator()

        commits, prs = [], []
        for repo in repos:
            try:
                commits += gh.get_recent_commits(repo=repo, hours=24, authors=team_members)
                prs += gh.get_recent_prs(repo=repo, hours=24, authors=team_members)
            except Exception as e:
                logger.error(f"Error fetching {repo}: {e}")

        digest = gen.generate(commits=commits, prs=prs)

        if slack_webhook:
            try:
                requests.post(slack_webhook, json={"text": digest}, timeout=10)
            except Exception as e:
                logger.error(f"Slack webhook error: {e}")

        if webhook_url:
            try:
                requests.post(webhook_url, json={"digest": digest}, timeout=10)
            except Exception as e:
                logger.error(f"Webhook error: {e}")

    def remove_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        if self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        return True

    def list_jobs(self) -> list[dict]:
        return list(self._jobs.values())

    def shutdown(self):
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
