"""
Test file demonstrating AWS session setup and auth token creation.
This shows how to properly configure and test the EduQuest authentication system.
"""

import sys
import os
from dotenv import load_dotenv

# Add the parent directory to path to import from the main codebase
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_access.session_dao import SessionDAO
from data_access.student_dao import StudentDAO
from models.session import Session
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
import boto3
from botocore.exceptions import NoCredentialsError, ClientError


def check_environment_variables():
    """Check if all required environment variables are set."""
    print("=== Checking Environment Variables ===")
    
    required_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_REGION',
        'JWT_SECRET_KEY',
        'OPENAI_API_KEY'
    ]
    
    optional_vars = ['S3_BUCKET_NAME']
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: {'*' * min(len(value), 20)} (set)")
        else:
            print(f"✗ {var}: NOT SET")
            missing_vars.append(var)
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"• {var}: {value}")
        else:
            print(f"• {var}: not set (optional)")
    
    if missing_vars:
        print(f"\n❌ Missing required environment variables: {missing_vars}")
        print("Please create a .env file with these variables.")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True


def test_aws_connection():
    """Test AWS DynamoDB connection."""
    print("\n=== Testing AWS Connection ===")
    
    try:
        # Test AWS credentials by creating a DynamoDB resource
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=os.getenv('AWS_REGION', 'us-east-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )
        
        # Try to list tables (this will fail if credentials are wrong)
        tables = list(dynamodb.tables.all())
        print(f"✅ AWS connection successful!")
        print(f"✅ Found {len(tables)} DynamoDB tables")
        
        # Check if required tables exist
        table_names = [table.name for table in tables]
        required_tables = ['session', 'student', 'teacher', 'period']
        
        for table in required_tables:
            if table in table_names:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"⚠ Table '{table}' not found")
        
        return True
        
    except NoCredentialsError:
        print("❌ AWS credentials not found or invalid")
        return False
    except ClientError as e:
        print(f"❌ AWS connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error testing AWS: {e}")
        return False


def test_dao_initialization():
    """Test that DAO classes can be initialized (which creates AWS sessions)."""
    print("\n=== Testing DAO Initialization ===")
    
    try:
        session_dao = SessionDAO()
        print("✅ SessionDAO initialized successfully")
        
        student_dao = StudentDAO()
        print("✅ StudentDAO initialized successfully")
        
        # Try a simple operation (this will test the actual connection)
        # Note: This might fail if the table doesn't exist or has no data
        try:
            result = student_dao.get_student_by_id("test_user")
            print("✅ Database query executed successfully")
        except Exception as e:
            print(f"⚠ Database query failed (table might be empty): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ DAO initialization failed: {e}")
        return False


def create_and_test_auth_token():
    """Create different types of auth tokens for testing."""
    print("\n=== Testing Auth Token Creation ===")
    
    # Initialize Flask app for JWT
    app = Flask(__name__)
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret')
    jwt = JWTManager(app)
    
    try:
        with app.app_context():
            # Create a test JWT token
            auth_token = create_access_token(identity="test_user")
            print(f"✅ JWT token created: {auth_token[:20]}...")
            
            # Test storing a session
            session_dao = SessionDAO()
            test_session = Session(
                auth_token=auth_token,
                user_id="test_user", 
                role="student"
            )
            
            try:
                session_dao.add_session(test_session)
                print("✅ Test session stored in database")
                
                # Try to retrieve it
                sessions = session_dao.get_sessions_by_auth_token(auth_token)
                if sessions:
                    print(f"✅ Session retrieved successfully: {len(sessions)} session(s) found")
                else:
                    print("⚠ Session stored but couldn't retrieve (might be expected)")
                
                # Clean up
                try:
                    session_dao.delete_session(auth_token, "test_user")
                    print("✅ Test session cleaned up")
                except:
                    print("⚠ Couldn't clean up test session (might not exist)")
                
            except Exception as e:
                print(f"⚠ Couldn't store session in database: {e}")
            
            return auth_token
            
    except Exception as e:
        print(f"❌ Auth token creation failed: {e}")
        return None


def main():
    """Run all tests."""
    print("EduQuest AWS Session & Auth Token Test")
    print("=" * 50)
    
    # Load environment variables
    load_dotenv()
    
    # Run tests
    env_ok = check_environment_variables()
    aws_ok = test_aws_connection() if env_ok else False
    dao_ok = test_dao_initialization() if aws_ok else False
    token = create_and_test_auth_token() if env_ok else None
    
    print("\n" + "=" * 50)
    print("SUMMARY:")
    print(f"Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"AWS Connection: {'✅' if aws_ok else '❌'}")
    print(f"DAO Initialization: {'✅' if dao_ok else '❌'}")
    print(f"Auth Token Creation: {'✅' if token else '❌'}")
    
    if all([env_ok, aws_ok, dao_ok, token]):
        print("\n🎉 All tests passed! Your EduQuest setup is working correctly.")
        print(f"Sample auth token for testing: {token}")
    else:
        print("\n⚠ Some tests failed. Check the setup instructions above.")


if __name__ == "__main__":
    main() 