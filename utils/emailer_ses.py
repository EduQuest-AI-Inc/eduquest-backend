import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def send_abuse_alert_email(teacher_email: str, student_name: str, sensitive_message: str):
    """
    Send an email to a teacher alerting them about a student mentioning abuse.
    
    Args:
        teacher_email: Email address of the teacher
        student_name: Full name of the student
        sensitive_message: The message that triggered the abuse detection
    """
    try:
        ses_client = boto3.client(
            'ses',
            region_name=os.getenv('AWS_REGION', 'us-east-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        sender_email = os.getenv('SES_SENDER_EMAIL', 'noreply@eduquestai.org')
        
        subject = f"EduQuest: Student Safety Alert - {student_name}"
        
        body_text = f"""
Dear Teacher,

This is an automated alert from EduQuest. Our system has detected that a student in your class has mentioned experiencing abuse.

Student Name: {student_name}
Sensitive Message: {sensitive_message}

Please follow your school's protocols for handling such reports. This may require immediate attention.

Best regards,
EduQuest Safety System
        """.strip()
        
        body_html = f"""
<html>
<head></head>
<body>
    <h2>Student Safety Alert</h2>
    <p>Dear Teacher,</p>
    <p>This is an automated alert from EduQuest. Our system has detected that a student in your class has mentioned experiencing abuse.</p>
    <p><strong>Student Name:</strong> {student_name}</p>
    <p><strong>Sensitive Message:</strong></p>
    <blockquote style="border-left: 3px solid #ccc; padding-left: 10px; margin-left: 10px;">
        {sensitive_message}
    </blockquote>
    <p>Please follow your school's protocols for handling such reports. This may require immediate attention.</p>
    <p>Best regards,<br>EduQuest Safety System</p>
</body>
</html>
        """.strip()
        
        response = ses_client.send_email(
            Source=sender_email,
            Destination={'ToAddresses': [teacher_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': body_text, 'Charset': 'UTF-8'},
                    'Html': {'Data': body_html, 'Charset': 'UTF-8'}
                }
            }
        )
        
        print(f"Abuse alert email sent to {teacher_email}. MessageId: {response['MessageId']}")
        return True
    except Exception as e:
        print(f"Error sending abuse alert email: {e}")
        # Don't raise - we don't want email failures to break the conversation flow
        return False