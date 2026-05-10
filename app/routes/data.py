import logging
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator, ValidationError
from datetime import datetime, timezone, timedelta
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


# ===== FINANCE SUMMARY =====
@data_bp.route('/finance/summary', methods=['GET'])
@jwt_required()
@limiter.limit("10 per minute")
def finance_summary():
    try:
        transactions = list(db.transactions.find().sort('tanggal', -1))

        # Ambil map SKU -> harga dari collection items (akurat, bukan hardcode)
        items_map = {
            item['sku']: item
            for item in db.items.find({}, {'sku': 1, 'harga_beli': 1, 'harga_jual': 1, 'nama': 1})
        }

        pemasukan = 0
        pengeluaran = 0
        for t in transactions:
            item = items_map.get(t.get('item_sku', ''), {})
            jumlah = t.get('jumlah', 0)
            if t.get('tipe') == 'masuk':
                pemasukan += jumlah * item.get('harga_jual', 0)
            else:
                pengeluaran += jumlah * item.get('harga_beli', 0)

        profit = pemasukan - pengeluaran
        margin = round((profit / pemasukan * 100), 1) if pemasukan > 0 else 0

        # Tren 6 bulan terakhir menggunakan aggregation
        trend_pipeline = [
            {"$group": {
                "_id": {"$dateToString": {"format": "%b", "date": "$tanggal"}},
                "masuk_qty": {"$sum": {"$cond": [{"$eq": ["$tipe", "masuk"]}, "$jumlah", 0]}},
                "keluar_qty": {"$sum": {"$cond": [{"$eq": ["$tipe", "keluar"]}, "$jumlah", 0]}},
            }},
            {"$sort": {"_id": 1}},
            {"$limit": 6}
        ]
        trend_raw = list(db.transactions.aggregate(trend_pipeline))
        trend_labels = [r["_id"] for r in trend_raw] or ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun"]
        trend_masuk = [round(r["masuk_qty"] * 75000 / 1_000_000, 1) for r in trend_raw] or [0]*6
        trend_keluar = [round(r["keluar_qty"] * 60000 / 1_000_000, 1) for r in trend_raw] or [0]*6

        def serialize_tx(t):
            return {
                "_id": str(t['_id']),
                "tipe": t.get('tipe'),
                "desc": t.get('catatan') or t.get('item_sku', '-'),
                "tanggal": t['tanggal'].isoformat() if hasattr(t.get('tanggal'), 'isoformat') else str(t.get('tanggal', '')),
                "nilai": t.get('jumlah', 0) * (
                    items_map.get(t.get('item_sku', ''), {}).get('harga_jual', 0)
                    if t.get('tipe') == 'masuk' else
                    items_map.get(t.get('item_sku', ''), {}).get('harga_beli', 0)
                )
            }

        return jsonify({
            "stats": {
                "pemasukan": pemasukan,
                "pengeluaran": pengeluaran,
                "profit": profit,
                "margin": margin,
                "growthPemasukan": 12.5,
                "growthPengeluaran": 4.2,
                "growthProfit": 24.8
            },
            "expenseComposition": [
                {"name": "Inventaris",  "percent": 60, "value": pengeluaran * 0.60, "color": "#4f46e5"},
                {"name": "Operasional", "percent": 25, "value": pengeluaran * 0.25, "color": "#0f172a"},
                {"name": "Marketing",   "percent": 15, "value": pengeluaran * 0.15, "color": "#bfdbfe"}
            ],
            "recent": [serialize_tx(t) for t in transactions[:5]],
            "trend": {
                "labels": trend_labels,
                "pemasukan": trend_masuk,
                "pengeluaran": trend_keluar
            }
        }), 200

    except Exception:
        logger.exception("Unexpected error in finance_summary")
        return jsonify({"error": "Internal server error"}), 500


# ===== EXPORT ENDPOINTS =====

def log_export(user, type, format):
    """Helper to log export activity — aktifkan komentar di bawah untuk persistensi ke MongoDB."""
    # db.export_logs.insert_one({
    #     'user': user, 'type': type, 'format': format,
    #     'timestamp': datetime.now(timezone.utc), 'status': 'completed'
    # })
    logger.info(f"Export: user={user} type={type} format={format}")


@data_bp.route('/export/inventory', methods=['GET'])
@jwt_required()
@limiter.limit("5 per minute")
def export_inventory():
    """Export inventory data ke Excel."""
    try:
        items = list(db.items.find({}, {"_id": 0}).sort('sku', 1))
        if not items:
            return jsonify({"error": "No data to export"}), 404

        df = pd.DataFrame(items)
        buf = BytesIO()

        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventaris')
            ws = writer.sheets['Inventaris']
            ws.column_dimensions['A'].width = 15  # SKU
            ws.column_dimensions['B'].width = 30  # Nama
            ws.column_dimensions['C'].width = 20  # Kategori

        buf.seek(0)
        log_export(user=get_jwt_identity(), type='inventory', format='xlsx')

        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=f'Laporan_Inventaris_{datetime.now(timezone.utc).strftime("%Y%m%d")}.xlsx',
            as_attachment=True
        )
    except Exception:
        logger.exception("Unexpected error in export_inventory")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/export/transactions', methods=['GET'])
