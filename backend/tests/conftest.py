import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.models.base import Base
from backend.app.core.db import get_db

# Use an in-memory SQLite database for testing to avoid connection errors when PG is offline
TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Create database engine using SQLite and initialize all schema tables
    # Set check_same_thread=False for sqlite multithreaded test sessions
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture(scope="function")
def db():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    # Create all tables on this in-memory SQLite database connection
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db):
    from fastapi.testclient import TestClient
    from backend.app.main import app

    # Override get_db dependency to use the test session
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
