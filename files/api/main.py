"""FastAPI entry point for FloodWatch Nigeria.

This file joins the project layers:
- HTML pages rendered with Jinja2.
- Telemetry ingestion for simulated or hardware sensor nodes.
- Account creation, login, and database-backed sessions.
- Risk classification, ML probability, and simulated notifications.
"""

from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import random
import secrets
import textwrap
from typing import Literal
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from pydantic import ValidationError
from sqlalchemy import and_, func, inspect, text
from sqlalchemy.orm import Session

import ml_model
import models
import news_feeds
import notifications
import telemetry_service
import current_state_service
import normalized_read_repository
import normalized_current_state_service
import alert_service
from database import engine, get_db
from risk_engine import classify
from weather_forecast import get_forecast


models.Base.metadata.create_all(bind=engine)


def migrate_telemetry_schema() -> None:
    """Add newer columns to older SQLite/MySQL databases without losing data."""
    existing_columns = {column["name"] for column in inspect(engine).get_columns("telemetry")}
    statements = []
    if "data_source" not in existing_columns:
        statements.append("ALTER TABLE telemetry ADD COLUMN data_source VARCHAR(24) NOT NULL DEFAULT 'simulated'")
    if "threshold_type" not in existing_columns:
        statements.append("ALTER TABLE telemetry ADD COLUMN threshold_type VARCHAR(32) NOT NULL DEFAULT 'prototype_demo'")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


def migrate_user_schema() -> None:
    """Add account settings fields to existing user databases."""
    existing_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    statements = []
    if "phone_number" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN phone_number VARCHAR(32)")
    if "preferred_language" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(8) NOT NULL DEFAULT 'en'")
    if "email_updates" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN email_updates BOOLEAN NOT NULL DEFAULT 1")
    if "sms_updates" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN sms_updates BOOLEAN NOT NULL DEFAULT 1")
    if "whatsapp_updates" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN whatsapp_updates BOOLEAN NOT NULL DEFAULT 0")
    if statements:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))


migrate_telemetry_schema()
migrate_user_schema()


from fastapi import FastAPI

app = FastAPI(
    title="FloodWatch Nigeria API",
    description="Flood early warning, account-aware GIS dashboard, and decision support.",
    version="1.1.0",
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
SESSION_COOKIE = "floodwatch_session"
GUEST_COOKIE = "floodwatch_guest"
SESSION_HOURS = 12
SESSION_SECONDS = SESSION_HOURS * 60 * 60
REGISTRATION_CONFIRM_SECONDS = 15 * 60
DELETION_CONFIRM_SECONDS = 10 * 60
RISK_RANK = {"Low": 1, "Moderate": 2, "High": 3, "Severe": 4}
ROLE_LEVELS = {"user": 1, "viewer": 1, "operator": 2, "admin": 3}
PENDING_REGISTRATIONS: dict[str, dict] = {}
PENDING_ACCOUNT_DELETIONS: dict[str, dict] = {}
DELETE_FEEDBACK_REASONS = {
    "found_alternative": "I have found another site",
    "no_longer_needed": "I do not need it anymore",
    "bug_or_issue": "There was a bug or an issue",
}
ENABLE_COMMUNITY_REPORTS = os.getenv("FLOOD_EWS_ENABLE_COMMUNITY_REPORTS", "0") == "1"
SECURE_SESSION_COOKIES = os.getenv("FLOOD_EWS_SECURE_COOKIES", "0") == "1"
INGEST_TOKEN = os.getenv("FLOOD_EWS_INGEST_TOKEN", "").strip()
CORE_ALERT_CHANNELS = {"web": "available", "email": "not_configured", "sms": "not_configured"}
CONTACT_EMAIL = os.getenv("FLOODWATCH_CONTACT_EMAIL", "").strip()
RUNTIME_DIR = Path(os.getenv("FLOOD_EWS_RUNTIME_DIR", str(BASE_DIR)))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
ACCOUNT_NOTIFICATION_LOG_PATH = RUNTIME_DIR / "simulated_account_notifications.jsonl"


@app.middleware("http")
async def protect_browser_writes(request: Request, call_next):
    """Reject cross-site browser writes before their cookies grant authority.

    Origin and Fetch Metadata are supplied by browsers for cross-site requests.
    Sensors can omit these headers; their ingest token is checked separately.
    """
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        expected = urlsplit(str(request.base_url))
        supplied = urlsplit(origin) if origin else None
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            supplied and (supplied.scheme, supplied.netloc) != (expected.scheme, expected.netloc)
        ):
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
    response = await call_next(request)
    # Even public Jinja pages vary with the session (name, menu and account
    # links). Do not let a browser/shared cache replay a signed-in response
    # after logout. Static CSS/JS contain no session data and remain cacheable.
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def get_password_hash(password: str) -> str:
    """Hash a password before database storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a submitted password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_email(db: Session, email: str) -> models.User | None:
    """Return a user by normalized email, or None if no account exists."""
    return db.query(models.User).filter(models.User.email == email.lower().strip()).first()


def role_level(role: str | None) -> int:
    """Translate a role name into a comparable permission level."""
    return ROLE_LEVELS.get((role or "user").strip().lower(), 0)


def has_role(user: models.User, minimum_role: str) -> bool:
    """Return True when the user meets an operational role requirement."""
    return role_level(user.role) >= role_level(minimum_role)


def safe_redirect_path(next_path: str | None, default: str = "/") -> str:
    """Return a local redirect target so forms cannot send users off-site.

    Login and registration now default to the home page because users should
    land somewhere calm and familiar after account actions. A local ``next``
    value is still supported for deliberate protected-page redirects, but full
    URLs and protocol-relative paths are rejected.
    """
    candidate = (next_path or default).strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
    ):
        return default
    return candidate


def normalize_phone_number(phone_number: str | None) -> str:
    """Normalize a contact number while preserving a leading plus sign.

    This is not a full international phone-number library. For the prototype,
    it removes spaces, dashes, and parentheses so SMS-capable contact details
    are stored consistently enough for simulated delivery logs and future
    provider integration.
    """
    raw_value = (phone_number or "").strip()
    if not raw_value:
        return ""
    normalized = []
    for index, char in enumerate(raw_value):
        if char.isdigit() or (char == "+" and index == 0):
            normalized.append(char)
    return "".join(normalized)


def valid_phone_number(phone_number: str) -> bool:
    """Check that a normalized contact number is plausible for SMS simulation."""
    if not phone_number:
        return False
    digits = "".join(char for char in phone_number if char.isdigit())
    return 7 <= len(digits) <= 15 and (phone_number[0].isdigit() or phone_number.startswith("+"))


def account_channel_status(user: models.User) -> dict[str, str]:
    """Describe account-security channels without pretending real delivery exists."""
    channels = {"email": "simulated"}
    if user.phone_number and user.sms_updates:
        channels["sms"] = "simulated"
    elif user.phone_number:
        channels["sms"] = "saved_but_disabled_by_preference"
    else:
        channels["sms"] = "no_phone_number"

    if user.phone_number and user.whatsapp_updates:
        channels["whatsapp"] = "preference_saved_provider_not_configured"
    else:
        channels["whatsapp"] = "not_configured"
    return channels


def log_account_notification(user: models.User, event_type: str, message: str, *, verification_code: str | None = None) -> dict[str, str]:
    """Write a simulated account-security notification event to a JSONL log.

    This supports the account-deletion demo requested by the user while staying
    honest: no real SMS, email, or WhatsApp message leaves the computer until a
    real provider is configured and tested.
    """
    channels = account_channel_status(user)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user.id,
        "email": user.email,
        "phone_number": user.phone_number,
        "message": message,
        "channels": channels,
    }
    if verification_code:
        event["verification_code"] = verification_code
    try:
        with ACCOUNT_NOTIFICATION_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(event) + "\n")
    except OSError:
        channels = {channel: "simulation_log_unavailable" for channel in channels}
    return channels


def clean_pending_account_deletions() -> None:
    """Remove expired account-deletion verification sessions."""
    now = datetime.utcnow()
    expired_tokens = [
        token
        for token, pending_deletion in PENDING_ACCOUNT_DELETIONS.items()
        if pending_deletion["expires_at"] <= now
    ]
    for token in expired_tokens:
        PENDING_ACCOUNT_DELETIONS.pop(token, None)


def create_pending_account_deletion(user: models.User, reason: str, feedback: str) -> tuple[str, str, dict[str, str]]:
    """Create a short-lived verification code before destructive account deletion."""
    clean_pending_account_deletions()
    token = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(900000) + 100000}"
    PENDING_ACCOUNT_DELETIONS[token] = {
        "user_id": user.id,
        "code_hash": hash_token(code),
        "reason": reason,
        "feedback": feedback[:600],
        "expires_at": datetime.utcnow() + timedelta(seconds=DELETION_CONFIRM_SECONDS),
    }
    channels = log_account_notification(
        user,
        "account_deletion_verification",
        "A simulated account-deletion verification code was generated. If you did not initiate this process, do not continue and contact the project administrator.",
        verification_code=code,
    )
    return token, code, channels


def public_user(user: models.User) -> dict:
    """Return only fields that are safe to expose to browser code."""
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "preferred_language": user.preferred_language,
        "email_updates": user.email_updates,
        "sms_updates": user.sms_updates,
        "whatsapp_updates": user.whatsapp_updates,
    }


def hash_token(raw_token: str) -> str:
    """Store only a one-way hash of the session token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_user_session(db: Session, user: models.User) -> str:
    """Create a short-lived bearer token for browser/API access."""
    raw_token = secrets.token_urlsafe(32)
    session = models.UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(hours=SESSION_HOURS),
    )
    db.add(session)
    db.commit()
    return raw_token


