import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from routes.parent.parent_service import ParentService
from routes.teacher.period_schedule_service import PeriodScheduleService

logger = logging.getLogger(__name__)

parent_bp = Blueprint("parent", __name__)
parent_service = ParentService()
period_schedule_service = PeriodScheduleService()


@parent_bp.route("/my-periods", methods=["GET"])
@jwt_required()
def my_periods():
    """Return all homeschool classes owned by the authenticated parent."""
    try:
        user_id = get_jwt_identity()
        periods = parent_service.get_periods_by_parent(user_id)
        return jsonify({"periods": periods}), 200
    except Exception as e:
        logger.error("Error fetching parent periods: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/generate-invite", methods=["POST"])
@jwt_required()
def generate_invite():
    """Generate a single-use 8-character invite code that expires in 24 hours."""
    try:
        user_id = get_jwt_identity()
        invite = parent_service.generate_invite(user_id)
        return jsonify(invite), 201
    except Exception as e:
        logger.error("Error generating invite: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/students", methods=["GET"])
@jwt_required()
def get_students():
    """Return student profiles for all students linked to this parent."""
    try:
        user_id = get_jwt_identity()
        students = parent_service.get_linked_students(user_id)
        return jsonify({"students": students}), 200
    except Exception as e:
        logger.error("Error fetching linked students: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# ─── Schedule endpoints ───────────────────────────────────────────────────────

@parent_bp.route("/period-schedule/generate", methods=["POST"])
@jwt_required()
def generate_period_schedule():
    """Generate (or regenerate) the AI schedule for a parent-owned period."""
    try:
        user_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.generate_and_save_schedule(
            period_id=period_id,
            user_id=user_id
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error generating parent schedule: %s", e, exc_info=True)
        return jsonify({"error": f"Failed to generate schedule: {e}"}), 500


@parent_bp.route("/period-schedule", methods=["GET"])
@jwt_required()
def get_period_schedule():
    """Return the schedule for a parent-owned period."""
    try:
        user_id = get_jwt_identity()
        period_id = request.args.get("period_id")
        if not period_id:
            return jsonify({"error": "period_id is required"}), 400

        result = period_schedule_service.get_schedule(
            period_id=period_id,
            user_id=user_id
        )
        if result is None:
            return jsonify({"error": "No schedule found for this period"}), 404
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error fetching parent schedule: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule", methods=["PUT"])
@jwt_required()
def update_period_schedule():
    """Save manual edits to the schedule for a parent-owned period."""
    try:
        user_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        schedule_dict = body.get("schedule")
        if not period_id or not schedule_dict:
            return jsonify({"error": "period_id and schedule are required"}), 400

        result = period_schedule_service.update_schedule(
            period_id=period_id,
            user_id=user_id,
            schedule_dict=schedule_dict
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error updating parent schedule: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@parent_bp.route("/period-schedule/quest-weeks", methods=["PUT"])
@jwt_required()
def set_quest_weeks():
    """Set which weeks have quests enabled for a parent-owned period."""
    try:
        user_id = get_jwt_identity()
        body = request.get_json(silent=True) or {}
        period_id = body.get("period_id")
        quest_enabled_weeks = body.get("quest_enabled_weeks")
        if not period_id or quest_enabled_weeks is None:
            return jsonify({"error": "period_id and quest_enabled_weeks are required"}), 400

        result = period_schedule_service.set_quest_weeks(
            period_id=period_id,
            user_id=user_id,
            quest_enabled_weeks=quest_enabled_weeks
        )
        return jsonify(result), 200

    except PermissionError as pe:
        return jsonify({"error": str(pe)}), 403
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 404
    except Exception as e:
        logger.error("Error setting quest weeks for parent: %s", e, exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
