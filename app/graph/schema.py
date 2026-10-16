from app.graph.client import get_graph

def initialize_schema():
    graph = get_graph()
    indexes = [
        "CREATE INDEX FOR (c:Claim) ON (c.id)",
        "CREATE INDEX FOR (s:Source) ON (s.id)",
        "CREATE INDEX FOR (e:Evidence) ON (e.id)",
        "CREATE INDEX FOR (a:Agent) ON (a.id)",
        "CREATE INDEX FOR (sess:Session) ON (sess.id)",
        "CREATE INDEX FOR (d:Decision) ON (d.id)"
    ]
    for idx_query in indexes:
        try:
            graph.query(idx_query)
        except Exception:
            pass