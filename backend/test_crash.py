import requests

BASE_URL = "http://localhost:8001"

print("Registering...")
resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
    "email": "crash_test@docscope.io",
    "password": "password123",
    "first_name": "Crash",
    "last_name": "Test",
    "org_name": "Crash Org"
})
if resp.status_code == 400 and "already registered" in resp.text:
    pass

print("Logging in...")
resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
    "email": "crash_test@docscope.io",
    "password": "password123"
})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("Fetching processing docs...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/documents/processing", headers=headers)
    print("Processing Status:", r.status_code)
    print("Response:", r.text[:100])
except Exception as e:
    print("Exception on processing:", e)

print("Fetching folders...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/folders", headers=headers)
    print("Folders Status:", r.status_code)
    print("Response:", r.text[:100])
except Exception as e:
    print("Exception on folders:", e)

print("Fetching analytics...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/analytics/dashboard", headers=headers)
    print("Analytics Status:", r.status_code)
    print("Response:", r.text[:100])
except Exception as e:
    print("Exception on analytics:", e)
