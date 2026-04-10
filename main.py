"""
standup-digest: Async standup collector & AI summarizer for remote teams.
Team members submit their daily updates via API or web form.
The scheduler aggregates updates and emails a clean digest to the whole team.
"""

import os
import json
import smtplib
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database import db, init_db
from summarizer import generate_summary
from notifier import send_digest_email

app = FastAPI(
    title="StandupDigest",
    description="Async standup collector & AI summarizer for remote teams",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()


# --- Models ---

class StandupUpdate(BaseModel):
    team_id: str
    member_name: str
    member_email: str
    yesterday: str
    today: str
    blockers: Optional[str] = None

class TeamConfig(BaseModel):
    team_id: str
    team_name: str
    digest_email: str
    digest_time: str = "09:00"   # HH:MM in team's timezone
    timezone: str = "UTC"
    members: List[str] = []

class DigestRequest(BaseModel):
    team_id: str
    date: Optional[str] = None   # YYYY-MM-DD, defaults to today


# --- Routes ---

@app.on_event("startup")
async def startup_event():
    init_db()
    _schedule_all_digests()


@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/updates", status_code=201)
async def submit_update(update: StandupUpdate):
    """Team member submits their daily standup update."""
    today = date.today().isoformat()
    record = {
        "team_id": update.team_id,
        "member_name": update.member_name,
        "member_email": update.member_email,
        "yesterday": update.yesterday,
        "today": update.today,
        "blockers": update.blockers or "",
        "submitted_at": datetime.utcnow().isoformat(),
        "date": today,
    }
    db["updates"].append(record)
    _save_db()
    return {"message": "Update submitted successfully", "date": today}


@app.get("/api/updates/{team_id}")
async def get_updates(team_id: str, date: Optional[str] = None):
    """Get all updates for a team on a given date."""
    target_date = date or date.today().isoformat()
    updates = [
        u for u in db["updates"]
        if u["team_id"] == team_id and u["date"] == target_date
    ]
    return {"team_id": team_id, "date": target_date, "updates": updates, "count": len(updates)}


@app.post("/api/teams", status_code=201)
async def create_team(config: TeamConfig):
    """Register a new team."""
    if any(t["team_id"] == config.team_id for t in db["teams"]):
        raise HTTPException(status_code=409, detail="Team already exists")
    db["teams"].append(config.dict())
    _save_db()
    _schedule_team_digest(config)
    return {"message": "Team created", "team_id": config.team_id}


@app.get("/api/teams/{team_id}")
async def get_team(team_id: str):
    team = next((t for t in db["teams"] if t["team_id"] == team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@app.post("/api/digest/send")
async def trigger_digest(req: DigestRequest, background_tasks: BackgroundTasks):
    """Manually trigger sending a digest for a team."""
    team = next((t for t in db["teams"] if t["team_id"] == req.team_id), None)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    target_date = req.date or date.today().isoformat()
    background_tasks.add_task(_send_digest_for_team, team, target_date)
    return {"message": f"Digest queued for {req.team_id} on {target_date}"}


@app.get("/api/digests/{team_id}")
async def get_digests(team_id: str):
    """Get previously sent digests for a team."""
    digests = [d for d in db["digests"] if d["team_id"] == team_id]
    return {"team_id": team_id, "digests": digests}


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# --- Internal helpers ---

def _send_digest_for_team(team: dict, target_date: str):
    updates = [
        u for u in db["updates"]
        if u["team_id"] == team["team_id"] and u["date"] == target_date
    ]
    if not updates:
        print(f"[digest] No updates for {team['team_id']} on {target_date}")
        return

    summary = generate_summary(team["team_name"], updates, target_date)
    sent = send_digest_email(
        to_email=team["digest_email"],
        team_name=team["team_name"],
        date=target_date,
        summary=summary,
        updates=updates,
    )

    record = {
        "team_id": team["team_id"],
        "date": target_date,
        "sent_at": datetime.utcnow().isoformat(),
        "recipient": team["digest_email"],
        "update_count": len(updates),
        "summary": summary,
        "sent": sent,
    }
    db["digests"].append(record)
    _save_db()
    print(f"[digest] Sent digest for {team['team_id']} on {target_date} → {team['digest_email']}")


def _schedule_team_digest(config: TeamConfig):
    hour, minute = config.digest_time.split(":")
    job_id = f"digest_{config.team_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        _send_digest_for_team,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id=job_id,
        args=[config.dict(), date.today().isoformat()],
    )
    print(f"[scheduler] Scheduled digest for {config.team_id} at {config.digest_time}")


def _schedule_all_digests():
    for team in db["teams"]:
        _schedule_team_digest(TeamConfig(**team))
    if not scheduler.running:
        scheduler.start()


def _save_db():
    with open("data/db.json", "w") as f:
        json.dump(db, f, indent=2)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
