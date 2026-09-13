"""Grant a role to an existing account from the trusted server terminal.

Run beside main.py, using the same FLOOD_EWS_DATABASE_URL as the service.
Registration never grants privileged access merely for claiming an email.
"""

import argparse

from sqlalchemy import func
from database import SessionLocal
from models import User


def assign_role(db, email: str, role: str) -> User:
    """Resolve one existing account; refuse typos rather than creating users."""
    if role not in {"viewer", "operator", "admin"}:
        raise ValueError("Role must be viewer, operator or admin.")
    user = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    if user is None:
        raise ValueError("Account not found. Register and confirm the account first.")
    user.role = role
    db.commit()
    db.refresh(user)
    return user


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Existing account email; no password is needed here.")
    parser.add_argument("--role", choices=["viewer", "operator", "admin"], required=True)
    arguments = parser.parse_args()
    with SessionLocal() as db:
        try:
            user = assign_role(db, arguments.email, arguments.role)
        except ValueError as error:
            parser.exit(1, f"{error}\n")
        print(f"Updated account {user.id}: role={user.role}. Refresh the dashboard.")
