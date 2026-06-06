from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services.website_profiles import WebsiteProfileService


class WebsiteAgent:
    def __init__(self, db: Session) -> None:
        self.db = db

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def open_profile(self, name: str) -> dict:
        return WebsiteProfileService(self.db).open_or_request_profile(name)

    def auto_login(self, profile_id: int) -> dict:
        return WebsiteProfileService(self.db).auto_login(profile_id)
