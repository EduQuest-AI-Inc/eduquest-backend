from dotenv import load_dotenv
from exceptions.validation_error import ValidationError
from flask.wrappers import Response
from typing import Tuple

# Load environment variables BEFORE any other imports so feature flags
# (e.g. USE_SUPABASE) are available at module import time.
load_dotenv()

from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os

from routes.conversation.routes import conversation_bp
from routes.auth.routes import auth_bp
from routes.user.routes import user_bp
from routes.period.routes import period_bp
from routes.teacher.routes import teacher_bp
from routes.enrollment.routes import enrollment_bp
from routes.quest.routes import quest_bp
from routes.waitlist.routes import waitlist_bp
from routes.parent_waitlist import parent_waitlist_bp
from routes.parent.routes import parent_bp
from datetime import timedelta
from flask import jsonify
from exceptions.validation_error import ValidationError
from exceptions.not_found_error import NotFoundError
from exceptions.auth_error import AuthError
from constants.timeouts import JWT_EXPIRY_HOURS

# Initialize Flask app
app = Flask(__name__)

# Config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')  # Set secret securely
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=JWT_EXPIRY_HOURS)

# Initialize JWT
jwt = JWTManager(app)

allowed_origins = [
    "https://eduquestai.org",
    "https://www.eduquestai.org",
    "http://eduquestai.org",
    "http://eduquestai.org.s3-website.us-east-2.amazonaws.com",
    "https://eduquestai.org.s3-website.us-east-2.amazonaws.com",
    "http://localhost:5000",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174"
]

api_gateway_url = os.getenv('API_GATEWAY_URL')
if api_gateway_url:
    allowed_origins.append(api_gateway_url)

CORS(
    app,
    resources={r"/*": {"origins": allowed_origins}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)

# Register Blueprints
app.register_blueprint(conversation_bp, url_prefix='/conversation')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(period_bp, url_prefix='/period')
app.register_blueprint(teacher_bp, url_prefix = '/teacher')
app.register_blueprint(enrollment_bp, url_prefix = '/enrollment')
app.register_blueprint(quest_bp, url_prefix = '/quest')
app.register_blueprint(waitlist_bp, url_prefix='/pilot-waitlist')
app.register_blueprint(parent_waitlist_bp, url_prefix='/parent-waitlist')
app.register_blueprint(parent_bp, url_prefix='/parent')

@app.errorhandler(ValidationError)
def handle_validation_error(e: ValidationError) -> Tuple[Response, int]:
    return jsonify({"error": str(e)}), 400

@app.errorhandler(NotFoundError)
def handle_not_found_error(e):
    return jsonify({"error": str(e)}), 404

@app.errorhandler(AuthError)
def handle_auth_error(e):
    return jsonify({"error": str(e)}), 401

@app.route('/helloworld', methods=['GET'])
def hello_world() -> str:
    return "helloworld"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
