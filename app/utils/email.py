from email.mime.text import MIMEText
from email.header import Header
import smtplib

from app.core.config import settings


def send_email(to_email: str, subject: str, body: str):
    sender_email = settings.MAIL_FROM
    sender_password = settings.MAIL_PASSWORD  # 授权码

    message = MIMEText(body, 'html', 'utf-8')
    message['From'] = Header(f"Your Blog Service <{sender_email}>", 'utf-8')
    message['To'] = Header(to_email, 'utf-8')
    message['Subject'] = Header(subject, 'utf-8')

    try:
        if settings.MAIL_SSL:
            server = smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT)
        else:
            server = smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT)
            if settings.MAIL_TLS:
                server.starttls()

        if settings.USE_CREDENTIALS:
            server.login(settings.MAIL_USERNAME, sender_password)

        server.sendmail(sender_email, to_email, message.as_string())
        server.quit()
        print(f"Email sent to {to_email} successfully.")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # 在生产环境中，你可能需要更完善的错误处理和日志记录


async def send_verification_email(to_email: str, code: str):
    subject = "Your Email Verification Code"
    body = f"""
    <html>
    <body>
        <p>Hello,</p>
        <p>Your verification code is: <strong>{code}</strong></p>
        <p>This code is valid for {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.</p>
        <p>Thank you!</p>
    </body>
    </html>
    """
    send_email(to_email, subject, body)


async def send_password_reset_email(to_email: str, reset_token: str):
    reset_link = f"http://localhost:8000/reset-password?token={reset_token}"  # 假设前端会处理这个链接
    reset_link = f"{settings.APP_BASE_URL.rstrip('/')}/reset-password?token={reset_token}"
    subject = "Password Reset Request"
    body = f"""
    <html>
    <body>
        <p>Hello,</p>
        <p>You have requested to reset your password. Please click the link below to reset your password:</p>
        <p><a href="{reset_link}">Reset My Password</a></p>
        <p>This link is valid for {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes.</p>
        <p>If you did not request a password reset, please ignore this email.</p>
        <p>Thank you!</p>
    </body>
    </html>
    """
    send_email(to_email, subject, body)
