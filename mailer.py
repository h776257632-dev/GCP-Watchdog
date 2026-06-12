import smtplib
from email.mime.text import MIMEText
from email.header import Header
from config import settings

def send_mail(subject: str, body: str, to: str | None = None) -> None:
    host = settings.smtp_host
    port = settings.smtp_port
    sender = settings.qq_mail_user
    auth_code = settings.qq_mail_auth
    receiver = to or settings.qq_mail_to
    use_ssl = settings.smtp_ssl

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
