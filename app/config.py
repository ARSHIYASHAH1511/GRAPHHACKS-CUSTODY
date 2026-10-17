import os
from dotenv import load_dotenv

load_dotenv()

FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_GRAPH: str = os.getenv("FALKORDB_GRAPH", "custody")
APP_ENV: str = os.getenv("APP_ENV", "development")
