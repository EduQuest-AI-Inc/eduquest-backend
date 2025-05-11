from flask import Flask
from flask_cors import CORS
from routes.conversation import conversation_bp

# Initialize Flask app
app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "http://eduquest-frontend.s3-website.us-east-2.amazonaws.com"}})

# Register Blueprints
app.register_blueprint(conversation_bp)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)


# Test For Auto Deployment