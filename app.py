"""
standup-digest: Automated daily standup digest generator for engineering teams.
Pulls GitHub commits/PRs and formats them into readable team digests.
"""

import os
import json
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from digest import GitHubDigest, send_email_digest, send_slack_digest

load_dotenv()

app = FastAPI(
    title="standup-digest",
    description="Automated daily standup digest for engineering teams",
    version="1.0.0",
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
DIGEST_EMAIL_TO = os.getenv("DIGEST_EMAIL_TO", "")


class RepoConfig(BaseModel):
    owner: str
    repo: str
    branch: str = "main"


class DigestConfig(BaseModel):
    repos: list[RepoConfig]
    days_back: int = 1
    send_email: bool = True
    send_slack: bool = False


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
    <head><title>standup-digest</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 60px auto; padding: 0 20px; }
        h1 { color: #1a1a2e; } .btn { background: #4f46e5; color: white; padding: 10px 20px;
        border-radius: 6px; text-decoration: none; display: inline-block; margin: 5px; }
        pre { background: #f4f4f4; padding: 15px; border-radius: 6px; overflow-x: auto; }
    </style>
    </head>
    <body>
    <h1>🔁 standup-digest</h1>
    <p>Automated daily standup digest for engineering teams. Pulls GitHub activity and sends it to your team.</p>
    <h2>Quick Start</h2>
    <pre>POST /digest — Generate a digest now
GET /digest/preview — Preview digest in browser
POST /webhook — GitHub webhook endpoint</pre>
    <a href="/docs" class="btn">API Docs</a>
    <a href="/digest/preview" class="btn">Preview Digest</a>
    </body></html>
    """


@app.post("/digest")
async def generate_digest(config: DigestConfig, background_tasks: BackgroundTasks):
    """Generate and send a standup digest immediately."""
    digest_client = GitHubDigest(GITHUB_TOKEN)
    results = []

    for repo_cfg in config.repos:
        activity = await digest_client.get_repo_activity(
            repo_cfg.owner, repo_cfg.repo, repo_cfg.branch, config.days_back
        )
        results.append(activity)

    digest_text = digest_client.format_digest(results)

    if config.send_slack and SLACK_WEBHOOK_URL:
        background_tasks.add_task(send_slack_digest, SLACK_WEBHOOK_URL, digest_text)

    if config.send_email and SMTP_USER and DIGEST_EMAIL_TO:
        background_tasks.add_task(
            send_email_digest,
            SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS,
            DIGEST_EMAIL_TO, digest_text
        )

    return {"status": "queued", "digest_preview": digest_text[:500], "repos_processed": len(results)}


@app.get("/digest/preview", response_class=HTMLResponse)
async def preview_digest(owner: str = "torvalds", repo: str = "linux", days: int = 1):
    """Preview a digest in the browser."""
    digest_client = GitHubDigest(GITHUB_TOKEN)
    activity = await digest_client.get_repo_activity(owner, repo, "master", days)
    digest_text = digest_client.format_digest([activity])

    html_body = digest_text.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
    return f"""
    <html><head><title>Digest Preview</title>
    <style>body {{ font-family: monospace; max-width: 900px; margin: 40px auto; padding: 0 20px;
    background: #f9f9f9; }} .card {{ background: white; padding: 25px; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}</style></head>
    <body><div class="card"><h2>📋 Standup Digest Preview</h2>
    <p>{html_body}</p></div></body></html>
    """


@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None),
):
    """Handle GitHub push webhooks to trigger real-time digest updates."""
    body = await request.body()

    if GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
        expected = "sha256=" + hmac.new(
            GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event == "push":
        payload = json.loads(body)
        repo_name = payload.get("repository", {}).get("full_name", "unknown")
        pusher = payload.get("pusher", {}).get("name", "unknown")
        commits = payload.get("commits", [])

        return {
            "status": "received",
            "repo": repo_name,
            "pusher": pusher,
            "commit_count": len(commits),
            "message": f"Recorded {len(commits)} commits from {pusher}",
        }

    return {"status": "ignored", "event": x_github_event}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
