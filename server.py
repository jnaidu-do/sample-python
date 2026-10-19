import os
import ssl
from urllib.parse import urlparse, unquote

import pg8000.native
from flask import Flask

app = Flask(__name__)

PREVIEW_PR = os.getenv("PREVIEW_PR", "")
PREVIEW_BRANCH = os.getenv("PREVIEW_BRANCH", "")
HEADLINE = "Hello from Sample Python, now reviewed in a preview app!"


def connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        return None
    u = urlparse(url)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return pg8000.native.Connection(
        user=unquote(u.username),
        password=unquote(u.password),
        host=u.hostname,
        port=u.port or 5432,
        database=u.path.lstrip("/"),
        ssl_context=ctx,
    )


def db_status():
    """Create the schema on first use (this is the app's 'migration') and bump a visit counter."""
    try:
        conn = connect()
        if conn is None:
            return None, "no DATABASE_URL configured"
        conn.run("CREATE TABLE IF NOT EXISTS visits (id serial PRIMARY KEY, at timestamptz DEFAULT now())")
        conn.run("INSERT INTO visits DEFAULT VALUES")
        count = conn.run("SELECT count(*) FROM visits")[0][0]
        version = conn.run("SHOW server_version")[0][0]
        conn.close()
        return count, "PostgreSQL " + version
    except Exception as e:  # keep the page up even if the DB is unreachable
        return None, "database error: %s" % e


@app.route("/")
def index():
    count, info = db_status()
    banner = ""
    if PREVIEW_PR:
        banner = (
            '<div style="background:#0069ff;color:#fff;padding:10px 16px;border-radius:8px;margin-bottom:24px">'
            "Preview app for pull request #%s &middot; branch <code>%s</code></div>" % (PREVIEW_PR, PREVIEW_BRANCH)
        )
    visits = "%s visit(s) recorded in this app's own database" % count if count is not None else "database not available"
    return (
        "<html><body style=\"font-family:system-ui,sans-serif;max-width:640px;margin:64px auto\">"
        "%s<h1>%s</h1><p>%s</p><p style=\"color:#666\">%s</p></body></html>" % (banner, HEADLINE, visits, info)
    )


@app.route("/healthz")
def healthz():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
