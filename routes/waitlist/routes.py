# routes/waitlist/routes.py
from flask import Blueprint, jsonify, request
from .WaitlistService import WaitlistService  
import traceback, sys

waitlist_bp = Blueprint('waitlist', __name__)
svc = WaitlistService()

@waitlist_bp.route('/join', methods=['POST'])
def join_waitlist():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get('email', '')
        name  = data.get('name', '')
        result = svc.join(email, name)  
        resp = jsonify(result)
        origin = request.headers.get('Origin')
        if origin:
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Vary'] = 'Origin'
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
        return resp, 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"message": "Failed to join waitlist"}), 500
