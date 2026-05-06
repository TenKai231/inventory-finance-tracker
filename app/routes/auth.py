from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Pydantic schema untuk validasi input
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

# Mock user database (ganti dengan MongoDB users collection untuk production)
MOCK_USERS = {
    "admin": {"password": "secure123", "role": "owner"},
    "kasir": {"password": "kasir123", "role": "cashier"}
}

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per minute")  # ✅ Cegah brute force
def login():
    try:
        payload = LoginSchema(**request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    user = MOCK_USERS.get(payload.username)
    if not user or user["password"] != payload.password:
        return jsonify({"msg": "Invalid credentials"}), 401
    
    # Generate tokens
    access_token = create_access_token(identity=payload.username, additional_claims={"role": user["role"]})
    refresh_token = create_refresh_token(identity=payload.username)
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {"username": payload.username, "role": user["role"]}
    }), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    current_user = get_jwt_identity()
    # Ambil role dari user (mock)
    role = MOCK_USERS.get(current_user, {}).get("role", "user")
    new_token = create_access_token(identity=current_user, additional_claims={"role": role})
    return jsonify(access_token=new_token), 200

@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    current_user = get_jwt_identity()
    claims = MOCK_USERS.get(current_user, {})
    return jsonify({
        "username": current_user,
        "role": claims.get("role", "user")
    }), 200
