"""
Pytest fixtures for Nusa Matra Data Hub tests.
Sets up a temporary seeded SQLite database and test client.
"""

import os
import sys
import asyncio
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test-client host and security headers need deterministic configuration before
# any test module imports app.config/app.main during collection.
os.environ.setdefault(
    "NM_ALLOWED_HOSTS",
    '["test","testserver","localhost","127.0.0.1","api.nusamatra.site"]',
)
os.environ.setdefault("NM_RATE_LIMIT_REPORT_ONLY", "true")


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """
    Create and seed a test database before any tests run.
    Uses the seed_db.py script in synchronous mode.
    """
    test_db = str(Path(__file__).parent.parent / "data" / "nusa_matra_demo.db")

    # Only seed if DB doesn't exist yet
    if not os.path.exists(test_db):
        # Run seed script
        seed_script = Path(__file__).parent.parent / "data" / "seed_db.py"
        if seed_script.exists():
            import subprocess
            result = subprocess.run(
                [sys.executable, str(seed_script)],
                cwd=str(Path(__file__).parent.parent),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                pytest.fail(f"Seed script failed:\n{result.stderr}")

    # Point app config to this DB
    os.environ["NM_DATABASE_PATH"] = test_db
    yield


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client for the FastAPI app."""
    # Import after env setup so config picks up test DB path
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
