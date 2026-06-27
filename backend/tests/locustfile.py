import uuid
import random
import io
from locust import HttpUser, task, between

class DocscopeUser(HttpUser):
    # Simulated think time between tasks (1 to 5 seconds)
    wait_time = between(1, 5)

    def on_start(self):
        """
        Called when a simulated user starts.
        Registers a new unique user and organization, obtaining an auth token.
        """
        self.email = f"loadtest_{uuid.uuid4().hex[:10]}@example.com"
        self.password = "StrongPass123!"
        self.first_name = "Load"
        self.last_name = "Tester"
        self.org_name = f"LoadTestOrg_{uuid.uuid4().hex[:6]}"
        self.token = None

        # Call register endpoint
        payload = {
            "email": self.email,
            "password": self.password,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "org_name": self.org_name
        }
        
        with self.client.post("/api/v1/auth/register", json=payload, catch_response=True) as response:
            if response.status_code == 201:
                data = response.json()
                self.token = data.get("access_token")
            else:
                response.failure(f"Registration failed: {response.text}")

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}"
        } if self.token else {}

    @task(3)
    def search_documents(self):
        """Simulate searching for documents."""
        if not self.token:
            return
        
        queries = [
            "financial reports for 2025",
            "security policy and compliance",
            "malware scan criteria",
            "architecture overview",
            "api endpoints specs"
        ]
        
        payload = {
            "query": random.choice(queries),
            "top_k": 10
        }
        
        self.client.post(
            "/api/v1/search",
            json=payload,
            headers=self.headers,
            name="/api/v1/search"
        )

    @task(2)
    def chat_ask(self):
        """Simulate sending questions to the chat/ask assistant (Server-Sent Events)."""
        if not self.token:
            return
        
        questions = [
            "What documents are processed?",
            "How do I configure the API?",
            "Is there any malware detected?",
            "Can I scan doc files?",
            "What is Qdrant used for?"
        ]
        
        question = random.choice(questions)
        # Note: the chat route takes query parameters and returns text/event-stream
        params = {
            "query": question,
            "top_k": 5
        }
        
        with self.client.post(
            "/api/v1/chat/ask",
            params=params,
            headers=self.headers,
            name="/api/v1/chat/ask",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                # We can stream a bit of the response or read it all
                # The response will be event-stream formatted
                content = response.content
                if b"data:" in content:
                    response.success()
                else:
                    response.failure("Received empty or invalid event-stream")
            else:
                response.failure(f"Chat failed with status {response.status_code}")

    @task(1)
    def upload_document(self):
        """Simulate uploading a text document."""
        if not self.token:
            return
        
        # Create a mock text file in memory
        file_content = f"DOCSCOPE stress testing document content. UUID: {uuid.uuid4()}.\n" * 10
        file_bytes = io.BytesIO(file_content.encode('utf-8'))
        
        files = {
            "file": (f"stress_doc_{uuid.uuid4().hex[:8]}.txt", file_bytes, "text/plain")
        }
        
        data = {
            "folder_id": ""  # optional parent folder
        }
        
        # FastAPI /upload route takes multipart/form-data
        self.client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/v1/documents/upload"
        )

    @task(1)
    def view_dashboard_analytics(self):
        """Simulate visiting the dashboard analytics metrics endpoint."""
        if not self.token:
            return
            
        self.client.get(
            "/api/v1/analytics/dashboard",
            headers=self.headers,
            name="/api/v1/analytics/dashboard"
        )
