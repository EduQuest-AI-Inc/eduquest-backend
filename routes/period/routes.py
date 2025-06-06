from flask import Blueprint, request, jsonify
from .period_service import PeriodService

period_bp = Blueprint('period', __name__)
period_service = PeriodService()

@period_bp.route('/verify', methods=['POST'])
def verify_period():
    try:
        data = request.get_json()
        period_id = data.get('period_id')

        result = period_service.verify_period_id(period_id)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400

    except LookupError as le:
        return jsonify({"error": str(le)}), 404

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500