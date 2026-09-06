"""Application settings, loaded from environment variables.

Every secret (Gemini key, Firebase service-account) lives here and is read from
the environment — never hard-coded, never shipped to the browser.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-flash-latest"

    # Firebase Admin credentials.
    # Provide EITHER a path to a service-account JSON file (local dev)
    # OR the full JSON as a single-line string (deployment / Render env var).
    firebase_credentials_path: str | None = None
    firebase_credentials_json: str | None = None

    # Limits
    max_note_words: int = 5000
    min_note_words: int = 5


settings = Settings()  # type: ignore[call-arg]
