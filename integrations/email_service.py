"""
Email service for EduQuest using AWS SES.
Handles sending password reset emails and other transactional emails.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service using AWS SES.
    """
    
    def __init__(self) -> None:
        self.ses_client = boto3.client(
            'ses',
            region_name=os.getenv('AWS_REGION', 'us-east-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )
        self.from_email = os.getenv('SES_FROM_EMAIL', 'noreply@eduquestai.org')
        self.frontend_base_url = os.getenv('FRONTEND_BASE_URL', 'https://eduquestai.org')
    
    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: Optional[str] = None,
    ) -> dict:
        """Generic transactional email sender.

        Used by features outside auth (e.g. trial-reminder emails). Returns
        the same shape as send_password_reset_email so callers can branch
        on `success`. Recipient PII is never logged — only the email domain
        plus the SES MessageId, per the data minimization rule.
        """
        body: dict = {"Text": {"Data": text_body, "Charset": "UTF-8"}}
        if html_body:
            body["Html"] = {"Data": html_body, "Charset": "UTF-8"}
        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": body,
                },
            )
            message_id = response.get("MessageId", "")
            domain = to_email.rsplit("@", 1)[-1] if "@" in to_email else "?"
            logger.info(
                "ses.send ok message_id=%s recipient_domain=%s subject=%s",
                message_id, domain, subject,
            )
            return {"success": True, "message_id": message_id}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error("ses.send failed: %s - %s", error_code, error_message)
            return {"success": False, "error": f"{error_code}: {error_message}"}
        except Exception as e:
            logger.error("ses.send unexpected error: %s", e)
            return {"success": False, "error": str(e)}

    def send_trial_reminder_email(
        self,
        *,
        to_email: str,
        first_name: Optional[str],
        days_left: int,
    ) -> dict:
        """7-day trial-end reminder for parent/teacher accounts.

        Owner-facing only — never sent to students. Body contains no student
        PII; just the owner's first name (already on the email envelope).
        """
        name = (first_name or "there").strip()
        days = max(int(days_left), 1)
        billing_url = f"{self.frontend_base_url}/billing"
        subject = f"Your EduQuest trial ends in {days} day{'s' if days != 1 else ''}"

        text_body = (
            f"Hi {name},\n\n"
            f"Your 14-day EduQuest trial ends in {days} day"
            f"{'s' if days != 1 else ''}. To keep creating and managing classes, "
            "choose a plan and subscribe before your trial ends.\n\n"
            f"Pick a plan: {billing_url}\n\n"
            "If you don't subscribe, your students can still keep working on the "
            "classes they're already in, but you won't be able to create new "
            "classes or manage existing ones.\n\n"
            "Thanks,\nThe EduQuest Team"
        )

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background-color:#FAF3DD;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="min-height:100vh;">
        <tr><td align="center" style="padding:40px 20px;">
            <table role="presentation" width="100%" style="max-width:520px;background-color:#ffffff;border-radius:20px;box-shadow:0 2px 10px rgba(0,0,0,0.05);">
                <tr><td style="padding:40px 30px;">
                    <h1 style="margin:0 0 10px 0;font-size:28px;color:#9A031E;font-weight:600;text-align:center;">EduQuest</h1>
                    <p style="margin:0 0 20px 0;font-size:16px;color:#333;">Hi {name},</p>
                    <p style="margin:0 0 20px 0;font-size:16px;color:#333;">
                        Your 14-day EduQuest trial ends in
                        <strong>{days} day{'s' if days != 1 else ''}</strong>.
                        To keep creating and managing classes, choose a plan
                        and subscribe before your trial ends.
                    </p>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr><td align="center" style="padding:20px 0;">
                            <a href="{billing_url}" style="display:inline-block;background-color:#9A031E;color:#ffffff;text-decoration:none;font-weight:600;font-size:16px;padding:14px 36px;border-radius:9999px;">Pick a plan</a>
                        </td></tr>
                    </table>
                    <p style="margin:0;font-size:14px;color:#666;">
                        If you don't subscribe, your students can keep working on
                        classes they're already in, but you won't be able to
                        create new classes or manage existing ones.
                    </p>
                </td></tr>
                <tr><td style="padding:20px 30px;background-color:#f9f9f9;border-radius:0 0 20px 20px;text-align:center;">
                    <p style="margin:0;font-size:12px;color:#999;">&copy; {datetime.now().year} EduQuest. All rights reserved.</p>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>
"""

        return self.send_email(
            to_email=to_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        user_first_name: Optional[str] = None
    ) -> dict:
        """
        Send a password reset email.
        
        Args:
            to_email: Recipient email address
            reset_token: The raw (unhashed) reset token
            user_first_name: User's first name for personalization
        
        Returns:
            dict with 'success', 'message_id' (if sent), and 'error' (if failed)
        """
        reset_link = f"{self.frontend_base_url}/reset-password?token={reset_token}"
        request_time = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        expiry_minutes = 45
        
        # Personalize greeting
        greeting = f"Hi {user_first_name}," if user_first_name else "Hi,"
        
        # Plain text version
        text_body = f"""{greeting}

We received a request to reset your EduQuest password.

Click the link below to set a new password:
{reset_link}

This link will expire in {expiry_minutes} minutes.

Request time: {request_time}

If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.

Need help? Contact us at support@eduquestai.org

