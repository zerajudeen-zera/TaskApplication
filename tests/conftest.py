import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import app, get_db_connection
from werkzeug.security import generate_password_hash
import bcrypt

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def setup_test_user():
    """Ensure testuser exists before each test with a hashed password."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username=%s", ("testuser",))
    

    hashed_pw = bcrypt.hashpw("testpass".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor.execute(
        "INSERT INTO users (username, password) VALUES (%s, %s)",
        ("testuser", hashed_pw)
    )

    conn.commit()
    cursor.close()
    conn.close()
