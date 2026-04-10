"""Simple JSON-file database for standup-digest."""
import json
import os

DB_PATH = "data/db.json"

_default = {
    "updates": [],
    "teams": [],
    "digests": [],
}

db: dict = {}


def init_db():
    global db
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        with open(DB_PATH) as f:
            db.update(json.load(f))
    else:
        db.update(_default)
        with open(DB_PATH, "w") as f:
            json.dump(_default, f, indent=2)
    print(f"[db] Loaded {len(db.get('teams', []))} teams, {len(db.get('updates', []))} updates")
