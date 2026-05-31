"""Simple transactional email templates. Plain text by default; minimal HTML
where it makes the message more readable.

Keep these dumb — no Jinja, no fancy components. We can graduate to MJML or
React Email later if the customer count justifies it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RenderedEmail:
    subject: str
    text: str
    html: str | None = None


def magic_link_signup(magic_url: str, workspace_name: str = "your workspace") -> RenderedEmail:
    return RenderedEmail(
        subject="Welcome to Summit Automates — sign in here",
        text=f"""Welcome to Summit Automates!

Your subscription is active and {workspace_name} is ready. Click the link
below to sign in and start setting up your content automation:

  {magic_url}

This link is valid for 30 minutes. Keep it private — anyone with the link
can sign in as you.

If you didn't request this, you can ignore this email — the link will
expire on its own.

— Summit Automates
admin@summitautomates.com
""",
        html=f"""<!doctype html>
<html><body style="font-family: -apple-system, system-ui, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px; color: #0f172a; line-height: 1.5;">
  <h1 style="font-size: 22px; margin: 0 0 16px;">Welcome to Summit Automates</h1>
  <p>Your subscription is active and <b>{workspace_name}</b> is ready.</p>
  <p style="margin: 24px 0;">
    <a href="{magic_url}" style="background: #0f172a; color: white; padding: 12px 20px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600;">Sign in to your workspace</a>
  </p>
  <p style="color: #475569; font-size: 14px;">Or paste this URL into your browser:</p>
  <p style="color: #475569; font-size: 13px; word-break: break-all; background: #f1f5f9; padding: 12px; border-radius: 6px;">{magic_url}</p>
  <p style="color: #64748b; font-size: 13px; margin-top: 24px;">
    This link is valid for 30 minutes. Keep it private — anyone with the link can sign in as you.
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;">
  <p style="color: #94a3b8; font-size: 12px;">
    Summit Automates · <a href="mailto:admin@summitautomates.com" style="color: #94a3b8;">admin@summitautomates.com</a>
  </p>
</body></html>""",
    )


def magic_link_login(magic_url: str) -> RenderedEmail:
    return RenderedEmail(
        subject="Sign in to Summit Automates",
        text=f"""Sign in to Summit Automates by clicking the link below:

  {magic_url}

This link is valid for 30 minutes. If you didn't request it, ignore this
email — it expires automatically.

— Summit Automates
""",
        html=f"""<!doctype html>
<html><body style="font-family: -apple-system, system-ui, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px; color: #0f172a; line-height: 1.5;">
  <h1 style="font-size: 22px; margin: 0 0 16px;">Sign in</h1>
  <p>Click the button below to sign in to Summit Automates.</p>
  <p style="margin: 24px 0;">
    <a href="{magic_url}" style="background: #0f172a; color: white; padding: 12px 20px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: 600;">Sign in</a>
  </p>
  <p style="color: #64748b; font-size: 13px;">Valid for 30 minutes. If you didn't request this, ignore the email.</p>
</body></html>""",
    )


def subscription_cancelled() -> RenderedEmail:
    return RenderedEmail(
        subject="Your Summit Automates subscription was cancelled",
        text="""Your subscription has been cancelled.

We're keeping your workspace data for 30 days in case you want to come
back. After 30 days everything is permanently deleted (encrypted API
keys, social tokens, generated posts, all of it).

To reactivate, manage your subscription on Whop:
  https://whop.com/orders

If you want immediate deletion before 30 days, reply to this email.

— Summit Automates
""",
    )
