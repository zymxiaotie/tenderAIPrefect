# utils/db.py
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool
from config import Config

db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=Config().DATABASE_URL)

@contextmanager
def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)