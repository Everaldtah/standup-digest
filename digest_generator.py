"""
Digest generator — uses OpenAI to produce human-readable standup bullets.
Falls back to a structured plain-text digest if OpenAI is unavailable.
"""

import os
from textwrap import dedent


class DigestGenerator:
    def __init__(self, openai_api_key: str | None = None):
        self.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise RuntimeError("openai package not installed. Run: pip install openai")
        return self._client

    def _build_raw_context(self, commits: list[dict], prs: list[dict]) -> str:
        lines = ["=== COMMITS ==="]
        for c in commits:
            lines.append(f"[{c['repo']}] {c['author']}: {c['message']} ({c['sha']})")

        lines.append("\n=== PULL REQUESTS ===")
        for pr in prs:
            status = "MERGED" if pr.get("merged") else pr["state"].upper()
            lines.append(f"[{pr['repo']}] #{pr['number']} {pr['title']} — {pr['author']} [{status}]")

        return "\n".join(lines)

    def generate(self, commits: list[dict], prs: list[dict]) -> str:
        """Generate a standup digest markdown string."""
        if not commits and not prs:
            return "## Daily Standup Digest\n\n_No activity found in the specified time window._"

        raw = self._build_raw_context(commits, prs)

        if not self.api_key:
            return self._fallback_digest(commits, prs)

        try:
            return self._ai_digest(raw, commits, prs)
        except Exception:
            return self._fallback_digest(commits, prs)

    def _ai_digest(self, raw_context: str, commits: list[dict], prs: list[dict]) -> str:
        client = self._get_client()
        prompt = dedent(f"""
            You are a helpful engineering manager assistant. Based on the GitHub activity below,
            generate a concise daily standup digest in Markdown format.

            Format rules:
            - Group by author/contributor
            - Use bullet points
            - Focus on what was accomplished and what is in review
            - Keep each bullet under 15 words
            - Add a brief "Team Summary" section at the top (2-3 sentences)
            - Use emojis sparingly (✅ for merged, 🔄 for in-review, 💻 for commits)

            GitHub Activity:
            {raw_context}
        """).strip()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.3,
        )
        return response.choices[0].message.content

    def _fallback_digest(self, commits: list[dict], prs: list[dict]) -> str:
        """Plain-text digest without AI, grouped by author."""
        by_author: dict[str, dict] = {}

        for c in commits:
            a = c["author"]
            by_author.setdefault(a, {"commits": [], "prs": []})
            by_author[a]["commits"].append(c)

        for pr in prs:
            a = pr["author"]
            by_author.setdefault(a, {"commits": [], "prs": []})
            by_author[a]["prs"].append(pr)

        lines = [
            "## Daily Standup Digest",
            f"_{len(commits)} commits · {len(prs)} PRs · {len(by_author)} contributors_\n",
        ]

        for author, data in sorted(by_author.items()):
            lines.append(f"### {author}")
            for c in data["commits"]:
                lines.append(f"- 💻 [{c['repo']}] {c['message']}")
            for pr in data["prs"]:
                icon = "✅" if pr.get("merged") else "🔄"
                lines.append(f"- {icon} PR #{pr['number']}: {pr['title']} ({pr['state']})")
            lines.append("")

        return "\n".join(lines)
