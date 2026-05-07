import logging
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, set_refresh_cookies, unset_jwt_cookies
)
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator, ValidationError
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
import bcrypt

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Pydantic schema untuk validasi input login
class LoginSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

    @field_validator("username", mode="before")
    @classmethod
    def username_alphanumeric(cls, v):
        if not isinstance(v, str):
            raise ValueError("Username must be a string")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username hanya boleh alphanumeric, underscore, atau dash")
        return v.lower()

# Pydantic schema untuk validasi input registrasi
class RegisterSchema(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    nama_toko: str = Field(..., min_length=2, max_length=100)

    @field_validator("username", mode="before")
    @classmethod
    def username_alphanumeric(cls, v):
        if not isinstance(v, str):
            raise ValueError("Username must be a string")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username hanya boleh alphanumeric, underscore, atau dash")
        return v.lower()

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    # Validasi input — 400 kalau schema tidak sesuai
    if not request.is_json or not request.json:
        return jsonify({"error": "Request harus berupa JSON"}), 400

    try:
        payload = LoginSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    # Cek kredensial
    try:
        user = db.users.find_one({"username": payload.username})
        if not user or not bcrypt.checkpw(payload.password.encode('utf-8'), user["password"]):
            return jsonify({"msg": "Invalid credentials"}), 401

        # Generate tokens
        access_token = create_access_token(
            identity=user["username"],
            additional_claims={"role": user["role"]}
        )
        refresh_token = create_refresh_token(identity=user["username"])

        resp = make_response(jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {"username": user["username"], "role": user["role"]}
        }), 200)
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        return resp

    except Exception:
        logger.exception("Unexpected error in login")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user = get_jwt_identity()
        user = db.users.find_one({"username": current_user})
        role = user["role"] if user else "user"
        new_token = create_access_token(identity=current_user, additional_claims={"role": role})
        return jsonify(access_token=new_token), 200
    except Exception:
        logger.exception("Unexpected error in refresh")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    try:
        current_user = get_jwt_identity()
        user = db.users.find_one({"username": current_user})
        role = user["role"] if user else "user"
        return jsonify({
            "username": current_user,
            "role": role
        }), 200
    except Exception:
        logger.exception("Unexpected error in get_current_user")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("3 per minute")
def register():
    if not request.is_json or not request.json:
        return jsonify({"error": "Request harus berupa JSON"}), 400

    # Validasi schema
    try:
        payload = RegisterSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    # Simpan ke DB
    try:
        hashed_pw = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt())
        user_doc = {
            "username": payload.username,
            "password": hashed_pw,
            "nama_toko": payload.nama_toko,
            "role": "owner",  # user yang daftar sendiri jadi owner toko mereka
            "created_at": datetime.now(timezone.utc),
        }
        # Pastikan unique index ada sebelum insert
        db.users.create_index("username", unique=True, background=True)
        db.users.insert_one(user_doc)

        # Auto-login setelah register
        access_token = create_access_token(
            identity=payload.username,
            additional_claims={"role": "owner"}
        )
        refresh_token = create_refresh_token(identity=payload.username)

        resp = make_response(jsonify({
            "msg": "Registrasi berhasil",
            "access_token": access_token,
            "user": {"username": payload.username, "role": "owner"}
        }), 201)
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        return resp

    except DuplicateKeyError:
        return jsonify({"error": f"Username '{payload.username}' sudah digunakan"}), 409
    except Exception:
        logger.exception("Unexpected error in register")
        return jsonify({"error": "Internal server error"}), 500
