"""Email notification sender for standup-digest."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict


def send_digest_email(
    to_email: str,
    team_name: str,
    date: str,
    summary: str,
    updates: List[Dict],
) -> bool:
    """Send the daily standup digest email."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print(f"[mailer] SMTP not configured — would send digest to {to_email}")
        return False

    subject = f"[StandupDigest] {team_name} — {date}"
    html = _build_html(team_name, date, summary, updates)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(summary, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"[mailer] Digest sent to {to_email}")
        return True
    except Exception as e:
        print(f"[mailer] Failed to send to {to_email}: {e}")
        return False


def _build_html(team_name: str, date: str, summary: str, updates: List[Dict]) -> str:
    rows = ""
    for u in updates:
        blockers_html = (
            f'<span style="color:#e53e3e">⚠️ {u["blockers"]}</span>'
            if u.get("blockers")
            else '<span style="color:#68d391">None</span>'
        )
        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #e2e8f0;font-weight:bold">{u['member_name']}</td>
            <td style="padding:8px;border-bottom:1px solid #e2e8f0">{u['yesterday']}</td>
            <td style="padding:8px;border-bottom:1px solid #e2e8f0">{u['today']}</td>
            <td style="padding:8px;border-bottom:1px solid #e2e8f0">{blockers_html}</td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px">
        <h1 style="color:#2d3748">📋 {team_name} Standup — {date}</h1>
        <div style="background:#f7fafc;border-left:4px solid #4299e1;padding:16px;margin:16px 0;white-space:pre-line">
            {summary}
        </div>
        <h2 style="color:#4a5568">Individual Updates</h2>
        <table style="width:100%;border-collapse:collapse">
            <thead>
                <tr style="background:#edf2f7">
                    <th style="padding:8px;text-align:left">Member</th>
                    <th style="padding:8px;text-align:left">Yesterday</th>
                    <th style="padding:8px;text-align:left">Today</th>
                    <th style="padding:8px;text-align:left">Blockers</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="color:#a0aec0;font-size:12px;margin-top:24px">
            Powered by StandupDigest — async standups for remote teams
        </p>
    </body>
    </html>
    """
