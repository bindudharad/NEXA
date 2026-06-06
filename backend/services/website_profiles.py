from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.agents.notifications import NotificationAgent
from backend.database.models import (
    WebsiteAction,
    WebsiteCredential,
    WebsiteHistory,
    WebsiteLearning,
    WebsiteMonitoring,
    WebsiteProfile,
    WebsiteRetryRule,
    WebsiteSession,
)
from backend.services.secure_store import SecureStore

logger = logging.getLogger("nexa.websites")


class WebsiteProfileService:
    retryable_markers = ("server busy", "timeout", "503", "504", "connection failure", "network error")

    def __init__(self, db: Session, secure_store: SecureStore | None = None) -> None:
        self.db = db
        self.secure_store = secure_store or SecureStore()
        self.notifications = NotificationAgent(db)

    def analyze(self, name: str, url: str, html: str | None = None, headless: bool = True) -> dict:
        if html is None and url.startswith("data:text/html"):
            html = self._html_from_data_url(url)
        if html is not None:
            return self._analyze_html(name, url, html)
        return asyncio.run(self._analyze_with_playwright(name, url, headless))

    def create_profile(
        self,
        name: str,
        url: str,
        field_mapping: dict | None = None,
        navigation_rules: dict | None = None,
        login_process: dict | None = None,
        retry_policy: dict | None = None,
        credentials: dict | None = None,
        success_check: dict | None = None,
    ) -> dict:
        profile = self.db.query(WebsiteProfile).filter(WebsiteProfile.name.ilike(name)).one_or_none()
        now = datetime.utcnow()
        if not profile:
            profile = WebsiteProfile(name=name, url=url)
            self.db.add(profile)
        profile.url = url
        profile.field_mapping_json = json.dumps(field_mapping or {}, default=str)
        profile.navigation_rules_json = json.dumps(navigation_rules or {}, default=str)
        profile.login_process_json = json.dumps(login_process or self._default_login_process(field_mapping or {}), default=str)
        normalized_retry = self._retry_policy(retry_policy)
        profile.retry_policy_json = json.dumps(normalized_retry, default=str)
        profile.success_check_json = json.dumps(success_check or {}, default=str)
        profile.updated_at = now
        self.db.commit()
        self.db.refresh(profile)
        if credentials:
            self.save_credentials(profile.id, credentials)
        self._upsert_retry_rule(profile.id, normalized_retry)
        self._learn(profile.id, name, "field_mapping", field_mapping or {})
        self._learn(profile.id, name, "login_process", login_process or self._default_login_process(field_mapping or {}))
        self._history(profile.id, "profile_saved", {"name": name, "url": url})
        return self.serialize(profile, include_credentials=False)

    def save_credentials(self, profile_id: int, credentials: dict, label: str = "default") -> dict:
        profile = self._profile(profile_id)
        encrypted = self.secure_store.encrypt(json.dumps(credentials, default=str))
        row = self.db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile.id, WebsiteCredential.label == label).one_or_none()
        if not row:
            row = WebsiteCredential(profile_id=profile.id, label=label, encrypted_payload=encrypted)
            self.db.add(row)
        else:
            row.encrypted_payload = encrypted
            row.updated_at = datetime.utcnow()
        self.db.commit()
        self._history(profile.id, "credentials_saved", {"fields": sorted(credentials.keys())})
        return {"profile_id": profile.id, "label": label, "encrypted": True, "stored_fields": sorted(credentials.keys())}

    def auto_login(self, profile_id: int, headless: bool = False) -> dict:
        profile = self._profile(profile_id)
        restored = self._restore_session(profile)
        if restored:
            return restored
        retry_policy = json.loads(profile.retry_policy_json)
        max_retries = int(retry_policy.get("max_retries", 5))
        delay = int(retry_policy.get("retry_interval_seconds", retry_policy.get("base_delay_seconds", 5)))
        multiplier = max(1, int(retry_policy.get("backoff_multiplier", 2)))
        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                result = asyncio.run(self._auto_login_once(profile, headless))
                self._session(profile.id, "success", attempt, result.get("cookies", []))
                self._history(profile.id, "login_success", {"attempt": attempt, "title": result.get("title")})
                return {"status": "success", "attempts": attempt, **{k: v for k, v in result.items() if k != "cookies"}}
            except Exception as exc:
                last_error = str(exc)
                self._session(profile.id, "failed", attempt, [])
                self._history(profile.id, "login_retry", {"attempt": attempt, "error": last_error})
                if attempt < max_retries:
                    time.sleep(delay * (multiplier ** (attempt - 1)))
        self.notifications.notify("Website unavailable", f"{profile.name} unavailable. Tried {max_retries} times. Would you like me to continue monitoring?")
        self._history(profile.id, "login_failed", {"attempts": max_retries, "error": last_error})
        return {"status": "failed", "attempts": max_retries, "error": last_error, "monitoring_prompt": True}

    def open_or_request_profile(self, name: str) -> dict:
        profile = self.db.query(WebsiteProfile).filter(WebsiteProfile.name.ilike(name)).one_or_none()
        if not profile:
            message = f"Website profile for {name} does not exist. Please provide the website URL to analyze and save it."
            self.notifications.notify("Nexa Website Profile Required", message)
            self._history(None, "profile_missing", {"name": name})
            return {"requires_profile": True, "name": name, "message": message}
        return self.auto_login(profile.id)

    def set_monitoring(self, profile_id: int, enabled: bool, interval_seconds: int = 300) -> dict:
        profile = self._profile(profile_id)
        profile.monitoring_enabled = enabled
        profile.monitoring_interval_seconds = interval_seconds
        profile.updated_at = datetime.utcnow()
        row = self.db.query(WebsiteMonitoring).filter(WebsiteMonitoring.profile_id == profile.id).one_or_none()
        if not row:
            row = WebsiteMonitoring(profile_id=profile.id)
            self.db.add(row)
        row.enabled = enabled
        row.interval_seconds = interval_seconds
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self._history(profile.id, "monitoring_updated", {"enabled": enabled, "interval_seconds": interval_seconds})
        return self.serialize(profile)

    def check_monitored(self) -> list[dict]:
        results = []
        for profile in self.db.query(WebsiteProfile).filter(WebsiteProfile.monitoring_enabled.is_(True)).all():
            if not self._monitor_due(profile):
                continue
            result = self._check_available(profile)
            results.append(result)
            if result["available"]:
                self.notifications.notify("Website available", f"{profile.name} is available now.")
                profile.monitoring_enabled = False
                row = self.db.query(WebsiteMonitoring).filter(WebsiteMonitoring.profile_id == profile.id).one_or_none()
                if row:
                    row.enabled = False
                    row.last_available_at = datetime.utcnow()
        self.db.commit()
        return results

    def _monitor_due(self, profile: WebsiteProfile) -> bool:
        last = (
            self.db.query(WebsiteHistory)
            .filter(WebsiteHistory.profile_id == profile.id, WebsiteHistory.event_type.in_(["monitor_check", "monitor_check_failed"]))
            .order_by(WebsiteHistory.created_at.desc())
            .first()
        )
        if not last:
            return True
        elapsed = (datetime.utcnow() - last.created_at).total_seconds()
        return elapsed >= profile.monitoring_interval_seconds

    def create_action(self, profile_id: int, name: str, action: dict) -> dict:
        profile = self._profile(profile_id)
        row = WebsiteAction(profile_id=profile.id, name=name, action_json=json.dumps(action, default=str))
        self.db.add(row)
        self.db.commit()
        self._history(profile.id, "action_saved", {"name": name})
        return {"id": row.id, "profile_id": profile.id, "name": name, "action": action}

    def list_profiles(self) -> list[dict]:
        return [self.serialize(row) for row in self.db.query(WebsiteProfile).order_by(WebsiteProfile.updated_at.desc()).all()]

    def history(self, profile_id: int) -> list[dict]:
        self._profile(profile_id)
        return [
            {"id": row.id, "event_type": row.event_type, "detail": json.loads(row.detail_json), "created_at": row.created_at.isoformat()}
            for row in self.db.query(WebsiteHistory).filter(WebsiteHistory.profile_id == profile_id).order_by(WebsiteHistory.created_at.desc()).limit(100).all()
        ]

    def delete_profile(self, profile_id: int) -> dict:
        profile = self._profile(profile_id)
        name = profile.name
        for model in (WebsiteCredential, WebsiteAction, WebsiteSession, WebsiteHistory, WebsiteMonitoring, WebsiteRetryRule, WebsiteLearning):
            self.db.query(model).filter(model.profile_id == profile.id).delete()
        self.db.delete(profile)
        self.db.commit()
        return {"deleted": True, "profile_id": profile_id, "name": name}

    def export_profile(self, profile_id: int) -> dict:
        profile = self._profile(profile_id)
        return {
            "profile": self.serialize(profile, include_credentials=False),
            "actions": [
                {"name": row.name, "action": json.loads(row.action_json)}
                for row in self.db.query(WebsiteAction).filter(WebsiteAction.profile_id == profile.id).all()
            ],
            "encrypted_credentials": [
                {"label": row.label, "encrypted_payload": row.encrypted_payload}
                for row in self.db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile.id).all()
            ],
        }

    def import_profile(self, payload: dict) -> dict:
        profile_data = payload.get("profile", payload)
        created = self.create_profile(
            profile_data["name"],
            profile_data["url"],
            profile_data.get("field_mapping", {}),
            profile_data.get("navigation_rules", {}),
            profile_data.get("login_process", {}),
            profile_data.get("retry_policy", {}),
            None,
            profile_data.get("success_check", {}),
        )
        profile_id = created["id"]
        for credential in payload.get("encrypted_credentials", []):
            row = self.db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile_id, WebsiteCredential.label == credential.get("label", "default")).one_or_none()
            if not row:
                row = WebsiteCredential(profile_id=profile_id, label=credential.get("label", "default"), encrypted_payload=credential["encrypted_payload"])
                self.db.add(row)
            else:
                row.encrypted_payload = credential["encrypted_payload"]
        for action in payload.get("actions", []):
            self.create_action(profile_id, action["name"], action.get("action", {}))
        self.db.commit()
        self._history(profile_id, "profile_imported", {"name": created["name"]})
        return self.serialize(self._profile(profile_id))

    def kcet_result(self, application_number: str | None = None, date_of_birth: str | None = None, save_profile: bool = False, url: str | None = None) -> dict:
        profile = self.db.query(WebsiteProfile).filter(WebsiteProfile.name.ilike("KCET")).one_or_none()
        if not profile:
            if not application_number or not date_of_birth:
                return {"requires_input": True, "fields": ["application_number", "date_of_birth"], "save_profile_available": True}
            if save_profile:
                created = self.create_profile(
                    "KCET",
                    url or "https://kea.kar.nic.in",
                    {"application_number": "[name='application_number']", "date_of_birth": "[name='dob']"},
                    {},
                    {"submit_selector": "button[type=submit]"},
                    {"max_retries": 5, "retry_interval_seconds": 5, "backoff_multiplier": 2},
                    {"application_number": application_number, "date_of_birth": date_of_birth},
                    {"expected_text": "result"},
                )
                profile = self._profile(created["id"])
            else:
                return {"requires_profile_save": True, "application_number": application_number, "date_of_birth": "***"}
        result = self.auto_login(profile.id, headless=True)
        if result.get("status") != "success":
            return result
        extracted = {"status": "available", "source": profile.name, "screenshot": result.get("screenshot"), "result_summary": "KCET result page loaded. Extract detailed marks from the captured page."}
        self._history(profile.id, "kcet_result_extracted", extracted)
        return extracted

    def serialize(self, profile: WebsiteProfile, include_credentials: bool = False) -> dict:
        payload = {
            "id": profile.id,
            "name": profile.name,
            "url": profile.url,
            "field_mapping": json.loads(profile.field_mapping_json),
            "navigation_rules": json.loads(profile.navigation_rules_json),
            "login_process": json.loads(profile.login_process_json),
            "retry_policy": json.loads(profile.retry_policy_json),
            "success_check": json.loads(profile.success_check_json),
            "monitoring_enabled": profile.monitoring_enabled,
            "monitoring_interval_seconds": profile.monitoring_interval_seconds,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }
        if include_credentials:
            payload["credentials"] = self._credentials(profile.id)
        return payload

    def _analyze_html(self, name: str, url: str, html: str) -> dict:
        fields = []
        for match in re.finditer(r"<(input|select|textarea)\b([^>]*)>", html, flags=re.I):
            tag, attrs = match.group(1).lower(), match.group(2)
            field = self._field_from_attrs(tag, attrs)
            fields.append(field)
        buttons = [
            self._button_from_attrs(match.group(1) or match.group(3) or "", match.group(2) or "")
            for match in re.finditer(r"<button\b([^>]*)>(.*?)</button>|<input\b([^>]*type=['\"]?(submit|button)['\"]?[^>]*)>", html, flags=re.I | re.S)
        ]
        captcha = bool(re.search(r"captcha|g-recaptcha|hcaptcha", html, flags=re.I))
        mapping = self._field_mapping(fields)
        analysis = {
            "name": name,
            "url": url,
            "login_forms": self._login_forms(fields, buttons),
            "fields": fields,
            "field_mapping": mapping,
            "buttons": buttons,
            "dropdowns": [field for field in fields if field["tag"] == "select"],
            "captcha_present": captcha,
            "navigation": {"links_detected": len(re.findall(r"<a\b", html, flags=re.I))},
            "retry_policy": {"max_retries": 5, "retry_interval_seconds": 5},
            "success_check": {"expected_url_change": True},
        }
        self._history(None, "website_analyzed", {"name": name, "url": url, "fields": len(fields), "captcha": captcha})
        return analysis

    async def _analyze_with_playwright(self, name: str, url: str, headless: bool) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            html = await page.content()
            title = await page.title()
            await browser.close()
        result = self._analyze_html(name, url, html)
        result["title"] = title
        return result

    async def _auto_login_once(self, profile: WebsiteProfile, headless: bool) -> dict:
        from playwright.async_api import async_playwright

        credentials = self._credentials(profile.id)
        field_mapping = json.loads(profile.field_mapping_json)
        login_process = json.loads(profile.login_process_json)
        success_check = json.loads(profile.success_check_json)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(accept_downloads=True)
            restored_cookies = self._latest_cookies(profile.id)
            if restored_cookies:
                await context.add_cookies(restored_cookies)
            page = await context.new_page()
            await page.goto(profile.url, wait_until="domcontentloaded", timeout=30000)
            filled = []
            for semantic, selector in field_mapping.items():
                if semantic in credentials and selector:
                    await page.fill(selector, str(credentials[semantic]))
                    filled.append(semantic)
            button = login_process.get("submit_selector")
            if button:
                await page.click(button)
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            title = await page.title()
            content = await page.content()
            success = self._success(profile.url, page.url, content, success_check)
            screenshot_path = Path("backend/logs") / f"website-{profile.id}-{int(time.time())}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            cookies = await context.cookies()
            await browser.close()
            if not success:
                raise RuntimeError("Login success check failed")
            return {"title": title, "url": page.url, "filled_fields": filled, "screenshot": str(screenshot_path), "cookies": cookies}

    def _restore_session(self, profile: WebsiteProfile) -> dict | None:
        cookies = self._latest_cookies(profile.id)
        if not cookies:
            return None
        self._history(profile.id, "session_restore_available", {"cookies": len(cookies)})
        return {"status": "session_restored", "attempts": 0, "url": profile.url, "restored_cookies": len(cookies)}

    def _latest_cookies(self, profile_id: int) -> list[dict]:
        row = (
            self.db.query(WebsiteSession)
            .filter(WebsiteSession.profile_id == profile_id, WebsiteSession.status == "success", WebsiteSession.encrypted_cookies != "")
            .order_by(WebsiteSession.created_at.desc())
            .first()
        )
        if not row:
            return []
        try:
            return json.loads(self.secure_store.decrypt(row.encrypted_cookies))
        except Exception:
            logger.warning("Stored website session cookies could not be decrypted for profile_id=%s", profile_id)
            return []

    def _success(self, original_url: str, current_url: str, content: str, success_check: dict) -> bool:
        expected_text = success_check.get("expected_text")
        if expected_text and expected_text.lower() not in content.lower():
            return False
        if success_check.get("expected_url_contains") and success_check["expected_url_contains"] not in current_url:
            return False
        if success_check.get("expected_url_change") and current_url == original_url:
            return False
        if any(marker in content.lower() for marker in self.retryable_markers):
            return False
        return True

    def _retry_policy(self, retry_policy: dict | None) -> dict:
        policy = {"max_retries": 5, "retry_interval_seconds": 5, "base_delay_seconds": 5, "backoff_multiplier": 2, "retry_conditions": list(self.retryable_markers)}
        policy.update(retry_policy or {})
        max_retries = int(policy.get("max_retries", 5))
        if max_retries not in {3, 5, 10, 15}:
            max_retries = 5
        policy["max_retries"] = max_retries
        return policy

    def _upsert_retry_rule(self, profile_id: int, policy: dict) -> None:
        row = self.db.query(WebsiteRetryRule).filter(WebsiteRetryRule.profile_id == profile_id).one_or_none()
        if not row:
            row = WebsiteRetryRule(profile_id=profile_id)
            self.db.add(row)
        row.max_retries = int(policy.get("max_retries", 5))
        row.base_delay_seconds = int(policy.get("base_delay_seconds", policy.get("retry_interval_seconds", 5)))
        row.backoff_multiplier = int(policy.get("backoff_multiplier", 2))
        row.retry_conditions_json = json.dumps(policy.get("retry_conditions", list(self.retryable_markers)))
        row.updated_at = datetime.utcnow()
        self.db.commit()

    def _learn(self, profile_id: int, website_name: str, key: str, value: dict) -> None:
        row = WebsiteLearning(profile_id=profile_id, website_name=website_name, learned_key=key, learned_value_json=json.dumps(value, default=str), confidence=100)
        self.db.add(row)
        self.db.commit()

    def _check_available(self, profile: WebsiteProfile) -> dict:
        try:
            result = self.analyze(profile.name, profile.url, headless=True)
            available = not result.get("captcha_present", False)
            self._history(profile.id, "monitor_check", {"available": available})
            row = self.db.query(WebsiteMonitoring).filter(WebsiteMonitoring.profile_id == profile.id).one_or_none()
            if row:
                row.last_checked_at = datetime.utcnow()
                if available:
                    row.last_available_at = datetime.utcnow()
                self.db.commit()
            return {"profile_id": profile.id, "name": profile.name, "available": available}
        except Exception as exc:
            self._history(profile.id, "monitor_check_failed", {"error": str(exc)})
            row = self.db.query(WebsiteMonitoring).filter(WebsiteMonitoring.profile_id == profile.id).one_or_none()
            if row:
                row.last_checked_at = datetime.utcnow()
                self.db.commit()
            return {"profile_id": profile.id, "name": profile.name, "available": False, "error": str(exc)}

    def _field_from_attrs(self, tag: str, attrs: str) -> dict:
        attr = self._attrs(attrs)
        selector = self._selector(attr)
        label_source = " ".join(str(attr.get(key, "")) for key in ("name", "id", "placeholder", "aria-label", "autocomplete", "type"))
        return {
            "tag": tag,
            "type": attr.get("type", "text" if tag == "input" else tag),
            "name": attr.get("name"),
            "id": attr.get("id"),
            "placeholder": attr.get("placeholder"),
            "autocomplete": attr.get("autocomplete"),
            "selector": selector,
            "semantic": self._semantic(label_source),
            "required": "required" in attrs.lower(),
        }

    def _button_from_attrs(self, attrs: str, label: str) -> dict:
        attr = self._attrs(attrs)
        text = re.sub(r"<[^>]+>", "", label or attr.get("value", "")).strip()
        return {"text": text or attr.get("value") or attr.get("type") or "Submit", "selector": self._selector(attr) or "button[type=submit]"}

    def _attrs(self, attrs: str) -> dict:
        result = {}
        for key, value in re.findall(r"([\w:-]+)(?:\s*=\s*['\"]?([^'\"\s>]+)['\"]?)?", attrs):
            result[key.lower()] = value or True
        return result

    def _selector(self, attrs: dict) -> str | None:
        if attrs.get("id"):
            return f"#{attrs['id']}"
        if attrs.get("name"):
            return f"[name='{attrs['name']}']"
        if attrs.get("type"):
            return f"input[type='{attrs['type']}']"
        return None

    def _semantic(self, text: str) -> str:
        lower = text.lower()
        checks = [
            ("usn", ("usn", "university seat")),
            ("application_number", ("application", "registration", "regno")),
            ("date_of_birth", ("dob", "birth", "dateofbirth")),
            ("password", ("password", "passwd", "pwd")),
            ("email", ("email", "e-mail")),
            ("username", ("username", "user name", "userid", "login")),
            ("otp", ("otp", "one time")),
            ("search", ("search", "query")),
        ]
        for semantic, needles in checks:
            if any(item in lower for item in needles):
                return semantic
        return "custom"

    def _field_mapping(self, fields: list[dict]) -> dict:
        mapping = {}
        for field in fields:
            semantic = field["semantic"]
            if semantic != "custom" and semantic not in mapping:
                mapping[semantic] = field["selector"]
        return mapping

    def _login_forms(self, fields: list[dict], buttons: list[dict]) -> list[dict]:
        has_password = any(field["semantic"] == "password" for field in fields)
        has_user = any(field["semantic"] in {"username", "email", "usn", "application_number"} for field in fields)
        if not (has_password or has_user):
            return []
        submit = next((button["selector"] for button in buttons if re.search(r"login|submit|sign", button["text"], re.I)), buttons[0]["selector"] if buttons else None)
        return [{"fields": [field for field in fields if field["semantic"] != "custom"], "submit_selector": submit}]

    def _default_login_process(self, field_mapping: dict) -> dict:
        return {"steps": [{"type": "fill", "fields": list(field_mapping.keys())}, {"type": "click", "selector": "button[type=submit]"}], "submit_selector": "button[type=submit]"}

    def _credentials(self, profile_id: int, label: str = "default") -> dict:
        row = self.db.query(WebsiteCredential).filter(WebsiteCredential.profile_id == profile_id, WebsiteCredential.label == label).one_or_none()
        if not row:
            return {}
        return json.loads(self.secure_store.decrypt(row.encrypted_payload))

    def _session(self, profile_id: int, status: str, retry_count: int, cookies: list[dict]) -> None:
        encrypted = self.secure_store.encrypt(json.dumps(cookies, default=str)) if cookies else ""
        self.db.add(WebsiteSession(profile_id=profile_id, status=status, encrypted_cookies=encrypted, last_attempt_at=datetime.utcnow(), last_success_at=datetime.utcnow() if status == "success" else None, retry_count=retry_count))
        self.db.commit()

    def _history(self, profile_id: int | None, event_type: str, detail: dict) -> None:
        self.db.add(WebsiteHistory(profile_id=profile_id, event_type=event_type, detail_json=json.dumps(detail, default=str)))
        self.db.commit()

    def _profile(self, profile_id: int) -> WebsiteProfile:
        profile = self.db.get(WebsiteProfile, profile_id)
        if not profile:
            raise ValueError("Website profile not found")
        return profile

    def _html_from_data_url(self, url: str) -> str:
        _, data = url.split(",", 1)
        if ";base64" in url[: url.index(",")]:
            return base64.b64decode(data).decode("utf-8")
        return data.replace("%20", " ")
