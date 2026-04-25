"""
standup-digest: Async standup collector and AI-powered daily digest generator.
Collects team responses via web form, summarizes with AI, and emails managers.
"""

import os
import json
import smtplib
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3

app = FastAPI(title="Standup Digest", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
MANAGER_EMAIL = os.getenv("MANAGER_EMAIL", "")
DB_PATH = os.getenv("DB_PATH", "standup.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS standups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_member TEXT NOT NULL,
            team_name TEXT NOT NULL,
            yesterday TEXT NOT NULL,
            today TEXT NOT NULL,
            blockers TEXT,
            submitted_at TEXT NOT NULL,
            digest_sent INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            manager_email TEXT NOT NULL,
            digest_time TEXT DEFAULT '09:00',
            timezone TEXT DEFAULT 'UTC'
        )
    """)
    conn.commit()
    conn.close()


init_db()


class StandupEntry(BaseModel):
    team_member: str
    team_name: str
    yesterday: str
    today: str
    blockers: Optional[str] = None


class TeamConfig(BaseModel):
    name: str
    manager_email: str
    digest_time: str = "09:00"
    timezone: str = "UTC"


def summarize_standups_with_ai(standups: list, team_name: str) -> str:
    if not ANTHROPIC_API_KEY:
        # Fallback plain summary without AI
        lines = [f"**Standup Digest — {team_name} — {date.today()}**\n"]
        for s in standups:
            lines.append(f"### {s['team_member']}")
            lines.append(f"**Yesterday:** {s['yesterday']}")
            lines.append(f"**Today:** {s['today']}")
            if s['blockers']:
                lines.append(f"**Blockers:** {s['blockers']}")
            lines.append("")
        return "\n".join(lines)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    entries_text = "\n\n".join([
        f"Team member: {s['team_member']}\n"
        f"Yesterday: {s['yesterday']}\n"
        f"Today: {s['today']}\n"
        f"Blockers: {s['blockers'] or 'None'}"
        for s in standups
    ])

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
                f"You are a helpful engineering manager assistant. Summarize these daily standups "
                f"for team '{team_name}' into a clear, scannable digest. "
                f"Group themes, highlight blockers prominently, and add a 2-sentence team pulse. "
                f"Format as Markdown.\n\nStandups:\n{entries_text}"
            )
        }]
    )
    return message.content[0].text


def send_digest_email(manager_email: str, team_name: str, digest_html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Standup Digest — {team_name} — {date.today()}"
    msg["From"] = SMTP_USER
    msg["To"] = manager_email

    plain = digest_html.replace("**", "").replace("###", "").replace("##", "")
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(f"<pre>{digest_html}</pre>", "html"))

    if not SMTP_USER or not SMTP_PASS:
        print(f"[SMTP not configured] Would send digest to {manager_email}:\n{digest_html}")
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, manager_email, msg.as_string())


def generate_and_send_digest(team_name: str):
    conn = get_db()
    team = conn.execute(
        "SELECT * FROM teams WHERE name = ?", (team_name,)
    ).fetchone()
    if not team:
        conn.close()
        return

    today = date.today().isoformat()
    standups = conn.execute(
        "SELECT * FROM standups WHERE team_name = ? AND submitted_at LIKE ? AND digest_sent = 0",
        (team_name, f"{today}%")
    ).fetchall()

    if not standups:
        conn.close()
        return

    standups_list = [dict(s) for s in standups]
    digest = summarize_standups_with_ai(standups_list, team_name)
    send_digest_email(team["manager_email"], team_name, digest)

    ids = [s["id"] for s in standups_list]
    conn.execute(
        f"UPDATE standups SET digest_sent = 1 WHERE id IN ({','.join('?' * len(ids))})",
        ids
    )
    conn.commit()
    conn.close()
    print(f"[standup-digest] Digest sent for team '{team_name}'")


@app.post("/standup", status_code=201)
def submit_standup(entry: StandupEntry):
    conn = get_db()
    conn.execute(
        "INSERT INTO standups (team_member, team_name, yesterday, today, blockers, submitted_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (entry.team_member, entry.team_name, entry.yesterday,
         entry.today, entry.blockers, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "submitted", "message": "Standup recorded successfully"}


@app.post("/teams", status_code=201)
def create_team(team: TeamConfig):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO teams (name, manager_email, digest_time, timezone) VALUES (?, ?, ?, ?)",
            (team.name, team.manager_email, team.digest_time, team.timezone)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Team already exists")
    finally:
        conn.close()
    return {"status": "created", "team": team.name}


@app.get("/standups/{team_name}")
def get_standups(team_name: str, date_filter: Optional[str] = None):
    conn = get_db()
    if date_filter:
        rows = conn.execute(
            "SELECT * FROM standups WHERE team_name = ? AND submitted_at LIKE ?",
            (team_name, f"{date_filter}%")
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM standups WHERE team_name = ? ORDER BY submitted_at DESC LIMIT 50",
            (team_name,)
        ).fetchall()
    conn.close()
    return {"standups": [dict(r) for r in rows]}


@app.post("/digest/{team_name}")
def trigger_digest(team_name: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_and_send_digest, team_name)
    return {"status": "digest_queued", "team": team_name}


@app.get("/health")
def health():
    return {"status": "ok", "service": "standup-digest", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
