/**
 * standup-digest: Async standup collector with smart digest generation.
 * Replaces synchronous standup meetings for distributed/remote teams.
 */

const express = require('express');
const Database = require('better-sqlite3');
const crypto = require('crypto');
const https = require('https');
const http = require('http');
require('dotenv').config();

const app = express();
app.use(express.json());

const DB_PATH = process.env.DATABASE_PATH || 'standup.db';
const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    timezone TEXT DEFAULT 'UTC',
    digest_time TEXT DEFAULT '09:00',
    slack_webhook TEXT,
    teams_webhook TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    slack_user_id TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS updates (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    update_date TEXT NOT NULL,
    yesterday TEXT,
    today TEXT NOT NULL,
    blockers TEXT,
    mood INTEGER,
    submitted_at TEXT NOT NULL,
    FOREIGN KEY(team_id) REFERENCES teams(id),
    FOREIGN KEY(member_id) REFERENCES members(id),
    UNIQUE(member_id, update_date)
  );

  CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    digest_date TEXT NOT NULL,
    content TEXT NOT NULL,
    update_count INTEGER DEFAULT 0,
    missing_members TEXT DEFAULT '[]',
    sent_at TEXT,
    channels_sent TEXT DEFAULT '[]',
    FOREIGN KEY(team_id) REFERENCES teams(id)
  );

  CREATE INDEX IF NOT EXISTS idx_updates_date ON updates(update_date);
  CREATE INDEX IF NOT EXISTS idx_updates_team ON updates(team_id);
  CREATE INDEX IF NOT EXISTS idx_digests_team ON digests(team_id);
