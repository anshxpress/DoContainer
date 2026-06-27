import pytest
from fastapi import status

def test_tenant_isolation(client):
    # 1. Register User A in Org A
    user_a_payload = {
        "email": "user_a@orga.com",
        "password": "passwordA123",
        "first_name": "User",
        "last_name": "A",
        "org_name": "Org A"
    }
    response_a = client.post("/api/v1/auth/register", json=user_a_payload)
    assert response_a.status_code == status.HTTP_201_CREATED
    data_a = response_a.json()
    token_a = data_a["access_token"]
    org_a_id = data_a["organization"]["id"]

    # 2. Register User B in Org B
    user_b_payload = {
        "email": "user_b@orgb.com",
        "password": "passwordB123",
        "first_name": "User",
        "last_name": "B",
        "org_name": "Org B"
    }
    response_b = client.post("/api/v1/auth/register", json=user_b_payload)
    assert response_b.status_code == status.HTTP_201_CREATED
    data_b = response_b.json()
    token_b = data_b["access_token"]
    org_b_id = data_b["organization"]["id"]

    # 3. User A requests their own Org A resource (should succeed)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    response_self_a = client.get(f"/api/v1/tenant-test/{org_a_id}", headers=headers_a)
    assert response_self_a.status_code == status.HTTP_200_OK
    assert response_self_a.json()["org_id"] == org_a_id

    # 4. User A requests Org B's resource (should be rejected)
    response_cross_a = client.get(f"/api/v1/tenant-test/{org_b_id}", headers=headers_a)
    assert response_cross_a.status_code == status.HTTP_403_FORBIDDEN
    assert "Cross-tenant request rejected" in response_cross_a.json()["detail"]

    # 5. User B requests their own Org B resource (should succeed)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    response_self_b = client.get(f"/api/v1/tenant-test/{org_b_id}", headers=headers_b)
    assert response_self_b.status_code == status.HTTP_200_OK
    assert response_self_b.json()["org_id"] == org_b_id

    # 6. User B requests Org A's resource (should be rejected)
    response_cross_b = client.get(f"/api/v1/tenant-test/{org_a_id}", headers=headers_b)
    assert response_cross_b.status_code == status.HTTP_403_FORBIDDEN
    assert "Cross-tenant request rejected" in response_cross_b.json()["detail"]
