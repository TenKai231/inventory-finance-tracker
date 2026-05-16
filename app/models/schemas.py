from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

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

# Warehouse Schemas
class WarehouseReceiveSchema(BaseModel):
    sku: str = Field(..., min_length=3)
    qty: int = Field(..., gt=0)
    location: str = Field(..., min_length=2)
    expired_date: Optional[str] = None
    catatan: Optional[str] = ""

class WarehouseMutasiSchema(BaseModel):
    sku: str = Field(..., min_length=3)
    from_location: str = Field(..., min_length=2)
    to_location: str = Field(..., min_length=2)
    qty: int = Field(..., gt=0)
    alasan: Optional[str] = ""

class WarehouseOpnameSchema(BaseModel):
    sku: str = Field(..., min_length=3)
    location: str = Field(..., min_length=2)
    actual_stok: int = Field(..., ge=0)
    alasan_perbedaan: Optional[str] = ""

# Delivery Schemas
class DeliveryItemSchema(BaseModel):
    sku: str = Field(...)
    qty: int = Field(..., gt=0)

class DeliveryCreateSchema(BaseModel):
    customer_name: str = Field(..., min_length=3)
    address: str = Field(..., min_length=5)
    customer_phone: Optional[str] = ""
    items: List[DeliveryItemSchema] = Field(..., min_length=1)
    driver_id: Optional[str] = None
    estimated_arrival: str = Field(...)

class DeliveryStatusSchema(BaseModel):
    status: str = Field(..., pattern="^(pending|picked|in_transit|delivered|cancelled)$")
    notes: Optional[str] = ""
    actual_arrival: Optional[str] = None

class DeliveryAssignDriverSchema(BaseModel):
    driver_id: str = Field(...)

class DeliveryBulkUpdateSchema(BaseModel):
    delivery_ids: List[str] = Field(..., min_length=1)
    status: str = Field(..., pattern="^(pending|picked|in_transit|delivered|cancelled)$")
    notes: Optional[str] = ""

# Staff Management Schemas
class StaffCreateSchema(BaseModel):
    nama_lengkap: str = Field(..., min_length=3)
    username: str = Field(..., min_length=4)
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: str = Field(..., pattern="^(manager|kasir|gudang|kurir)$")
    departemen: Optional[str] = ""
    temporary_password: str = Field(..., min_length=8)

class StaffUpdateSchema(BaseModel):
    nama_lengkap: Optional[str] = Field(None, min_length=3)
    email: Optional[str] = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    role: Optional[str] = Field(None, pattern="^(manager|kasir|gudang|kurir)$")
    departemen: Optional[str] = ""
    status: Optional[str] = Field(None, pattern="^(active|inactive|on_leave|suspended)$")
