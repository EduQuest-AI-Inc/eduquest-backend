from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

from routes.conversation.routes import conversation_bp
from routes.auth.routes import auth_bp
from routes.user.routes import user_bp
from routes.period.routes import period_bp
from routes.teacher.routes import teacher_bp
from routes.enrollment.routes import enrollment_bp
from routes.quest.routes import quest_bp

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')  # Set secret securely
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600  # 1 hour (in seconds)

# Initialize JWT
jwt = JWTManager(app)

# Enable CORS for your frontend
CORS(app, resources={r"/*": {
    "origins": [
        # Production domains
        "https://eduquestai.org",
        "http://eduquestai.org", 
        "http://eduquestai.org.s3-website.us-east-2.amazonaws.com",
        "https://eduquestai.org.s3-website.us-east-2.amazonaws.com",
        
        # Development domains
        "http://localhost:3000",
        "http://localhost:5173", 
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174"
    ],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True
}})

# Register Blueprints
app.register_blueprint(conversation_bp, url_prefix='/conversation')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(period_bp, url_prefix='/period')
app.register_blueprint(teacher_bp, url_prefix = '/teacher')
app.register_blueprint(enrollment_bp, url_prefix = '/enrollment')
app.register_blueprint(quest_bp, url_prefix = '/quest')

# Add helloworld route for testing connection
@app.route('/helloworld', methods=['GET'])
def hello_world():
    return "helloworld"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
