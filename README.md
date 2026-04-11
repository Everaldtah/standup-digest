# Standup Digest

> Auto-generate daily standup summaries from your team's GitHub activity — delivered to Slack or any webhook.

## Problem It Solves

Daily standups eat 15–30 minutes of every developer's morning. Half that time is spent trying to remember what you did yesterday. Standup Digest pulls your team's commits and PRs automatically and turns them into crisp, human-readable bullet points — so your standup is ready before you even open Slack.

## Features

- **GitHub Activity Ingestion** — fetches commits and PRs across multiple repos
- **AI-Powered Summaries** — GPT-4o-mini summarises activity into standup bullets grouped by author
- **Slack Delivery** — posts formatted digest directly to any Slack channel via webhook
- **Daily Scheduling** — configure once, get digests every morning at your chosen hour
- **Multi-Repo Support** — monitor any number of repositories in one digest
- **Fallback Mode** — structured plain-text digest works even without an OpenAI key
- **REST API** — integrate with any tool via HTTP endpoints
- **Author Filtering** — focus on specific team members

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async REST API framework
- **OpenAI GPT-4o-mini** — standup text generation
- **APScheduler** — daily cron scheduling
- **GitHub REST API** — commit and PR fetching

## Installation

```bash
git clone https://github.com/Everaldtah/standup-digest
cd standup-digest

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your keys
```

## Usage

### Start the server

```bash
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

### Generate a digest on demand

```bash
curl -X POST http://localhost:8000/digest/generate \
  -H "Content-Type: application/json" \
  -d '{
    "github_token": "ghp_your_token",
    "repos": ["your-org/backend", "your-org/frontend"],
    "since_hours": 24,
    "team_members": ["alice", "bob"],
    "openai_api_key": "sk-..."
  }'
```

### Schedule a daily Slack digest

```bash
curl -X POST http://localhost:8000/digest/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "github_token": "ghp_your_token",
    "repos": ["your-org/backend"],
    "cron_hour": 9,
    "slack_webhook": "https://hooks.slack.com/services/..."
  }'
```

### Example output

```markdown
## Daily Standup Digest
_12 commits · 4 PRs · 3 contributors_

### alice
- 💻 [backend] Fix null pointer in user auth flow
- 🔄 PR #142: Add rate limiting middleware (open)

### bob
- ✅ PR #139: Migrate database schema (merged)
- 💻 [frontend] Update dashboard chart colours
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` read scope |
| `OPENAI_API_KEY` | No | Enables AI-generated summaries |
| `SLACK_WEBHOOK_URL` | No | Default Slack delivery channel |

## Monetization Model

| Plan | Price | Limits |
|---|---|---|
| Free | $0/mo | 2 repos, 1 schedule, plain-text only |
| Starter | $12/mo | 10 repos, 5 schedules, AI summaries |
| Team | $29/mo | Unlimited repos, Jira integration, custom branding |
| Enterprise | $99/mo | SSO, audit logs, priority support |

Target MRR: $5K within 6 months targeting 50 small dev teams.

## Roadmap

- [ ] Jira ticket activity integration
- [ ] Linear.app integration
- [ ] Custom digest templates
- [ ] Weekly/sprint summary mode
- [ ] GitHub Actions trigger support
