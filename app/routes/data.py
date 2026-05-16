import logging
from flask import Blueprint, request, jsonify, send_file, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.extensions import limiter, db
from pydantic import BaseModel, Field, field_validator, ValidationError
from datetime import datetime, timezone, timedelta
from pymongo.errors import DuplicateKeyError
from app.models.schemas import (
    ItemSchema, TransactionSchema,
    WarehouseReceiveSchema, WarehouseMutasiSchema, WarehouseOpnameSchema,
    DeliveryCreateSchema, DeliveryStatusSchema, DeliveryAssignDriverSchema, DeliveryBulkUpdateSchema
)
import pandas as pd
from io import BytesIO
from bson import ObjectId

logger = logging.getLogger(__name__)

data_bp = Blueprint('data', __name__, url_prefix='/api')

# Pastikan unique index pada SKU dibuat sekali saat app startup.
# Ini mencegah duplikat pada level database (atomic, aman dari race condition).
def ensure_indexes():
    try:
        db.items.drop_index("sku_1")
    except Exception:
        pass
    db.items.create_index([("user", 1), ("sku", 1)], unique=True, background=True)
    db.deliveries.create_index([("user", 1), ("resi", 1)], unique=True, background=True)
    db.warehouse_zones.create_index([("user", 1), ("zone_code", 1)], unique=True, background=True)
    db.warehouse_logs.create_index([("user", 1), ("timestamp", -1)], background=True)
    logger.info("MongoDB index ensured: items user+sku (unique), deliveries resi (unique)")