def clean_pending_registrations() -> None:
    """Remove expired pending sign-up confirmations from memory.

    The confirmation page is deliberately a temporary checkpoint, not a
    permanent account record.  If the server restarts or the token expires,
    the visitor simply fills the form again.
    """
    now = datetime.utcnow()
    expired_tokens = [
        token
        for token, pending_registration in PENDING_REGISTRATIONS.items()
        if pending_registration["expires_at"] <= now
    ]
    for token in expired_tokens:
        PENDING_REGISTRATIONS.pop(token, None)


def create_pending_registration(first_name: str, last_name: str, email: str, phone_number: str, password: str, next_path: str) -> str:
    """Store a short-lived registration preview without creating the account."""
    clean_pending_registrations()
    token = secrets.token_urlsafe(24)
    PENDING_REGISTRATIONS[token] = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone_number": phone_number,
        "password_hash": get_password_hash(password),
        "password_length": len(password),
        "next_path": safe_redirect_path(next_path, "/"),
        "expires_at": datetime.utcnow() + timedelta(seconds=REGISTRATION_CONFIRM_SECONDS),
    }
    return token


def set_session_cookie(response: Response, raw_token: str) -> None:
    """Attach the session token as an HTTP-only cookie for server-rendered pages."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=SECURE_SESSION_COOKIES,
    )
    response.delete_cookie(GUEST_COOKIE)


def get_user_from_token(db: Session, raw_token: str | None) -> models.User | None:
    """Resolve a raw bearer/cookie token to a live user account."""
    if not raw_token:
        return None

    session = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.token_hash == hash_token(raw_token),
            models.UserSession.revoked_at.is_(None),
            models.UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if not session:
        return None
    return db.get(models.User, session.user_id)


def get_current_user(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> models.User:
    """Require login before returning protected API data."""
    raw_token = None
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    elif session_cookie:
        raw_token = session_cookie

    user = get_user_from_token(db, raw_token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


def require_role(minimum_role: Literal["viewer", "operator", "admin"]):
    """Build a FastAPI dependency that enforces an operational role.

    Registered users may read monitoring data; operators may additionally
    import evidence, review evaluation reports and manage alert workflows.
    The database role is read on every request: changing a menu, URL, request
    body or browser-stored role cannot grant authority or retain a demoted role.
    """

    def dependency(current_user: models.User = Depends(get_current_user)) -> models.User:
        if not has_role(current_user, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{minimum_role.title()} role required.",
            )
        return current_user

    return dependency


def authorize_ingestion(x_ingest_token: str | None = Header(default=None)) -> None:
    """Check the optional deployment ingest key, preserving the local demo.

    Public deployments must configure this key and clients must supply it in
    X-Ingest-Token. A data_source label alone never authenticates hardware.
    """
    if INGEST_TOKEN and not secrets.compare_digest(x_ingest_token or "", INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="A valid ingest token is required.")


def get_optional_page_user(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Read the logged-in user for public Jinja2 pages, if one exists."""
    return get_user_from_token(db, session_cookie)


