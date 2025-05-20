# auth/routes.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token

auth_bp = Blueprint('auth', __name__)

# Dummy user store — replace with real user database or service
users = {
    'admin': 'password123',
    'user1': 'securepass'
}

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password required'}), 400

    if username not in users:
        return jsonify({'message': 'No user found'}), 404

    if users[username] == password:
        access_token = create_access_token(identity=username)
        return jsonify({'token': access_token}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@auth_bp.route('/signup', methods=['POST'])
def signup ():
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Missing JSON body'}), 400
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password required.'}), 400
    if username in users:
        return jsonify({'message': 'User already exists'}), 409
    users[username] = password
    return jsonify({'message': 'Signup successful'}), 201