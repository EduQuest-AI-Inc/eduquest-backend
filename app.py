from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os
import sys

from routes.conversation.routes import conversation_bp
from routes.auth.routes import auth_bp
from routes.user.routes import user_bp
from routes.period.routes import period_bp
from routes.teacher.routes import teacher_bp
from routes.enrollment.routes import enrollment_bp
from routes.quest.routes import quest_bp
from datetime import timedelta

# Load environment variables from .env file
load_dotenv()

def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = {
        # I commented out JWT_SECRET_KEY, not sure if any devs are still using a fallback secret
        # 'JWT_SECRET_KEY': 'JWT secret key for token signing',
        'OPENAI_API_KEY': 'OpenAI API key for AI functionality',
        'AWS_ACCESS_KEY_ID': 'AWS access key for DynamoDB and S3',
        'AWS_SECRET_ACCESS_KEY': 'AWS secret key for DynamoDB and S3',
        'AWS_REGION': 'AWS region (defaults to us-east-2 if not set)',
        # test_aws_setup.py lists bucket name as optional
        # 'S3_BUCKET_NAME': 'S3 bucket name for file storage'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("ERROR: Missing required environment variables:")
        print("\n".join(missing_vars))
        print("\nPlease set these variables in your .env file or environment.")
        print("See .env.example for reference.")
        sys.exit(1)

    # Additional validation for JWT_SECRET_KEY strength
    jwt_secret = os.getenv('JWT_SECRET_KEY', 'fallback-secret')
    if len(jwt_secret) < 32:
        print("WARNING: JWT_SECRET_KEY should be at least 32 characters long for security.")
    
    print("✓ All required environment variables are set")

# Validate environment variables before initializing the app
validate_environment()

# Initialize Flask app
app = Flask(__name__)

# Config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')  # Set secret securely
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

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
        "http://localhost:5000",
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

# Add helloworld route for testing
@app.route('/helloworld', methods=['GET'])
def hello_world():
    return "helloworld"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
