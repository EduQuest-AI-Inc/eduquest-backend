"""Parent waitlist routes.

Public (no JWT) signup for homeschool parents. No child data is
accepted — see parent_waitlist_service.py for validation rules.
"""

import sys
import traceback

from flask import Blueprint, jsonify, request

from .parent_waitlist_service import (
    ParentWaitlistService,
    ParentWaitlistValidationError,
)

parent_waitlist_bp = Blueprint("parent_waitlist", __name__)
_svc = ParentWaitlistService()


@parent_waitlist_bp.route("/join", methods=["POST"])
def join_parent_waitlist():
    """
    Join the parent (homeschool) waitlist.

    Public endpoint — no authentication required.

    Request JSON:
        first_name (str, required)
        last_name (str, required)
        email (str, required)
        num_children (int, required, 0-20)
        learning_challenge (str, optional)
        open_to_interview (bool, optional, default false)
        contact_method (str, optional; only stored when open_to_interview=true)

    Returns:
        200 { "status": "ok" | "already_signed_up" }
        400 { "message": "Invalid submission." }
        503 { "message": "Parent waitlist is not available." }
    """
    if not _svc.enabled:
        return jsonify({"message": "Parent waitlist is not available."}), 503

    payload = request.get_json(silent=True) or {}
    try:
        result = _svc.join(payload)
        return jsonify(result), 200
    except ParentWaitlistValidationError:
        # Intentionally generic to reduce scraping signal.
        return jsonify({"message": "Invalid submission."}), 400
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"message": "Failed to join waitlist."}), 500