def template_context(request: Request, current_user: models.User | None = None, **extra) -> dict:
    """Common context shared by all pages."""
    # EmailJS explicitly designates these three identifiers as public browser
    # configuration. Whitelist them rather than exposing the server environment;
    # private keys, account passwords and session tokens never enter this JSON.
    emailjs_config = {
        "publicKey": os.getenv("FLOOD_EWS_EMAILJS_PUBLIC_KEY", "").strip(),
        "serviceId": os.getenv("FLOOD_EWS_EMAILJS_SERVICE_ID", "").strip(),
        "contactTemplateId": os.getenv("FLOOD_EWS_EMAILJS_CONTACT_TEMPLATE_ID", "").strip(),
    }
    emailjs_configured = all(emailjs_config.values())
    if current_user:
        first = (current_user.first_name or "").strip()
        last = (current_user.last_name or "").strip()
        user_display_name = f"{first} {last}".strip() or "User"
        user_initials = f"{first[0] if first else 'U'}{last[0] if last else ''}".upper()
        greeting_name = first or "User"
    else:
        user_display_name = "Guest visitor"
        user_initials = "GV"
        greeting_name = "Visitor"

    context = {
        "request": request,
        "current_user": current_user,
        "is_logged_in": current_user is not None,
        "user_role": current_user.role if current_user else "guest",
        "can_operate": bool(current_user and has_role(current_user, "operator")),
        "is_admin": bool(current_user and has_role(current_user, "admin")),
        "user_display_name": user_display_name,
        "user_initials": user_initials,
        "greeting_name": greeting_name,
        "contact_email": CONTACT_EMAIL,
        "contact_email_configured": bool(CONTACT_EMAIL),
        "emailjs_config": emailjs_config,
        "emailjs_configured": emailjs_configured,
    }
    context.update(extra)
    return context


