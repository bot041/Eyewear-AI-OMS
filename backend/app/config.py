from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "AI Eyewear OMS"
    secret_key: str = "eyewear-oms-secret-key-demo"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    database_url: str = "sqlite:///./oms.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,https://eyewareaioms-eceestvdx-bhuvan-kambad-s-projects.vercel.app"

    # AI / ML configuration
    kimi_api_key: str = ""
    kimi_api_base: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"
    enable_llm_explanations: bool = False
    enable_recommended_actions: bool = False
    llm_timeout_seconds: int = 8

    # Persisted model artifacts
    ai_model_dir: str = "./app/models/ai"
    tat_model_file: str = "tat_regressor.pkl"
    breach_model_file: str = "breach_classifier.pkl"

    # Alert provider configuration
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_from_email: str = "samasur018@gmail.com"
    alert_to_email: str = "samasur018@gmail.com"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_whatsapp_to: str = ""

    # Resend email configuration
    resend_api_key: str = ""
    operations_email: str = "samasur018@gmail.com"
    email_from: str = "samasur018@gmail.com"

    class Config:
        env_file = ".env"

settings = Settings()
