from data_access.student_dao import StudentDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.period_dao import PeriodDAO
from data_access.teacher_dao import TeacherDAO
from typing import Optional, List
import traceback

class AbuseReportService:
    def __init__(self):
        self.student_dao = StudentDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.period_dao = PeriodDAO()
        self.teacher_dao = TeacherDAO()

    def handle_abuse_detection(self, student_id: str, sensitive_message: str, period_id: Optional[str] = None):
        """
        Handle automatic abuse detection by notifying the student's teacher.
        
        Args:
            student_id: ID of the student who mentioned abuse
            sensitive_message: The message that triggered the detection
            period_id: Optional period_id if available from conversation context
        """
        try:
            # Get student information
            student = self.student_dao.get_student_by_id(student_id)
            if not student:
                print(f"Warning: Student {student_id} not found for abuse report")
                return False
            
            student_name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
            if not student_name:
                student_name = student_id  # Fallback to ID if name not available
            
            # Get teacher information
            teacher_emails = self._get_teacher_emails_for_student(student_id, period_id)
            
            if not teacher_emails:
                print(f"Warning: No teacher found for student {student_id}")
                return False
            
            # Send email to all teachers
            success_count = 0
            for teacher_email in teacher_emails:
                try:
                    from utils.emailer_ses import send_abuse_alert_email
                    if send_abuse_alert_email(teacher_email, student_name, sensitive_message):
                        success_count += 1
                except Exception as e:
                    print(f"Error sending email to {teacher_email}: {e}")
                    traceback.print_exc()
            
            print(f"Abuse alert sent to {success_count}/{len(teacher_emails)} teachers for student {student_id}")
            return success_count > 0
            
        except Exception as e:
            print(f"Error in handle_abuse_detection: {e}")
            traceback.print_exc()
            return False

    def _get_teacher_emails_for_student(self, student_id: str, period_id: Optional[str] = None) -> List[str]:
        """
        Get email addresses of all teachers for a student.
        
        Args:
            student_id: ID of the student
            period_id: Optional specific period_id to check
            
        Returns:
            List of teacher email addresses
        """
        teacher_emails = set()
        
        try:
            # If period_id is provided, use it directly
            if period_id:
                period = self.period_dao.get_period_by_id(period_id)
                if period:
                    teacher_id = period.get('teacher_id')
                    if teacher_id:
                        teacher = self.teacher_dao.get_teacher_by_id(teacher_id)
                        if teacher and teacher.get('email'):
                            teacher_emails.add(teacher['email'])
            
            # Also check all enrollments for the student
            student = self.student_dao.get_student_by_id(student_id)
            if student:
                enrollments = student.get('enrollments', [])
                if isinstance(enrollments, list):
                    for enrolled_period_id in enrollments:
                        try:
                            period = self.period_dao.get_period_by_id(enrolled_period_id)
                            if period:
                                teacher_id = period.get('teacher_id')
                                if teacher_id:
                                    teacher = self.teacher_dao.get_teacher_by_id(teacher_id)
                                    if teacher and teacher.get('email'):
                                        teacher_emails.add(teacher['email'])
                        except Exception as e:
                            print(f"Error getting teacher for period {enrolled_period_id}: {e}")
                            continue
                
                # Also check enrollment table for additional enrollments
                try:
                    from data_access.enrollment_dao import EnrollmentDAO
                    enrollment_dao = EnrollmentDAO()
                    # Get enrollments by scanning (we'd need a student_id index for efficiency)
                    # For now, we'll rely on the student's enrollments list
                except Exception as e:
                    print(f"Error checking enrollment table: {e}")
            
        except Exception as e:
            print(f"Error in _get_teacher_emails_for_student: {e}")
            traceback.print_exc()
        
        return list(teacher_emails)