— The EduQuest Team
"""

        # HTML version
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your EduQuest Password</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #FAF3DD;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="min-height: 100vh;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                    <tr>
                        <td style="padding: 40px 30px; text-align: center;">
                            <!-- Logo / Brand -->
                            <h1 style="margin: 0 0 10px 0; font-size: 28px; color: #9A031E; font-weight: 600;">EduQuest</h1>
                            <p style="margin: 0 0 30px 0; font-size: 14px; color: #666;">Your personalized learning journey</p>
                            
                            <!-- Content -->
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: #333; text-align: left;">
                                {greeting}
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: #333; text-align: left;">
                                We received a request to reset your EduQuest password.
                            </p>
                            
                            <!-- CTA Button -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                                <tr>
                                    <td align="center" style="padding: 20px 0;">
                                        <a href="{reset_link}" 
                                           style="display: inline-block; background-color: #9A031E; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; padding: 14px 40px; border-radius: 9999px;">
                                            Reset Password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Expiry notice -->
                            <p style="margin: 0 0 20px 0; font-size: 14px; color: #666; text-align: center;">
                                This link expires in <strong>{expiry_minutes} minutes</strong>
                            </p>
                            
                            <!-- Request time -->
                            <p style="margin: 0 0 20px 0; font-size: 13px; color: #999; text-align: center;">
                                Requested: {request_time}
                            </p>
                            
                            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                            
                            <!-- Security notice -->
                            <p style="margin: 0 0 10px 0; font-size: 13px; color: #666; text-align: left;">
                                <strong>Didn't request this?</strong>
                            </p>
                            <p style="margin: 0; font-size: 13px; color: #666; text-align: left;">
                                If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: #f9f9f9; border-radius: 0 0 20px 20px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #999;">
                                &copy; {datetime.now().year} EduQuest. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={
                    'ToAddresses': [to_email]
                },
                Message={
                    'Subject': {
                        'Data': 'Reset Your EduQuest Password',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': text_body,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': html_body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            
            message_id = response.get('MessageId', '')
            logger.info(f"Password reset email sent to {to_email}, MessageId: {message_id}")
            
            return {
                'success': True,
                'message_id': message_id
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Failed to send password reset email to {to_email}: {error_code} - {error_message}")
            
            return {
                'success': False,
                'error': f"{error_code}: {error_message}"
            }
        except Exception as e:
            logger.error(f"Unexpected error sending password reset email to {to_email}: {e}")
            return {
                'success': False,
                'error': str(e)
            }


    def send_parent_waitlist_confirmation(
        self,
        to_email: str,
        first_name: Optional[str] = None,
    ) -> dict:
        """Send a confirmation email after a parent joins the home waitlist.

        Mirrors the return shape of send_password_reset_email so callers
        can handle success/failure the same way.
        """
        greeting = f"Hi {first_name}," if first_name else "Hi there,"
        privacy_url = f"{self.frontend_base_url}/privacy"

        text_body = f"""{greeting}

Thanks for joining the EduQuest home waitlist! We're building EduQuest for homeschool families, and your signup helps us shape what we build next.

If you opted in to a 20-minute interview, someone from our team may reach out to schedule a chat — we'd love to hear about what you're working on with your kids.

Privacy Policy: {privacy_url}

Talk soon,
— The EduQuest Team
"""

        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to the EduQuest home waitlist</title>
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #FAF3DD;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="min-height: 100vh;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h1 style="margin: 0 0 10px 0; font-size: 28px; color: #9A031E; font-weight: 600; text-align: center;">EduQuest</h1>
                            <p style="margin: 0 0 30px 0; font-size: 14px; color: #666; text-align: center;">Personalized learning for home</p>

                            <p style="margin: 0 0 20px 0; font-size: 16px; color: #333;">
                                {greeting}
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: #333;">
                                Thanks for joining the EduQuest home waitlist. We're building EduQuest for homeschool families, and your signup helps us shape what we build next.
                            </p>
                            <p style="margin: 0 0 20px 0; font-size: 16px; color: #333;">
                                If you opted in to a 20-minute interview, someone from our team may reach out to schedule a chat — we'd love to hear what you're working on with your kids.
                            </p>

                            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">

                            <p style="margin: 0; font-size: 13px; color: #666; text-align: center;">
                                <a href="{privacy_url}" style="color: #0047AB; text-decoration: none;">Privacy Policy</a>
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 20px 30px; background-color: #f9f9f9; border-radius: 0 0 20px 20px; text-align: center;">
                            <p style="margin: 0; font-size: 12px; color: #999;">
                                &copy; {datetime.now().year} EduQuest. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

        try:
            response = self.ses_client.send_email(
                Source=self.from_email,
                Destination={'ToAddresses': [to_email]},
                Message={
                    'Subject': {
                        'Data': 'Welcome to the EduQuest home waitlist',
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {'Data': text_body, 'Charset': 'UTF-8'},
                        'Html': {'Data': html_body, 'Charset': 'UTF-8'},
                    }
                }
            )
            message_id = response.get('MessageId', '')
            logger.info(f"Parent waitlist confirmation sent to {to_email}, MessageId: {message_id}")
            return {'success': True, 'message_id': message_id}
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Failed to send parent waitlist confirmation to {to_email}: {error_code} - {error_message}")
            return {'success': False, 'error': f"{error_code}: {error_message}"}
        except Exception as e:
            logger.error(f"Unexpected error sending parent waitlist confirmation to {to_email}: {e}")
            return {'success': False, 'error': str(e)}


# Singleton instance
_email_service = None


def get_email_service() -> EmailService:
    """Get the singleton email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service

