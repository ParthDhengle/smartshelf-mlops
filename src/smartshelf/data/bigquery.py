from google.cloud import bigquery
import os
from dotenv import load_dotenv

load_dotenv()

def get_bigquery_client():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    return bigquery.Client()