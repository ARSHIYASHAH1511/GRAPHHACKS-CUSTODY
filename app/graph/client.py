import os
from falkordb import FalkorDB

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", 6379))
GRAPH_NAME = os.getenv("FALKORDB_GRAPH", "custody")

def get_graph():
    client = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    return client.select_graph(GRAPH_NAME)