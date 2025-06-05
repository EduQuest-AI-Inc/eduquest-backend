from flask import Blueprint, jsonify, request
from .user_service import UserService

user_bp = Blueprint('user', __name__)
user_service = UserService()

@user_bp.route('/profile', methods=['GET'])
def get_profile():
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing or invalid"}), 401

    try:
        auth_token = auth_header.split(" ", 1)[1]
        user_data = user_service.get_user_profile(auth_token)
        return jsonify(user_data), 200

    except IndexError:
        return jsonify({"error": "Session data not found or malformed"}), 404

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


