import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

def get_llm(temperature=0.1, max_tokens=4096):
    """
    Returns the configured LLM based on .env
    Defaults to models/gemini-2.5-flash. optionally falls back to OpenAI gpt-4o-mini.
    Pass max_tokens=None to remove token cap (e.g. for resume extraction).
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=max_tokens
        )
    else:
        # Default to Gemini
        kwargs = dict(
            model="models/gemini-2.5-flash",
            temperature=temperature,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

# Constants for token management
MAX_JD_TOKENS = 8000      # truncate JD to this before passing to LLM
MAX_PROFILE_TOKENS = 3000 # truncate profile if needed
SCORING_CACHE = {}        # simple in-memory cache