# Pydantic schemas (Moved to app/models/schemas.py)

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
        user = get_jwt_identity()
        cursor = db.items.find({"user": user}).skip(skip).limit(limit)
        total = db.items.count_documents({"user": user})
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
        doc['user'] = get_jwt_identity()
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
        user = get_jwt_identity()
        result = db.items.update_one({"sku": payload.sku, "user": user}, {"$set": doc})
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

        user = get_jwt_identity()
        result = db.items.delete_one({"sku": sku, "user": user})
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
        user = get_jwt_identity()
        cursor = db.transactions.find({"user": user}).sort('tanggal', -1).skip(skip).limit(limit)
        total = db.transactions.count_documents({"user": user})
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
        user = get_jwt_identity()
        doc['user'] = user

        # Update stok otomatis pakai find_one_and_update (Atomic Operation)
        if payload.tipe == 'masuk':
            result = db.items.find_one_and_update(
                {"sku": payload.item_sku, "user": user},
                {"$inc": {"stok": payload.jumlah}},
                return_document=ReturnDocument.AFTER
            )
            if not result:
                return jsonify({"error": "Item not found"}), 404
        else:
            result = db.items.find_one_and_update(
                {"sku": payload.item_sku, "user": user, "stok": {"$gte": payload.jumlah}},
                {"$inc": {"stok": -payload.jumlah}},
                return_document=ReturnDocument.AFTER
            )
            if not result:
                # Bedakan: item tidak ada vs stok kurang
                item_exists = db.items.count_documents({"sku": payload.item_sku, "user": user}) > 0
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
        user = get_jwt_identity()
        
        stock_by_category = list(db.items.aggregate([
            {"$match": {"user": user}},
            {"$group": {
                "_id": "$kategori",
                "total_stok": {"$sum": "$stok"},
                "total_value": {"$sum": {"$multiply": ["$stok", "$harga_beli"]}}
            }},
            {"$sort": {"total_stok": -1}}
        ]))

        items_map = {
            item['sku']: item
            for item in db.items.find({"user": user}, {'sku': 1, 'harga_beli': 1, 'harga_jual': 1})
        }
        
        transactions = list(db.transactions.find({"user": user}).sort("tanggal", 1))
        monthly_tx = {}
        for t in transactions:
            try:
                month_key = t['tanggal'].strftime('%Y-%m') if hasattr(t.get('tanggal'), 'strftime') else "Unknown"
            except:
                month_key = "Unknown"
            
            if month_key not in monthly_tx:
                monthly_tx[month_key] = {"_id": month_key, "masuk": 0, "keluar": 0, "masuk_value": 0, "keluar_value": 0}
            
            item = items_map.get(t.get('item_sku', ''), {})
            jumlah = t.get('jumlah', 0)
            if t.get('tipe') == 'masuk':
                monthly_tx[month_key]['masuk'] += jumlah
                monthly_tx[month_key]['masuk_value'] += jumlah * item.get('harga_jual', 0)
            else:
                monthly_tx[month_key]['keluar'] += jumlah
                monthly_tx[month_key]['keluar_value'] += jumlah * item.get('harga_beli', 0)
                
        transactions_by_month = list(monthly_tx.values())

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
        user = get_jwt_identity()
        transactions = list(db.transactions.find({"user": user}).sort('tanggal', -1))

        # Ambil map SKU -> harga dari collection items (akurat, bukan hardcode)
        items_map = {
            item['sku']: item
            for item in db.items.find({"user": user}, {'sku': 1, 'harga_beli': 1, 'harga_jual': 1, 'nama': 1})
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

        trend_dict = {}
        trend_months = []
        for t in reversed(transactions):
            try:
                month = t['tanggal'].strftime('%b') if hasattr(t.get('tanggal'), 'strftime') else "Unk"
            except:
                month = "Unk"
            if month not in trend_months:
                trend_months.append(month)
            
            if month not in trend_dict:
                trend_dict[month] = {'masuk': 0, 'keluar': 0}
            
            item = items_map.get(t.get('item_sku', ''), {})
            jumlah = t.get('jumlah', 0)
            if t.get('tipe') == 'masuk':
                trend_dict[month]['masuk'] += jumlah * item.get('harga_jual', 0)
            else:
                trend_dict[month]['keluar'] += jumlah * item.get('harga_beli', 0)

        trend_labels = trend_months[-6:] if trend_months else ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun"]
        trend_masuk = [round(trend_dict.get(m, {}).get('masuk', 0) / 1_000_000, 1) for m in trend_labels]
        trend_keluar = [round(trend_dict.get(m, {}).get('keluar', 0) / 1_000_000, 1) for m in trend_labels]

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
        user = get_jwt_identity()
        items = list(db.items.find({"user": user}, {"_id": 0}).sort('sku', 1))
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

        user = get_jwt_identity()
        query = {"user": user}
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

        user = get_jwt_identity()
        transactions = list(db.transactions.find({
            'user': user,
            'tanggal': {'$gte': date_from, '$lte': date_to}
        }))

        # Ambil harga aktual dari items (lebih akurat dari hardcode)
        items_map = {
            item['sku']: item
            for item in db.items.find({"user": user}, {'sku': 1, 'harga_beli': 1, 'harga_jual': 1})
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


# ===== SETTINGS ENDPOINTS =====
@data_bp.route('/settings/profile', methods=['GET', 'PUT'])
@jwt_required()
def manage_profile():
    current_user = get_jwt_identity()
    user = db.users.find_one({"username": current_user})
    if not user: return jsonify({"error": "User not found"}), 404

    if request.method == 'GET':
        business = db.business.find_one({"owner": current_user}) or {}
        return jsonify({
            "profile": {
                "namaLengkap": user.get("full_name", ""),
                "username": user["username"],
                "email": user.get("email", ""),
                "role": user.get("role", "user"),
                "photoUrl": user.get("photo_url", "")
            },
            "business": {
                "nama": business.get("name", ""),
                "alamat": business.get("address", ""),
                "telepon": business.get("phone", "")
            }
        })

    elif request.method == 'PUT':
        payload = request.json
        db.users.update_one({"username": current_user}, {"$set": {
            "full_name": payload.get("namaLengkap"),
            "email": payload.get("email"),
            "photo_url": payload.get("photoUrl")
        }})
        return jsonify({"msg": "Profile updated"}), 200

@data_bp.route('/settings/business', methods=['PUT'])
@jwt_required()
def manage_business():
    current_user = get_jwt_identity()
    payload = request.json
    db.business.update_one(
        {"owner": current_user}, 
        {"$set": {
            "name": payload.get("nama"),
            "address": payload.get("alamat"),
            "phone": payload.get("telepon")
        }}, 
        upsert=True
    )
    return jsonify({"msg": "Business updated"}), 200

@data_bp.route('/settings/account', methods=['DELETE'])
@jwt_required()
def delete_account():
    current_user = get_jwt_identity()
    db.users.delete_one({"username": current_user})
    db.business.delete_one({"owner": current_user})
    # Pastikan pakai field "user" sesuai pembaruan multi-tenant yang telah dibuat
    db.items.delete_many({"user": current_user})
    db.transactions.delete_many({"user": current_user})
    
    resp = make_response(jsonify({"msg": "Account deleted"}), 200)
    resp.set_cookie('access_token_cookie', '', expires=0)
    resp.set_cookie('refresh_token_cookie', '', expires=0)
    return resp

# ==========================================
# WAREHOUSE ENDPOINTS
# ==========================================

@data_bp.route('/warehouse/summary', methods=['GET'])
@jwt_required()
def warehouse_summary():
    user = get_jwt_identity()
    zones = list(db.warehouse_zones.find({"user": user}))
    
    total_capacity = sum(z.get('capacity', 0) for z in zones)
    current_load = sum(z.get('current_load', 0) for z in zones)
    capacity_percent = (current_load / total_capacity * 100) if total_capacity > 0 else 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    items_received_today = db.warehouse_logs.count_documents({
        "user": user,
        "type": "receive",
        "timestamp": {"$gte": today_start}
    })

    # Find low stock
    low_stock = db.items.count_documents({
        "user": user,
        "$expr": {"$lt": ["$stok", {"$ifNull": ["$min_stok", 0]}]}
    })

    # Find expiring
    next_week = datetime.now(timezone.utc) + timedelta(days=7)
    expiring_soon = db.items.count_documents({
        "user": user,
        "expired_date": {"$lt": next_week, "$gte": datetime.now(timezone.utc)}
    })

    return jsonify({
        "stats": {
            "totalCapacity": round(capacity_percent, 1),
            "itemsReceivedToday": items_received_today,
            "lowStockAlerts": low_stock,
            "expiringSoon": expiring_soon
        },
        "zones": [serialize_doc(z) for z in zones]
    }), 200

@data_bp.route('/warehouse/items', methods=['GET'])
@jwt_required()
def warehouse_items():
    user = get_jwt_identity()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))
    search = request.args.get('search', '')
    location = request.args.get('location', '')
    status = request.args.get('status', '')

    query = {"user": user}
    if search:
        query["$or"] = [
            {"sku": {"$regex": search, "$options": "i"}},
            {"nama": {"$regex": search, "$options": "i"}}
        ]
    if location:
        query["location"] = location

    # Minimal logic for status if needed (normal, low, out, expiring)
    # Skipped complex filter for brevity
    
    cursor = db.items.find(query).skip((page - 1) * limit).limit(limit)
    total = db.items.count_documents(query)

    items = [serialize_doc(i) for i in cursor]
    # Evaluate status
    now = datetime.now(timezone.utc)
    for i in items:
        stok = i.get('stok', 0)
        min_stok = i.get('min_stok', 0)
        exp = i.get('expired_date')
        if stok == 0:
            i['status'] = 'out'
        elif min_stok > 0 and stok < min_stok:
            i['status'] = 'low'
        elif exp and isinstance(exp, datetime) and (exp - now).days < 7:
            i['status'] = 'expiring'
        else:
            i['status'] = 'normal'

    return jsonify({"page": page, "limit": limit, "total": total, "data": items}), 200

