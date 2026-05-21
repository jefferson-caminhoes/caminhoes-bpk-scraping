from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017/caminhoes_bpk"
    rabbitmq_url: str = "amqp://localhost:5672"
    api_base_url: str = "http://localhost:3000"
    api_integration_token: str = ""
    # Credenciais do admin da API para obter JWT automaticamente
    api_admin_email: str = "admin@empresa.com"
    api_admin_password: str = "change-me"
    stakeholder_secret_key: str = ""
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "phi3:mini"
    scraping_cron: str = "*/30 * * * *"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
