from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models import User


def promote_user_to_admin(
    session: Session,
    *,
    username: str | None = None,
    email: str | None = None,
) -> int | None:
    """Promote one existing user and return only their database identifier."""
    if (username is None) == (email is None):
        raise ValueError("Provide exactly one user identifier.")

    criterion = User.username == username if username is not None else User.email == email
    user = session.scalar(select(User).where(criterion))
    if user is None:
        return None

    user.role = "admin"
    session.commit()
    return user.id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote an existing user to administrator.")
    identifier = parser.add_mutually_exclusive_group(required=True)
    identifier.add_argument("--username")
    identifier.add_argument("--email")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Delay session construction so --help works without database credentials.
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        promoted_user_id = promote_user_to_admin(
            session,
            username=args.username,
            email=args.email,
        )

    if promoted_user_id is None:
        print("No matching user found.", file=sys.stderr)
        return 1

    print(f"Promoted user id: {promoted_user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
