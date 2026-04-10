# StandupDigest

**Async standup collector & AI summarizer for remote teams.**

Stop wasting 15 minutes every morning on a synchronous standup meeting. StandupDigest lets each team member submit their daily update asynchronously via a simple form or API call. At a configured time, an AI-powered digest email is automatically sent to the team with a clean summary, blockers highlighted, and individual updates neatly formatted.

---

## Problem It Solves

Remote teams are spread across timezones. Daily standup meetings either exclude half the team or require someone to join at an inconvenient hour. Async standup tools are either too expensive (Status Hero ~$3/user/mo, Geekbot ~$3/user/mo) or too feature-heavy. StandupDigest is a focused, self-hostable alternative.

---

## Features

- **Web form** — team members submit updates via browser (no app install needed)
- **REST API** — integrate with Slack bots, Notion, or any tool via POST requests
- **AI summaries** — GPT-4o-mini condenses the team's updates into an actionable paragraph (falls back to a clean template if no API key)
- **Blocker highlighting** — blockers are surfaced prominently in the digest email
- **Scheduled delivery** — configure digest time per team (e.g., 9:00 AM UTC)
- **Multi-team support** — manage multiple teams from one instance
- **Zero-dependency storage** — uses a local JSON file (swap for PostgreSQL in production)

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API & web server
- **APScheduler** — cron-based digest delivery
- **OpenAI GPT-4o-mini** — AI summaries (optional)
- **SMTP** — email delivery (works with Gmail, SendGrid, Mailgun)

---

## Installation

```bash
git clone https://github.com/Everaldtah/standup-digest
cd standup-digest
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your SMTP credentials
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

---

## Usage

### 1. Register your team

```bash
curl -X POST http://localhost:8000/api/teams \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "backend-team",
    "team_name": "Backend Team",
    "digest_email": "team-leads@company.com",
    "digest_time": "09:00",
    "timezone": "UTC"
  }'
```

### 2. Submit a standup update

```bash
curl -X POST http://localhost:8000/api/updates \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "backend-team",
    "member_name": "Alice Chen",
    "member_email": "alice@company.com",
    "yesterday": "Finished the payment webhook integration and deployed to staging",
    "today": "Writing unit tests for the billing module",
    "blockers": "Waiting on Stripe sandbox credentials from DevOps"
  }'
```

### 3. Trigger a digest manually

```bash
curl -X POST http://localhost:8000/api/digest/send \
  -H "Content-Type: application/json" \
  -d '{"team_id": "backend-team"}'
```

### 4. View today's updates

```bash
curl http://localhost:8000/api/updates/backend-team
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SMTP_HOST` | Yes | SMTP server (e.g. smtp.gmail.com) |
| `SMTP_PORT` | Yes | SMTP port (587 for TLS) |
| `SMTP_USER` | Yes | SMTP username |
| `SMTP_PASS` | Yes | SMTP password / app password |
| `FROM_EMAIL` | No | Sender email address |
| `OPENAI_API_KEY` | No | Enables AI-powered summaries |
| `PORT` | No | Server port (default: 8000) |

---

## Monetization Model

| Tier | Price | Features |
|---|---|---|
| **Free** | $0 | 1 team, 5 members, basic templates |
| **Starter** | $9/mo | 3 teams, 15 members, AI summaries |
| **Team** | $29/mo | Unlimited teams, Slack integration, analytics |
| **Enterprise** | $99/mo | SSO, audit log, priority support, custom branding |

**Why it can grow:** Most teams pay $3-5/user/month for Status Hero or Geekbot. A flat-fee model at $29/mo is immediately cheaper for any team over 6 people. Self-hostable builds trust with security-conscious companies.
