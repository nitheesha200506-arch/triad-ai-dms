
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017/"
    )

    DATABASE_NAME = os.getenv(
        "DATABASE_NAME",
        "triad_dms"
    )

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    JWT_ACCESS_TOKEN_EXPIRES = 3600

    MAX_CONTENT_LENGTH = 11 * 1024 * 1024
