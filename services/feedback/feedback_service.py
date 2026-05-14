import logging
from typing import Optional

from data_access.feedback_dao import FeedbackDAO
from data_access.user_dao import UserDAO
from integrations.email_service import EmailService, get_email_service

logger = logging.getLogger(__name__)

FEEDBACK_RECIPIENT = "support@eduquestai.org"


class FeedbackService:
    def __init__(
        self,
        dao: Optional[FeedbackDAO] = None,
        user_dao: Optional[UserDAO] = None,
        email_service: Optional[EmailService] = None,
    ) -> None:
        self.dao = dao or FeedbackDAO()
        self.user_dao = user_dao or UserDAO()
        self.email_service = email_service or get_email_service()

    def submit(self, user_id: str, message: str, page: Optional[str] = None) -> None:
        self.dao.insert(user_id, message)

        user = self.user_dao.get_by_id(user_id) or {}
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        email = user.get("email", "")
        phone = user.get("phone_number") or ""

        phone_line = f"Phone: {phone}\n" if phone else ""
        page_line = f"Page: {page}\n" if page else ""

        text_body = (
            f"From: {first_name} {last_name} <{email}>\n"
            f"User ID: {user_id}\n"
            f"{phone_line}"
            f"{page_line}"
            f"\nMessage:\n{message}"
        )

        result = self.email_service.send_email(
            to_email=FEEDBACK_RECIPIENT,
            subject=f"New feedback from {first_name} {last_name}",
            text_body=text_body,
        )
        if not result.get("success"):
            logger.error(
                "feedback email failed user_id=%s error=%s",
                user_id,
                result.get("error"),
            )
