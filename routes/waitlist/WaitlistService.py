from typing import Dict, Optional
from data_access.supabase.waitlist_dao import WaitlistDAO
from data_access.supabase.teacher_dao import TeacherDAO


class WaitlistService:
    """
    Service layer for pilot study waitlist operations.
    Handles business logic for joining waitlist and checking status.
    """

    def __init__(self, dao: Optional[WaitlistDAO] = None, teacher_dao: Optional[TeacherDAO] = None) -> None:
        self.dao = dao or WaitlistDAO()
        self.teacher_dao = teacher_dao or TeacherDAO()

    def join(self, user_id: str, referral_code: Optional[str] = None) -> Dict:
        """
        Add a teacher to the pilot study waitlist.
        
        Args:
            user_id: The teacher's username/ID
            referral_code: Optional referral code from another teacher
            
        Returns:
            Dict with waitlist entry details including position and referral code
        """
        # Validate teacher exists and get their email
        teacher = self.teacher_dao.get_teacher_by_id(user_id)
        if not teacher:
            raise ValueError("Teacher not found")

        teacher_email = teacher.get("email")
        if not teacher_email:
            raise ValueError("Teacher email not found")

        # Check if teacher is already approved
        if teacher.get("pilot_approved"):
            return {
                "already_approved": True,
                "message": "You are already approved for the pilot study"
            }

        # Validate referral code if provided
        referred_by = None
        if referral_code:
            validation = self.dao.validate_referral_code(referral_code)
            if validation.get("valid"):
                referred_by = validation.get("referrer_id")
                # Don't allow self-referral
                if referred_by == user_id:
                    referred_by = None

        # Join the waitlist (pass teacher_email for DynamoDB sort key)
        entry = self.dao.join_waitlist(user_id, teacher_email, referred_by)

        return {
            "success": True,
            "position": entry.get("position"),
            "referral_code": entry.get("referralCode"),
            "status": entry.get("status"),
            "joined_at": entry.get("joinedAt"),
            "referred_by": entry.get("referredBy"),
        }

    def get_status(self, user_id: str) -> Dict:
        """
        Get the waitlist status for a teacher.
        
        Args:
            user_id: The teacher's username/ID
            
        Returns:
            Dict with waitlist status details
        """
        # Check if teacher is already approved via the teacher record
        teacher = self.teacher_dao.get_teacher_by_id(user_id)
        if teacher and teacher.get("pilot_approved"):
            return {
                "on_waitlist": False,
                "approved": True,
                "position": None,
                "referral_code": None,
                "status": "approved",
            }

        # Get waitlist entry status
        return self.dao.get_status(user_id)

    def approve(self, user_id: str) -> Dict:
        """
        Approve a teacher for pilot study access.
        Updates both the waitlist entry and the teacher record.
        
        Args:
            user_id: The teacher's username/ID
            
        Returns:
            Dict with approval result
        """
        # Approve in waitlist
        waitlist_success = self.dao.approve_user(user_id)

        # Update teacher record
        try:
            self.teacher_dao.update_teacher(user_id, {"pilot_approved": True})
            teacher_success = True
        except Exception:
            teacher_success = False

        return {
            "success": waitlist_success and teacher_success,
            "waitlist_updated": waitlist_success,
            "teacher_updated": teacher_success,
        }
