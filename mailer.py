import smtplib
from email.mime.text import MIMEText
from email.header import Header
from config import settings

def send_mail(
    subject: str, 
    body: str, 
    to: str | None = None,
    host: str | None = None,
    port: int | None = None,
    sender: str | None = None,
    auth_code: str | None = None,
    use_ssl: bool | None = None
) -> None:
    host = host if host is not None else settings.smtp_host
    port = port if port is not None else settings.smtp_port
    sender = sender if sender is not None else settings.qq_mail_user
    auth_code = auth_code if auth_code is not None else settings.qq_mail_auth
    receiver = to or settings.qq_mail_to
    use_ssl = use_ssl if use_ssl is not None else settings.smtp_ssl

    if not host or not sender or not auth_code or not receiver:
        raise RuntimeError("Mail config missing in DB / ENV (host, sender, auth_code, receiver)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = receiver

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            server.login(sender, auth_code)
            server.sendmail(sender, [receiver], msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                pass
            server.login(sender, auth_code)
            server.sendmail(sender, [receiver], msg.as_string())
