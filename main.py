"""
standup-digest: Async team standup aggregator with AI-powered summaries.
Team members submit daily updates via API or Slack. The system aggregates
updates, detects blockers, and emails a daily digest to the team lead.
"""

import os
import re
import json
import uuid
import smtplib
import sqlite3
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

load_dotenv()

app = FastAPI(
    title="Standup Digest",
    description="Async daily standup aggregator with AI summaries",
    version="1.0.0"
)

DB_PATH = os.getenv("DB_PATH", "standup.db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DIGEST_TIME = os.getenv("DIGEST_TIME", "09:00")  # 24h HH:MM
DIGEST_TZ = os.getenv("DIGEST_TZ", "UTC")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

BLOCKER_KEYWORDS = [
    "blocked", "blocking", "stuck", "waiting for", "need help", "can't proceed",
    "dependency", "delayed", "postponed", "escalate", "urgent", "help needed",
    "issue", "problem", "error", "bug", "failing", "broken"
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            digest_email TEXT NOT NULL,
            timezone TEXT DEFAULT 'UTC',
            digest_time TEXT DEFAULT '09:00',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS members (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );

        CREATE TABLE IF NOT EXISTS updates (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            standup_date TEXT NOT NULL,
            yesterday TEXT,
            today TEXT,
            blockers TEXT,
            mood INTEGER,
            has_blockers INTEGER DEFAULT 0,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id),
            FOREIGN KEY (member_id) REFERENCES members(id),
            UNIQUE (member_id, standup_date)
        );

        CREATE TABLE IF NOT EXISTS digests (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            standup_date TEXT NOT NULL,
            ai_summary TEXT,
            blockers_summary TEXT,
            participation_rate REAL,
            sent_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );
    """)
    conn.commit()
    conn.close()


init_db()


# --- AI Summarization ---

async def summarize_with_ai(updates_text: str, team_name: str, standup_date: str) -> str:
    """Use Claude or OpenAI to generate a team digest summary."""

    prompt = f"""You are summarizing async standup updates for the {team_name} engineering team for {standup_date}.

Here are the individual updates:

{updates_text}

Write a concise team digest with:
1. **Overall Team Progress** (2-3 sentences, big picture)
2. **Key Completions** (bullet list of most important things done yesterday)
3. **Today's Focus** (bullet list of main priorities across the team)
4. **Blockers & Risks** (only if blockers exist — flag urgency)
5. **Team Mood** (if mood scores provided, note the vibe)

Be specific, action-oriented, and highlight cross-team dependencies. Keep it under 300 words."""

    # Try Claude first
    if ANTHROPIC_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 600,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return resp.json()["content"][0]["text"]
        except Exception as e:
            print(f"Claude API error: {e}")

    # Fallback to OpenAI
    if OPENAI_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 600
                    },
                    timeout=30.0
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI API error: {e}")

    # Fallback: rule-based summary
    return generate_rule_based_summary(updates_text, team_name, standup_date)


def generate_rule_based_summary(updates_text: str, team_name: str, standup_date: str) -> str:
    """Fallback summary when no AI API is available."""
    lines = updates_text.strip().split("\n")
    completed_items = [l for l in lines if "yesterday" in l.lower() or "✓" in l or "completed" in l.lower()]
    today_items = [l for l in lines if "today" in l.lower() or "planning" in l.lower()]
    blocker_items = [l for l in lines if any(kw in l.lower() for kw in BLOCKER_KEYWORDS)]

    summary = f"## {team_name} — Standup Digest for {standup_date}\n\n"
    summary += "**Overall Team Progress**\n"
    summary += "Team submitted updates for the day. See individual summaries below.\n\n"

    if completed_items:
        summary += "**Key Completions**\n"
        for item in completed_items[:5]:
            summary += f"- {item.strip()}\n"
        summary += "\n"

    if today_items:
        summary += "**Today's Focus**\n"
        for item in today_items[:5]:
            summary += f"- {item.strip()}\n"
        summary += "\n"

    if blocker_items:
        summary += "**⚠️ Blockers & Risks**\n"
        for item in blocker_items[:5]:
            summary += f"- {item.strip()}\n"

    return summary


def detect_blockers(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in BLOCKER_KEYWORDS)


# --- Email ---

def send_digest_email(to_email: str, team_name: str, standup_date: str,
                      summary: str, blocker_summary: str, participation: str):
    subject = f"[{team_name}] Standup Digest — {standup_date}"

    blocker_section = f"\n⚠️ BLOCKERS FLAGGED:\n{blocker_summary}\n" if blocker_summary else ""

    body = f"""STANDUP DIGEST: {team_name}
Date: {standup_date}
Participation: {participation}
{blocker_section}
{'='*60}

{summary}

{'='*60}
Powered by standup-digest | http://localhost:8003
"""

    if not SMTP_USER or not SMTP_PASS:
        print(f"\n[DRY RUN] Would send digest to {to_email}:")
        print(f"Subject: {subject}")
        print(body)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Standup Digest <{SMTP_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


async def generate_and_send_digest(team_id: str, target_date: Optional[str] = None):
    today = target_date or date.today().isoformat()
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    if not team:
        conn.close()
        return

    updates = conn.execute(
        """SELECT u.*, m.name as member_name, m.email as member_email
           FROM updates u JOIN members m ON u.member_id = m.id
           WHERE u.team_id=? AND u.standup_date=?""",
        (team_id, today)
    ).fetchall()

    total_members = conn.execute(
        "SELECT COUNT(*) FROM members WHERE team_id=? AND is_active=1", (team_id,)
    ).fetchone()[0]

    conn.close()

    if not updates:
        print(f"No updates for team {team['name']} on {today}")
        return

    participation_rate = len(updates) / total_members if total_members > 0 else 0
    participation_str = f"{len(updates)}/{total_members} ({participation_rate:.0%})"

    # Build text for AI
    updates_text = ""
    blockers = []
    for u in updates:
        updates_text += f"\n### {u['member_name']}\n"
        if u["yesterday"]:
            updates_text += f"Yesterday: {u['yesterday']}\n"
        if u["today"]:
            updates_text += f"Today: {u['today']}\n"
        if u["blockers"]:
            updates_text += f"Blockers: {u['blockers']}\n"
            blockers.append(f"  {u['member_name']}: {u['blockers']}")
        if u["mood"]:
            updates_text += f"Mood: {u['mood']}/5\n"

    summary = await summarize_with_ai(updates_text, team["name"], today)
    blocker_summary = "\n".join(blockers) if blockers else ""

    # Save digest
    digest_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO digests
           (id, team_id, standup_date, ai_summary, blockers_summary, participation_rate, sent_at, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (digest_id, team_id, today, summary, blocker_summary, participation_rate,
         datetime.utcnow().isoformat(), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    send_digest_email(team["digest_email"], team["name"], today, summary, blocker_summary, participation_str)


# --- Scheduled Digest ---

def run_daily_digests():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams").fetchall()
    conn.close()

    import asyncio
    for team in teams:
        asyncio.run(generate_and_send_digest(team["id"]))


scheduler = BackgroundScheduler()
# Run at 9am daily (configurable)
hour, minute = map(int, DIGEST_TIME.split(":"))
scheduler.add_job(run_daily_digests, "cron", hour=hour, minute=minute, id="daily_digest")
scheduler.start()


# --- Models ---

class TeamCreate(BaseModel):
    name: str
    slug: str
    digest_email: str
    timezone: str = "UTC"
    digest_time: str = "09:00"


class MemberCreate(BaseModel):
    name: str
    email: str


class UpdateSubmit(BaseModel):
    member_email: str
    yesterday: Optional[str] = None
    today: Optional[str] = None
    blockers: Optional[str] = None
    mood: Optional[int] = None  # 1-5
    standup_date: Optional[str] = None


# --- Routes ---

@app.get("/")
def root():
    return {"service": "standup-digest", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/teams", status_code=201)
def create_team(data: TeamCreate):
    team_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO teams (id, name, slug, digest_email, timezone, digest_time, created_at) VALUES (?,?,?,?,?,?,?)",
            (team_id, data.name, data.slug, data.digest_email, data.timezone, data.digest_time, now)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Team slug already exists")
    finally:
        conn.close()
    return {"team_id": team_id, "message": f"Team '{data.name}' created"}


@app.get("/teams")
def list_teams():
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY created_at").fetchall()
    conn.close()
    return [dict(t) for t in teams]


@app.post("/teams/{slug}/members", status_code=201)
def add_member(slug: str, data: MemberCreate):
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")
    member_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO members (id, team_id, name, email, created_at) VALUES (?,?,?,?,?)",
        (member_id, team["id"], data.name, data.email, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"member_id": member_id, "message": f"{data.name} added to {team['name']}"}


@app.post("/teams/{slug}/update")
def submit_update(slug: str, data: UpdateSubmit):
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")

    member = conn.execute(
        "SELECT * FROM members WHERE team_id=? AND email=?", (team["id"], data.member_email)
    ).fetchone()
    if not member:
        raise HTTPException(404, f"Member {data.member_email} not found in team")

    standup_date = data.standup_date or date.today().isoformat()
    has_blockers = detect_blockers(data.blockers) or detect_blockers(data.today)

    update_id = str(uuid.uuid4())
    try:
        conn.execute(
            """INSERT OR REPLACE INTO updates
               (id, team_id, member_id, standup_date, yesterday, today, blockers, mood, has_blockers, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (update_id, team["id"], member["id"], standup_date,
             data.yesterday, data.today, data.blockers, data.mood,
             1 if has_blockers else 0, datetime.utcnow().isoformat())
        )
        conn.commit()
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()

    return {
        "update_id": update_id,
        "blockers_detected": has_blockers,
        "message": "Update submitted successfully"
    }


@app.get("/teams/{slug}/updates")
def get_updates(slug: str, standup_date: Optional[str] = None):
    today = standup_date or date.today().isoformat()
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")

    updates = conn.execute(
        """SELECT u.*, m.name as member_name FROM updates u
           JOIN members m ON u.member_id = m.id
           WHERE u.team_id=? AND u.standup_date=?
           ORDER BY u.submitted_at""",
        (team["id"], today)
    ).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM members WHERE team_id=? AND is_active=1", (team["id"],)
    ).fetchone()[0]
    conn.close()

    return {
        "date": today,
        "submitted": len(updates),
        "total_members": total,
        "participation": f"{len(updates)}/{total}",
        "updates": [dict(u) for u in updates]
    }


