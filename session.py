from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI RBAC Microservice"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "ADMIN"
    POSTGRES_DB: str = "courriel"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    JWT_SECRET_KEY: str = "mysecretkey"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


settings = Settings()