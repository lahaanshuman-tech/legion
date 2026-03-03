from dotenv import load_dotenv
import os

# =========================
# LOAD ENV FIRST
# =========================
load_dotenv()

from flask import Flask, render_template, send_from_directory, session
from flask_cors import CORS
from flask_socketio import SocketIO

# 🔥 import AFTER dotenv
from logic import register_routes, register_socket, init_db

# =========================
# CREATE APP
# =========================
app = Flask(
    __name__,
    static_folder="frontend",
    template_folder="templates"
)

# ✅ IMPORTANT: allow cookies for sessions
CORS(app, supports_credentials=True)

# =========================
# SECURITY
# =========================
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "dev-secret-change-me"
)

# =========================
# DATABASE (SUPABASE)
# =========================
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError("DATABASE_URL missing in .env")

# Supabase sometimes gives postgres://
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# =========================
# SOCKET.IO
# =========================
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    manage_session=True   # 🔥 ADD THIS
)

# =========================
# INIT SYSTEMS
# =========================
init_db(app)
register_routes(app)
register_socket(socketio)

# =========================
# ROOT ROUTE (FIXED FLOW)
# =========================
@app.route("/")
def home():
    # 🔐 Step 1: universal site gate
    if not session.get("site_access"):
        return send_from_directory("frontend", "gate.html")

    # 🔐 Step 2: logged in?
    if not session.get("user_id"):
        return send_from_directory("frontend", "login.html")

    # 🔐 Step 3: admin vs member
    if session.get("role") == "admin":
        return send_from_directory("frontend", "admin.html")

    # default member
    return send_from_directory("frontend", "dashboard.html")


# =========================
# CHAT PAGE (PROTECTED)
# =========================


# =========================
# RUN
# =========================
if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        debug=True
    )