def render_public(request: Request, template_name: str, current_user: models.User | None, **extra):
    """Render a page that is open to visitors and registered users."""
    return templates.TemplateResponse(request, template_name, template_context(request, current_user, **extra))


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Return a small project icon so browser requests do not produce 404 noise."""
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


def require_page_user(
    request: Request,
    current_user: models.User | None,
    next_path: str,
    minimum_role: Literal["viewer", "operator", "admin"] = "viewer",
):
    """Enforce the page boundary before rendering any protected content.

    Anonymous visitors get the login form, while an authenticated account
    with insufficient authority gets a 403 page (not another login loop).
    ``next_path`` is supplied by our routes, never used as a permission check.
    The corresponding APIs independently apply the same role requirements.
    """
    if not current_user:
        return RedirectResponse(url=f"/login?next={next_path}", status_code=status.HTTP_303_SEE_OTHER)
    if not has_role(current_user, minimum_role):
        return templates.TemplateResponse(
            request,
            "pages/access_denied.html",
            template_context(request, current_user, active_page="access_denied", required_role=minimum_role),
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return None


@app.get("/", include_in_schema=False)
def home_page(request: Request, current_user: models.User | None = Depends(get_optional_page_user)):
    account_deleted = request.query_params.get("account_deleted") == "1"
    return render_public(request, "pages/home.html", current_user, active_page="home", account_deleted=account_deleted)


@app.get("/about", include_in_schema=False)
def about_page(request: Request, current_user: models.User | None = Depends(get_optional_page_user)):
    return render_public(request, "pages/about.html", current_user, active_page="about")


@app.get("/projects", include_in_schema=False)
def projects_page(request: Request, current_user: models.User | None = Depends(get_optional_page_user)):
    return render_public(request, "pages/projects.html", current_user, active_page="projects")


@app.get("/news", include_in_schema=False)
def news_page(request: Request, current_user: models.User | None = Depends(get_optional_page_user)):
    return render_public(request, "pages/news.html", current_user, active_page="news")


@app.get("/contact", include_in_schema=False)
def contact_page(request: Request, current_user: models.User | None = Depends(get_optional_page_user)):
    return render_public(request, "pages/contact.html", current_user, active_page="contact")


@app.get("/guest", include_in_schema=False)
def guest_entry(current_user: models.User | None = Depends(get_optional_page_user)):
    """Guest browsing grants no account privileges and never logs a user out."""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response = RedirectResponse(url="/news", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key=GUEST_COOKIE, value="true", max_age=SESSION_SECONDS, httponly=False, samesite="lax")
    return response


@app.get("/login", include_in_schema=False)
def login_page(
    request: Request,
    next: str = Query(default="/"),
    current_user: models.User | None = Depends(get_optional_page_user),
):
    target = safe_redirect_path(next, "/")
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return render_public(request, "pages/auth/login.html", current_user, active_page="login", next_path=target)


@app.get("/register", include_in_schema=False)
def register_page(
    request: Request,
    next: str = Query(default="/"),
    current_user: models.User | None = Depends(get_optional_page_user),
):
    target = safe_redirect_path(next, "/")
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return render_public(request, "pages/auth/register.html", current_user, active_page="register", next_path=target)


@app.post("/login", include_in_schema=False)
def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next_path: str = Form(default="/"),
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        context = template_context(
            request,
            None,
            active_page="login",
            next_path=next_path,
            form_error="Invalid email or password.",
            submitted_email=email,
        )
        return templates.TemplateResponse(request, "pages/auth/login.html", context, status_code=status.HTTP_401_UNAUTHORIZED)

    token = create_user_session(db, user)
    response = RedirectResponse(url=safe_redirect_path(next_path, "/"), status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, token)
    return response


@app.post("/register", include_in_schema=False)
def register_form(
    request: Request,
    first_name: str | None = Form(default=None),
    last_name: str | None = Form(default=None),
    email: str | None = Form(default=None),
    phone_number: str | None = Form(default=None),
    password: str | None = Form(default=None),
    next_path: str = Form(default="/"),
    terms_accepted: str | None = Form(default=None),
    confirm: str | None = Form(default=None),
    pending_token: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if confirm == "yes":
        clean_pending_registrations()
        pending_registration = PENDING_REGISTRATIONS.get(pending_token or "")
        if not pending_registration:
            context = template_context(
                request,
                None,
                active_page="register",
                next_path=next_path,
                form_error="Your confirmation session expired. Please review the form again.",
                submitted_email=email or "",
                submitted_phone_number=phone_number or "",
                submitted_first_name=first_name or "",
                submitted_last_name=last_name or "",
            )
            return templates.TemplateResponse(request, "pages/auth/register.html", context, status_code=status.HTTP_400_BAD_REQUEST)

        if get_user_by_email(db, pending_registration["email"]):
            PENDING_REGISTRATIONS.pop(pending_token or "", None)
            context = template_context(
                request,
                None,
                active_page="register",
                next_path=next_path,
                form_error="An account with this email already exists.",
                submitted_email=pending_registration["email"],
                submitted_phone_number=pending_registration["phone_number"],
                submitted_first_name=pending_registration["first_name"],
                submitted_last_name=pending_registration["last_name"],
            )
            return templates.TemplateResponse(request, "pages/auth/register.html", context, status_code=status.HTTP_409_CONFLICT)

        user = models.User(
            first_name=pending_registration["first_name"],
            last_name=pending_registration["last_name"],
            email=pending_registration["email"],
            phone_number=pending_registration["phone_number"],
            password_hash=pending_registration["password_hash"],
            role="user",
            email_updates=True,
            sms_updates=True,
            whatsapp_updates=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        PENDING_REGISTRATIONS.pop(pending_token or "", None)
        token = create_user_session(db, user)

        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        set_session_cookie(response, token)
        return response

    normalized_email = (email or "").lower().strip()
    cleaned_first_name = (first_name or "").strip()
    cleaned_last_name = (last_name or "").strip()
    cleaned_phone_number = normalize_phone_number(phone_number)
    password_value = password or ""
    if (
        not cleaned_first_name
        or not cleaned_last_name
        or not valid_phone_number(cleaned_phone_number)
        or len(password_value) < 8
        or "@" not in normalized_email
        or "." not in normalized_email.split("@")[-1]
    ):
        context = template_context(
            request,
            None,
            active_page="register",
            next_path=next_path,
            form_error="Please check your name, email, phone number, and password before continuing.",
            submitted_email=email,
            submitted_phone_number=phone_number,
            submitted_first_name=first_name,
            submitted_last_name=last_name,
        )
        return templates.TemplateResponse(request, "pages/auth/register.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if terms_accepted != "yes":
        context = template_context(
            request,
            None,
            active_page="register",
            next_path=next_path,
            form_error="Please accept the terms and privacy policy before continuing.",
            submitted_email=email,
            submitted_phone_number=phone_number,
            submitted_first_name=first_name,
            submitted_last_name=last_name,
        )
        return templates.TemplateResponse(request, "pages/auth/register.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    if get_user_by_email(db, normalized_email):
        context = template_context(
            request,
            None,
            active_page="register",
            next_path=next_path,
            form_error="An account with this email already exists.",
            submitted_email=email,
            submitted_phone_number=phone_number,
            submitted_first_name=first_name,
            submitted_last_name=last_name,
        )
        return templates.TemplateResponse(request, "pages/auth/register.html", context, status_code=status.HTTP_409_CONFLICT)

    confirmation_token = create_pending_registration(
        cleaned_first_name,
        cleaned_last_name,
        normalized_email,
        cleaned_phone_number,
        password_value,
        next_path,
    )
    context = template_context(
        request,
        None,
        active_page="register",
        next_path=next_path,
        first_name=cleaned_first_name,
        last_name=cleaned_last_name,
        email=normalized_email,
        phone_number=cleaned_phone_number,
        masked_password="*" * len(password_value),
        pending_token=confirmation_token,
        expiry_minutes=REGISTRATION_CONFIRM_SECONDS // 60,
    )
    return templates.TemplateResponse(request, "pages/auth/confirm_register.html", context)


@app.post("/logout", include_in_schema=False)
def logout(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
):
    if session_cookie:
        session = db.query(models.UserSession).filter(models.UserSession.token_hash == hash_token(session_cookie)).first()
        if session:
            session.revoked_at = datetime.utcnow()
            db.commit()
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(GUEST_COOKIE)
    return response


def settings_context(
    request: Request,
    current_user: models.User,
    db: Session,
    **extra,
) -> dict:
    """Build settings context with recent user-submitted observations."""
    reports = (
        db.query(models.CommunityReport)
        .filter(models.CommunityReport.user_id == current_user.id)
        .order_by(models.CommunityReport.created_at.desc())
        .limit(5)
        .all()
    )
    return template_context(
        request,
        current_user,
        active_page="settings",
        reports=reports,
        community_reports_enabled=ENABLE_COMMUNITY_REPORTS,
        delete_feedback_reasons=DELETE_FEEDBACK_REASONS,
        **extra,
    )


@app.get("/settings", include_in_schema=False)
def settings_page(
    request: Request,
    updated: Literal["profile", "report"] | None = Query(default=None),
    current_user: models.User | None = Depends(get_optional_page_user),
    db: Session = Depends(get_db),
):
    redirect = require_page_user(request, current_user, "/settings")
    if redirect:
        return redirect
    return templates.TemplateResponse(request, "pages/settings.html", settings_context(request, current_user, db, updated=updated))


@app.post("/settings/profile", include_in_schema=False)
def update_profile(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone_number: str = Form(...),
    preferred_language: Literal["en", "ha", "fr", "ig", "yo"] = Form(default="en"),
    email_updates: str | None = Form(default=None),
    sms_updates: str | None = Form(default=None),
    whatsapp_updates: str | None = Form(default=None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    cleaned_first_name = first_name.strip()
    cleaned_last_name = last_name.strip()
    cleaned_phone_number = normalize_phone_number(phone_number)
    if not cleaned_first_name or not cleaned_last_name:
        context = settings_context(request, user, db, profile_error="First name and last name are required.")
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if not valid_phone_number(cleaned_phone_number):
        context = settings_context(request, user, db, profile_error="A valid phone number is required for SMS-capable account contact.")
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    user.first_name = cleaned_first_name
    user.last_name = cleaned_last_name
    user.phone_number = cleaned_phone_number
    user.preferred_language = preferred_language
    user.email_updates = email_updates == "yes"
    user.sms_updates = sms_updates == "yes"
    user.whatsapp_updates = whatsapp_updates == "yes"
    db.commit()
    return RedirectResponse(url="/settings?updated=profile", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/report", include_in_schema=False)
def submit_report(
    request: Request,
    title: str = Form(...),
    location: str = Form(...),
    message: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not ENABLE_COMMUNITY_REPORTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Community reporting is parked until supervisor approval.",
        )

    cleaned_title = title.strip()[:140]
    cleaned_location = location.strip()[:160]
    cleaned_message = message.strip()[:1200]
    if not cleaned_title or not cleaned_location or not cleaned_message:
        context = settings_context(request, current_user, db, report_error="Report title, location, and observation are required.")
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    report = models.CommunityReport(
        user_id=current_user.id,
        title=cleaned_title,
        location=cleaned_location,
        message=cleaned_message,
    )
    db.add(report)
    db.commit()
    return RedirectResponse(url="/settings?updated=report", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/settings/delete/request", include_in_schema=False)
def request_account_deletion(
    request: Request,
    delete_reason: Literal["found_alternative", "no_longer_needed", "bug_or_issue"] = Form(...),
    delete_feedback: str = Form(default=""),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start account deletion by generating a short-lived verification code."""
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    reason_label = DELETE_FEEDBACK_REASONS.get(delete_reason)
    if not reason_label:
        context = settings_context(request, user, db, delete_error="Please choose a reason before requesting a verification code.")
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    token, code, channels = create_pending_account_deletion(user, delete_reason, delete_feedback.strip())
    context = settings_context(
        request,
        user,
        db,
        delete_step="verify",
        deletion_token=token,
        deletion_code=code,
        deletion_channels=channels,
        selected_delete_reason=delete_reason,
        delete_feedback=delete_feedback.strip(),
        delete_reason_label=reason_label,
        delete_notice="We are sorry you have to go. A simulated verification code has been generated for this local prototype.",
    )
    return templates.TemplateResponse(request, "pages/settings.html", context)


