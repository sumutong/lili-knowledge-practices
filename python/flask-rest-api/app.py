#!/usr/bin/env python3
"""
Flask 全栈 RESTful API 服务
依赖: pip install flask flask-sqlalchemy flask-cors pyjwt bcrypt marshmallow gunicorn
启动: python app.py
"""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Flask, Blueprint, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from marshmallow import Schema, fields, validate, ValidationError
from sqlalchemy import func, text

# ─── 应用初始化 ─────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "postgresql://postgres:***@localhost:5432/flask_api"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_EXPIRATION_HOURS"] = 24

CORS(app, resources={r"/api/*": {"origins": "*"}})
db = SQLAlchemy(app)

# ─── 数据模型 ───────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="user")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    posts = db.relationship("Post", backref="author", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="draft")  # draft | published | archived
    tags = db.Column(db.String(500), default="")
    view_count = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "content": self.content,
            "status": self.status,
            "tags": self.tags.split(",") if self.tags else [],
            "view_count": self.view_count,
            "user_id": self.user_id,
            "author": self.author.username if self.author else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# ─── Marshmallow 验证 Schema ───────────────────────────────
class RegisterSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True)


class PostSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    content = fields.Str(required=True, validate=validate.Length(min=1))
    status = fields.Str(validate=validate.OneOf(["draft", "published", "archived"]))
    tags = fields.List(fields.Str(), load_default=[])


class PostQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    status = fields.Str(validate=validate.OneOf(["draft", "published", "archived"]))
    search = fields.Str()
    tag = fields.Str()

# ─── JWT 工具 ───────────────────────────────────────────────
def generate_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token 已过期")
    except jwt.InvalidTokenError:
        raise ValueError("无效的 Token")

# ─── 认证装饰器 ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "缺少认证 Token"}), 401
        try:
            payload = decode_token(auth_header[7:])
            user = db.session.get(User, payload["sub"])
            if not user or not user.is_active:
                return jsonify({"success": False, "error": "用户不存在或已被禁用"}), 401
            g.current_user = user
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify({"success": False, "error": "需要管理员权限"}), 403
        return f(*args, **kwargs)
    return decorated

# ─── 错误处理 ───────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(e):
    return jsonify({"success": False, "error": "请求参数错误"}), 400


@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "资源未找到"}), 404


@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return jsonify({"success": False, "error": "服务器内部错误"}), 500

# ─── 认证 Blueprint ─────────────────────────────────────────
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    try:
        data = RegisterSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "error": "验证失败", "details": e.messages}), 422

    if User.query.filter(
        db.or_(User.username == data["username"], User.email == data["email"])
    ).first():
        return jsonify({"success": False, "error": "用户名或邮箱已存在"}), 409

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    token = generate_token(user)
    return jsonify({"success": True, "data": {"user": user.to_dict(), "token": token}}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = LoginSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "error": "验证失败", "details": e.messages}), 422

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"success": False, "error": "用户名或密码错误"}), 401
    if not user.is_active:
        return jsonify({"success": False, "error": "账户已被禁用"}), 403

    token = generate_token(user)
    return jsonify({"success": True, "data": {"user": user.to_dict(), "token": token}})


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"success": True, "data": g.current_user.to_dict()})

# ─── 用户 Blueprint ─────────────────────────────────────────
user_bp = Blueprint("users", __name__, url_prefix="/api/users")


@user_bp.route("", methods=["GET"])
@login_required
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    pagination = db.paginate(
        db.select(User).order_by(User.id.desc()),
        page=page, per_page=per_page, max_per_page=100,
    )
    return jsonify({
        "success": True,
        "data": [u.to_dict() for u in pagination.items],
        "meta": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    })


@user_bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "用户未找到"}), 404
    return jsonify({"success": True, "data": user.to_dict()})


@user_bp.route("/<int:user_id>", methods=["PATCH"])
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "用户未找到"}), 404

    data = request.get_json() or {}
    if "email" in data:
        user.email = data["email"]
    if "role" in data:
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = data["is_active"]
    db.session.commit()
    return jsonify({"success": True, "data": user.to_dict()})


