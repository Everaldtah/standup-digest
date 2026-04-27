"""
standup-digest — Async standup collector & AI summarizer
Collects team updates via REST API, stores them, generates AI-powered
daily digest reports, and delivers via email/webhook.
"""

import os
import json
import smtplib
import httpx
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import Database, StandupEntry, TeamConfig

app = FastAPI(
    title="Standup Digest",
    description="Async standup collector with AI-powered daily digests",
    version="1.0.0",
)

security = HTTPBearer()
db = Database()

# ── Models ──────────────────────────────────────────────────────────────────

class StandupSubmission(BaseModel):
    team_id: str
    user_name: str
    yesterday: str
    today: str
    blockers: Optional[str] = None

class TeamRegistration(BaseModel):
    team_id: str
    team_name: str
    admin_email: str
    digest_time: str = "09:00"
    notify_emails: list[str] = []
    webhook_url: Optional[str] = None

class DigestRequest(BaseModel):
    team_id: str
    target_date: Optional[str] = None

# ── Auth ─────────────────────────────────────────────────────────────────────

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token != os.getenv("API_TOKEN", "dev-token-change-me"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/teams/register")
def register_team(config: TeamRegistration):
    db.upsert_team(config.dict())
    return {"message": "Team registered", "team_id": config.team_id}

@app.post("/standup/submit")
def submit_standup(entry: StandupSubmission):
    record = StandupEntry(
        team_id=entry.team_id,
        user_name=entry.user_name,
        yesterday=entry.yesterday,
        today=entry.today,
        blockers=entry.blockers or "",
        submitted_at=datetime.utcnow().isoformat(),
        date=date.today().isoformat(),
    )
    db.save_standup(record)
    return {"message": "Standup recorded", "user": entry.user_name, "date": record.date}

@app.get("/standup/team/{team_id}")
def get_team_standups(team_id: str, target_date: Optional[str] = None, token: str = Depends(verify_token)):
    target = target_date or date.today().isoformat()
    entries = db.get_standups(team_id, target)
    return {"team_id": team_id, "date": target, "count": len(entries), "entries": entries}

@app.post("/digest/generate")
def generate_digest(req: DigestRequest, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    background_tasks.add_task(_generate_and_deliver, req.team_id, req.target_date)
    return {"message": "Digest generation started", "team_id": req.team_id}

@app.get("/digest/{team_id}")
def get_digest(team_id: str, target_date: Optional[str] = None, token: str = Depends(verify_token)):
    target = target_date or date.today().isoformat()
    digest = db.get_digest(team_id, target)
    if not digest:
        raise HTTPException(status_code=404, detail="No digest found for this date")
    return digest

@app.get("/teams/{team_id}/stats")
def team_stats(team_id: str, days: int = 7, token: str = Depends(verify_token)):
    stats = []
    for i in range(days):
        d = (date.today() - timedelta(days=i)).isoformat()
        entries = db.get_standups(team_id, d)
        stats.append({"date": d, "submissions": len(entries)})
    return {"team_id": team_id, "stats": stats}

# ── AI Summarization ──────────────────────────────────────────────────────────

def _call_ai(prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_summary(prompt)

    if os.getenv("ANTHROPIC_API_KEY"):
        return _anthropic_summarize(prompt, api_key)
    return _openai_summarize(prompt, api_key)

def _anthropic_summarize(prompt: str, api_key: str) -> str:
    try:
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        return _fallback_summary(prompt)

def _openai_summarize(prompt: str, api_key: str) -> str:
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return _fallback_summary(prompt)

def _fallback_summary(prompt: str) -> str:
    return "AI summarization not configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY to enable."

def _build_prompt(entries: list, team_name: str, target_date: str) -> str:
    lines = "\n".join(
        f"- {e['user_name']}:\n  Yesterday: {e['yesterday']}\n  Today: {e['today']}\n  Blockers: {e['blockers'] or 'None'}"
        for e in entries
    )
    return f"""You are a team lead summarizing async standup updates for {team_name} on {target_date}.

Team updates:
{lines}

Write a concise digest (3-5 sentences) that:
1. Highlights the most important work happening today
2. Calls out any blockers that need attention
3. Identifies any cross-team dependencies
4. Ends with a morale/momentum note

Keep it professional, scannable, and actionable."""

# ── Delivery ──────────────────────────────────────────────────────────────────

def _generate_and_deliver(team_id: str, target_date: Optional[str]):
    target = target_date or date.today().isoformat()
    entries = db.get_standups(team_id, target)
    team = db.get_team(team_id)

    if not entries:
        return

    team_name = team.get("team_name", team_id) if team else team_id
    prompt = _build_prompt(entries, team_name, target)
    summary = _call_ai(prompt)

    blockers = [e for e in entries if e.get("blockers")]
    digest = {
        "team_id": team_id,
        "team_name": team_name,
        "date": target,
        "participant_count": len(entries),
        "participants": [e["user_name"] for e in entries],
        "summary": summary,
        "blockers": [{"user": e["user_name"], "blocker": e["blockers"]} for e in blockers],
        "entries": entries,
        "generated_at": datetime.utcnow().isoformat(),
    }

    db.save_digest(digest)

    if team:
        if team.get("notify_emails"):
            _send_email_digest(digest, team["notify_emails"], team.get("admin_email"))
        if team.get("webhook_url"):
            _send_webhook(digest, team["webhook_url"])

def _send_email_digest(digest: dict, recipients: list, sender: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]):
        return

    body = f"""
<h2>📋 Standup Digest — {digest['team_name']} — {digest['date']}</h2>
<p><strong>{digest['participant_count']} updates</strong> from: {', '.join(digest['participants'])}</p>

<h3>AI Summary</h3>
<p>{digest['summary']}</p>
"""
    if digest["blockers"]:
        blockers_html = "".join(f"<li><strong>{b['user']}:</strong> {b['blocker']}</li>" for b in digest["blockers"])
        body += f"<h3>🚧 Blockers</h3><ul>{blockers_html}</ul>"

    body += "<hr><p><small>Powered by standup-digest · <a href='#'>Unsubscribe</a></small></p>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Standup Digest — {digest['team_name']} — {digest['date']}"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipients, msg.as_string())
    except Exception:
        pass

def _send_webhook(digest: dict, url: str):
    try:
        httpx.post(url, json={"type": "standup_digest", "data": digest}, timeout=10)
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
