from flask import Blueprint, request, jsonify
from routes.enrollment.enrollment_service import EnrollmentService

enrollment_bp = Blueprint('enrollment', __name__)
service = EnrollmentService()

@enrollment_bp.route('/enroll', methods=['POST'])
def enroll():
    try:
        data = request.json
        student_id = data.get("student_id")
        period_id = data.get("period_id")
        semester = data.get("semester", "Fall 2025")

        try:
            print("Calling enroll_student")
            result = service.enroll_student(student_id, period_id, semester)
            return jsonify(result), 200
        except Exception as e:
            print("enroll_student failed:", e)
            import traceback
            traceback.print_exc()

    except Exception as e:
        print("ENROLLMENT ERROR:", str(e))
    return jsonify({"error": "Server error"}), 500


@enrollment_bp.route('/enrollments/<period_id>', methods=['GET'])
def get_enrollments(period_id):
    try:
        enrollments = service.get_enrollments_for_period(period_id)
        return jsonify(enrollments), 200
    except Exception as e:
        print("GET ENROLLMENTS ERROR:", str(e))
        return jsonify({"error": "Failed to fetch enrollments"}), 500


@enrollment_bp.route('/student-profile/<period_id>/<student_id>', methods=['GET'])
def get_student_profile(period_id, student_id):
    try:
        print(f"Received request for period_id: {period_id}, student_id: {student_id}") 
        profile = service.get_student_profile(period_id, student_id)
        print(f"Profile data: {profile}") 
        if profile:
            return jsonify(profile), 200
        else:
            print("No profile found")  
            return jsonify({"error": "Profile not found"}), 404
    except Exception as e:
        print("GET STUDENT PROFILE ERROR:", str(e))
        import traceback
        traceback.print_exc()  
        return jsonify({"error": "Server error"}), 500