`);


// ─── Helpers ─────────────────────────────────────────────────────────────────

function genId() { return crypto.randomBytes(6).toString('hex'); }

function todayDate() { return new Date().toISOString().split('T')[0]; }

function postWebhook(url, payload) {
  return new Promise((resolve) => {
    try {
      const data = JSON.stringify(payload);
      const parsed = new URL(url);
      const opts = {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) }
      };
      const lib = parsed.protocol === 'https:' ? https : http;
      const req = lib.request(opts, res => resolve({ ok: res.statusCode < 400, status: res.statusCode }));
      req.on('error', e => resolve({ ok: false, error: e.message }));
      req.setTimeout(5000, () => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
      req.write(data);
      req.end();
    } catch (e) {
      resolve({ ok: false, error: e.message });
    }
  });
}

function moodEmoji(score) {
  if (!score) return '';
  if (score >= 4) return '😄';
  if (score >= 3) return '😐';
  return '😔';
}

function generateDigestText(team, updates, missingMembers, date) {
  const lines = [];
  lines.push(`📋 *${team.name} Standup — ${date}*`);
  lines.push(`${updates.length} update(s) submitted`);
  if (missingMembers.length) lines.push(`⚠️ Missing: ${missingMembers.map(m => m.name).join(', ')}`);
  lines.push('');

  const blockers = updates.filter(u => u.blockers && u.blockers.trim());

  for (const u of updates) {
    const mood = moodEmoji(u.mood);
    lines.push(`*${u.member_name}* ${mood}`);
    if (u.yesterday) lines.push(`  ✅ *Yesterday:* ${u.yesterday}`);
    lines.push(`  🔨 *Today:* ${u.today}`);
    if (u.blockers && u.blockers.trim()) lines.push(`  🚧 *Blockers:* ${u.blockers}`);
    lines.push('');
  }

  if (blockers.length > 0) {
    lines.push('─────────────────────');
    lines.push(`🚧 *${blockers.length} Active Blocker(s)*`);
    for (const b of blockers) {
      lines.push(`  • ${b.member_name}: ${b.blockers}`);
    }
  }

  return lines.join('\n');
}

function generateDigestHTML(team, updates, missingMembers, date) {
  const blockers = updates.filter(u => u.blockers && u.blockers.trim());
  const avgMood = updates.filter(u => u.mood).reduce((s, u, _, a) => s + u.mood / a.length, 0);

  return `
    <h2>${team.name} — Standup for ${date}</h2>
    <p><strong>${updates.length}</strong> update(s) |
       ${missingMembers.length ? `<span style="color:orange">Missing: ${missingMembers.map(m => m.name).join(', ')}</span>` : '<span style="color:green">Full team submitted</span>'}
       ${avgMood ? ` | Team mood: ${moodEmoji(avgMood)} ${avgMood.toFixed(1)}/5` : ''}
    </p>
    ${updates.map(u => `
      <div style="border-left:3px solid #5865F2;padding:0.75rem 1rem;margin:0.75rem 0;background:#f8f9fa;border-radius:0 6px 6px 0">
        <strong>${u.member_name}</strong> ${moodEmoji(u.mood)}
        ${u.yesterday ? `<p style="margin:0.25rem 0"><span style="color:#28a745">✅ Yesterday:</span> ${u.yesterday}</p>` : ''}
        <p style="margin:0.25rem 0"><span style="color:#007bff">🔨 Today:</span> ${u.today}</p>
        ${u.blockers ? `<p style="margin:0.25rem 0"><span style="color:#dc3545">🚧 Blocker:</span> ${u.blockers}</p>` : ''}
      </div>
    `).join('')}
    ${blockers.length ? `
      <div style="background:#fff3cd;padding:1rem;border-radius:6px;margin-top:1rem">
        <strong>🚧 ${blockers.length} Active Blocker(s)</strong>
        <ul>${blockers.map(b => `<li><strong>${b.member_name}:</strong> ${b.blockers}</li>`).join('')}</ul>
      </div>
    ` : ''}
  `;
}


// ─── Teams ────────────────────────────────────────────────────────────────────

app.post('/teams', (req, res) => {
  const { name, timezone = 'UTC', digest_time = '09:00', slack_webhook, teams_webhook } = req.body;
  if (!name) return res.status(400).json({ error: 'name is required' });
  const id = genId();
  const now = new Date().toISOString();
  try {
    db.prepare('INSERT INTO teams (id,name,timezone,digest_time,slack_webhook,teams_webhook,created_at) VALUES (?,?,?,?,?,?,?)')
      .run(id, name, timezone, digest_time, slack_webhook, teams_webhook, now);
    res.status(201).json(db.prepare('SELECT * FROM teams WHERE id=?').get(id));
  } catch (e) {
    if (e.message.includes('UNIQUE')) return res.status(409).json({ error: 'Team name already exists' });
    throw e;
  }
});

app.get('/teams', (req, res) => {
  const teams = db.prepare('SELECT * FROM teams WHERE active=1').all();
  res.json(teams);
});

app.get('/teams/:id', (req, res) => {
  const team = db.prepare('SELECT * FROM teams WHERE id=?').get(req.params.id);
  if (!team) return res.status(404).json({ error: 'Team not found' });
  const members = db.prepare('SELECT * FROM members WHERE team_id=? AND active=1').all(req.params.id);
  res.json({ ...team, members });
});


// ─── Members ──────────────────────────────────────────────────────────────────

app.post('/teams/:teamId/members', (req, res) => {
  const team = db.prepare('SELECT * FROM teams WHERE id=?').get(req.params.teamId);
  if (!team) return res.status(404).json({ error: 'Team not found' });
  const { name, email, slack_user_id } = req.body;
  if (!name) return res.status(400).json({ error: 'name is required' });
  const id = genId();
  const now = new Date().toISOString();
  db.prepare('INSERT INTO members (id,team_id,name,email,slack_user_id,created_at) VALUES (?,?,?,?,?,?)')
    .run(id, req.params.teamId, name, email, slack_user_id, now);
  res.status(201).json(db.prepare('SELECT * FROM members WHERE id=?').get(id));
});


// ─── Standup Updates ──────────────────────────────────────────────────────────

app.post('/updates', (req, res) => {
  const { team_id, member_id, yesterday, today, blockers, mood, date } = req.body;
  if (!team_id || !member_id || !today) {
    return res.status(400).json({ error: 'team_id, member_id, and today are required' });
  }
  const member = db.prepare('SELECT * FROM members WHERE id=? AND team_id=?').get(member_id, team_id);
  if (!member) return res.status(404).json({ error: 'Member not found in this team' });

  const updateDate = date || todayDate();
  const id = genId();
  const now = new Date().toISOString();

  try {
    db.prepare(`
      INSERT INTO updates (id,team_id,member_id,update_date,yesterday,today,blockers,mood,submitted_at)
      VALUES (?,?,?,?,?,?,?,?,?)
      ON CONFLICT(member_id,update_date) DO UPDATE SET
        yesterday=excluded.yesterday,today=excluded.today,
        blockers=excluded.blockers,mood=excluded.mood,submitted_at=excluded.submitted_at
    `).run(id, team_id, member_id, updateDate, yesterday, today, blockers, mood, now);

    res.status(201).json({ message: 'Standup submitted', date: updateDate, member: member.name });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/updates', (req, res) => {
  const { team_id, date, member_id } = req.query;
  let sql = `
    SELECT u.*, m.name as member_name, m.email
    FROM updates u JOIN members m ON u.member_id = m.id
    WHERE 1=1
  `;
  const params = [];
  if (team_id) { sql += ' AND u.team_id=?'; params.push(team_id); }
  if (date) { sql += ' AND u.update_date=?'; params.push(date); }
  if (member_id) { sql += ' AND u.member_id=?'; params.push(member_id); }
  sql += ' ORDER BY u.submitted_at DESC LIMIT 200';
  res.json(db.prepare(sql).all(...params));
});


// ─── Digest Generation ────────────────────────────────────────────────────────

app.post('/teams/:teamId/digest', async (req, res) => {
  const { date, send = false } = req.body;
  const team = db.prepare('SELECT * FROM teams WHERE id=?').get(req.params.teamId);
  if (!team) return res.status(404).json({ error: 'Team not found' });

  const digestDate = date || todayDate();
  const members = db.prepare('SELECT * FROM members WHERE team_id=? AND active=1').all(req.params.teamId);

  const updates = db.prepare(`
    SELECT u.*, m.name as member_name FROM updates u
    JOIN members m ON u.member_id = m.id
    WHERE u.team_id=? AND u.update_date=?
    ORDER BY m.name
  `).all(req.params.teamId, digestDate);

  const submittedIds = new Set(updates.map(u => u.member_id));
  const missingMembers = members.filter(m => !submittedIds.has(m.id));

  const textContent = generateDigestText(team, updates, missingMembers, digestDate);
  const htmlContent = generateDigestHTML(team, updates, missingMembers, digestDate);

  const id = genId();
  const now = new Date().toISOString();
  const channelsSent = [];

  if (send) {
    if (team.slack_webhook) {
      const result = await postWebhook(team.slack_webhook, { text: textContent });
      if (result.ok) channelsSent.push('slack');
    }
    if (team.teams_webhook) {
      const result = await postWebhook(team.teams_webhook, {
        type: 'message', text: textContent
      });
      if (result.ok) channelsSent.push('teams');
    }
  }

  try {
    db.prepare(`
      INSERT INTO digests (id,team_id,digest_date,content,update_count,missing_members,sent_at,channels_sent)
      VALUES (?,?,?,?,?,?,?,?)
      ON CONFLICT DO NOTHING
    `).run(id, req.params.teamId, digestDate, textContent,
           updates.length, JSON.stringify(missingMembers.map(m=>m.name)),
           send ? now : null, JSON.stringify(channelsSent));
  } catch (_) {}

  res.json({
    date: digestDate,
    team: team.name,
    updates_submitted: updates.length,
    total_members: members.length,
    missing: missingMembers.map(m => m.name),
    channels_sent: channelsSent,
    digest_text: textContent,
    digest_html: htmlContent
  });
});

app.get('/teams/:teamId/digest/:date', (req, res) => {
  const digest = db.prepare('SELECT * FROM digests WHERE team_id=? AND digest_date=?')
    .get(req.params.teamId, req.params.date);
  if (!digest) return res.status(404).json({ error: 'Digest not found for this date' });
  digest.missing_members = JSON.parse(digest.missing_members || '[]');
  digest.channels_sent = JSON.parse(digest.channels_sent || '[]');
  res.json(digest);
});

app.get('/teams/:teamId/history', (req, res) => {
  const limit = parseInt(req.query.limit || '14');
  const digests = db.prepare(`
    SELECT digest_date, update_count, sent_at,
           (SELECT COUNT(*) FROM members WHERE team_id=? AND active=1) as total_members
    FROM digests WHERE team_id=? ORDER BY digest_date DESC LIMIT ?
  `).all(req.params.teamId, req.params.teamId, limit);
  res.json(digests);
});

// Status: who has/hasn't submitted today
app.get('/teams/:teamId/status', (req, res) => {
  const date = req.query.date || todayDate();
  const members = db.prepare('SELECT * FROM members WHERE team_id=? AND active=1').all(req.params.teamId);
  const updates = db.prepare(`
    SELECT member_id, submitted_at FROM updates WHERE team_id=? AND update_date=?
  `).all(req.params.teamId, date);
  const submittedMap = Object.fromEntries(updates.map(u => [u.member_id, u.submitted_at]));
  const result = members.map(m => ({
    member_id: m.id, name: m.name, email: m.email,
    submitted: !!submittedMap[m.id],
    submitted_at: submittedMap[m.id] || null
  }));
  const submitted = result.filter(m => m.submitted).length;
  res.json({ date, submitted, total: members.length, completion_pct: members.length ? Math.round(submitted/members.length*100) : 0, members: result });
});


// ─── Dashboard ────────────────────────────────────────────────────────────────

app.get('/', (req, res) => {
  const teams = db.prepare('SELECT * FROM teams WHERE active=1').all();
  const today = todayDate();

  const teamCards = teams.map(t => {
    const members = db.prepare('SELECT COUNT(*) as c FROM members WHERE team_id=? AND active=1').get(t.id);
    const submitted = db.prepare('SELECT COUNT(*) as c FROM updates WHERE team_id=? AND update_date=?').get(t.id, today);
    const pct = members.c > 0 ? Math.round(submitted.c / members.c * 100) : 0;
    return `
      <div class="team-card">
        <div class="team-name">${t.name}</div>
        <div class="team-stats">${submitted.c}/${members.c} submitted today (${pct}%)</div>
        <div class="progress"><div class="progress-bar" style="width:${pct}%"></div></div>
        <div class="team-actions">
          <a href="/teams/${t.id}/status-page">View Status</a>
        </div>
      </div>
    `;
  }).join('') || '<p style="color:#718096">No teams yet. Create one via the API.</p>';

  res.send(`<!DOCTYPE html>
