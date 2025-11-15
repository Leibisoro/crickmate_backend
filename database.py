import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()  # load .env file

def get_connection():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT") or 3306),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        autocommit=True   # optional
    )
    return conn
                                                                                                  