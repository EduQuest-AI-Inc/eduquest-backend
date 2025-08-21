import boto3
import os
import sys

# Add the current directory (eduquest-backend) to Python path so we can import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from data_access.config import DynamoDBConfig
from data_access.student_dao import StudentDAO

# current_path = os.getcwd()  # Get current working directory
# parent_path = os.path.dirname(current_path)  # Get parent folder

def migrate_tutorial_fields():
    """
    Migrate existing students to add completed_tutorial field.
    This script adds the new field to all existing student records.
    """
    config = DynamoDBConfig()
    table = config.get_table("student")
    student_dao = StudentDAO()
    
    print("Starting student table migration for completed_tutorial field...")
    
    try:
        # Scan all students
        response = table.scan()
        students = response.get('Items', [])
        
        migrated_count = 0
        for student in students:
            student_id = student.get('student_id')
            
            # Check if completed_tutorial field already exists
            has_completed_tutorial = 'completed_tutorial' in student
            
            if not has_completed_tutorial:
                try:
                    # Add the new field with default value False
                    student_dao.update_student(student_id, {'completed_tutorial': False})
                    migrated_count += 1
                    print(f"Migrated student {student_id}")
                except Exception as e:
                    print(f"Error migrating student {student_id}: {e}")
        
        print(f"Migration completed. {migrated_count} students migrated.")
        
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_tutorial_fields()