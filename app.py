from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os

# from routes.conversation.routes import conversation_bp
from routes.auth.routes import auth_bp
from routes.user.routes import user_bp

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Config
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')  # Set secret securely

# Initialize JWT
jwt = JWTManager(app)

# Enable CORS for your frontend (add localhost for dev if needed)
CORS(app, resources={r"/*": 
                {"origins": [
                    "http://eduquest-frontend.s3-website.us-east-2.amazonaws.com",
                    "http://localhost:5173"
                    ]
                }
            }
    )

# Register Blueprints
# app.register_blueprint(conversation_bp)
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')

# Add helloworld route for testing
@app.route('/helloworld', methods=['GET'])
def hello_world():
    return "helloworld"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
