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
    echo=False
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
            if 'is_archived' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN is_archived BOOLEAN DEFAULT 0")
            if 'archived_at' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN archived_at DATETIME")
            if 'created_by_user_id' not in group_cols:
                cur.execute("ALTER TABLE groups ADD COLUMN created_by_user_id INTEGER")

        # 2. Members table migrations
        member_cols = get_columns('members')
        if member_cols:
            if 'role' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN role VARCHAR(30) DEFAULT 'member'")
            if 'phone' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN phone VARCHAR(30)")
            if 'user_id' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN user_id INTEGER")
            if 'custom_role_id' not in member_cols:
                cur.execute("ALTER TABLE members ADD COLUMN custom_role_id INTEGER")

        # 3. Expenses table migrations
        expense_cols = get_columns('expenses')
        if expense_cols:
            if 'category' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN category VARCHAR(50) DEFAULT 'General'")
            if 'merchant' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN merchant VARCHAR(150)")
            if 'expense_date' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN expense_date DATETIME")
            if 'activity_id' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN activity_id INTEGER")
            if 'notes' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN notes VARCHAR(500)")
            if 'status' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN status VARCHAR(20) DEFAULT 'confirmed'")
            if 'updated_at' not in expense_cols:
                cur.execute("ALTER TABLE expenses ADD COLUMN updated_at DATETIME")

        # 4. Settlements table migrations
        settlement_cols = get_columns('settlements')
        if settlement_cols:
            if 'notes' not in settlement_cols:
                cur.execute("ALTER TABLE settlements ADD COLUMN notes VARCHAR(500)")
            if 'parent_settlement_id' not in settlement_cols:
                cur.execute("ALTER TABLE settlements ADD COLUMN parent_settlement_id INTEGER")
            if 'verified_by_member_id' not in settlement_cols:
                cur.execute("ALTER TABLE settlements ADD COLUMN verified_by_member_id INTEGER")
            if 'updated_at' not in settlement_cols:
                cur.execute("ALTER TABLE settlements ADD COLUMN updated_at DATETIME")

            settle_sql_row = cur.execute("SELECT sql FROM sqlite_master WHERE name='settlements'").fetchone()
            if settle_sql_row and "cancelled" not in (settle_sql_row[0] or ""):
                cur.execute("PRAGMA foreign_keys=off;")
                cur.execute("ALTER TABLE settlements RENAME TO _settlements_old;")
                cur.execute("""
                    CREATE TABLE settlements (
                        id INTEGER NOT NULL, 
                        group_id INTEGER NOT NULL, 
                        from_member_id INTEGER NOT NULL, 
                        to_member_id INTEGER NOT NULL, 
                        amount_paise INTEGER NOT NULL, 
                        status VARCHAR(20) NOT NULL, 
                        payment_provider VARCHAR(50), 
                        provider_reference VARCHAR(200), 
                        created_at DATETIME NOT NULL, 
                        completed_at DATETIME, 
                        notes VARCHAR(500), 
                        parent_settlement_id INTEGER, 
                        verified_by_member_id INTEGER, 
                        updated_at DATETIME, 
                        PRIMARY KEY (id), 
                        CONSTRAINT check_settlement_amount_positive CHECK (amount_paise > 0), 
                        CONSTRAINT check_different_settlement_members CHECK (from_member_id != to_member_id), 
                        CONSTRAINT check_settlement_status CHECK (status IN ('pending', 'completed', 'failed', 'cancelled')), 
                        FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
                        FOREIGN KEY(from_member_id) REFERENCES members (id), 
                        FOREIGN KEY(to_member_id) REFERENCES members (id)
                    );
                """)
                cur.execute("INSERT INTO settlements SELECT * FROM _settlements_old;")
                cur.execute("DROP TABLE _settlements_old;")
                cur.execute("PRAGMA foreign_keys=on;")

        # 5. Expense evidences table migrations
        evidence_cols = get_columns('expense_evidences')
        if evidence_cols:
            if 'activity_id' not in evidence_cols:
                cur.execute("ALTER TABLE expense_evidences ADD COLUMN activity_id INTEGER")

        conn.commit()
        conn.close()

        # Create any new tables defined in models (users, activities, custom_categories, etc.)
        from app.database import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Migration warning: {e}")
