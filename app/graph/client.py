import os
from falkordb import FalkorDB

def get_client():
    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    user = os.getenv("FALKORDB_USER", None)
    password = os.getenv("FALKORDB_PASSWORD", None)

    kwargs = {"host": host, "port": port}
    if user:
        kwargs["username"] = user
    if password:
        kwargs["password"] = password

    return FalkorDB(**kwargs)

def get_graph(graph_name: str = "custody"):
    db = get_client()
    return db.select_graph(graph_name)