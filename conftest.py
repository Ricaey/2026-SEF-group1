"""pytest fixtures for ADMIN subsystem tests."""
import os
import pytest
import httpx

BASE_URL = os.getenv("ADMIN_BASE_URL", "http://localhost:8002")
API = "/api/v1/admin"
DB_PASSWORD = os.getenv("DB_PASSWORD", None)

# Seed accounts from seed.py
ACCOUNTS = {
    "normal_admin": "Admin@123",
    "senior_admin": "Admin@123",
    "sys_admin": "Admin@123",
    "audit_admin": "Admin@123",
}

ROLES = {
    "normal_admin": "NORMAL_ADMIN",
    "senior_admin": "SENIOR_ADMIN",
    "sys_admin": "SYSTEM_ADMIN",
    "audit_admin": "AUDIT_ADMIN",
}


def make_auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TokenStore:
    """Mutable token cache.  Tests that change passwords call refresh() to update."""

    def __init__(self):
        self._tokens = {}

    def init(self, client: httpx.Client):
        for username, password in ACCOUNTS.items():
            resp = client.post(f"{API}/auth/login", json={"username": username, "password": password})
            if resp.status_code == 200 and resp.json().get("success"):
                self._tokens[username] = resp.json()["data"]["token"]
            else:
                self._tokens[username] = None

    def get(self, username: str) -> str | None:
        return self._tokens.get(username)

    def refresh(self, client: httpx.Client, username: str, password: str | None = None):
        """Re-login and update cached token.  Call after restoring a changed password."""
        pwd = password or ACCOUNTS.get(username, "")
        resp = client.post(f"{API}/auth/login", json={"username": username, "password": pwd})
        if resp.status_code == 200 and resp.json().get("success"):
            self._tokens[username] = resp.json()["data"]["token"]
            return self._tokens[username]
        return None


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def client():
    """Session-scoped HTTP client."""
    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(10.0)) as c:
        yield c


@pytest.fixture(scope="session")
def store(client):
    """TokenStore — initialised once per session, mutated by password-change tests."""
    s = TokenStore()
    s.init(client)
    return s


# Thin function-scoped fixtures that read from the mutable TokenStore.
# After a password-change test calls store.refresh(), these automatically
# return the updated token for the next test function.

@pytest.fixture
def tokens(store):
    return {u: store.get(u) for u in ACCOUNTS}


@pytest.fixture
def normal_token(store):
    return store.get("normal_admin")


@pytest.fixture
def senior_token(store):
    return store.get("senior_admin")


@pytest.fixture
def system_token(store):
    return store.get("sys_admin")


@pytest.fixture
def audit_token(store):
    return store.get("audit_admin")


@pytest.fixture
def normal_admin_id(client, system_token):
    """Get normal_admin's admin_id."""
    resp = client.get(f"{API}/admins", headers=make_auth(system_token))
    items = resp.json()["data"]["items"]
    for a in items:
        if a["username"] == "normal_admin":
            return a["admin_id"]
    return None


# ---------------------------------------------------------------------------
# database helpers
# ---------------------------------------------------------------------------

def db_connect():
    """Optional MySQL connection for database-level assertions."""
    if not DB_PASSWORD:
        return None
    try:
        import pymysql
        return pymysql.connect(
            host="localhost", user="root", password=DB_PASSWORD,
            database="admin_db", charset="utf8mb4",
        )
    except Exception:
        return None


def db_unlock_user(username: str):
    """Manually unlock a user in the database."""
    db = db_connect()
    if db is None:
        return False
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE admin_info SET status='active', failed_attempts=0, lock_until=NULL "
            "WHERE username=%s", (username,)
        )
        db.commit()
        db.close()
        return True
    except Exception:
        return False
