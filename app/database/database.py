import sqlite3
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# SQLite requires this setting for FastAPI applications.
connect_args = {}

if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


# Create the database engine.
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug
)


# Create the session factory.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


# Base class for all database models.
class Base(DeclarativeBase):
    pass


# Provide a database session to API routes.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Safely apply incremental schema migrations to SQLite database without data loss."""
    if not settings.database_url.startswith("sqlite"):
        return

    # Extract db path from URL e.g. sqlite:///./splitsmart.db
    db_path = settings.database_url.replace("sqlite:///", "")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        def get_columns(table):
            try:
                return [row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            except Exception:
                return []

        # 1. Groups table migrations
        group_cols = get_columns('groups')
        if group_cols:
            if 'activity_type' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN activity_type VARCHAR(50) DEFAULT 'general'")
            if 'start_date' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN start_date DATETIME")
            if 'end_date' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN end_date DATETIME")
            if 'budget_paise' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN budget_paise INTEGER DEFAULT 0")
            if 'currency' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'")

        # 2. Members table migrations
        member_cols = get_columns('members')
        if member_cols:
            if 'role' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN role VARCHAR(30) DEFAULT 'member'")
            if 'phone' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN phone VARCHAR(30)")

        # 3. Expenses table migrations
        expense_cols = get_columns('expenses')
        if expense_cols:
            if 'category' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN category VARCHAR(50) DEFAULT 'General'")
            if 'merchant' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN merchant VARCHAR(150)")
            if 'expense_date' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN expense_date DATETIME")

        conn.commit()
        conn.close()

        # Create any new tables defined in models
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Migration warning: {e}")
