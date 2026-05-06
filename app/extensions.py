from pymongo import MongoClient
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config import settings

# MongoDB Connection (singleton)
mongo_client = MongoClient(settings.MONGO_URI)
db = mongo_client.get_database()

# Flask Extensions
jwt = JWTManager()
cors = CORS()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # No Redis needed for MVP
)