@app.post("/settings/delete", include_in_schema=False)
def delete_account(
    request: Request,
    deletion_token: str = Form(...),
    verification_code: str = Form(...),
    confirm_delete: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the logged-in account only after code and DELETE confirmation."""
    user = db.get(models.User, current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    clean_pending_account_deletions()
    pending_deletion = PENDING_ACCOUNT_DELETIONS.get(deletion_token.strip())
    if not pending_deletion or pending_deletion["user_id"] != user.id:
        context = settings_context(request, user, db, delete_error="Your deletion verification code expired. Please request a new code.")
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    if pending_deletion["code_hash"] != hash_token(verification_code.strip()):
        context = settings_context(
            request,
            user,
            db,
            delete_step="verify",
            deletion_token=deletion_token,
            deletion_code=None,
            deletion_channels=account_channel_status(user),
            selected_delete_reason=pending_deletion["reason"],
            delete_feedback=pending_deletion["feedback"],
            delete_reason_label=DELETE_FEEDBACK_REASONS.get(pending_deletion["reason"], "Selected reason"),
            delete_error="The verification code is incorrect.",
        )
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    if confirm_delete.strip() != "DELETE":
        context = settings_context(
            request,
            user,
            db,
            delete_step="verify",
            deletion_token=deletion_token,
            deletion_code=None,
            deletion_channels=account_channel_status(user),
            selected_delete_reason=pending_deletion["reason"],
            delete_feedback=pending_deletion["feedback"],
            delete_reason_label=DELETE_FEEDBACK_REASONS.get(pending_deletion["reason"], "Selected reason"),
            delete_error="Type DELETE exactly before removing your account.",
        )
        return templates.TemplateResponse(request, "pages/settings.html", context, status_code=status.HTTP_400_BAD_REQUEST)

    log_account_notification(
        user,
        "account_deleted",
        "Your FloodWatch account has been deleted in the local prototype. If you did not initiate this process, contact the project administrator immediately.",
    )
    PENDING_ACCOUNT_DELETIONS.pop(deletion_token.strip(), None)
    db.query(models.CommunityReport).filter(models.CommunityReport.user_id == current_user.id).delete(synchronize_session=False)
    db.query(models.UserSession).filter(models.UserSession.user_id == current_user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()

    response = RedirectResponse(url="/?account_deleted=1", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(GUEST_COOKIE)
    return response


@app.get("/dashboard", include_in_schema=False)
def dashboard_page(
    request: Request,
    current_user: models.User | None = Depends(get_optional_page_user),
):
    return render_public(request, "pages/dashboard.html", current_user, active_page="dashboard")


@app.get("/data", include_in_schema=False)
def data_page(
    request: Request,
    current_user: models.User | None = Depends(get_optional_page_user),
):
    return render_public(request, "pages/data.html", current_user, active_page="data")


@app.get("/evaluation", include_in_schema=False)
def evaluation_page(
    request: Request,
    current_user: models.User | None = Depends(get_optional_page_user),
):
    """Only operators/admins may view detailed model/scenario evidence."""
    denied = require_page_user(request, current_user, "/evaluation", "operator")
    if denied is not None:
        return denied
    return templates.TemplateResponse(request, "pages/evaluation.html", template_context(request, current_user, active_page="evaluation"))


@app.get("/dashboard/", include_in_schema=False)
def dashboard_slash_redirect():
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/dashboard/pages/{legacy_path:path}", include_in_schema=False)
def old_static_page_redirect(legacy_path: str):
    """Redirect old static prototype URLs to the Jinja2 home page."""
    return RedirectResponse(url="/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


compute_rate_of_rise_m = current_state_service.compute_rate_of_rise_m


assess_record = current_state_service.assess_record
status_from_record = current_state_service.status_from_record


alert_channels = alert_service.channels
alert_to_public = alert_service.to_public


def scenario_to_public(run: models.ScenarioRun) -> dict:
    """Serialize one scenario run and parse its metrics snapshot."""
    try:
        metrics_snapshot = json.loads(run.metrics_snapshot_json or "{}")
    except json.JSONDecodeError:
        metrics_snapshot = {}
    return {
        "id": run.id,
        "station_id": run.station_id,
        "station_name": run.station_name,
        "scenario": run.scenario,
        "before_risk": run.before_risk,
        "after_risk": run.after_risk,
        "before_water_level_m": run.before_water_level_m,
        "after_water_level_m": run.after_water_level_m,
        "operator_id": run.operator_id,
        "operator_email": run.operator_email,
        "metrics_snapshot": metrics_snapshot,
        "created_at": run.created_at,
    }


record_alert_audit = alert_service.record_audit
persist_alert_event = alert_service.persist_event


def model_metrics_payload() -> dict:
    """Load saved model metrics and shape them for charts/reports."""
    metrics_path = BASE_DIR / "model_metrics.json"
    if metrics_path.exists():
        try:
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
    else:
        payload = {}

    return {
        "data_source": payload.get("data_source", "model metrics file not available"),
        "prediction_target": payload.get("prediction_target", "unknown"),
        "prediction_horizon_ticks": int(payload.get("prediction_horizon_ticks", 0) or 0),
        "baseline_warning_ratio": float(payload.get("baseline_warning_ratio", 0.0) or 0.0),
        "label_policy": payload.get("label_policy", {}),
        "results": payload.get("results", {}),
        "feature_importances": payload.get("feature_importances", {}),
        "generated_at": payload.get("generated_at"),
        "retrieved_at": datetime.now(timezone.utc),
        "train_samples": payload.get("train_samples"),
        "test_samples": payload.get("test_samples"),
    }


def _escape_pdf_text(value: object) -> str:
    """Escape characters that have special meaning inside a PDF text object."""
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def simple_pdf(title: str, lines: list[str]) -> bytes:
    """Create a small standards-compatible PDF using only built-in Python.

    This avoids adding a PDF dependency before provider/deployment choices are
    finalized. The output is intentionally simple: a title and wrapped evidence
    lines that can be downloaded during a defense or scenario review.
    """
    # Wrap and paginate rather than silently truncating metrics or guidance.
    text_lines = [title, ""]
    for line in lines:
        text_lines.extend(textwrap.wrap(str(line), width=88) or [""])
    pages = [text_lines[index:index + 44] for index in range(0, len(text_lines), 44)]
    page_ids = [4 + index * 2 for index in range(len(pages))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(f"{number} 0 R" for number in page_ids) + f"] /Count {len(pages)} >>").encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_id, page_lines in zip(page_ids, pages):
        commands = ["BT", "/F1 10 Tf", "50 790 Td"]
        for line in page_lines:
            commands.extend([f"({_escape_pdf_text(line)}) Tj", "0 -16 Td"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        objects.extend([
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id + 1} 0 R >>".encode("ascii"),
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ])
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


@app.post("/api/telemetry", response_model=models.TelemetryResponse, dependencies=[Depends(authorize_ingestion)])
def create_telemetry(reading: models.TelemetryCreate, db: Session = Depends(get_db)):
    """Receive one simulated or hardware telemetry reading and persist it."""
    return telemetry_service.ingest(
        db,
        reading,
        persist_alert_event=persist_alert_event,
    )


@app.get("/api/telemetry", response_model=list[models.TelemetryResponse])
def read_telemetry(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    data_source: Literal["simulated", "hardware"] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return the normalized telemetry-shaped history projection.

    The public compatibility contract is preserved while persistence is read
    from normalized observations, provenance and temporal thresholds.
    """
    return normalized_read_repository.list_evidence(
        db,
        skip=skip,
        limit=limit,
        data_source=data_source,
    )


@app.post("/api/telemetry/upload-csv", response_model=models.CsvUploadResult)
async def upload_telemetry_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Upload telemetry evidence from a CSV file as an operator-only action.

    Required columns match ``TelemetryCreate``. Values are passed through the
    same Pydantic validation as live REST/hardware readings, so CSV imports
    cannot bypass the API's safety checks.
    """
    _operator_email = operator.email  # Explicit dependency evidence for defense explanation.
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload a .csv telemetry file.")

    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file is too large for the prototype upload limit.")

    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV must be UTF-8 encoded.") from None

    required_columns = {
        "station_id",
        "station_name",
        "lat",
        "lon",
        "timestamp",
        "water_level_m",
        "danger_level_m",
        "rainfall_mm_hr",
        "flow_rate_m3s",
        "battery_pct",
        "signal",
    }
    reader = csv.DictReader(io.StringIO(csv_text), strict=True)
    try:
        # Parse before saving anything: malformed quotes and oversized fields
        # must produce a client error, not a server crash halfway through import.
        fieldnames = reader.fieldnames
        rows = list(reader)
    except csv.Error:
        raise HTTPException(status_code=422, detail="CSV contains malformed quoting or an oversized field.") from None
    if len(rows) > 2000:
        raise HTTPException(status_code=413, detail="Upload at most 2000 telemetry rows at a time.")
    if not fieldnames:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV header row is required.")
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise HTTPException(status_code=422, detail="CSV headers must not be duplicated.")
    missing_columns = sorted(required_columns - set(reader.fieldnames))
    if missing_columns:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"CSV missing required columns: {', '.join(missing_columns)}")

    accepted = 0
    errors: list[str] = []
    for line_number, row in enumerate(rows, start=2):
        if None in row or any(value is None for value in row.values()):
            errors.append(f"line {line_number}: field count does not match the CSV header")
            continue
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            payload = {name: row.get(name) for name in required_columns}
            payload["data_source"] = (row.get("data_source") or "simulated").strip() or "simulated"
            reading = models.TelemetryCreate(**payload)
        except ValidationError as exc:
            errors.append(f"line {line_number}: {exc.errors()[0]['msg']}")
            continue

        # CSV ingestion uses the same repository/dual-write boundary as REST
        # telemetry so normalized and compatibility persistence cannot drift.
        telemetry_service.ingest(
            db,
            reading,
            persist_alert_event=persist_alert_event,
        )
        accepted += 1

    return {"accepted": accepted, "rejected": len(errors), "errors": errors[:25]}


@app.get("/api/risk-status", response_model=list[models.RiskStatus])
def read_risk_status(
    data_source: Literal["simulated", "hardware", "hybrid"] | None = Query(default="hybrid"),
    language: Literal["en", "ha", "fr", "ig", "yo"] = Query(default="en"),
    db: Session = Depends(get_db),
):
    """Return newest-per-station risk, optionally filtered by data source."""
    return telemetry_service.risk_statuses(
        db,
        data_source=data_source,
        language=language,
        alert_channels=alert_channels(),
        risk_rank=RISK_RANK,
    )

@app.get("/api/alerts")
def get_recent_alerts(
    limit: int = 15,
    db: Session = Depends(get_db),
    actor: models.User | None = Depends(get_optional_page_user),
):
    """Return recent alert events for the situation room.

    Persistent alert workflow records are returned first. Older JSONL
    simulation logs are used as a fallback so existing demo evidence remains
    visible after the database workflow was added.
    """
    safe_limit = max(1, min(limit, 50))
    persistent_alerts = (
        db.query(models.AlertEvent)
        .order_by(models.AlertEvent.updated_at.desc(), models.AlertEvent.id.desc())
        .limit(safe_limit)
        .all()
    )
    alerts = [alert_to_public(alert) for alert in persistent_alerts]
    # Station bulletins are shared with registered users. Internal operator
    # notes and staff account identifiers are not personal notifications and
    # must not be disclosed outside the operational role.
    if actor is None or not has_role(actor, "operator"):
        for alert in alerts:
            alert["operator_notes"] = None
            for field in ("acknowledged_by", "escalated_by", "resolved_by"):
                alert[field] = None
    # Avoid reintroducing resolved workflow items as new legacy-log duplicates.
    if alerts:
        return alerts
    log_path = notifications.NOTIFICATION_LOG_PATH
    if len(alerts) < safe_limit and log_path.exists():
        try:
            with log_path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines[-50:]):
                    line = line.strip()
                    if line:
                        try:
                            event = json.loads(line)
                            timestamp_value = event.get("timestamp") or datetime.now(timezone.utc).isoformat()
                            alerts.append({
                                "id": 0,
                                "station_id": event.get("station_id", "unknown"),
                                "station_name": event.get("station_name", "Unknown station"),
                                "data_source": event.get("data_source", "simulated"),
                                "risk_level": event.get("risk_level", "Moderate"),
                                "message": event.get("message", "A station status update was logged for review."),
                                "channels": event.get("channels", alert_channels()),
                                "status": "new",
                                "operator_notes": None,
                                "created_at": timestamp_value,
                                "updated_at": timestamp_value,
                                "acknowledged_by": None,
                                "acknowledged_at": None,
                                "escalated_by": None,
                                "escalated_at": None,
                                "resolved_by": None,
                                "resolved_at": None,
                            })
                            if len(alerts) >= safe_limit:
                                break
                        except json.JSONDecodeError:
                            continue
        except OSError:
            pass

    if len(alerts) < 4:
        active_statuses = read_risk_status(data_source="hybrid", language="en", db=db)
        alert_worthy = [s for s in active_statuses if s.risk_level in ("Moderate", "High", "Severe")]
        for s in alert_worthy[:6]:
            timestamp_value = s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp)
            alerts.append({
                "id": 0,
                "station_id": s.station_id,
                "station_name": s.station_name,
                "risk_level": s.risk_level,
                "message": s.message,
                "channels": alert_channels(),
                "data_source": s.data_source,
                "status": "new",
                "operator_notes": None,
                "created_at": timestamp_value,
                "updated_at": timestamp_value,
                "acknowledged_by": None,
                "acknowledged_at": None,
                "escalated_by": None,
                "escalated_at": None,
                "resolved_by": None,
                "resolved_at": None,
            })

    return alerts[:safe_limit]


@app.post("/api/alerts/dispatch")
def dispatch_alert(
    payload: dict,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Log a simulated multi-channel alert note for a station without issuing commands."""
    station_id = str(payload.get("station_id") or "").strip()
    if not station_id:
        raise HTTPException(status_code=422, detail="station_id is required before an alert simulation can be logged")
    candidates = [
        item for item in telemetry_service.risk_statuses(
            db,
            data_source="hybrid",
            language="en",
            alert_channels=dict(CORE_ALERT_CHANNELS),
            risk_rank=RISK_RANK,
        )
        if item.station_id == station_id
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail="No telemetry exists for this station. Start the simulator or connect hardware first.")
    current = candidates[0]

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "station_id": station_id,
        "station_name": current.station_name,
        "data_source": current.data_source,
        "risk_level": current.risk_level,
        "message": f"Simulated alert bulletin logged: {current.message}",
        "channels": alert_channels(),
        "operator_id": operator.id,
        "operator_email": operator.email,
    }

    try:
        with notifications.NOTIFICATION_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass

    persisted = persist_alert_event(
        db,
        station_id,
        current.station_name,
        current.data_source,
        current.risk_level,
        event["message"],
    )
    if persisted:
        record_alert_audit(db, persisted, operator, "log_simulated_alert", persisted.status, persisted.status, "Simulated alert bulletin logged for review.")
        db.commit()

    return {"status": "success", "event": event, "alert": alert_to_public(persisted) if persisted else None}


