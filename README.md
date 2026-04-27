# standup-digest

> Async standup collector with AI-powered daily digest reports for remote teams.

## The Problem

Daily standup meetings waste 15–30 minutes of focused work time for every team member. Timezone differences make synchronous standups impossible for global teams. Most async alternatives are either too complex or just Slack bots that dump raw updates nobody reads.

**standup-digest** collects updates asynchronously via API, summarizes them with AI, and delivers clean digest reports at your team's configured time — via email or webhook.

## Features

- **REST API** for submitting standups from any tool (Slack bot, CLI, web form)
- **AI summaries** powered by Claude or GPT-4o-mini — highlights key work, blockers, and cross-team deps
- **Scheduled delivery** — digests auto-generate at your team's configured time daily
- **Email delivery** — formatted HTML digest delivered to all team members
- **Webhook delivery** — POST digest JSON to Slack, Teams, Discord, or any endpoint
- **Blocker tracking** — blockers are extracted and highlighted separately
- **Team stats** — 7-day participation rate dashboard
- **Multi-team** — support multiple teams from one instance

## Tech Stack

- Python 3.11+
- FastAPI + Uvicorn
- Anthropic Claude / OpenAI GPT-4o-mini (AI summaries)
- JSON file storage (swap to PostgreSQL for production)

## Installation

```bash
# Clone and install
git clone https://github.com/Everaldtah/standup-digest.git
cd standup-digest
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add your API token and AI key

# Run
uvicorn main:app --reload --port 8000
```

## Usage

### Register a team
```bash
curl -X POST http://localhost:8000/teams/register \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "eng-team",
    "team_name": "Engineering",
    "admin_email": "lead@company.com",
    "digest_time": "09:00",
    "notify_emails": ["team@company.com"],
    "webhook_url": "https://hooks.slack.com/your-webhook"
  }'
```

### Submit a standup
```bash
curl -X POST http://localhost:8000/standup/submit \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "eng-team",
    "user_name": "Alice",
    "yesterday": "Finished the auth refactor, reviewed 3 PRs",
    "today": "Starting on the payment integration",
    "blockers": "Need design sign-off on the checkout flow"
  }'
```

### Manually trigger a digest
```bash
curl -X POST http://localhost:8000/digest/generate \
  -H "Authorization: Bearer your-secret-api-token" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "eng-team"}'
```

### Run the auto-scheduler
```bash
python scheduler.py
```

### API Docs
Visit `http://localhost:8000/docs` for interactive Swagger UI.

## Monetization Model

| Plan | Price | Features |
|------|-------|---------|
| Free | $0 | 1 team, 5 members, email digest |
| Team | $29/mo | 5 teams, unlimited members, Slack/webhook |
| Business | $99/mo | Unlimited teams, custom branding, SSO, analytics |

**Revenue drivers:** B2B SaaS teams pay for async-first tooling. Target remote-first companies, agencies, and distributed engineering teams. Integrate with Slack/Teams as a native bot for viral growth.

## Roadmap

- [ ] Slack bot integration
- [ ] Web dashboard with charts
- [ ] PostgreSQL backend
- [ ] Custom AI prompt templates
- [ ] Mobile app for quick standup submission

## License

MIT
