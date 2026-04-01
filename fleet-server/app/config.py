from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    database_url: str = "sqlite:///./fleet.db"
    update_packages_dir: str = "./packages"
    server_base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"


settings = Settings()
