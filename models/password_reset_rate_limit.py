from pydantic import BaseModel


class PasswordResetRateLimit(BaseModel):
    key: str
    count: int
    expires_at: str

    def to_item(self):
        return self.model_dump()
