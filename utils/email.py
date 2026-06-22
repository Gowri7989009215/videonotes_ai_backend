"""
Email sending utilities — supports Resend API and Gmail SMTP fallback.
"""

import httpx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import settings


async def _send_via_resend(to: str, subject: str, html: str) -> None:
    """Send email via Resend API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            timeout=15.0,
        )
        resp.raise_for_status()


def _send_via_smtp(to: str, subject: str, html: str) -> None:
    """Send email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.gmail_user
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.gmail_user, settings.gmail_pass)
        server.sendmail(msg["From"], to, msg.as_string())


async def send_mail(to: str, subject: str, html: str) -> None:
    """Send email using the configured provider."""
    if not settings.email_from and not settings.gmail_user:
        print("[Email] WARNING: No email provider configured, skipping send.")
        return

    try:
        if settings.resend_api_key:
            await _send_via_resend(to, subject, html)
        elif settings.gmail_user and settings.gmail_pass:
            _send_via_smtp(to, subject, html)
        else:
            print("[Email] WARNING: No email provider configured, skipping send.")
    except Exception as e:
        print(f"[Email] Failed to send email to {to}: {e}")


async def send_verification_email(to: str, code: str) -> None:
    """Send email verification code."""
    subject = "Verify your VideoNotes AI account"
    html = f"""
    <p>Welcome to <strong>VideoNotes AI</strong>!</p>
    <p>Your email verification code is:</p>
    <p style="font-size: 20px; font-weight: bold;">{code}</p>
    <p>This code expires in 15 minutes.</p>
    """
    await send_mail(to, subject, html)


async def send_password_reset_email(to: str, code: str) -> None:
    """Send password reset code."""
    subject = "Reset your VideoNotes AI password"
    html = f"""
    <p>You requested to reset your <strong>VideoNotes AI</strong> password.</p>
    <p>Your reset code is:</p>
    <p style="font-size: 20px; font-weight: bold;">{code}</p>
    <p>This code expires in 15 minutes. If you didn't request this, you can ignore this email.</p>
    """
    await send_mail(to, subject, html)


async def send_job_completion_email(to: str, job_id: str) -> None:
    """Send job completion notification."""
    subject = "Your VideoNotes AI job is ready"
    html = f"""
    <p>Your VideoNotes AI job <strong>{job_id}</strong> has completed.</p>
    <p>You can log in to your dashboard to download the generated PDF.</p>
    """
    await send_mail(to, subject, html)
