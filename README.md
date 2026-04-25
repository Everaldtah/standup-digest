# Standup Digest

> Async daily standup collector that summarizes team responses with AI and emails managers a clean digest — no meetings required.

## Problem It Solves

Remote and async teams waste time in synchronous standup meetings, or lose visibility when standups are scattered across Slack threads. Standup Digest collects responses via a simple API/form, uses AI to summarize themes and blockers, and delivers a clean digest email — so managers stay informed without the overhead of a daily meeting.

## Features

- Submit standup entries via REST API (integrate with any frontend or Slack bot)
- AI-powered summarization using Claude (groups themes, highlights blockers, adds team pulse)
- Scheduled daily digest emails per team
- Per-team configuration: manager email, digest send time, timezone
- Manual digest trigger endpoint
- SQLite-backed storage (zero-ops, easy to migrate to Postgres)
- Full CORS support for embedding in any dashboard

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API framework
- **Anthropic Claude API** — AI summarization (claude-haiku, fast and cheap)
- **APScheduler** — digest scheduling
- **SQLite** — lightweight persistent storage
- **smtplib** — email delivery

## Installation

```bash
git clone https://github.com/Everaldtah/standup-digest.git
cd standup-digest

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials
```

## Usage

### Start the server
```bash
uvicorn main:app --reload --port 8000
```

### Create a team
```bash
curl -X POST http://localhost:8000/teams \
  -H "Content-Type: application/json" \
  -d '{"name": "engineering", "manager_email": "cto@company.com", "digest_time": "09:00"}'
```

### Submit a standup entry
```bash
curl -X POST http://localhost:8000/standup \
  -H "Content-Type: application/json" \
  -d '{
    "team_member": "Alice",
    "team_name": "engineering",
    "yesterday": "Finished the auth refactor, reviewed 2 PRs",
    "today": "Starting the payment integration",
    "blockers": "Waiting on Stripe API key from ops"
  }'
```

### Trigger a digest manually
```bash
curl -X POST http://localhost:8000/digest/engineering
```

### View standups for a team
```bash
curl http://localhost:8000/standups/engineering
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/standup` | Submit a standup entry |
| POST | `/teams` | Register a team |
| GET | `/standups/{team}` | Fetch standup entries |
| POST | `/digest/{team}` | Manually trigger digest email |
| GET | `/health` | Health check |

## Monetization Model

- **Free tier**: 1 team, 5 members, plain-text digest
- **Pro ($19/mo)**: 5 teams, AI summaries, custom digest schedule
- **Business ($79/mo)**: Unlimited teams, Slack integration, digest history, analytics
- **Enterprise**: Custom pricing, SSO, Jira/Linear sync

## Why It Has Traction Potential

Remote-first and async-first companies are growing rapidly. The $0 meeting cost pitch resonates immediately with CTOs and engineering managers. Comp tools like Geekbot charge $2.50/user/mo on Slack — this is a standalone, cheaper, stackable alternative.
