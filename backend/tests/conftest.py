# conftest.py — Supabase PostgreSQL test fixtures with transaction rollback isolation
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

# Ensure DATABASE_URL is set from .env before any app imports
# The .env should contain Supabase connection string
from app.db.session import get_engine


@pytest.fixture(scope="session")
def engine():
    """Session-scoped engine using Supabase from .env"""
    return get_engine()


@pytest.fixture(scope="function")
def db(engine):
    """
    Function-scoped database session with transaction rollback.
    
    Each test gets a clean database state by:
    1. Starting a transaction
    2. Running the test
    3. Rolling back the transaction (discarding all changes)
    
    This provides isolation without needing separate schemas or databases.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    # Create a session bound to this connection
    session = Session(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False)
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="function")
def db_with_commit(engine):
    """
    Alternative fixture for tests that need to commit (e.g., testing persistence).
    Creates a savepoint, allows commit, then rolls back to savepoint.
    """
    connection = engine.connect()
    transaction = connection.begin()
    
    session = Session(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False)
    
    # Create a savepoint for nested transaction support
    savepoint = connection.begin_nested()
    
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        nonlocal savepoint
        if transaction.nested and not transaction._parent.nested:
            savepoint = connection.begin_nested()
    
    try:
        yield session
    finally:
        event.remove(session, "after_transaction_end", restart_savepoint)
        session.close()
        transaction.rollback()
        connection.close()


# Helper for tests that need raw connection
@pytest.fixture(scope="function")
def connection(engine):
    """Raw connection for tests needing direct SQL execution"""
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()