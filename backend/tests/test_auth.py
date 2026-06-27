import pytest
from fastapi import status

def test_user_registration_and_login(client):
    # 1. Register a new user and organization
    reg_payload = {
        "email": "testuser@docscope.io",
        "password": "strongpassword123",
        "first_name": "John",
        "last_name": "Doe",
        "org_name": "Docscope Inc"
    }
    
    response = client.post("/api/v1/auth/register", json=reg_payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "Organization Admin"
    assert data["user"]["email"] == "testuser@docscope.io"
    assert data["organization"]["name"] == "Docscope Inc"
    
    # Verify cookie was set
    assert "refresh_token" in response.cookies

    # 2. Try to register with the same email (should fail)
    response_dup = client.post("/api/v1/auth/register", json=reg_payload)
    assert response_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert response_dup.json()["detail"] == "A user with this email already exists."

    # 3. Log in with the registered credentials
    login_payload = {
        "email": "testuser@docscope.io",
        "password": "strongpassword123"
    }
    response_login = client.post("/api/v1/auth/login", json=login_payload)
    assert response_login.status_code == status.HTTP_200_OK
    data_login = response_login.json()
    assert "access_token" in data_login
    assert data_login["role"] == "Organization Admin"
    assert data_login["user"]["email"] == "testuser@docscope.io"
