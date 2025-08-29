from data_access.enrollment_dao import EnrollmentDAO
from data_access.student_dao import StudentDAO
from data_access.period_dao import PeriodDAO
from models.enrollment import Enrollment
from datetime import datetime

class EnrollmentService:
    def __init__(self):
        self.enrollment_dao = EnrollmentDAO()
        self.student_dao = StudentDAO()
        self.period_dao = PeriodDAO()

    def enroll_student(self, student_id: str, period_id: str, semester: str = "Fall 2025") -> dict:
        print("Starting enrollment process")
        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            raise Exception(f"Student {student_id} not found")

        period = self.period_dao.get_period_by_id(period_id)

        print(f"ENROLLMENT DEBUG — student_id={student_id}, period_id={period_id}")
        print(f"Period fetched: {period}")

        if not period:
            raise Exception(f"Period {period_id} not found")

        # Create enrollment record
        enrollment = Enrollment(
            student_id=student_id,
            period_id=period_id,
            semester=semester,
            enrolled_at=datetime.utcnow().isoformat()
        )

        self.enrollment_dao.add_enrollment(enrollment)

        return {"message": f"Student {student_id} enrolled in {period_id} successfully"}
    
    def get_enrollments_for_period(self, period_id: str):
        enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
        period = self.period_dao.get_period_by_id(period_id)
        
        print(f"DEBUG: Period ID: {period_id}")
        print(f"DEBUG: Period data: {period}")
        print(f"DEBUG: Period file_urls: {period.get('file_urls', []) if period else 'No period found'}")

        return {
            "students": enrollments,
            "file_urls": period.get("file_urls", []) if period else []
        }
    
    def get_enrollment_by_id(self, enrollment_id: str):
        return self.enrollment_dao.get_enrollment_by_id(enrollment_id)

    def delete_enrollment(self, student_id: str, period_id: str, enrolled_at: str):
        self.enrollment_dao.delete_enrollment(period_id, enrolled_at)
        return {"message": f"Enrollment for {student_id} deleted from {period_id}"}

    def get_student_profile(self, period_id: str, student_id: str):
        try:
            enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)
            if not enrollments:
                print(f"No enrollments found for period {period_id}")
                return None

            matched_enrollment = next((e for e in enrollments if e.get("student_id") == student_id), None)
            if not matched_enrollment:
                print(f"Student ID {student_id} not found in period {period_id}")
                return None

            student = self.student_dao.get_student_by_id(student_id)
            if not student:
                print(f"No student found with ID {student_id}")
                return None

            return {
                "interest": student.get("interest"),
                "strength": student.get("strength"),
                "weakness": student.get("weakness"),
                "learning_style": student.get("learning_style"),
            }

        except Exception as e:
            print("Error in get_student_profile:", str(e))
            return None