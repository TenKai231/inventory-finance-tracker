from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import pandas as pd
from io import BytesIO
from bson import ObjectId

data_bp = Blueprint('data', __name__, url_prefix='/api')

# Pydantic schemas
class ItemSchema(BaseModel):
    sku: str = Field(..., min_length=3, max_length=20)
    nama: str = Field(..., min_length=2, max_length=100)
    kategori: str = Field(..., min_length=2)
    stok: int = Field(..., ge=0)
    harga_beli: float = Field(..., gt=0)
    harga_jual: float = Field(..., gt=0)
    
    @field_validator('sku', mode='before')
    @classmethod
    def sku_uppercase(cls, v):
        return v.upper() if isinstance(v, str) else v

class TransactionSchema(BaseModel):
    tipe: str = Field(..., pattern="^(masuk|keluar)$")  # ✅ pattern, bukan regex
    item_sku: str = Field(..., min_length=3)
    jumlah: int = Field(..., gt=0)
    catatan: str = Field("", max_length=200)
    
    @field_validator('item_sku', mode='before')  # ✅ field_validator + mode='before'
    @classmethod
    def sku_uppercase(cls, v):
        return v.upper() if isinstance(v, str) else v

# Helper: convert ObjectId ke string untuk JSON
def serialize_doc(doc):
    doc['_id'] = str(doc['_id'])
    return doc

# ===== ITEM ENDPOINTS =====
@data_bp.route('/items', methods=['GET'])
@jwt_required()
@limiter.limit("30 per minute")
def get_items():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit
    
    cursor = db.items.find().skip(skip).limit(limit)
    total = db.items.count_documents({})
    
    return jsonify({
        "page": page, "limit": limit, "total": total,
        "data": [serialize_doc(doc) for doc in cursor]
    }), 200

@data_bp.route('/items', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def create_item():
    try:
        payload = ItemSchema(**request.json)
        doc = payload.model_dump()
        doc['created_at'] = datetime.utcnow()
        result = db.items.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        return jsonify(doc), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ===== TRANSACTION ENDPOINTS =====
@data_bp.route('/transactions', methods=['GET'])
@jwt_required()
@limiter.limit("30 per minute")
def get_transactions():
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit
    
    cursor = db.transactions.find().sort('tanggal', -1).skip(skip).limit(limit)
    total = db.transactions.count_documents({})
    
    return jsonify({
        "page": page, "limit": limit, "total": total,
        "data": [serialize_doc(doc) for doc in cursor]
    }), 200

@data_bp.route('/transactions', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def create_transaction():
    try:
        payload = TransactionSchema(**request.json)
        doc = payload.model_dump()
        doc['tanggal'] = datetime.utcnow()
        doc['user'] = get_jwt_identity()
        
        # Update stok otomatis
        item = db.items.find_one({"sku": payload.item_sku})
        if not item:
            return jsonify({"error": "Item not found"}), 404
        
        new_stok = item['stok'] + (payload.jumlah if payload.tipe == 'masuk' else -payload.jumlah)
        if new_stok < 0:
            return jsonify({"error": "Stok tidak cukup"}), 400
        
        db.items.update_one({"sku": payload.item_sku}, {"$set": {"stok": new_stok}})
        
        result = db.transactions.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        return jsonify(doc), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ===== DASHBOARD AGGREGATION =====
@data_bp.route('/dashboard/summary', methods=['GET'])
@jwt_required()
@limiter.limit("10 per minute")
def dashboard_summary():
    # Aggregation: stok per kategori
    stock_by_category = list(db.items.aggregate([
        {"$group": {
            "_id": "$kategori",
            "total_stok": {"$sum": "$stok"},
            "total_value": {"$sum": {"$multiply": ["$stok", "$harga_beli"]}}
        }},
        {"$sort": {"total_stok": -1}}
    ]))
    
    # Aggregation: transaksi per bulan
    transactions_by_month = list(db.transactions.aggregate([
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$tanggal"}},
            "masuk": {"$sum": {"$cond": [{"$eq": ["$tipe", "masuk"]}, "$jumlah", 0]}},
            "keluar": {"$sum": {"$cond": [{"$eq": ["$tipe", "keluar"]}, "$jumlah", 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]))
    
    return jsonify({
        "stock_by_category": [{**doc, "_id": doc.pop("_id")} for doc in stock_by_category],
        "transactions_by_month": [{**doc, "_id": doc.pop("_id")} for doc in transactions_by_month],
        "generated_at": datetime.utcnow().isoformat()
    }), 200

# ===== EXPORT EXCEL (PROTECTED) =====
@data_bp.route('/export/transactions', methods=['GET'])
@jwt_required()
@limiter.limit("3 per minute")
def export_excel():
    # ✅ CARA BENAR Flask-JWT-Extended v4+: pakai get_jwt()
    claims = get_jwt()
    
    # Cek role dari claims
    if claims.get('role') != 'owner':
        return jsonify({"error": "Unauthorized: owner access only"}), 403
    
    # Fetch data transaksi
    docs = list(db.transactions.find({}, {"_id": 0}).sort('tanggal', -1))
    
    if not docs:
        return jsonify({"msg": "No transactions to export"}), 200
    
    # Convert ke DataFrame & Excel
    df = pd.DataFrame(docs)
    buf = BytesIO()
    
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Transaksi')
    
    buf.seek(0)
    
    # Generate filename dengan timestamp
    filename = f'laporan_transaksi_{datetime.utcnow().strftime("%Y%m%d_%H%M")}.xlsx'
    
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        download_name=filename,
        as_attachment=True
    )