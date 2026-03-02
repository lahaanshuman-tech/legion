from flask import request, session, send_from_directory, jsonify, render_template
from flask_socketio import emit
from flask import redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy
import os

# =========================
# GLOBAL DB (correct pattern)
# =========================
db = SQLAlchemy()

User = None
Application = None
Message = None


# =========================
# INIT DB (called from server)
# =========================
def init_db(app):
    global User, Application, Message

    # 🔥 DO NOT set DB URI here — server.py must do it
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("SQLALCHEMY_DATABASE_URI not set before init_db")

    db.init_app(app)

    # -------- MODELS --------
    class UserModel(db.Model):
        __tablename__ = "users"
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(100), unique=True, nullable=False)
        password_hash = db.Column(db.String(200), nullable=False)
        role = db.Column(db.String(20), default="member")

    class ApplicationModel(db.Model):
        __tablename__ = "applications"
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(100), nullable=False)
        password_hash = db.Column(db.String(200), nullable=False)
        reason = db.Column(db.String(300))
        status = db.Column(db.String(20), default="pending")
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class MessageModel(db.Model):
        __tablename__ = "messages"
        id = db.Column(db.Integer, primary_key=True)
        sender_id = db.Column(db.Integer)
        text = db.Column(db.Text)
        created_at = db.Column(
            db.DateTime,
            default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))
        )
        expires_at = db.Column(db.DateTime)

    # expose models globally
    User = UserModel
    Application = ApplicationModel
    Message = MessageModel

    globals()["User"] = User
    globals()["Application"] = Application
    globals()["Message"] = Message

    # create tables + admin
    with app.app_context():
        db.create_all()

        admin_user = os.getenv("ADMIN_USER", "admin_master")
        admin_pass = os.getenv("ADMIN_PASS", "very_strong_password")

        if not User.query.filter_by(username=admin_user).first():
            admin_obj = User(
                username=admin_user,
                password_hash=generate_password_hash(admin_pass),
                role="admin",
            )
            db.session.add(admin_obj)
            db.session.commit()


# =========================
# ROUTES
# =========================
def register_routes(app):

    @app.route("/frontend/<path:path>")
    def serve_frontend(path):
        return send_from_directory("frontend", path)

    # ---------- universal password ----------
    @app.route("/api/uni-pass", methods=["POST"])
    def uni_pass():
        data = request.json or {}
        if data.get("password") == os.getenv("SITE_PASSWORD"):
            session["site_access"] = True
            return {"status": "ok"}
        return {"status": "denied"}, 401

    # ---------- login ----------
    @app.route("/api/login", methods=["POST"])
    def login():
        if not session.get("site_access"):
            return {"error": "no access"}, 403

        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return {"error": "missing credentials"}, 400

        user = User.query.filter_by(username=username).first()

        if not user:
            return {"error": "invalid username"}, 401

        if check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["role"] = user.role
            return {"status": "ok"}

        return {"error": "invalid password"}, 401

    # ---------- dashboard ----------
    @app.route("/api/dashboard")
    def dashboard():
        if not session.get("user_id"):
            return {"error": "login required"}, 401

        user = User.query.get(session["user_id"])
        return {"username": user.username, "role": user.role}

    # ---------- application submit ----------
    @app.route("/api/m/submit-form", methods=["POST"])
    def submit_application():
        data = request.json or {}

        username = data.get("username")
        password = data.get("password")
        reason = data.get("reason", "")

        if not username or not password:
            return {"error": "missing fields"}, 400

        if User.query.filter_by(username=username).first():
            return {"error": "username taken"}, 400

        hashed_pw = generate_password_hash(password)

        app_obj = Application(
            username=username,
            password_hash=hashed_pw,
            reason=reason,
        )
        db.session.add(app_obj)
        db.session.commit()

        return {"status": "application_submitted"}

    # ---------- chat history ----------
    @app.route("/api/m/chat-hist")
    def chat_hist():
        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        # delete expired
        Message.query.filter(Message.expires_at < now).delete()
        db.session.commit()

        msgs = Message.query.order_by(Message.created_at).all()

        return jsonify({
            "messages": [
                {
                    "username": (
                        User.query.get(m.sender_id).username
                        if User.query.get(m.sender_id)
                        else "Unknown"
                    ),
                    "text": m.text,
                    "created_at": m.created_at.isoformat(),
                }
                for m in msgs
            ]
        })

    # ---------- members ----------
    @app.route("/api/m/mem-list")
    def mem_list():
        users = User.query.filter_by(role="member").all()
        return jsonify({"members": [u.username for u in users]})

    # ---------- games ----------
    @app.route("/api/m/game-list")
    def game_list():
        return jsonify({"games": ["Cricket", "Lock and Key ", "Ghost in the Grave Yard", "Rivals", "World Of Tanks"]})

    # ================= ADMIN =================

    @app.route("/api/admin/application-list")
    def admin_applications():
        if session.get("role") != "admin":
            return {"error": "admin only"}, 403

        apps = Application.query.all()
        return jsonify({
            "applications": [
                {
                    "username": a.username,
                    "reason": a.reason,
                    "status": a.status,
                    "created_at": a.created_at.isoformat(),
                }
                for a in apps
            ]
        })

    @app.route("/api/admin/approve-app", methods=["POST"])
    def approve_app():
        if session.get("role") != "admin":
            return {"error": "admin only"}, 403

        data = request.json or {}
        username = data.get("username")

        app_obj = Application.query.filter_by(username=username).first()
        if not app_obj:
            return {"error": "application not found"}, 404

        new_user = User(
            username=app_obj.username,
            password_hash=app_obj.password_hash,
            role="member",
        )

        db.session.add(new_user)
        app_obj.status = "approved"
        db.session.commit()

        return {"status": "member_created"}

    @app.route("/api/admin/reject-app", methods=["POST"])
    def reject_app():
        if session.get("role") != "admin":
            return {"error": "admin only"}, 403

        data = request.json or {}
        username = data.get("username")

        app_obj = Application.query.filter_by(username=username).first()
        if not app_obj:
            return {"error": "application not found"}, 404

        app_obj.status = "rejected"
        db.session.commit()

        return {"status": "application_rejected"}


    @app.route("/chat")
    def chat_page():
        if not session.get("site_access"):
            return redirect(url_for("home"))

        if not session.get("user_id"):
            return redirect(url_for("home"))

        return render_template("chat.html")

# =========================
# SOCKET LOGIC
# =========================
def register_socket(socketio):

    @socketio.on("send_msg")
    def handle_message(data):
        if not session.get("user_id"):
            return

        text = (data or {}).get("text")
        if not text:
            return

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        expires = now + timedelta(hours=2)

        msg = Message(
            sender_id=session["user_id"],
            text=text,
            created_at=now,
            expires_at=expires,
        )
        db.session.add(msg)
        db.session.commit()

        user = User.query.get(session["user_id"])

        emit(
            "receive_msg",
            {
                "username": user.username,
                "text": text,
                "created_at": now.isoformat(),
            },
            broadcast=True,
        )