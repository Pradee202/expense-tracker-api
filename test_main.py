import uuid
from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_home():
    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "Expense Tracker API is running!"
    }


def test_register_and_login():
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    password = "testpassword123"

    register_response = client.post(
        "/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password
        }
    )

    assert register_response.status_code == 200

    login_response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200

    login_data = login_response.json()

    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"

def test_protected_route():
    username = "protecteduser123"
    password = "testpassword123"

    client.post(
        "/register",
        json={
            "username": username,
            "email": "protecteduser123@example.com",
            "password": password
        }
    )

    login_response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/protected",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    assert response.json() == {
        "message": "You are authenticated",
        "username": username
    }


def test_protected_route_without_token():
    response = client.get("/protected")

    assert response.status_code == 401

def test_expense_crud():
    username = f"expenseuser_{uuid.uuid4().hex[:8]}"
    password = "testpassword123"

    # Register user
    register_response = client.post(
        "/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password
        }
    )

    assert register_response.status_code == 200

    # Login
    login_response = client.post(
        "/login",
        data={
            "username": username,
            "password": password
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Create expense
    create_response = client.post(
        "/expenses",
        json={
            "title": "Test Food",
            "amount": 500,
            "category": "Food",
            "date": "2026-09-23"
        },
        headers=headers
    )

    assert create_response.status_code == 200

    expense = create_response.json()

    assert expense["title"] == "Test Food"
    assert expense["amount"] == 500
    assert expense["category"] == "Food"
    assert expense["user_id"] > 0

    expense_id = expense["id"]

    # Get expense
    get_response = client.get(
        f"/expenses/{expense_id}",
        headers=headers
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == expense_id

    # Update expense
    update_response = client.put(
        f"/expenses/{expense_id}",
        json={
            "title": "Updated Food",
            "amount": 750,
            "category": "Food",
            "date": "2026-09-23"
        },
        headers=headers
    )

    assert update_response.status_code == 200

    updated_expense = update_response.json()

    assert updated_expense["title"] == "Updated Food"
    assert updated_expense["amount"] == 750

    # Delete expense
    delete_response = client.delete(
        f"/expenses/{expense_id}",
        headers=headers
    )

    assert delete_response.status_code == 200

    assert delete_response.json() == {
        "message": "Expense deleted successfully"
    }

    # Verify expense no longer exists
    get_deleted_response = client.get(
        f"/expenses/{expense_id}",
        headers=headers
    )

    assert get_deleted_response.status_code == 404

def test_user_expense_isolation():
    # Create User A
    username_a = f"user_a_{uuid.uuid4().hex[:8]}"
    password_a = "testpassword123"

    client.post(
        "/register",
        json={
            "username": username_a,
            "email": f"{username_a}@example.com",
            "password": password_a
        }
    )

    # Login User A
    login_a = client.post(
        "/login",
        data={
            "username": username_a,
            "password": password_a
        }
    )

    token_a = login_a.json()["access_token"]

    headers_a = {
        "Authorization": f"Bearer {token_a}"
    }

    # User A creates an expense
    expense_response = client.post(
        "/expenses",
        json={
            "title": "Private Expense",
            "amount": 1000,
            "category": "Personal",
            "date": "2026-09-23"
        },
        headers=headers_a
    )

    assert expense_response.status_code == 200

    expense_id = expense_response.json()["id"]

    # Create User B
    username_b = f"user_b_{uuid.uuid4().hex[:8]}"
    password_b = "testpassword123"

    client.post(
        "/register",
        json={
            "username": username_b,
            "email": f"{username_b}@example.com",
            "password": password_b
        }
    )

    # Login User B
    login_b = client.post(
        "/login",
        data={
            "username": username_b,
            "password": password_b
        }
    )

    token_b = login_b.json()["access_token"]

    headers_b = {
        "Authorization": f"Bearer {token_b}"
    }

    # User B tries to access User A's expense
    response = client.get(
        f"/expenses/{expense_id}",
        headers=headers_b
    )

    assert response.status_code == 404