@app.post("/teams/{slug}/digest")
async def generate_digest(slug: str, background_tasks: BackgroundTasks,
                          standup_date: Optional[str] = None):
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")
    team_id = team["id"]
    conn.close()
    background_tasks.add_task(generate_and_send_digest, team_id, standup_date)
    return {"message": "Digest generation triggered"}


@app.get("/teams/{slug}/digests")
def get_digests(slug: str):
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")
    digests = conn.execute(
        "SELECT * FROM digests WHERE team_id=? ORDER BY standup_date DESC", (team["id"],)
    ).fetchall()
    conn.close()
    return [dict(d) for d in digests]


@app.get("/teams/{slug}/missing")
def missing_updates(slug: str, standup_date: Optional[str] = None):
    today = standup_date or date.today().isoformat()
    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE slug=?", (slug,)).fetchone()
    if not team:
        raise HTTPException(404, "Team not found")

    all_members = conn.execute(
        "SELECT * FROM members WHERE team_id=? AND is_active=1", (team["id"],)
    ).fetchall()
    submitted_ids = {
        r["member_id"] for r in conn.execute(
            "SELECT member_id FROM updates WHERE team_id=? AND standup_date=?",
            (team["id"], today)
        ).fetchall()
    }
    conn.close()

    missing = [{"name": m["name"], "email": m["email"]} for m in all_members if m["id"] not in submitted_ids]
    return {"date": today, "missing_count": len(missing), "missing": missing}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