<html>
<head>
  <title>Standup Digest</title>
  <style>
    body { font-family: system-ui,sans-serif; max-width:960px; margin:0 auto; padding:2rem; background:#1a1a2e; color:#e0e0e0; }
    h1 { color:#7c3aed; } h2 { color:#a78bfa; border-bottom:1px solid #2d2d4e; padding-bottom:0.5rem; }
    .subtitle { color:#6b7280; margin-bottom:1.5rem; } a { color:#a78bfa; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:1rem; margin:1rem 0; }
    .team-card { background:#16213e; border:1px solid #2d2d4e; border-radius:8px; padding:1.25rem; }
    .team-name { font-weight:700; font-size:1.1rem; color:#c4b5fd; }
    .team-stats { font-size:0.85rem; color:#9ca3af; margin:0.5rem 0; }
    .progress { background:#2d2d4e; border-radius:99px; height:6px; margin:0.5rem 0; }
    .progress-bar { background:#7c3aed; height:100%; border-radius:99px; transition:width 0.3s; }
    .team-actions { margin-top:0.75rem; font-size:0.85rem; }
    .section { background:#16213e; border:1px solid #2d2d4e; border-radius:8px; padding:1.5rem; margin:1rem 0; }
    pre { background:#0f0f1a; padding:1rem; border-radius:4px; font-size:0.8rem; overflow-x:auto; }
  </style>
</head>
<body>
  <h1>Standup Digest</h1>
  <p class="subtitle">Async standup collector for distributed teams — <strong>${today}</strong></p>

  <div class="section">
    <h2>Teams</h2>
    <div class="grid">${teamCards}</div>
  </div>

  <div class="section">
    <h2>Quick API</h2>
    <pre>
# Create a team
curl -X POST http://localhost:3001/teams \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Engineering","timezone":"America/New_York","slack_webhook":"https://hooks.slack.com/..."}'

# Add a member
curl -X POST http://localhost:3001/teams/TEAM_ID/members \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Alice","email":"alice@company.com"}'

# Submit a standup update
curl -X POST http://localhost:3001/updates \\
  -H "Content-Type: application/json" \\
  -d '{"team_id":"TEAM_ID","member_id":"MEMBER_ID","yesterday":"Finished auth module","today":"Working on API tests","blockers":"","mood":4}'

# Generate and send digest
curl -X POST http://localhost:3001/teams/TEAM_ID/digest \\
  -H "Content-Type: application/json" \\
  -d '{"send":true}'

# Check who submitted today
curl http://localhost:3001/teams/TEAM_ID/status
    </pre>
  </div>
</body>
</html>`);
});

// Simple per-team status page
app.get('/teams/:teamId/status-page', (req, res) => {
  const team = db.prepare('SELECT * FROM teams WHERE id=?').get(req.params.teamId);
  if (!team) return res.status(404).send('Team not found');
  const date = req.query.date || todayDate();
  const members = db.prepare('SELECT * FROM members WHERE team_id=? AND active=1').all(req.params.teamId);
  const updates = db.prepare(`
    SELECT u.*, m.name as member_name FROM updates u
    JOIN members m ON u.member_id=m.id
    WHERE u.team_id=? AND u.update_date=?
    ORDER BY m.name
  `).all(req.params.teamId, date);
  const submittedIds = new Set(updates.map(u => u.member_id));
  const missing = members.filter(m => !submittedIds.has(m.id));

  const updateCards = updates.map(u => `
    <div style="border-left:3px solid #7c3aed;padding:0.75rem 1rem;margin:0.75rem 0;background:#1e2040;border-radius:0 6px 6px 0">
      <strong style="color:#c4b5fd">${u.member_name}</strong> ${moodEmoji(u.mood)}
      ${u.yesterday ? `<p style="margin:0.25rem 0;font-size:0.9rem">✅ <em>${u.yesterday}</em></p>` : ''}
      <p style="margin:0.25rem 0;font-size:0.9rem">🔨 ${u.today}</p>
      ${u.blockers ? `<p style="margin:0.25rem 0;font-size:0.9rem;color:#f87171">🚧 ${u.blockers}</p>` : ''}
    </div>
  `).join('');

  res.send(`<!DOCTYPE html>
<html>
<head><title>${team.name} Standup — ${date}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:0 auto;padding:2rem;background:#1a1a2e;color:#e0e0e0;} h1{color:#7c3aed;} .missing{background:#2d0a0a;padding:0.75rem;border-radius:6px;color:#f87171;margin:1rem 0;} a{color:#a78bfa;}</style>
</head>
<body>
  <h1>${team.name} — ${date}</h1>
  <p>${updates.length}/${members.length} members submitted | <a href="/">Back to dashboard</a></p>
  ${missing.length ? `<div class="missing">⚠️ Not yet submitted: ${missing.map(m=>m.name).join(', ')}</div>` : '<p style="color:#4ade80">✅ Full team submitted!</p>'}
  ${updateCards || '<p style="color:#718096">No updates submitted yet today.</p>'}
</body>
</html>`);
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`Standup Digest running on http://localhost:${PORT}`));
module.exports = app;
