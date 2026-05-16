from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import limiter, db
from app.models.schemas import StaffCreateSchema, StaffUpdateSchema
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from werkzeug.security import generate_password_hash
import logging
import random
import string

logger = logging.getLogger(__name__)

staff_bp = Blueprint('staff', __name__, url_prefix='/api/staff')

def serialize_doc(doc):
    if not doc:
        return doc
    doc['_id'] = str(doc.get('_id', ''))
    if 'password' in doc:
        del doc['password']
    return doc

# Middleware untuk check role owner
def owner_required(fn):
    def wrapper(*args, **kwargs):
        current_user = get_jwt_identity()
        user = db.users.find_one({"username": current_user})
        if not user or user.get("role") != "owner":
            return jsonify({"error": "Akses ditolak. Hanya owner yang diizinkan."}), 403
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@staff_bp.route('/summary', methods=['GET'])
@jwt_required()
@owner_required
def staff_summary():
    owner_username = get_jwt_identity()
    
    # Ambil semua user yang owner-nya adalah user ini, tapi bukan owner itu sendiri
    # (Asumsi struktur RBAC: user punya field `owner` yang merujuk ke akun utama, 
    # atau dalam single tenant kita hanya filter role != 'owner')
    # Sesuai prompt: "Total user dengan role != 'owner'"
    query = {"role": {"$ne": "owner"}}
    
    all_staff = list(db.users.find(query))
    total_staff = len(all_staff)
    
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    
    active_today = 0
    on_leave = 0
    security_alerts = 0
    
    role_distribution = {"manager": 0, "kasir": 0, "gudang": 0, "kurir": 0}
    
    for staff in all_staff:
        role = staff.get("role", "")
        if role in role_distribution:
            role_distribution[role] += 1
            
        status = staff.get("status", "active")
        if status == "on_leave":
            on_leave += 1
            
        last_login = staff.get("last_login")
        if last_login and isinstance(last_login, datetime) and last_login >= yesterday:
            active_today += 1
            
        failed_attempts = staff.get("failed_login_attempts", 0)
        if failed_attempts >= 3:
            security_alerts += 1
            
    return jsonify({
        "stats": {
            "totalStaff": total_staff,
            "activeToday": active_today,
            "onLeave": on_leave,
            "securityAlerts": security_alerts
        },
        "roleDistribution": role_distribution
    }), 200

@staff_bp.route('', methods=['GET'])
@jwt_required()
@owner_required
def get_staff_list():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))
    search = request.args.get('search', '')
    role = request.args.get('role', 'all')
    status = request.args.get('status', 'all')
    
    query = {"role": {"$ne": "owner"}, "is_deleted": {"$ne": True}}
    
    if search:
        query["$or"] = [
            {"nama_lengkap": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"username": {"$regex": search, "$options": "i"}}
        ]
        
    if role and role != 'all':
        query["role"] = role
        
    if status and status != 'all':
        query["status"] = status
        
    cursor = db.users.find(query).sort("last_login", -1).skip((page - 1) * limit).limit(limit)
    total = db.users.count_documents(query)
    
    return jsonify({
        "page": page,
        "limit": limit,
        "total": total,
        "data": [serialize_doc(doc) for doc in cursor]
    }), 200

@staff_bp.route('', methods=['POST'])
@jwt_required()
@owner_required
def create_staff():
    admin_user = get_jwt_identity()
    try:
        payload = StaffCreateSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
        
    # Check if username or email exists
    if db.users.find_one({"username": payload.username}):
        return jsonify({"error": "Username sudah digunakan"}), 400
    if db.users.find_one({"email": payload.email}):
        return jsonify({"error": "Email sudah terdaftar"}), 400
        
    new_user = {
        "nama_lengkap": payload.nama_lengkap,
        "username": payload.username,
        "email": payload.email,
        "password": generate_password_hash(payload.temporary_password),
        "role": payload.role,
        "departemen": payload.departemen,
        "status": "active",
        "created_by": admin_user,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_deleted": False,
        "failed_login_attempts": 0
    }
    
    result = db.users.insert_one(new_user)
    
    # Log Activity
    db.staff_activity_logs.insert_one({
        "user_id": result.inserted_id,
        "action": "account_created",
        "details": {"role": payload.role},
        "performed_by": admin_user,
        "timestamp": datetime.now(timezone.utc)
    })
    
    return jsonify({"msg": "Staff berhasil ditambahkan"}), 201

