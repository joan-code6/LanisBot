import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from sph_client import SchulportalHessenAPI


@dataclass
class APIResult:
    success: bool
    data: Any
    error: Optional[str] = None


class LanisAPI:
    def __init__(self):
        self.sessions: Dict[str, SchulportalHessenAPI] = {}

    def get_session(self, user_id: str) -> Optional[SchulportalHessenAPI]:
        return self.sessions.get(user_id)

    def create_session(self, user_id: str) -> SchulportalHessenAPI:
        api = SchulportalHessenAPI()
        self.sessions[user_id] = api
        return api

    def remove_session(self, user_id: str):
        if user_id in self.sessions:
            self.sessions[user_id].close()
            del self.sessions[user_id]

    async def login(
        self, user_id: str, school_id: str, username: str, password: str
    ) -> APIResult:
        try:
            if user_id not in self.sessions:
                self.create_session(user_id)

            api = self.sessions[user_id]
            result = api.login(school_id, username, password)

            if result.get("success"):
                return APIResult(success=True, data=result)
            else:
                return APIResult(success=False, data=None, error=result.get("message"))
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def logout(self, user_id: str) -> APIResult:
        try:
            if user_id in self.sessions:
                api = self.sessions[user_id]
                result = api.logout()
                self.remove_session(user_id)
                return APIResult(success=result.get("success", True), data=result)
            return APIResult(success=False, data=None, error="Not logged in")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_messages(self, user_id: str, limit: int = 10) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.nachrichten_get_headers(get_type="All", last=limit)
            if result.get("success"):
                headers = result.get("data", {}).get("data", {}).get("headers", [])
                formatted = []
                for h in headers[:limit]:
                    formatted.append({
                        "id": h.get("id"),
                        "subject": h.get("subject", "No subject"),
                        "from": h.get("from", {}).get("Name", "Unknown"),
                        "date": h.get("date", "Unknown"),
                        "read": h.get("read", False),
                    })
                return APIResult(success=True, data={"messages": formatted})
            return APIResult(success=False, data=None, error="Failed to fetch messages")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_calendar(self, user_id: str, days: int = 7) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.kalender_get_events(year=0, start="week")
            if result.get("success"):
                events = result.get("data", {}).get("events", [])
                return APIResult(success=True, data={"events": events[:20]})
            return APIResult(success=False, data=None, error="Failed to fetch calendar")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_homework(self, user_id: str) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.meinunterricht_get_overview()
            if result.get("success"):
                entries = result.get("data", {}).get("entries", [])
                homework = [e for e in entries if e.get("type") == "homework"]
                return APIResult(success=True, data={"homework": homework})
            return APIResult(success=False, data=None, error="Failed to fetch homework")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_substitution(self, user_id: str) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.vertretungsplan_get_plan(include_raw=False)
            if result.get("success"):
                return APIResult(success=True, data=result.get("data"))
            return APIResult(success=False, data=None, error="Failed to fetch substitution plan")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_timetable(self, user_id: str) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.stundenplan_get_plan()
            if result.get("success"):
                return APIResult(success=True, data=result.get("data"))
            return APIResult(success=False, data=None, error="Failed to fetch timetable")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))

    async def get_profile(self, user_id: str) -> APIResult:
        try:
            api = self.sessions.get(user_id)
            if not api or not api.logged_in:
                return APIResult(success=False, data=None, error="Not logged in")

            result = api.benutzer_get_data()
            if result.get("success"):
                return APIResult(success=True, data=result.get("data"))
            return APIResult(success=False, data=None, error="Failed to fetch profile")
        except Exception as e:
            return APIResult(success=False, data=None, error=str(e))


lanis_api = LanisAPI()