def change_alert_status(
    alert_id: int,
    target_status: Literal["acknowledged", "escalated", "resolved"],
    action: str,
    payload: models.AlertActionRequest,
    db: Session,
    operator: models.User,
) -> dict:
    """HTTP-compatible wrapper around the alert workflow service."""
    try:
        return alert_service.change_status(
            db, alert_id, target_status, action, payload.notes, operator
        )
    except alert_service.AlertNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert event not found.")
    except alert_service.InvalidAlertTransitionError:
        raise HTTPException(status_code=409, detail="This alert status transition is not allowed. Refresh the alert queue.")


@app.post("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: int,
    payload: models.AlertActionRequest,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Mark an alert as acknowledged by an operator with optional notes."""
    return change_alert_status(alert_id, "acknowledged", "acknowledge", payload, db, operator)


@app.post("/api/alerts/{alert_id}/escalate")
def escalate_alert(
    alert_id: int,
    payload: models.AlertActionRequest,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Mark an alert as escalated for official review without issuing commands."""
    return change_alert_status(alert_id, "escalated", "escalate", payload, db, operator)


@app.post("/api/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: int,
    payload: models.AlertActionRequest,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Mark an alert as resolved after operator review."""
    return change_alert_status(alert_id, "resolved", "resolve", payload, db, operator)


@app.get("/api/alerts/{alert_id}/audit", response_model=list[models.AlertAuditPublic])
def read_alert_audit(
    alert_id: int,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Return the audit trail for one alert event."""
    _operator_email = operator.email  # Keeps dependency explicit and easy to explain.
    try:
        return alert_service.audit_trail(db, alert_id)
    except alert_service.AlertNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert event not found.")


@app.post("/api/scenario/run")
def run_scenario(
    payload: dict,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Inject a dynamic scenario reading for rapid demonstration."""
    station_id = str(payload.get("station_id") or "").strip()
    scenario = str(payload.get("scenario") or "flood").strip().lower()
    if not station_id:
        raise HTTPException(status_code=422, detail="station_id is required before a scenario can be applied")
    if scenario not in {"flood", "normal"}:
        raise HTTPException(status_code=422, detail="scenario must be either 'flood' or 'normal'")

    candidates = [
        item for item in telemetry_service.risk_statuses(
            db,
            data_source="hybrid",
            language="en",
            alert_channels=dict(CORE_ALERT_CHANNELS),
            risk_rank=RISK_RANK,
        )
        if item.station_id == station_id
    ]
    if not candidates:
        raise HTTPException(status_code=404, detail="No telemetry exists for this station. Start the simulator or connect hardware first.")
    current = candidates[0]

    danger = current.danger_level_m
    lat = current.lat
    lon = current.lon
    station_name = current.station_name
    current_w = current.water_level_m
    before_risk = current.risk_level

    if scenario == "flood":
        new_level = max(current_w, min(danger * 1.15, current_w + round(danger * 0.12, 2)))
        rainfall = round(random.uniform(22.0, 38.0), 1)
    else:
        new_level = max(0.0, current_w * 0.8)
        rainfall = round(random.uniform(0.0, 5.0), 1)

    # Scenario data is explicitly synthetic, but it must still traverse the
    # same dual-write/application boundary as every other telemetry source.
    # Direct legacy-only inserts would make the normalized /api/risk-status
    # consumer blind to the scenario after DB-4 promotion.
    scenario_reading = models.TelemetryCreate(
        station_id=station_id,
        station_name=station_name,
        data_source="simulated",
        lat=lat,
        lon=lon,
        timestamp=datetime.now(timezone.utc),
        water_level_m=round(new_level, 2),
        danger_level_m=danger,
        threshold_type=current.threshold_type,
        rainfall_mm_hr=rainfall,
        flow_rate_m3s=round(new_level * 10.5, 1),
        battery_pct=96.0,
        signal="online",
    )
    new_record = telemetry_service.ingest(
        db,
        scenario_reading,
        persist_alert_event=persist_alert_event,
    )
    assessment = assess_record(new_record, db)

    run = models.ScenarioRun(
        station_id=station_id,
        station_name=station_name,
        scenario=scenario,
        before_risk=before_risk,
        after_risk=assessment.risk_level,
        before_water_level_m=current_w,
        after_water_level_m=new_record.water_level_m,
        operator_id=operator.id,
        operator_email=operator.email,
        metrics_snapshot_json=json.dumps(model_metrics_payload(), default=str),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "status": "scenario_applied",
        "scenario_run": scenario_to_public(run),
        "station_id": station_id,
        "water_level_m": new_record.water_level_m,
        "danger_level_m": new_record.danger_level_m,
        "risk_level": assessment.risk_level,
        "message": assessment.message,
    }



@app.get("/api/weather-forecast", dependencies=[Depends(require_role("viewer"))])
def read_weather_forecast(
    latitude: float = Query(default=6.5244),
    longitude: float = Query(default=3.3792),
):
    """Expose short-term weather context without changing the trained risk model."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid map coordinates.")

    try:
        return get_forecast(latitude, longitude)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "provider": "Open-Meteo",
            "location": {"latitude": latitude, "longitude": longitude},
            "message": "Weather forecast is temporarily unavailable. Flood-risk telemetry remains active.",
        }


@app.get("/health", response_model=models.HealthStatus)
def health_check(response: Response, db: Session = Depends(get_db)):
    """Return a small deployment/CI health response."""
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
        service_status = "ok"
    except Exception:  # noqa: BLE001 - health endpoints should degrade cleanly.
        database_status = "unavailable"
        service_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": service_status,
        "database": database_status,
        "model_available": ml_model.model_available(),
        "news_provider": news_feeds.configured_provider(),
        "timestamp": datetime.now(timezone.utc),
    }


