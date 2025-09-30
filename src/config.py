import os
from dotenv import load_dotenv
load_dotenv()

DB_URL = os.getenv("DB_URL", "sqlite:///./finnews.db")
MODEL_DIR = os.getenv("MODEL_DIR", "./models")
ENV = os.getenv("ENV", "dev")
