"""Plain, dependency-free email body templates. Kept as simple string
functions rather than a templating engine - two templates today, and the
future ones (team_invitation, welcome, billing_notification, security_alert,
workspace_invitation - see app.email.contracts.EmailType) can each be added
the same way without introducing a new rendering dependency."""


def render_password_reset_email(*, reset_url: str, expires_minutes: int) -> tuple[str, str, str]:
    subject = "Reset your Conversa password"
    text_body = (
        "We received a request to reset your Conversa password.\n\n"
        f"Reset it here (expires in {expires_minutes} minutes):\n{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    html_body = (
        "<p>We received a request to reset your Conversa password.</p>"
        f'<p><a href="{reset_url}">Reset your password</a> (expires in {expires_minutes} minutes).</p>'
        "<p>If you didn't request this, you can safely ignore this email.</p>"
    )
    return subject, html_body, text_body


def render_verification_email(*, verify_url: str, expires_minutes: int) -> tuple[str, str, str]:
    subject = "Verify your Conversa email address"
    text_body = (
        "Please verify your email address to finish setting up your Conversa account.\n\n"
        f"Verify it here (expires in {expires_minutes} minutes):\n{verify_url}\n\n"
        "If you didn't create this account, you can safely ignore this email."
    )
    html_body = (
        "<p>Please verify your email address to finish setting up your Conversa account.</p>"
        f'<p><a href="{verify_url}">Verify your email</a> (expires in {expires_minutes} minutes).</p>'
        "<p>If you didn't create this account, you can safely ignore this email.</p>"
    )
    return subject, html_body, text_body
