/**
 * Demo seed script — creates a sample team, members, and standup updates.
 * Run after starting the server: node seed.js
 */

const http = require('http');

function api(method, path, data) {
  return new Promise((resolve, reject) => {
    const body = data ? JSON.stringify(data) : null;
    const opts = {
      hostname: 'localhost', port: 3001, path, method,
      headers: { 'Content-Type': 'application/json', ...(body ? { 'Content-Length': Buffer.byteLength(body) } : {}) }
    };
    const req = http.request(opts, res => {
      let buf = '';
      res.on('data', d => buf += d);
      res.on('end', () => {
        try { resolve(JSON.parse(buf)); }
        catch { resolve(buf); }
      });
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
}

async function run() {
  console.log('Creating Engineering team...');
  const team = await api('POST', '/teams', {
    name: 'Engineering',
    timezone: 'America/New_York',
    digest_time: '09:30',
  });
  console.log(`  Team ID: ${team.id}`);

  const memberData = [
    { name: 'Alice Chen', email: 'alice@example.com' },
    { name: 'Bob Martinez', email: 'bob@example.com' },
    { name: 'Carol Singh', email: 'carol@example.com' },
    { name: 'David Lee', email: 'david@example.com' },
  ];

  console.log('Adding team members...');
  const members = [];
  for (const m of memberData) {
    const member = await api('POST', `/teams/${team.id}/members`, m);
    members.push(member);
    console.log(`  Added: ${member.name} (${member.id})`);
  }

  const updates = [
    { member: members[0], yesterday: 'Finished OAuth2 integration', today: 'Writing unit tests for auth module', blockers: '', mood: 4 },
    { member: members[1], yesterday: 'Fixed performance regression in search', today: 'Reviewing Alice\'s PR, then working on pagination', blockers: 'Waiting on design specs for new filter UI', mood: 3 },
    { member: members[2], yesterday: 'Set up CI/CD pipeline for staging', today: 'Deploying new version to staging, then E2E tests', blockers: '', mood: 5 },
    // David hasn't submitted yet (intentionally missing)
  ];

  console.log('Submitting standup updates...');
  for (const u of updates) {
    const result = await api('POST', '/updates', {
      team_id: team.id,
      member_id: u.member.id,
      yesterday: u.yesterday,
      today: u.today,
      blockers: u.blockers,
      mood: u.mood,
    });
    console.log(`  ${u.member.name}: ${result.message}`);
  }

  console.log('\nGenerating digest (without sending)...');
  const digest = await api('POST', `/teams/${team.id}/digest`, { send: false });
  console.log(`\n─────────────────────────────────────────`);
  console.log(digest.digest_text);
  console.log(`─────────────────────────────────────────`);
  console.log(`\nMissing members: ${digest.missing.join(', ') || 'none'}`);

  console.log(`\nChecking submission status...`);
  const status = await api('GET', `/teams/${team.id}/status`, null);
  console.log(`  ${status.submitted}/${status.total} submitted (${status.completion_pct}%)`);
  status.members.forEach(m => console.log(`    ${m.submitted ? '✅' : '⬜'} ${m.name}`));

  console.log(`\nDone! Visit http://localhost:3001 for the dashboard.`);
  console.log(`Team ID: ${team.id}`);
}

run().catch(console.error);