@app.get("/api/news-feed", response_model=models.NewsFeedResponse)
def read_news_feed(
    limit: int = Query(default=8, ge=1, le=20),
    refresh: bool = Query(default=False),
):
    """Return configured news/resource feed items, or an honest setup prompt."""
    return news_feeds.fetch_news(limit=limit, force_refresh=refresh)


@app.get("/api/model-evaluation", response_model=models.ModelEvaluationResponse, dependencies=[Depends(require_role("operator"))])
def read_model_evaluation():
    """Expose model metrics for the evaluation dashboard."""
    return model_metrics_payload()


@app.get("/api/model-evaluation/report.pdf", dependencies=[Depends(require_role("operator"))])
def download_model_evaluation_report():
    """Download a simple PDF report for the current saved model metrics."""
    metrics = model_metrics_payload()
    lines = [
        f"Data source: {metrics['data_source']}",
        f"Prediction target: {metrics['prediction_target']}",
        f"Horizon ticks: {metrics['prediction_horizon_ticks']}",
        f"Baseline warning ratio: {metrics['baseline_warning_ratio']}",
        "",
        "Model comparison:",
    ]
    for model_name, values in metrics.get("results", {}).items():
        lines.append(
            f"- {model_name}: accuracy={values.get('accuracy')}, precision={values.get('precision')}, "
            f"recall={values.get('recall')}, f1={values.get('f1')}, FP={values.get('false_positive')}, FN={values.get('false_negative')}"
        )
    lines.extend([
        "",
        "Safety note: metrics are simulator-generated evidence only, not field-validated flood performance.",
    ])
    return Response(
        content=simple_pdf("FloodWatch Model Evaluation Report", lines),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="floodwatch-model-evaluation.pdf"'},
    )