@data_bp.route('/warehouse/receive', methods=['POST'])
@jwt_required()
def warehouse_receive():
    user = get_jwt_identity()
    try:
        payload = WarehouseReceiveSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    item = db.items.find_one({"user": user, "sku": payload.sku})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    prev_stok = item.get('stok', 0)
    new_stok = prev_stok + payload.qty

    # Update item
    update_data = {"stok": new_stok, "location": payload.location}
    if payload.expired_date:
        update_data["expired_date"] = datetime.fromisoformat(payload.expired_date.replace('Z', '+00:00'))

    db.items.update_one({"_id": item['_id']}, {"$set": update_data})

    # Log
    db.warehouse_logs.insert_one({
        "user": user,
        "type": "receive",
        "item_sku": payload.sku,
        "location_to": payload.location,
        "qty": payload.qty,
        "prev_stok": prev_stok,
        "new_stok": new_stok,
        "alasan": payload.catatan,
        "timestamp": datetime.now(timezone.utc)
    })

    return jsonify({"msg": "Barang diterima"}), 200

@data_bp.route('/warehouse/mutasi', methods=['PUT'])
@jwt_required()
def warehouse_mutasi():
    user = get_jwt_identity()
    try:
        payload = WarehouseMutasiSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    item = db.items.find_one({"user": user, "sku": payload.sku})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # Simplified mutasi: just updating the location of the SKU for now
    # If partial qty mutasi is needed, it implies splitting SKU records which is complex.
    # We assume mutasi moves the entire qty or we don't split batches for now.
    db.items.update_one({"_id": item['_id']}, {"$set": {"location": payload.to_location}})

    db.warehouse_logs.insert_one({
        "user": user,
        "type": "mutasi",
        "item_sku": payload.sku,
        "location_from": payload.from_location,
        "location_to": payload.to_location,
        "qty": payload.qty,
        "alasan": payload.alasan,
        "timestamp": datetime.now(timezone.utc)
    })
    return jsonify({"msg": "Mutasi berhasil"}), 200

