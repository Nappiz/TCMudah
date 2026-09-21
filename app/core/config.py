import os
from pydantic import BaseModel


class Settings(BaseModel):
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_ORIGIN: str = "http://localhost:3000"

    JWT_SECRET: str = "change_me"
    JWT_ALG: str = "HS256"
    JWT_EXPIRES_MIN: int = 120

    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    PAYMENTS_BUCKET: str = "payments"
    SUPABASE_TIMEOUT_SECONDS: int = 15
    SUPABASE_MAX_CONNECTIONS: int = 20
    SUPABASE_MAX_KEEPALIVE_CONNECTIONS: int = 10
    SYNC_WORKER_LIMIT: int = 20
    PAYMENT_UPLOAD_MAX_BYTES: int = 2_000_000
    PAYMENT_UPLOAD_TTL_MINUTES: int = 10
    PAYMENT_READ_TTL_SECONDS: int = 300

    BANK_NAME: str = "BANK_DEV"
    BANK_ACCOUNT: str = "7881292673"
    BANK_HOLDER: str = "BADRUZZAMAN NAFIZ"
    GROUP_LINK: str = "https://chat.whatsapp.com/JExaTob0k08CvPzJtSfN5l"


from functools import lru_cache

@lru_cache()
def get_settings() -> Settings:
    from dotenv import load_dotenv
    load_dotenv()

    return Settings(
        # App
        APP_ENV=os.getenv("APP_ENV", "dev"),
        APP_HOST=os.getenv("APP_HOST", "0.0.0.0"),
        APP_PORT=int(os.getenv("APP_PORT", "8000")),
        APP_ORIGIN=os.getenv("APP_ORIGIN", "http://localhost:3000"),

        # Auth / JWT
        JWT_SECRET=os.getenv("JWT_SECRET", "change_me"),
        JWT_ALG=os.getenv("JWT_ALG", "HS256"),
        JWT_EXPIRES_MIN=int(os.getenv("JWT_EXPIRES_MIN", "120")),

        # Supabase
        SUPABASE_URL=os.environ["SUPABASE_URL"],
        SUPABASE_SERVICE_ROLE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        PAYMENTS_BUCKET=os.getenv("PAYMENTS_BUCKET", "payments"),
        SUPABASE_TIMEOUT_SECONDS=int(os.getenv("SUPABASE_TIMEOUT_SECONDS", "15")),
        SUPABASE_MAX_CONNECTIONS=int(os.getenv("SUPABASE_MAX_CONNECTIONS", "20")),
        SUPABASE_MAX_KEEPALIVE_CONNECTIONS=int(
            os.getenv("SUPABASE_MAX_KEEPALIVE_CONNECTIONS", "10")
        ),
        SYNC_WORKER_LIMIT=int(os.getenv("SYNC_WORKER_LIMIT", "20")),
        PAYMENT_UPLOAD_MAX_BYTES=int(
            os.getenv("PAYMENT_UPLOAD_MAX_BYTES", "2000000")
        ),
        PAYMENT_UPLOAD_TTL_MINUTES=int(
            os.getenv("PAYMENT_UPLOAD_TTL_MINUTES", "10")
        ),
        PAYMENT_READ_TTL_SECONDS=int(
            os.getenv("PAYMENT_READ_TTL_SECONDS", "300")
        ),

        # Checkout / Payments
        BANK_NAME=os.getenv("BANK_NAME", "BANK_DEV"),
        BANK_ACCOUNT=os.getenv("BANK_ACCOUNT", "7881292673"),
        BANK_HOLDER=os.getenv("BANK_HOLDER", "BADRUZZAMAN NAFIZ"),
        GROUP_LINK=os.getenv("GROUP_LINK", "https://chat.whatsapp.com/JExaTob0k08CvPzJtSfN5l"),
    )
