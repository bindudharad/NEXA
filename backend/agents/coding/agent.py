from sqlalchemy.orm import Session

from backend.analytics import CodingAnalytics


class CodingAgent:
    def __init__(self, db: Session) -> None:
        self.analytics = CodingAnalytics(db)

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def daily_report(self) -> dict:
        return self.analytics.daily_report()

    def weekly_report(self) -> dict:
        return self.analytics.weekly_report()

    def snapshot(self) -> dict:
        return self.analytics.snapshot()
