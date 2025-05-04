import os

DATABASE_USER = os.getenv("DATABASE_USER", "photoserv")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "photoserv")
DATABASE_NAME = os.getenv("DATABASE_NAME", "photoserv")
DATABASE_HOST = os.getenv("DATABASE_HOST", "database")
DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")