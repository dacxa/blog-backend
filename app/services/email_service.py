import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import HTTPException

from app.core.config import settings


def generate_code() -> str:
    """Generate a zero-padded six-digit verification code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def send_verification_code(email: str, code: str) -> None:
    # 1. 初始化带有多媒体(HTML)支持的邮件对象
    msg = MIMEMultipart()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = email
    msg["Subject"] = "【卡塞尔学院】执行部档案录入密钥"

    # 获取过期时间（容错处理，如果没有配置则默认5分钟）
    expire_minutes = getattr(settings, 'VERIFICATION_CODE_EXPIRE_MINUTES', 5)

    # 2. 炫酷的 HTML 邮件正文
    html_content = f"""
    <div style="font-family: 'Helvetica Neue', Arial, sans-serif; padding: 30px; background-color: #050505; color: #fff;">
        <div style="border: 1px solid #8b0000; padding: 25px; background: rgba(20, 0, 0, 0.8);">
            <h2 style="color: #ff4d4d; letter-spacing: 2px; border-bottom: 1px solid #330000; padding-bottom: 10px;">卡塞尔学院 - Norma(诺玛) 系统下发</h2>
            <p style="color: #ccc; margin-top: 15px;">您好，</p>
            <p style="color: #ccc;">您正在请求录入执行部档案，您本次通讯请求的血统验证密钥为：</p>

            <div style="margin: 25px 0; padding: 15px; background: #220000; border-left: 4px solid #ff4d4d; font-size: 32px; font-weight: bold; letter-spacing: 15px; color: #ffcccc; text-align: center;">
                {code}
            </div>

            <p style="color: #888; font-size: 12px; margin-top: 30px;">
                【警告】有效时间为 {expire_minutes} 分钟。任何人索取此代码均视为试图窃取机密！<br>
                如果这不是您本人的操作，请立即销毁本邮件（或忽略）。
            </p>
        </div>
    </div>
    """

    # 附加 HTML 格式的正文
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # 3. 发送邮件并进行端口自适应 & 异常处理
    try:
        # 如果是 465 端口，必须一开始就走 SSL
        if settings.MAIL_PORT == 465:
            with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT) as smtp:
                smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                smtp.sendmail(settings.MAIL_FROM, [email], msg.as_string())

        # 其他端口（如 587）走普通端口，然后按需开启 starttls
        else:
            with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as smtp:
                if getattr(settings, "MAIL_TLS", False):
                    smtp.starttls()
                smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                smtp.sendmail(settings.MAIL_FROM, [email], msg.as_string())

        print(f"✉️ 邮件已成功发送给: {email}")

    except Exception as e:
        print(f"❌ 邮件发送失败，原因: {e}")
        # 如果连不上别人的收件箱或填错了密码，必须把错误抛给前端，不要假装发送成功
        raise HTTPException(
            status_code=500,
            detail="诺玛网络中断，未能向该终端下发邮件，请检查后端邮箱配置。"
        )
