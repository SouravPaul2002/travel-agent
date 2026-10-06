from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings

print("Configured Model:", settings.gemini_model)
llm = ChatGoogleGenerativeAI(
    model=settings.gemini_model,
    google_api_key=settings.google_api_key,
)
print("Invoking LLM...")
response = llm.invoke("Reply with the single word: ok")
print("LLM Response:", response.content)
