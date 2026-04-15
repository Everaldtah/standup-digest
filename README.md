# Standup Digest

> Replace synchronous standup meetings with async updates. Collect team check-ins via API, auto-generate digests, and post summaries to Slack or Teams.

## The Problem

Daily standups are often the most disrupted meeting on a distributed team's calendar:
- Timezone overlap is impossible for global teams
- 10-minute meetings become 30 minutes with 8+ people
- Nobody remembers what was said by end of day
- Remote team members feel left out if they miss the call

Standup Digest lets each team member submit their update asynchronously — then automatically compiles a clean digest sent to Slack, Microsoft Teams, or any webhook.

## Features

- **Multi-team support** — Create separate teams for Engineering, Design, Marketing, etc.
- **Flexible submissions** — Submit via REST API, CLI, or your own custom form
- **Smart digest generation** — Highlights blockers, shows team mood, flags who hasn't submitted
- **Slack & Teams integration** — Post digest to channels via webhooks
- **Completion tracking** — See at a glance who has/hasn't submitted today
- **Mood tracking** — Optional 1–5 mood score with emoji visualization
- **History** — Per-team digest archive for retrospectives
- **Cron-ready** — One endpoint to call on a schedule to auto-send digests

## Tech Stack

- **Node.js 18+**
- **Express.js** — HTTP server
- **better-sqlite3** — Embedded database
- **dotenv** — Configuration

## Installation

```bash
git clone https://github.com/Everaldtah/standup-digest.git
cd standup-digest

npm install
cp .env.example .env

npm start
```

Dashboard: **http://localhost:3001**

## Usage

### Create a team

```bash
curl -X POST http://localhost:3001/teams \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Engineering",
    "timezone": "America/New_York",
    "slack_webhook": "https://hooks.slack.com/services/YOUR/WEBHOOK"
  }'
```

### Add team members

```bash
curl -X POST http://localhost:3001/teams/TEAM_ID/members \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Chen", "email": "alice@company.com"}'
```

### Submit a standup update

```bash
curl -X POST http://localhost:3001/updates \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "TEAM_ID",
    "member_id": "MEMBER_ID",
    "yesterday": "Finished OAuth2 integration",
    "today": "Writing unit tests for auth module",
    "blockers": "",
    "mood": 4
  }'
```

### Generate and send digest to Slack

```bash
curl -X POST http://localhost:3001/teams/TEAM_ID/digest \
  -H "Content-Type: application/json" \
  -d '{"send": true}'
```

### Check who submitted today

```bash
curl http://localhost:3001/teams/TEAM_ID/status
```

### Run the demo seed script

```bash
# Start the server first, then:
node seed.js
```

## Cron Integration

To auto-send digests every morning, add this to your crontab:

```bash
# Send standup digest every weekday at 10am UTC
0 10 * * 1-5 curl -X POST http://localhost:3001/teams/TEAM_ID/digest -H "Content-Type: application/json" -d '{"send":true}'
```

Or use GitHub Actions, Railway cron, Render cron jobs, etc.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/teams` | Create a team |
| GET | `/teams` | List all teams |
| GET | `/teams/:id` | Get team with members |
| POST | `/teams/:id/members` | Add a member |
| POST | `/updates` | Submit a standup update |
| GET | `/updates` | Query updates (filter by team/date/member) |
| POST | `/teams/:id/digest` | Generate (and optionally send) digest |
| GET | `/teams/:id/digest/:date` | Retrieve stored digest for a date |
| GET | `/teams/:id/history` | Digest history |
| GET | `/teams/:id/status` | Today's submission status |

## Sample Digest Output

```
📋 *Engineering Standup — 2024-11-15*
3 update(s) submitted
⚠️ Missing: David Lee

*Alice Chen* 😄
  ✅ *Yesterday:* Finished OAuth2 integration
  🔨 *Today:* Writing unit tests for auth module

*Bob Martinez* 😐
  ✅ *Yesterday:* Fixed performance regression in search
  🔨 *Today:* Reviewing Alice's PR, then pagination
  🚧 *Blockers:* Waiting on design specs for filter UI

─────────────────────
🚧 1 Active Blocker(s)
  • Bob Martinez: Waiting on design specs for filter UI
```

## Monetization Model

| Tier | Price | Includes |
|------|-------|---------|
| **Free** | $0/mo | 1 team, 5 members, 30-day history |
| **Starter** | $12/mo | 3 teams, unlimited members, Slack/Teams, 1 year history |
| **Growth** | $29/mo | Unlimited teams, mood analytics, blocker reports, CSV export |
| **Enterprise** | $79/mo | SSO, custom forms, Jira/Linear integration, SLA |

**Revenue angle**: Remote-first companies are willing to pay to replace the cost of daily synchronous meetings. Even at $29/mo, if a single 30-min meeting is eliminated it's worth hundreds per month in team productivity.

## License

MIT