@data_bp.route('/warehouse/stock-opname', methods=['PUT'])
@jwt_required()
def warehouse_opname():
    user = get_jwt_identity()
    try:
        payload = WarehouseOpnameSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    item = db.items.find_one({"user": user, "sku": payload.sku})
    if not item:
        return jsonify({"error": "Item not found"}), 404

    prev_stok = item.get('stok', 0)
    selisih = payload.actual_stok - prev_stok

    db.items.update_one({"_id": item['_id']}, {
        "$set": {
            "stok": payload.actual_stok,
            "last_opname": datetime.now(timezone.utc)
        },
        "$push": {
            "opname_history": {
                "date": datetime.now(timezone.utc),
                "system_stok": prev_stok,
                "actual_stok": payload.actual_stok,
                "selisih": selisih,
                "alasan": payload.alasan_perbedaan,
                "user": user
            }
        }
    })

    db.warehouse_logs.insert_one({
        "user": user,
        "type": "opname",
        "item_sku": payload.sku,
        "qty": abs(selisih),
        "prev_stok": prev_stok,
        "new_stok": payload.actual_stok,
        "alasan": payload.alasan_perbedaan,
        "timestamp": datetime.now(timezone.utc)
    })
    return jsonify({"msg": "Opname berhasil"}), 200

@data_bp.route('/warehouse/activity-log', methods=['GET'])
@jwt_required()
def warehouse_activity_log():
    user = get_jwt_identity()
    limit = int(request.args.get('limit', 20))
    cursor = db.warehouse_logs.find({"user": user}).sort("timestamp", -1).limit(limit)
    return jsonify({"data": [serialize_doc(doc) for doc in cursor]}), 200

# ==========================================
# DELIVERY ENDPOINTS
# ==========================================

@data_bp.route('/delivery/summary', methods=['GET'])
@jwt_required()
def delivery_summary():
    user = get_jwt_identity()
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_deliveries = db.deliveries.count_documents({
        "user": user, "created_at": {"$gte": today_start}
    })
    in_transit = db.deliveries.count_documents({"user": user, "status": "in_transit"})
    delivered = db.deliveries.count_documents({
        "user": user, "status": "delivered", "actual_arrival": {"$gte": today_start}
    })
    delayed = db.deliveries.count_documents({
        "user": user, 
        "status": {"$in": ["pending", "picked", "in_transit"]},
        "estimated_arrival": {"$lt": datetime.now(timezone.utc)}
    })

    # Mock drivers for now, unless we have users with driver role
    drivers = list(db.users.find({"owner": user, "role": "driver"}))

    return jsonify({
        "stats": {
            "todayDeliveries": today_deliveries,
            "inTransit": in_transit,
            "delivered": delivered,
            "delayed": delayed
        },
        "drivers": [serialize_doc(d) for d in drivers]
    }), 200

