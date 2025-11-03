import os, base64, re
from typing import Dict, Optional
from data_access.waitlist_dao import WaitlistDAO

EMAIL_REGEX = re.compile(r"^\S+@\S+\.\S+$")

def _gen_code(n: int = 8) -> str:
    import os, base64
    return base64.urlsafe_b64encode(os.urandom(6)).decode("ascii").rstrip("=")[:n]

class WaitlistService:
    def __init__(self, dao: Optional[WaitlistDAO] = None):
        self.dao = dao or WaitlistDAO()

    def join(self, email_raw: str, name_raw: str) -> Dict[str, str]:
        email = (email_raw or "").strip().lower()
        name  = (name_raw or "").strip()
        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email")
        if len(name) < 2:
            raise ValueError("Invalid name")

        existing = self.dao.get_by_email(email)
        if existing:
            if "name" not in existing or not (existing.get("name") or "").strip():
                self.dao.update_name_if_missing(existing["waitlistID"], name)
                existing["name"] = name
            return {"waitlistID": existing["waitlistID"], "email": existing["email"], "name": existing.get("name", name)}

        for _ in range(5):
            code = _gen_code(8)
            if self.dao.put_unique_code(code, email, name):
                try:
                    from utils.emailer_ses import send_waitlist_code
                    send_waitlist_code(email, code, name=name)
                except Exception:
                    pass
                return {"waitlistID": code, "email": email, "name": name}

        raise RuntimeError("Could not allocate a unique waitlist code, please retry.")