@user_bp.route("/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"success": False, "error": "用户未找到"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True, "message": "用户已删除"})

# ─── 文章 Blueprint ─────────────────────────────────────────
post_bp = Blueprint("posts", __name__, url_prefix="/api/posts")


def generate_slug(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    base_slug = slug
    counter = 1
    while Post.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


@post_bp.route("", methods=["GET"])
def list_posts():
    try:
        query_params = PostQuerySchema().load(request.args)
    except ValidationError as e:
        return jsonify({"success": False, "error": "查询参数错误", "details": e.messages}), 422

    q = db.select(Post)

    # 非管理员只能看到已发布的
    is_admin = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_token(auth_header[7:])
            user = db.session.get(User, payload["sub"])
            is_admin = user and user.role == "admin"
        except Exception:
            pass

    if not is_admin:
        q = q.where(Post.status == "published")
    elif query_params.get("status"):
        q = q.where(Post.status == query_params["status"])

    if query_params.get("search"):
        search = f"%{query_params['search']}%"
        q = q.where(db.or_(Post.title.ilike(search), Post.content.ilike(search)))

    if query_params.get("tag"):
        q = q.where(Post.tags.contains(query_params["tag"]))

    q = q.order_by(Post.created_at.desc())

    page = query_params["page"]
    per_page = query_params["per_page"]
    pagination = db.paginate(q, page=page, per_page=per_page, max_per_page=100)

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in pagination.items],
        "meta": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        },
    })


@post_bp.route("/<slug>", methods=["GET"])
def get_post(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        return jsonify({"success": False, "error": "文章未找到"}), 404

    # 增加阅读量
    post.view_count = (post.view_count or 0) + 1
    db.session.commit()

    return jsonify({"success": True, "data": post.to_dict()})


@post_bp.route("", methods=["POST"])
@login_required
def create_post():
    try:
        data = PostSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "error": "验证失败", "details": e.messages}), 422

    post = Post(
        title=data["title"],
        slug=generate_slug(data["title"]),
        content=data["content"],
        status=data.get("status", "draft"),
        tags=",".join(data.get("tags", [])),
        user_id=g.current_user.id,
    )
    db.session.add(post)
    db.session.commit()
    return jsonify({"success": True, "data": post.to_dict()}), 201


@post_bp.route("/<slug>", methods=["PUT"])
@login_required
def update_post(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        return jsonify({"success": False, "error": "文章未找到"}), 404
    if post.user_id != g.current_user.id and g.current_user.role != "admin":
        return jsonify({"success": False, "error": "无权修改此文章"}), 403

    try:
        data = PostSchema().load(request.get_json() or {})
    except ValidationError as e:
        return jsonify({"success": False, "error": "验证失败", "details": e.messages}), 422

    post.title = data["title"]
    post.content = data["content"]
    post.status = data.get("status", post.status)
    post.tags = ",".join(data.get("tags", []))
    db.session.commit()
    return jsonify({"success": True, "data": post.to_dict()})


@post_bp.route("/<slug>", methods=["DELETE"])
@login_required
def delete_post(slug):
    post = Post.query.filter_by(slug=slug).first()
    if not post:
        return jsonify({"success": False, "error": "文章未找到"}), 404
    if post.user_id != g.current_user.id and g.current_user.role != "admin":
        return jsonify({"success": False, "error": "无权删除此文章"}), 403

    db.session.delete(post)
    db.session.commit()
    return jsonify({"success": True, "message": "文章已删除"})

# ─── 注册 Blueprint ─────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(user_bp)
app.register_blueprint(post_bp)


# ─── 健康检查 ───────────────────────────────────────────────
@app.route("/api/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    return jsonify({"status": "ok", "database": db_status, "timestamp": datetime.now().isoformat()})


# ─── 数据库初始化 CLI ──────────────────────────────────────
@app.cli.command("init-db")
def init_db():
    """创建所有数据库表"""
    db.create_all()
    # 创建默认管理员
    if not User.query.filter_by(username="admin").first():
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("✓ 默认管理员已创建 (admin / admin123)")
    print("✓ 数据库初始化完成")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