@data_bp.route('/deliveries', methods=['GET'])
@jwt_required()
def get_deliveries():
    user = get_jwt_identity()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))
    
    query = {"user": user, "is_deleted": {"$ne": True}}
    search = request.args.get('search', '')
    if search:
        query["$or"] = [
            {"resi": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}}
        ]
        
    status = request.args.get('status', '')
    if status:
        query["status"] = status

    cursor = db.deliveries.find(query).sort("created_at", -1).skip((page - 1) * limit).limit(limit)
    total = db.deliveries.count_documents(query)
    
    return jsonify({
        "page": page, "limit": limit, "total": total,
        "data": [serialize_doc(d) for d in cursor]
    }), 200

@data_bp.route('/deliveries', methods=['POST'])
@jwt_required()
def create_delivery():
    user = get_jwt_identity()
    try:
        payload = DeliveryCreateSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    resi = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    doc = payload.model_dump()
    doc['resi'] = resi
    doc['user'] = user
    doc['status'] = 'pending'
    doc['created_at'] = datetime.now(timezone.utc)
    doc['estimated_arrival'] = datetime.fromisoformat(payload.estimated_arrival.replace('Z', '+00:00'))
    doc['actual_arrival'] = None
    doc['tracking_history'] = [{
        "status": "created",
        "timestamp": datetime.now(timezone.utc),
        "note": "Pesanan dibuat"
    }]
    
    db.deliveries.insert_one(doc)
    return jsonify({"msg": "Delivery created", "resi": resi}), 201

@data_bp.route('/deliveries/<id>/status', methods=['PUT'])
@jwt_required()
def update_delivery_status(id):
    user = get_jwt_identity()
    try:
        payload = DeliveryStatusSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    update_data = {"status": payload.status}
    if payload.status == 'delivered':
        update_data["actual_arrival"] = datetime.now(timezone.utc)

    db.deliveries.update_one(
        {"_id": ObjectId(id), "user": user},
        {
            "$set": update_data,
            "$push": {
                "tracking_history": {
                    "status": payload.status,
                    "timestamp": datetime.now(timezone.utc),
                    "note": payload.notes
                }
            }
        }
    )
    return jsonify({"msg": "Status updated"}), 200

@data_bp.route('/deliveries/<id>/assign-driver', methods=['PUT'])
@jwt_required()
def assign_driver(id):
    user = get_jwt_identity()
    try:
        payload = DeliveryAssignDriverSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    db.deliveries.update_one(
        {"_id": ObjectId(id), "user": user},
        {
            "$set": {"driver_id": payload.driver_id},
            "$push": {
                "tracking_history": {
                    "status": "assigned",
                    "timestamp": datetime.now(timezone.utc),
                    "note": "Driver assigned"
                }
            }
        }
    )
    return jsonify({"msg": "Driver assigned"}), 200

@data_bp.route('/deliveries/<id>/tracking', methods=['GET'])
@jwt_required()
def get_delivery_tracking(id):
    user = get_jwt_identity()
    doc = db.deliveries.find_one({"_id": ObjectId(id), "user": user})
    if not doc:
        return jsonify({"error": "Not found"}), 404
        
    return jsonify({
        "delivery": serialize_doc(doc),
        "tracking_history": doc.get("tracking_history", [])
    }), 200

@data_bp.route('/deliveries/bulk-update-status', methods=['POST'])
@jwt_required()
def bulk_update_deliveries():
    user = get_jwt_identity()
    try:
        payload = DeliveryBulkUpdateSchema(**request.json)
    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400

    object_ids = [ObjectId(pid) for pid in payload.delivery_ids]
    
    update_data = {"status": payload.status}
    if payload.status == 'delivered':
        update_data["actual_arrival"] = datetime.now(timezone.utc)

    db.deliveries.update_many(
        {"_id": {"$in": object_ids}, "user": user},
        {
            "$set": update_data,
            "$push": {
                "tracking_history": {
                    "status": payload.status,
                    "timestamp": datetime.now(timezone.utc),
                    "note": payload.notes
                }
            }
        }
    )
    return jsonify({"msg": f"{len(payload.delivery_ids)} deliveries updated"}), 200