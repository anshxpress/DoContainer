from backend.app.core.config import settings
from typing import Optional

class LLMProvider:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        if self.provider == "gemini":
            import google.generativeai as genai
            if settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
            
    def generate_content(self, prompt: str) -> Optional[str]:
        if self.provider == "mock":
            return "This is a mock response."
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"LLM Error: {e}")
            return None

llm_service = LLMProvider()
