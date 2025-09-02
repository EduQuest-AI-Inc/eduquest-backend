# auth_service.py
# Handles user registration and authentication logic
from werkzeug.security import generate_password_hash, check_password_hash
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from models.student import Student
from models.teacher import Teacher
import os
import boto3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
import random
import string

student_dao = StudentDAO()
teacher_dao = TeacherDAO()


def _generate_verification_code() -> str:
    # 4-digit numeric code
    return ''.join(random.choices(string.digits, k=4))


def _send_verification_email(recipient_email: str, code: str) -> None:
    """Send a verification email using configured provider (SMTP or SES)."""
    subject = 'Your EduQuest verification code'
    body_text = f"Your verification code is: {code}. It expires in 10 minutes."
    body_html = f"""
        <html>
            <body>
                <p>Your verification code is:</p>
                <h2 style='letter-spacing:6px'>{code}</h2>
                <p>This code expires in 10 minutes.</p>
            </body>
        </html>
    """

    provider = (os.getenv('EMAIL_PROVIDER') or '').lower().strip()
    if provider == 'smtp':
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        sender = smtp_user
        if not smtp_user or not smtp_pass:
            print(f"[email] SMTP not configured (missing SMTP_USER/SMTP_PASS); skipping send to {recipient_email}")
            return
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient_email
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender, [recipient_email], msg.as_string())
            print(f"[email] SMTP verification email sent to {recipient_email}")
        except Exception as e:
            print(f"[email] SMTP send failed: {e}")
        return

    # Default to SES
    sender = os.getenv('SES_SENDER_EMAIL') or os.getenv('SENDER_EMAIL')
    if not sender:
        print(f"[email] No sender configured (SES/SENDER_EMAIL not set); skipping email to {recipient_email} with code {code}")
        return
    region = os.getenv('AWS_REGION', 'us-east-2')
    try:
        ses = boto3.client('ses', region_name=region)
        ses.send_email(
            Source=sender,
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': body_text, 'Charset': 'UTF-8'},
                    'Html': {'Data': body_html, 'Charset': 'UTF-8'}
                }
            }
        )
        print(f"[email] SES verification email sent to {recipient_email}")
    except Exception as e:
        print(f"[email] SES send failed: {e}")

def register_user(username: str, password: str, role: str, first_name: str = '', last_name: str = '', email: str = '', grade: str = None) -> bool:
    code = _generate_verification_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    if role == 'teacher':
        existing = teacher_dao.get_teacher_by_id(username)
        if existing:
            return False
        hashed_pw = generate_password_hash(password)
        teacher = Teacher(
            teacher_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            email_verified=False,
            email_verification_code=code,
            email_verification_expires_at=expires_at,
        )
        teacher_dao.add_teacher(teacher)
        _send_verification_email(email, code)
        return True
    else:
        existing = student_dao.get_student_by_id(username)
        if existing:
            return False
        hashed_pw = generate_password_hash(password)
        student = Student(
            student_id=username,
            password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            email=email,
            grade=grade,
            email_verified=False,
            email_verification_code=code,
            email_verification_expires_at=expires_at,
        )
        student_dao.add_student(student)
        _send_verification_email(email, code)
        return True

def authenticate_user(username: str, password: str, role: str) -> bool:
    if role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        return check_password_hash(user['password'], password)


def verify_email_code(username: str, role: str, code: str) -> bool:
    now = datetime.now(timezone.utc)
    if role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        stored_code = user.get('email_verification_code')
        expires_at = user.get('email_verification_expires_at')
        if not stored_code or not expires_at:
            return False
        try:
            exp = datetime.fromisoformat(expires_at)
        except Exception:
            return False
        if stored_code == code and exp >= now:
            teacher_dao.update_teacher(username, {
                'email_verified': True,
                'email_verification_code': None,
                'email_verification_expires_at': None,
            })
            return True
        return False
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        stored_code = user.get('email_verification_code')
        expires_at = user.get('email_verification_expires_at')
        if not stored_code or not expires_at:
            return False
        try:
            exp = datetime.fromisoformat(expires_at)
        except Exception:
            return False
        if stored_code == code and exp >= now:
            student_dao.update_student(username, {
                'email_verified': True,
                'email_verification_code': None,
                'email_verification_expires_at': None,
            })
            return True
        return False


def resend_verification_code(username: str, role: str) -> bool:
    code = _generate_verification_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    if role == 'teacher':
        user = teacher_dao.get_teacher_by_id(username)
        if not user:
            return False
        teacher_dao.update_teacher(username, {
            'email_verification_code': code,
            'email_verification_expires_at': expires_at,
        })
        _send_verification_email(user.get('email'), code)
        return True
    else:
        user = student_dao.get_student_by_id(username)
        if not user:
            return False
        student_dao.update_student(username, {
            'email_verification_code': code,
            'email_verification_expires_at': expires_at,
        })
        _send_verification_email(user.get('email'), code)
        return True