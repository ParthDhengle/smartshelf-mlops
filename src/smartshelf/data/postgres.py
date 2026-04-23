from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

def get_postgres_engine():
    return create_engine(os.getenv("DATABASE_URL"))