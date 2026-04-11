"""
Standup Digest — FastAPI application entry point
Generates AI-powered daily standup summaries from GitHub & Jira activity
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from github_client import GitHubClient
from digest_generator import DigestGenerator
from scheduler import StandupScheduler


# ── Models ────────────────────────────────────────────────────────────────────

class DigestRequest(BaseModel):
    github_token: str
    repos: list[str]           # ["owner/repo", ...]
    since_hours: int = 24      # look-back window
    team_members: list[str] = []  # filter by GitHub usernames
    openai_api_key: str | None = None  # override env var

class ScheduleRequest(BaseModel):
    github_token: str
    repos: list[str]
    team_members: list[str] = []
    cron_hour: int = 9         # 9 AM local
    webhook_url: str | None = None   # POST digest here
    slack_webhook: str | None = None

class DigestResponse(BaseModel):
    generated_at: str
    window_hours: int
    repos_scanned: int
    commits_found: int
    prs_found: int
    digest_markdown: str
    raw_data: dict


# ── App setup ─────────────────────────────────────────────────────────────────

scheduler = StandupScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    scheduler.shutdown()

app = FastAPI(
    title="Standup Digest",
    description="Auto-generate daily standup summaries from GitHub & Jira activity",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/digest/generate", response_model=DigestResponse)
async def generate_digest(req: DigestRequest):
    """
    Generate a standup digest on demand.
    Pulls commits & PRs from GitHub repos for the past N hours,
    then uses OpenAI to summarise into human-friendly standup bullets.
    """
    openai_key = req.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY required")

    gh = GitHubClient(token=req.github_token)
    gen = DigestGenerator(openai_api_key=openai_key)

    all_commits = []
    all_prs = []

    for repo in req.repos:
        try:
            commits = gh.get_recent_commits(
                repo=repo,
                hours=req.since_hours,
                authors=req.team_members,
            )
            prs = gh.get_recent_prs(
                repo=repo,
                hours=req.since_hours,
                authors=req.team_members,
            )
            all_commits.extend(commits)
            all_prs.extend(prs)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"GitHub error for {repo}: {e}")

    digest_md = gen.generate(commits=all_commits, prs=all_prs)

    return DigestResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        window_hours=req.since_hours,
        repos_scanned=len(req.repos),
        commits_found=len(all_commits),
        prs_found=len(all_prs),
        digest_markdown=digest_md,
        raw_data={"commits": all_commits[:5], "prs": all_prs[:5]},
    )


@app.post("/digest/schedule")
async def schedule_digest(req: ScheduleRequest, background_tasks: BackgroundTasks):
    """
    Schedule a recurring standup digest (runs daily at configured hour).
    Sends result to Slack webhook or a custom webhook URL.
    """
    job_id = scheduler.add_daily_job(
        github_token=req.github_token,
        repos=req.repos,
        team_members=req.team_members,
        hour=req.cron_hour,
        slack_webhook=req.slack_webhook,
        webhook_url=req.webhook_url,
    )
    return {"message": "Scheduled", "job_id": job_id, "runs_at_hour": req.cron_hour}


@app.get("/digest/schedules")
def list_schedules():
    return {"jobs": scheduler.list_jobs()}


@app.delete("/digest/schedule/{job_id}")
def delete_schedule(job_id: str):
    ok = scheduler.remove_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Deleted", "job_id": job_id}


@app.get("/")
def root():
    return {
        "name": "Standup Digest",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": ["/digest/generate", "/digest/schedule"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
