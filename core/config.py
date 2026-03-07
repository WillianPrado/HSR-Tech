from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Carrega variáveis do .env antes da configuração
load_dotenv()

class Settings(BaseSettings):
    
    OPENAI_API_KEY: str
    DEEP_SEEK_API_KEY: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_VERSION: str = "2024-04-10"
    STRIPE_START_PRICE_ID: str = ""
    STRIPE_MEDIUM_PRICE_ID: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_PUBLIC_KEY: str = ""
    PAYMENT_SUCCESS_URL: str = "http://localhost:3000/billing/success"
    PAYMENT_CANCEL_URL: str = "http://localhost:3000/billing/cancel"
    APP_ENV: str = "development"
    
    DATABASE_URL: str = "sqlite:///./sales.db"
    PYTHONPATH: str | None = None 
    SECRET_KEY: str 
    ALGORITHM: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_SECRET_KEY: str = "segredo"
    MAX_CONCURRENT_TRANSCRIPTIONS: int = 2
    TRANSCRIPTION_RETRY_ATTEMPTS: int = 5
    TRANSCRIPTION_RETRY_MIN_WAIT_SECONDS: int = 2
    TRANSCRIPTION_RETRY_MAX_WAIT_SECONDS: int = 30
    ANALYSIS_CREDITS_BASIC: int = 10
    ANALYSIS_CREDITS_PREMIUM: int = 30
    ANALYSIS_CREDITS_ENTERPRISE: int = 100
   
   
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  
        case_sensitive=False 
        
    )


settings = Settings()


def normalize_price_id(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""

    # Accept inline comments in .env like: price_123 # basic monthly
    if "#" in value:
        value = value.split("#", 1)[0].strip()

    # Remove accidental wrapping quotes.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()

    return value


def _is_placeholder(value: str) -> bool:
    normalized = normalize_price_id(value).lower()
    return (
        not normalized
        or normalized.startswith("price_xxxx")
        or normalized == "stripe_webhook_secret"
    )


def stripe_price_id_by_plan(plan_name: str) -> str | None:
    plan_map = {
        "basic": settings.STRIPE_START_PRICE_ID,
        "premium": settings.STRIPE_MEDIUM_PRICE_ID,
        "enterprise": settings.STRIPE_PRO_PRICE_ID,
    }
    price_id = normalize_price_id(plan_map.get(plan_name))
    return None if _is_placeholder(price_id or "") else price_id


def analysis_credits_by_plan(plan_name: str) -> int:
    normalized = (plan_name or "").strip().lower()
    plan_credits = {
        "basic": settings.ANALYSIS_CREDITS_BASIC,
        "premium": settings.ANALYSIS_CREDITS_PREMIUM,
        "enterprise": settings.ANALYSIS_CREDITS_ENTERPRISE,
    }
    return max(0, int(plan_credits.get(normalized, 0) or 0))


def should_enforce_stripe_strict_config() -> bool:
    return settings.APP_ENV.lower() in {"staging", "production"}


def validate_stripe_runtime_config() -> None:
    if not should_enforce_stripe_strict_config():
        return

    if _is_placeholder(settings.STRIPE_WEBHOOK_SECRET):
        raise ValueError("Invalid STRIPE_WEBHOOK_SECRET for non-local environment")

    for field_name, value in {
        "STRIPE_START_PRICE_ID": settings.STRIPE_START_PRICE_ID,
        "STRIPE_MEDIUM_PRICE_ID": settings.STRIPE_MEDIUM_PRICE_ID,
        "STRIPE_PRO_PRICE_ID": settings.STRIPE_PRO_PRICE_ID,
    }.items():
        if _is_placeholder(value):
            raise ValueError(f"Invalid {field_name} for non-local environment")