#!/usr/bin/env python3
"""
Backfill script to populate email_lc for existing student and teacher records.
Run once after deploying the email_lc changes.

Usage:
    cd eduquest-backend
    python scripts/backfill_email_lc.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_access.student_dao import StudentDAO
from data_access.teacher_dao import TeacherDAO
from dotenv import load_dotenv

load_dotenv()


def backfill_students():
    """Backfill email_lc for all students."""
    dao = StudentDAO()
    print("Scanning student table...")
    
    response = dao.table.scan()
    items = response.get('Items', [])
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = dao.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    updated = 0
    skipped = 0
    
    for item in items:
        user_id = item.get('user_id')
        email = item.get('email', '')
        existing_email_lc = item.get('email_lc')
        
        if not user_id:
            continue
            
        email_lc = email.strip().lower() if email else ''
        
        # Skip if already set correctly
        if existing_email_lc == email_lc:
            skipped += 1
            continue
        
        try:
            dao.table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET email_lc = :email_lc',
                ExpressionAttributeValues={':email_lc': email_lc}
            )
            updated += 1
            print(f"  Updated student {user_id}: email_lc = {email_lc}")
        except Exception as e:
            print(f"  ERROR updating student {user_id}: {e}")
    
    print(f"Students: {updated} updated, {skipped} already correct")
    return updated


def backfill_teachers():
    """Backfill email_lc for all teachers."""
    dao = TeacherDAO()
    print("Scanning teacher table...")
    
    response = dao.table.scan()
    items = response.get('Items', [])
    
    # Handle pagination
    while 'LastEvaluatedKey' in response:
        response = dao.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    updated = 0
    skipped = 0
    
    for item in items:
        user_id = item.get('user_id')
        email = item.get('email', '')
        existing_email_lc = item.get('email_lc')
        
        if not user_id:
            continue
            
        email_lc = email.strip().lower() if email else ''
        
        # Skip if already set correctly
        if existing_email_lc == email_lc:
            skipped += 1
            continue
        
        try:
            dao.table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET email_lc = :email_lc',
                ExpressionAttributeValues={':email_lc': email_lc}
            )
            updated += 1
            print(f"  Updated teacher {user_id}: email_lc = {email_lc}")
        except Exception as e:
            print(f"  ERROR updating teacher {user_id}: {e}")
    
    print(f"Teachers: {updated} updated, {skipped} already correct")
    return updated


def main():
    print("=" * 60)
    print("Backfill email_lc for existing users")
    print("=" * 60)
    
    student_count = backfill_students()
    print()
    teacher_count = backfill_teachers()
    
    print()
    print("=" * 60)
    print(f"Done! Total updated: {student_count + teacher_count}")
    print("=" * 60)


if __name__ == '__main__':
    main()

