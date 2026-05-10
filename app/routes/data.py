import logging
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator, ValidationError
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
import pandas as pd
from io import BytesIO
from bson import ObjectId

logger = logging.getLogger(__name__)

data_bp = Blueprint('data', __name__, url_prefix='/api')

# Pastikan unique index pada SKU dibuat sekali saat app startup.
# Ini mencegah duplikat pada level database (atomic, aman dari race condition).
def ensure_indexes():
    db.items.create_index("sku", unique=True, background=True)
    logger.info("MongoDB index ensured: items.sku (unique)")

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
    tipe: str = Field(..., pattern="^(masuk|keluar)$")
    item_sku: str = Field(..., min_length=3)
    jumlah: int = Field(..., gt=0)
    catatan: str = Field("", max_length=200)

    @field_validator('item_sku', mode='before')
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
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
    except (ValueError, TypeError):
        return jsonify({"error": "page dan limit harus berupa angka"}), 400

    skip = (page - 1) * limit

    try:
        cursor = db.items.find().skip(skip).limit(limit)
        total = db.items.count_documents({})
        return jsonify({
            "page": page, "limit": limit, "total": total,
            "data": [serialize_doc(doc) for doc in cursor]
        }), 200
    except Exception:
        logger.exception("Unexpected error in get_items")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/items', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def create_item():
    if not request.is_json or not request.json:
        return jsonify({"error": "Request harus berupa JSON"}), 400

    # Validasi schema — 400 kalau input tidak sesuai
    try:
        payload = ItemSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    # Operasi DB — tangkap DuplicateKeyError (409) dan unexpected error (500)
    try:
        doc = payload.model_dump()
        doc['created_at'] = datetime.now(timezone.utc)
        result = db.items.insert_one(doc)
        doc['_id'] = str(result.inserted_id)
        return jsonify(doc), 201
    except DuplicateKeyError:
        return jsonify({"error": f"SKU '{payload.sku}' sudah terdaftar"}), 409
    except Exception:
        logger.exception("Unexpected error in create_item")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/items', methods=['PUT'])
@jwt_required()
def update_item():
    if not request.is_json or not request.json:
        return jsonify({"error": "Request harus berupa JSON"}), 400

    try:
        payload = ItemSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    try:
        doc = payload.model_dump()
        doc['updated_at'] = datetime.now(timezone.utc)
        result = db.items.update_one({"sku": payload.sku}, {"$set": doc})
        if result.matched_count == 0:
            return jsonify({"error": "Item tidak ditemukan"}), 404
        return jsonify({"message": "Item berhasil diupdate"}), 200
    except Exception:
        logger.exception("Unexpected error in update_item")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/items/<path:sku>', methods=['DELETE'])
@jwt_required()
def delete_item(sku):
    try:
        # Cek role user, hanya owner yang boleh hapus
        claims = get_jwt()
        if claims.get("role") != "owner":
            return jsonify({"error": "Unauthorized. Hanya owner yang dapat menghapus item."}), 403

        result = db.items.delete_one({"sku": sku})
        if result.deleted_count == 0:
            return jsonify({"error": "Item tidak ditemukan"}), 404
        return jsonify({"message": "Item berhasil dihapus"}), 200
    except Exception:
        logger.exception("Unexpected error in delete_item")
        return jsonify({"error": "Internal server error"}), 500


# ===== TRANSACTION ENDPOINTS =====
@data_bp.route('/transactions', methods=['GET'])
@jwt_required()
@limiter.limit("30 per minute")
def get_transactions():
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
    except (ValueError, TypeError):
        return jsonify({"error": "page dan limit harus berupa angka"}), 400

    skip = (page - 1) * limit

    try:
        cursor = db.transactions.find().sort('tanggal', -1).skip(skip).limit(limit)
        total = db.transactions.count_documents({})
        return jsonify({
            "page": page, "limit": limit, "total": total,
            "data": [serialize_doc(doc) for doc in cursor]
        }), 200
    except Exception:
        logger.exception("Unexpected error in get_transactions")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/transactions', methods=['POST'])
@jwt_required()
@limiter.limit("10 per minute")
def create_transaction():
    if not request.is_json or not request.json:
        return jsonify({"error": "Request harus berupa JSON"}), 400

    # Validasi schema — 400 kalau input tidak sesuai
    try:
        payload = TransactionSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    # Logika bisnis + operasi DB — 500 kalau ada bug tak terduga
    try:
        from pymongo import ReturnDocument

        doc = payload.model_dump()
        doc['tanggal'] = datetime.now(timezone.utc)
        doc['user'] = get_jwt_identity()

        # Update stok otomatis pakai find_one_and_update (Atomic Operation)
        if payload.tipe == 'masuk':
            result = db.items.find_one_and_update(
                {"sku": payload.item_sku},
                {"$inc": {"stok": payload.jumlah}},
                return_document=ReturnDocument.AFTER
            )
            if not result:
                return jsonify({"error": "Item not found"}), 404
        else:
            result = db.items.find_one_and_update(
                {"sku": payload.item_sku, "stok": {"$gte": payload.jumlah}},
                {"$inc": {"stok": -payload.jumlah}},
                return_document=ReturnDocument.AFTER
            )
            if not result:
                # Bedakan: item tidak ada vs stok kurang
                item_exists = db.items.count_documents({"sku": payload.item_sku}) > 0
                if item_exists:
                    return jsonify({"error": "Stok tidak cukup"}), 400
                else:
                    return jsonify({"error": "Item not found"}), 404

        result_trans = db.transactions.insert_one(doc)
        doc['_id'] = str(result_trans.inserted_id)
        return jsonify(doc), 201

    except Exception:
        logger.exception("Unexpected error in create_transaction")
        return jsonify({"error": "Internal server error"}), 500


# ===== DASHBOARD AGGREGATION =====
@data_bp.route('/dashboard/summary', methods=['GET'])
@jwt_required()
@limiter.limit("10 per minute")
def dashboard_summary():
    try:
        stock_by_category = list(db.items.aggregate([
            {"$group": {
                "_id": "$kategori",
                "total_stok": {"$sum": "$stok"},
                "total_value": {"$sum": {"$multiply": ["$stok", "$harga_beli"]}}
            }},
            {"$sort": {"total_stok": -1}}
        ]))

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
            "generated_at": datetime.now(timezone.utc).isoformat()
        }), 200

    except Exception:
        logger.exception("Unexpected error in dashboard_summary")
        return jsonify({"error": "Internal server error"}), 500


# ===== EXPORT EXCEL (PROTECTED) =====
@data_bp.route('/export/transactions', methods=['GET'])
@jwt_required()
@limiter.limit("3 per minute")
def export_excel():
    claims = get_jwt()

    if claims.get('role') != 'owner':
        return jsonify({"error": "Unauthorized: owner access only"}), 403

    try:
        docs = list(db.transactions.find({}, {"_id": 0}).sort('tanggal', -1))

        if not docs:
            return jsonify({"error": "No transactions to export"}), 200

        df = pd.DataFrame(docs)
        buf = BytesIO()

        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Transaksi')

        buf.seek(0)
        filename = f'laporan_transaksi_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")}.xlsx'

        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=filename,
            as_attachment=True
        )

    except Exception:
        logger.exception("Unexpected error in export_excel")
        return jsonify({"error": "Internal server error"}), 500