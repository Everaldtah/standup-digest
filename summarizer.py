"""
Summarize standup updates using OpenAI GPT or a simple template fallback.
Set OPENAI_API_KEY in your .env to enable AI summaries.
"""

import os
from typing import List, Dict


def generate_summary(team_name: str, updates: List[Dict], date: str) -> str:
    """Generate a summary of the team's standup updates."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return _ai_summary(team_name, updates, date, api_key)
    return _template_summary(team_name, updates, date)


def _ai_summary(team_name: str, updates: List[Dict], date: str, api_key: str) -> str:
    """Use OpenAI to produce a smart summary."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        updates_text = "\n\n".join(
            f"**{u['member_name']}**\n"
            f"Yesterday: {u['yesterday']}\n"
            f"Today: {u['today']}\n"
            f"Blockers: {u['blockers'] or 'None'}"
            for u in updates
        )

        prompt = (
            f"Summarize these standup updates for team '{team_name}' on {date}.\n\n"
            f"{updates_text}\n\n"
            "Provide:\n"
            "1. A one-paragraph team summary (what's moving, overall momentum)\n"
            "2. Key blockers that need attention (if any)\n"
            "3. Notable achievements from yesterday\n"
            "Keep it concise and actionable for a team lead."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"[summarizer] AI error: {e}, falling back to template")
        return _template_summary(team_name, updates, date)


def _template_summary(team_name: str, updates: List[Dict], date: str) -> str:
    """Produce a clean template-based summary without AI."""
    blockers = [u for u in updates if u.get("blockers") and u["blockers"].strip()]
    submitted = len(updates)

    lines = [
        f"Team {team_name} Standup — {date}",
        f"{submitted} member{'s' if submitted != 1 else ''} submitted updates.",
        "",
    ]

    lines.append("── What happened yesterday ──")
    for u in updates:
        lines.append(f"• {u['member_name']}: {u['yesterday']}")

    lines.append("")
    lines.append("── Focus for today ──")
    for u in updates:
        lines.append(f"• {u['member_name']}: {u['today']}")

    if blockers:
        lines.append("")
        lines.append(f"⚠️  Blockers ({len(blockers)}):")
        for u in blockers:
            lines.append(f"• {u['member_name']}: {u['blockers']}")

    return "\n".join(lines)
