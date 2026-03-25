from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    database_url: str = "sqlite:///./fleet.db"

    class Config:
        env_file = ".env"


settings = Settings()
