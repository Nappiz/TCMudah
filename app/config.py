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

    BANK_NAME: str = "BANK_DEV"
    BANK_ACCOUNT: str = "7881292673"
    BANK_HOLDER: str = "BADRUZZAMAN NAFIZ"
    GROUP_LINK: str = "https://chat.whatsapp.com/GtwoxPC0N2nGP9Ay8Wa13g?mode=wwt"


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

        # Checkout / Payments
        BANK_NAME=os.getenv("BANK_NAME", "BANK_DEV"),
        BANK_ACCOUNT=os.getenv("BANK_ACCOUNT", "7881292673"),
        BANK_HOLDER=os.getenv("BANK_HOLDER", "BADRUZZAMAN NAFIZ"),
        GROUP_LINK=os.getenv("GROUP_LINK", "https://chat.whatsapp.com/GtwoxPC0N2nGP9Ay8Wa13g?mode=wwt"),
    )