@app.get("/api/scenario-runs", response_model=list[models.ScenarioRunPublic])
def read_scenario_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Return recent operator scenario runs."""
    _operator_email = operator.email
    runs = (
        db.query(models.ScenarioRun)
        .order_by(models.ScenarioRun.created_at.desc(), models.ScenarioRun.id.desc())
        .limit(limit)
        .all()
    )
    return [scenario_to_public(run) for run in runs]


@app.get("/api/scenario-runs/{run_id}/report.pdf")
def download_scenario_report(
    run_id: int,
    db: Session = Depends(get_db),
    operator: models.User = Depends(require_role("operator")),
):
    """Download a PDF evidence report for one operator scenario run."""
    _operator_email = operator.email
    run = db.get(models.ScenarioRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario run not found.")
    payload = scenario_to_public(run)
    metrics = payload.get("metrics_snapshot", {})
    lines = [
        f"Scenario run ID: {run.id}",
        f"Station: {run.station_name} ({run.station_id})",
        f"Scenario: {run.scenario}",
        f"Before risk: {run.before_risk} at {run.before_water_level_m} m",
        f"After risk: {run.after_risk} at {run.after_water_level_m} m",
        f"Operator: {run.operator_email}",
        f"Created at: {run.created_at.isoformat()} UTC",
        "",
        f"Model target: {metrics.get('prediction_target', 'unknown')}",
        f"Model data source: {metrics.get('data_source', 'unknown')}",
        "",
        "Saved holdout evaluation snapshot; not accuracy measured on this one scenario reading.",
        "Decision-support note: this report records a scenario simulation; follow official guidance.",
    ]
    for name, values in metrics.get("results", {}).items():
        lines.append(f"{name}: accuracy={values.get('accuracy')}, F1={values.get('f1')}, FP={values.get('false_positive')}, FN={values.get('false_negative')}")
    return Response(
        content=simple_pdf("FloodWatch Scenario Run Report", lines),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="floodwatch-scenario-{run.id}.pdf"'},
    )


@app.get("/api/auth/me", response_model=models.UserPublic)
def read_current_account(current_user: models.User = Depends(get_current_user)):
    """Return the authenticated account profile and role."""
    return public_user(current_user)


@app.get("/api/admin/users", response_model=list[models.UserPublic])
def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    """Admin-only list of users and roles for local operator setup."""
    _admin_email = admin.email
    users = db.query(models.User).order_by(models.User.created_at.asc(), models.User.id.asc()).all()
    return [public_user(user) for user in users]


@app.patch("/api/admin/users/{user_id}/role", response_model=models.UserPublic)
def update_user_role(
    user_id: int,
    payload: models.RoleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role("admin")),
):
    """Admin-only role update for viewer/operator/admin access."""
    _admin_email = admin.email
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role == "admin" and payload.role != "admin" and db.query(models.User).filter_by(role="admin").count() <= 1:
        raise HTTPException(status_code=409, detail="The last administrator cannot be demoted through the API.")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return public_user(user)


@app.post("/api/auth/register", response_model=models.AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: models.UserRegister, response: Response, db: Session = Depends(get_db)):
    """Persist a real user account and return both token and session cookie."""
    normalized_email = payload.email.lower().strip()
    if get_user_by_email(db, normalized_email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")

    cleaned_phone_number = normalize_phone_number(payload.phone_number)
    if not valid_phone_number(cleaned_phone_number):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A valid phone number is required for SMS-capable account contact.")

    user = models.User(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=normalized_email,
        phone_number=cleaned_phone_number,
        password_hash=get_password_hash(payload.password),
        role="user",
        email_updates=True,
        sms_updates=True,
        whatsapp_updates=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_user_session(db, user)
    set_session_cookie(response, token)
    return {"message": "Account created successfully.", "user": public_user(user), "access_token": token}


@app.post("/api/auth/login", response_model=models.AuthResponse)
def login_user(payload: models.UserLogin, response: Response, db: Session = Depends(get_db)):
    """Validate credentials and return both token and session cookie."""
    user = get_user_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    token = create_user_session(db, user)
    set_session_cookie(response, token)
    return {"message": "Login successful.", "user": public_user(user), "access_token": token}