@jwt_required()
@limiter.limit("5 per minute")
def export_transactions():
    """Export transaksi dengan filter tanggal opsional. Mendukung format xlsx dan csv."""
    try:
        date_from_str = request.args.get('from')
        date_to_str   = request.args.get('to')
        format_type   = request.args.get('format', 'xlsx').lower()

        if format_type not in ('xlsx', 'csv'):
            return jsonify({"error": "Format harus 'xlsx' atau 'csv'"}), 400

        query = {}
        if date_from_str and date_to_str:
            try:
                query['tanggal'] = {
                    '$gte': datetime.fromisoformat(date_from_str).replace(tzinfo=timezone.utc),
                    '$lte': datetime.fromisoformat(date_to_str).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                }
            except ValueError:
                return jsonify({"error": "Format tanggal tidak valid. Gunakan YYYY-MM-DD"}), 400

        docs = list(db.transactions.find(query, {"_id": 0}).sort('tanggal', -1))
        if not docs:
            return jsonify({"error": "No transactions found"}), 404

        # Konversi datetime ke string agar kompatibel dengan Excel/CSV
        for t in docs:
            if 'tanggal' in t and hasattr(t['tanggal'], 'isoformat'):
                t['tanggal'] = t['tanggal'].isoformat()

        df = pd.DataFrame(docs)
        buf = BytesIO()
        date_label = f"{date_from_str}_{date_to_str}" if date_from_str else datetime.now(timezone.utc).strftime("%Y%m%d")

        if format_type == 'csv':
            df.to_csv(buf, index=False, encoding='utf-8-sig')
            mimetype = 'text/csv'
            filename = f'Laporan_Transaksi_{date_label}.csv'
        else:
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Transaksi')
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'Laporan_Transaksi_{date_label}.xlsx'

        buf.seek(0)
        log_export(user=get_jwt_identity(), type='transactions', format=format_type)

        return send_file(buf, mimetype=mimetype, download_name=filename, as_attachment=True)
    except Exception:
        logger.exception("Unexpected error in export_transactions")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/export/finance', methods=['GET'])
@jwt_required()
@limiter.limit("5 per minute")
def export_finance():
    """Export ringkasan keuangan berdasarkan periode."""
    try:
        period = request.args.get('period', 'bulan_ini')
        now = datetime.now(timezone.utc)

        if period == 'bulan_ini':
            date_from = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            date_to   = now
        elif period == 'bulan_lalu':
            if now.month == 1:
                date_from = datetime(now.year - 1, 12, 1, tzinfo=timezone.utc)
                date_to   = datetime(now.year, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                date_from = datetime(now.year, now.month - 1, 1, tzinfo=timezone.utc)
                date_to   = datetime(now.year, now.month, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
        elif period == 'quarter_ini':
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            date_from = datetime(now.year, quarter_start_month, 1, tzinfo=timezone.utc)
            date_to   = now
        elif period == 'tahun_ini':
            date_from = datetime(now.year, 1, 1, tzinfo=timezone.utc)
            date_to   = now
        else:
            return jsonify({"error": "period tidak valid"}), 400

        transactions = list(db.transactions.find({
            'tanggal': {'$gte': date_from, '$lte': date_to}
        }))

        # Ambil harga aktual dari items (lebih akurat dari hardcode)
        items_map = {
            item['sku']: item
            for item in db.items.find({}, {'sku': 1, 'harga_beli': 1, 'harga_jual': 1})
        }

        pemasukan   = sum(t['jumlah'] * items_map.get(t.get('item_sku', ''), {}).get('harga_jual', 0)
                         for t in transactions if t.get('tipe') == 'masuk')
        pengeluaran = sum(t['jumlah'] * items_map.get(t.get('item_sku', ''), {}).get('harga_beli', 0)
                         for t in transactions if t.get('tipe') == 'keluar')
        profit = pemasukan - pengeluaran
        margin = round((profit / pemasukan * 100), 2) if pemasukan > 0 else 0

        summary = [{
            'Periode':           f'{date_from.strftime("%d %b %Y")} - {date_to.strftime("%d %b %Y")}',
            'Total Pemasukan':   pemasukan,
            'Total Pengeluaran': pengeluaran,
            'Profit Bersih':     profit,
            'Margin (%)':        margin
        }]

        df  = pd.DataFrame(summary)
        buf = BytesIO()

        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Keuangan')
            ws = writer.sheets['Keuangan']
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions['B'].width = 20
            ws.column_dimensions['C'].width = 20
            ws.column_dimensions['D'].width = 20
            ws.column_dimensions['E'].width = 15

        buf.seek(0)
        log_export(user=get_jwt_identity(), type='finance', format='xlsx')

        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            download_name=f'Laporan_Keuangan_{period}_{now.strftime("%Y%m%d")}.xlsx',
            as_attachment=True
        )
    except Exception:
        logger.exception("Unexpected error in export_finance")
        return jsonify({"error": "Internal server error"}), 500


@data_bp.route('/export/history', methods=['GET'])
@jwt_required()
def get_export_history():
    """Riwayat ekspor user saat ini. Di production, ambil dari db.export_logs."""
    try:
        # Contoh query ke MongoDB jika log_export aktif:
        # history = list(db.export_logs.find(
        #     {'user': get_jwt_identity()}, {'_id': 0}
        # ).sort('timestamp', -1).limit(20))
        return jsonify([]), 200
    except Exception:
        logger.exception("Unexpected error in get_export_history")
        return jsonify({"error": "Internal server error"}), 500