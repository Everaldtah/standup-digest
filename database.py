"""
Lightweight JSON file-based database for standup-digest.
Swap with PostgreSQL/SQLite in production by replacing these methods.
"""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class StandupEntry:
    team_id: str
    user_name: str
    yesterday: str
    today: str
    blockers: str
    submitted_at: str
    date: str


@dataclass
class TeamConfig:
    team_id: str
    team_name: str
    admin_email: str
    digest_time: str
    notify_emails: list
    webhook_url: Optional[str]


class Database:
    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", "./data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.standups_dir = self.data_dir / "standups"
        self.standups_dir.mkdir(exist_ok=True)
        self.digests_dir = self.data_dir / "digests"
        self.digests_dir.mkdir(exist_ok=True)
        self.teams_file = self.data_dir / "teams.json"
        if not self.teams_file.exists():
            self.teams_file.write_text("{}")

    def _load_teams(self) -> dict:
        return json.loads(self.teams_file.read_text())

    def _save_teams(self, teams: dict):
        self.teams_file.write_text(json.dumps(teams, indent=2))

    def upsert_team(self, config: dict):
        teams = self._load_teams()
        teams[config["team_id"]] = config
        self._save_teams(teams)

    def get_team(self, team_id: str) -> Optional[dict]:
        return self._load_teams().get(team_id)

    def save_standup(self, entry: StandupEntry):
        day_file = self.standups_dir / f"{entry.team_id}_{entry.date}.json"
        entries = []
        if day_file.exists():
            entries = json.loads(day_file.read_text())
        # Replace existing entry from same user on same day
        entries = [e for e in entries if e["user_name"] != entry.user_name]
        entries.append(asdict(entry))
        day_file.write_text(json.dumps(entries, indent=2))

    def get_standups(self, team_id: str, target_date: str) -> list:
        day_file = self.standups_dir / f"{team_id}_{target_date}.json"
        if not day_file.exists():
            return []
        return json.loads(day_file.read_text())

    def save_digest(self, digest: dict):
        digest_file = self.digests_dir / f"{digest['team_id']}_{digest['date']}.json"
        digest_file.write_text(json.dumps(digest, indent=2))

    def get_digest(self, team_id: str, target_date: str) -> Optional[dict]:
        digest_file = self.digests_dir / f"{team_id}_{target_date}.json"
        if not digest_file.exists():
            return None
        return json.loads(digest_file.read_text())
