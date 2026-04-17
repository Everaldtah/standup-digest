# standup-digest

> Automated daily standup digest for engineering teams — pulls GitHub commits and PRs, formats them into a clean team update, and delivers via Slack or email.

## The Problem

Remote engineering teams waste 15-30 minutes every morning on async standups — manually writing what they did yesterday across Slack, Jira, and GitHub. Managers lose visibility into team momentum, and developers lose focus time.

**standup-digest** solves this by automatically pulling your team's GitHub activity and generating a concise, formatted standup digest — no manual input required.

## Features

- **GitHub Activity Pulling** — fetches commits, PRs, and contributor stats for any repository
- **Multi-repo Support** — aggregate activity from multiple repos into one digest
- **Slack Delivery** — posts digests to any Slack channel via incoming webhook
- **Email Delivery** — sends HTML-formatted digests via SMTP
- **GitHub Webhook** — trigger real-time digest updates on push events
- **REST API** — generate digests on-demand via HTTP
- **Browser Preview** — preview digests in-browser before sending
- **Scheduled Delivery** — cron-style daily scheduling via `scheduler.py`

## Tech Stack

- **Python 3.11+**
- **FastAPI** — REST API and webhook handler
- **httpx** — async GitHub API client
- **Uvicorn** — ASGI server

## Installation

```bash
git clone https://github.com/Everaldtah/standup-digest
cd standup-digest

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your GitHub token and delivery settings
```

## Configuration

Edit `.env`:

```env
GITHUB_TOKEN=ghp_your_token          # GitHub PAT with repo scope
SLACK_WEBHOOK_URL=https://hooks...   # Optional: Slack webhook
SMTP_USER=you@gmail.com              # Optional: email delivery
SMTP_PASS=your_app_password
DIGEST_EMAIL_TO=team@company.com
```

## Usage

### Start the API server
```bash
uvicorn app:app --reload
# Visit http://localhost:8000
```

### Preview a digest in browser
```
GET http://localhost:8000/digest/preview?owner=YOUR_ORG&repo=YOUR_REPO&days=1
```

### Generate and send a digest via API
```bash
curl -X POST http://localhost:8000/digest \
  -H "Content-Type: application/json" \
  -d '{
    "repos": [{"owner": "your-org", "repo": "your-repo", "branch": "main"}],
    "days_back": 1,
    "send_slack": true,
    "send_email": false
  }'
```

### Run once from command line
```bash
REPO_OWNER=your-org REPO_NAME=your-repo python scheduler.py
```

### Schedule daily digest at 9am
```bash
REPO_OWNER=your-org REPO_NAME=your-repo python scheduler.py --schedule 09:00
```

### GitHub Webhook Setup
1. Go to your GitHub repo → Settings → Webhooks → Add webhook
2. Set Payload URL to `https://your-domain/webhook`
3. Set Content type to `application/json`
4. Set Secret to match `GITHUB_WEBHOOK_SECRET` in your `.env`
5. Select "Push events"

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/digest` | POST | Generate and send digest |
| `/digest/preview` | GET | Preview digest in browser |
| `/webhook` | POST | GitHub push webhook handler |
| `/health` | GET | Health check |
| `/docs` | GET | Interactive API docs |

## Monetization Model

| Plan | Price | Features |
|------|-------|---------|
| **Free** | $0 | 1 repo, manual trigger only |
| **Starter** | $19/mo | 5 repos, daily scheduled digest, Slack |
| **Team** | $49/mo | 20 repos, Slack + email, multiple channels |
| **Business** | $99/mo | Unlimited repos, JIRA integration, custom branding |

**Target market:** Engineering teams of 3-20 people at startups and agencies (~2M teams globally).

## Deployment

```bash
# Deploy to Render/Railway/Fly.io
# Set environment variables in dashboard
# Point GitHub webhooks to your deployment URL
```

## License

MIT
