from data_access.admin_dao import AdminDAO
from data_access.school_dao import SchoolDAO
from data_access.period_dao import PeriodDAO
from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from data_access.enrollment_dao import EnrollmentDAO
from data_access.guardrail_flag_dao import GuardrailFlagDAO
from data_access.individual_quest_dao import IndividualQuestDAO
from typing import Dict, List, Any

class AdminService:
    def __init__(self):
        self.admin_dao = AdminDAO()
        self.school_dao = SchoolDAO()
        self.period_dao = PeriodDAO()
        self.student_dao = StudentDAO()
        self.teacher_dao = TeacherDAO()
        self.enrollment_dao = EnrollmentDAO()
        self.guardrail_flag_dao = GuardrailFlagDAO()
        self.individual_quest_dao = IndividualQuestDAO()

    def get_all_classes(self, admin_id: str) -> List[Dict[str, Any]]:
        admin = self.admin_dao.get_admin_by_id(admin_id)
        if not admin:
            raise Exception("Administrator not found")

        school_id = admin.get("school_id")
        school_data = self.school_dao.get_school_by_id(school_id)

        if not school_data or len(school_data) == 0:
            return []

        school = school_data[0]
        period_ids = school.get("periods", [])

        classes = []
        for period_id in period_ids:
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                continue

            teacher_id = period.get("teacher_id")
            teacher = self.teacher_dao.get_teacher_by_id(teacher_id) if teacher_id else None

            enrollments = self.enrollment_dao.get_enrollments_by_period(period_id)

            students = []
            for enrollment in enrollments:
                student_id = enrollment.get("student_id")
                student = self.student_dao.get_student_by_id(student_id)
                if student:
                    students.append({
                        "student_id": student_id,
                        "first_name": student.get("first_name"),
                        "last_name": student.get("last_name"),
                        "email": student.get("email"),
                        "grade": student.get("grade")
                    })

            classes.append({
                "period_id": period_id,
                "course": period.get("course"),
                "teacher": {
                    "teacher_id": teacher_id,
                    "first_name": teacher.get("first_name") if teacher else None,
                    "last_name": teacher.get("last_name") if teacher else None,
                    "email": teacher.get("email") if teacher else None
                } if teacher else None,
                "students": students,
                "file_urls": period.get("file_urls", []),
                "student_count": len(students)
            })

        return classes

    def get_all_students(self, admin_id: str) -> List[Dict[str, Any]]:
        admin = self.admin_dao.get_admin_by_id(admin_id)
        if not admin:
            raise Exception("Administrator not found")

        school_id = admin.get("school_id")
        school_data = self.school_dao.get_school_by_id(school_id)

        if not school_data or len(school_data) == 0:
            return []

        school = school_data[0]
        student_ids = school.get("students", [])

        students = []
        for student_id in student_ids:
            student = self.student_dao.get_student_by_id(student_id)
            if not student:
                continue

            enrollments = student.get("enrollments", [])
            classes = []

            for period_id in enrollments:
                period = self.period_dao.get_period_by_id(period_id)
                if period:
                    classes.append({
                        "period_id": period_id,
                        "course": period.get("course")
                    })

            long_term_goals = student.get("long_term_goal", {})

            students.append({
                "student_id": student_id,
                "first_name": student.get("first_name"),
                "last_name": student.get("last_name"),
                "email": student.get("email"),
                "grade": student.get("grade"),
                "classes": classes,
                "long_term_goals": long_term_goals
            })

        return students

    def get_student_detail(self, admin_id: str, student_id: str) -> Dict[str, Any]:
        admin = self.admin_dao.get_admin_by_id(admin_id)
        if not admin:
            raise Exception("Administrator not found")

        student = self.student_dao.get_student_by_id(student_id)
        if not student:
            raise Exception("Student not found")

        school_id = admin.get("school_id")
        school_data = self.school_dao.get_school_by_id(school_id)

        if not school_data or len(school_data) == 0:
            raise Exception("School not found")

        school = school_data[0]
        if student_id not in school.get("students", []):
            raise Exception("Student does not belong to this school")

        enrollments = student.get("enrollments", [])
        classes = []

        for period_id in enrollments:
            period = self.period_dao.get_period_by_id(period_id)
            if not period:
                continue

            long_term_goal = student.get("long_term_goal", {}).get(period.get("course", period_id), None)

            quests = self.individual_quest_dao.get_quests_by_student_and_period(student_id, period_id)

            classes.append({
                "period_id": period_id,
                "course": period.get("course"),
                "long_term_goal": long_term_goal,
                "quests": quests
            })

        guardrail_flags = self.guardrail_flag_dao.get_flags_by_student(student_id)

        return {
            "student_id": student_id,
            "first_name": student.get("first_name"),
            "last_name": student.get("last_name"),
            "email": student.get("email"),
            "grade": student.get("grade"),
            "strength": student.get("strength"),
            "weakness": student.get("weakness"),
            "interest": student.get("interest"),
            "learning_style": student.get("learning_style"),
            "classes": classes,
            "guardrail_flags": guardrail_flags
        }

    def get_guardrail_flags(self, admin_id: str, resolved: bool = None) -> List[Dict[str, Any]]:
        admin = self.admin_dao.get_admin_by_id(admin_id)
        if not admin:
            raise Exception("Administrator not found")

        school_id = admin.get("school_id")
        school_data = self.school_dao.get_school_by_id(school_id)

        if not school_data or len(school_data) == 0:
            return []

        school = school_data[0]
        student_ids = school.get("students", [])

        all_flags = []
        for student_id in student_ids:
            flags = self.guardrail_flag_dao.get_flags_by_student(student_id)
            all_flags.extend(flags)

        if resolved is not None:
            all_flags = [flag for flag in all_flags if flag.get("resolved") == resolved]

        return all_flags

    def resolve_guardrail_flag(self, admin_id: str, flag_id: str, admin_notes: str = None) -> Dict[str, Any]:
        admin = self.admin_dao.get_admin_by_id(admin_id)
        if not admin:
            raise Exception("Administrator not found")

        flag = self.guardrail_flag_dao.get_flag_by_id(flag_id)
        if not flag:
            raise Exception("Guardrail flag not found")

        updates = {"resolved": True}
        if admin_notes:
            updates["admin_notes"] = admin_notes

        self.guardrail_flag_dao.update_flag(flag_id, updates)

        return {"message": "Guardrail flag resolved successfully"}
