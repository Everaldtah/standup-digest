# standup-digest

> Async daily standup aggregator with AI-powered summaries. Replace boring synchronous standup meetings with asynchronous updates and a smart digest that actually gets read.

## Problem It Solves

Daily standup meetings waste 15–30 minutes for the entire team — even when most updates could have been a message. Existing async standup tools (Geekbot, Standuply) are expensive ($3–5/user/month) and just collect text without adding intelligence. **standup-digest** aggregates team updates, uses AI (Claude or GPT-4) to generate a concise digest, detects blockers automatically, and emails it to the team lead — all for a fraction of the cost.

## Features

- **Async update submission** — team members submit via API (integrates with Slack bots, web forms, etc.)
- **AI-powered digest** — Claude or GPT-4 generates a concise team summary with highlights and risks
- **Automatic blocker detection** — scans updates for 16 blocker keywords and flags urgently
- **Daily email digest** — scheduled delivery at configurable time with participation stats
- **Multi-team support** — manage multiple engineering teams from one instance
- **Participation tracking** — see who hasn't submitted and nudge them
- **Mood tracking** — optional 1–5 mood score to track team health over time
- **Rule-based fallback** — works without AI APIs using keyword extraction
- **Historical digests** — browse past digests and track trends

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API
- **APScheduler** — scheduled digest delivery
- **Claude (Haiku) / GPT-4o Mini** — AI summarization (optional)
- **SQLite** — zero-config database
- **SMTP** — email delivery

## Installation

```bash
# Clone the repo
git clone https://github.com/Everaldtah/standup-digest.git
cd standup-digest

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY or OPENAI_API_KEY (optional but recommended)
# Add SMTP credentials for email delivery (optional for testing)

# Run the server
python main.py
```

API available at `http://localhost:8003`

## Usage

### 1. Create a team
```bash
curl -X POST http://localhost:8003/teams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Platform Engineering",
    "slug": "platform",
    "digest_email": "eng-lead@company.com",
    "timezone": "America/New_York",
    "digest_time": "09:00"
  }'
```

### 2. Add team members
```bash
curl -X POST http://localhost:8003/teams/platform/members \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Chen", "email": "alice@company.com"}'
```

### 3. Submit a standup update
```bash
curl -X POST http://localhost:8003/teams/platform/update \
  -H "Content-Type: application/json" \
  -d '{
    "member_email": "alice@company.com",
    "yesterday": "Completed the OAuth integration and fixed 2 P2 bugs.",
    "today": "Starting work on the webhook retry system.",
    "blockers": null,
    "mood": 4
  }'
```

### 4. Generate digest on demand
```bash
curl -X POST http://localhost:8003/teams/platform/digest
```

### 5. Check who hasn't submitted
```bash
curl http://localhost:8003/teams/platform/missing
```

### Run demo
```bash
python demo.py
```

## Blocker Keywords Detected

`blocked`, `blocking`, `stuck`, `waiting for`, `need help`, `can't proceed`, `dependency`, `delayed`, `postponed`, `escalate`, `urgent`, `help needed`, `issue`, `problem`, `error`, `bug`, `failing`, `broken`

## Monetization Model

| Plan | Price | Features |
|------|-------|---------|
| **Free** | $0 | 1 team, up to 5 members, no AI summary |
| **Starter** | $15/mo | 3 teams, up to 15 members, AI summaries |
| **Team** | $39/mo | Unlimited teams, Slack integration, mood analytics |
| **Enterprise** | $99/mo | SSO, custom branding, priority support, API access |

**Additional revenue:** Slack App marketplace listing, integration with Jira/Linear for ticket-linked blockers.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/teams` | Create a new team |
| `GET` | `/teams` | List all teams |
| `POST` | `/teams/{slug}/members` | Add a team member |
| `POST` | `/teams/{slug}/update` | Submit standup update |
| `GET` | `/teams/{slug}/updates` | Get today's updates |
| `GET` | `/teams/{slug}/missing` | See who hasn't submitted |
| `POST` | `/teams/{slug}/digest` | Generate & email digest |
| `GET` | `/teams/{slug}/digests` | Browse past digests |

## License

MIT
