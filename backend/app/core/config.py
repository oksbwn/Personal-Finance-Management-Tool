import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "WealthFam"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "duckdb:///./family_finance_v3.duckdb"
    
    # Security
    SECRET_KEY: str = "CHANGE_THIS_TO_A_SECURE_SECRET_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    model_config = ConfigDict(case_sensitive=True)

settings = Settings()