@staff_bp.route('/<id>', methods=['PUT'])
@jwt_required()
@owner_required
def update_staff(id):
    admin_user = get_jwt_identity()
    try:
        payload = StaffUpdateSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
        
    target_user = db.users.find_one({"_id": ObjectId(id)})
    if not target_user:
        return jsonify({"error": "Staff tidak ditemukan"}), 404
        
    if target_user.get("role") == "owner":
        return jsonify({"error": "Tidak dapat mengubah akun owner"}), 403
        
    update_data = {"updated_at": datetime.now(timezone.utc)}
    
    # Track changes for logging
    changes = {}
    
    if payload.nama_lengkap and payload.nama_lengkap != target_user.get("nama_lengkap"):
        update_data["nama_lengkap"] = payload.nama_lengkap
        changes["nama_lengkap"] = payload.nama_lengkap
        
    if payload.email and payload.email != target_user.get("email"):
        # Check uniqueness
        if db.users.find_one({"email": payload.email, "_id": {"$ne": ObjectId(id)}}):
            return jsonify({"error": "Email sudah digunakan oleh akun lain"}), 400
        update_data["email"] = payload.email
        changes["email"] = payload.email
        
    if payload.role and payload.role != target_user.get("role"):
        update_data["role"] = payload.role
        changes["old_role"] = target_user.get("role")
        changes["new_role"] = payload.role
        
    if payload.departemen is not None and payload.departemen != target_user.get("departemen"):
        update_data["departemen"] = payload.departemen
        
    if payload.status and payload.status != target_user.get("status"):
        update_data["status"] = payload.status
        changes["old_status"] = target_user.get("status")
        changes["new_status"] = payload.status
        
    if update_data:
        db.users.update_one({"_id": ObjectId(id)}, {"$set": update_data})
        
        if changes:
            action = "status_change" if "new_status" in changes else ("role_change" if "new_role" in changes else "profile_update")
            db.staff_activity_logs.insert_one({
                "user_id": ObjectId(id),
                "action": action,
                "details": changes,
                "performed_by": admin_user,
                "timestamp": datetime.now(timezone.utc)
            })
            
    return jsonify({"msg": "Data staff diperbarui"}), 200

@staff_bp.route('/<id>/reset-password', methods=['POST'])
@jwt_required()
@owner_required
def reset_password(id):
    admin_user = get_jwt_identity()
    target_user = db.users.find_one({"_id": ObjectId(id)})
    if not target_user:
        return jsonify({"error": "Staff tidak ditemukan"}), 404
        
    if target_user.get("role") == "owner":
        return jsonify({"error": "Tidak dapat mereset password owner via API ini"}), 403
        
    # Generate temp password
    chars = string.ascii_letters + string.digits
    temp_pass = ''.join(random.choice(chars) for _ in range(10))
    
    db.users.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "password": generate_password_hash(temp_pass),
            "password_changed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    db.staff_activity_logs.insert_one({
        "user_id": ObjectId(id),
        "action": "password_reset",
        "details": {"method": "forced_by_admin"},
        "performed_by": admin_user,
        "timestamp": datetime.now(timezone.utc)
    })
    
    return jsonify({"msg": "Password berhasil direset", "temporary_password": temp_pass}), 200

@staff_bp.route('/<id>/activity-log', methods=['GET'])
@jwt_required()
@owner_required
def get_activity_log(id):
    limit = int(request.args.get('limit', 20))
    cursor = db.staff_activity_logs.find({"user_id": ObjectId(id)}).sort("timestamp", -1).limit(limit)
    
    logs = []
    for doc in cursor:
        doc['_id'] = str(doc['_id'])
        doc['user_id'] = str(doc['user_id'])
        logs.append(doc)
        
    return jsonify({"logs": logs}), 200

@staff_bp.route('/<id>', methods=['DELETE'])
@jwt_required()
@owner_required
def delete_staff(id):
    admin_user = get_jwt_identity()
    target_user = db.users.find_one({"_id": ObjectId(id)})
    if not target_user:
        return jsonify({"error": "Staff tidak ditemukan"}), 404
        
    if target_user.get("username") == admin_user:
        return jsonify({"error": "Tidak dapat menghapus akun sendiri"}), 403
        
    if target_user.get("role") == "owner":
        return jsonify({"error": "Tidak dapat menghapus akun owner"}), 403
        
    # Cek apakah user punya transaksi
    # Asumsi transaksi mencatat "created_by" atau "user" dengan username staf tersebut
    tx_count = db.transactions.count_documents({"user": target_user.get("username")})
    
    if tx_count > 0:
        # Jika punya transaksi, lakukan soft delete
        db.users.update_one({"_id": ObjectId(id)}, {"$set": {"is_deleted": True, "status": "suspended"}})
        db.staff_activity_logs.insert_one({
            "user_id": ObjectId(id),
            "action": "soft_delete",
            "details": {"reason": "Has pending transactions"},
            "performed_by": admin_user,
            "timestamp": datetime.now(timezone.utc)
        })
        return jsonify({"msg": "Akun di-nonaktifkan secara permanen (soft delete) karena memiliki data transaksi."}), 200
    else:
        # Jika tidak ada transaksi, hard delete allowed
        db.users.delete_one({"_id": ObjectId(id)})
        return jsonify({"msg": "Akun dihapus permanen"}), 200
