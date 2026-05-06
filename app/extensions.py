from pymongo import MongoClient
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from app.config import settings

# MongoDB Connection (singleton)
# serverSelectionTimeoutMS: max time to find a usable server before raising error
# connectTimeoutMS: max time to establish a socket connection
mongo_client = MongoClient(
    settings.MONGO_URI,
    serverSelectionTimeoutMS=5000,   # fail fast if Atlas unreachable at startup
    connectTimeoutMS=5000,
)
db = mongo_client.get_database()

# Flask Extensions
jwt = JWTManager()
cors = CORS()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    # TODO: ganti ke Redis untuk production agar counter tidak reset saat container restart
    # storage_uri="redis://your-redis-host:6379"
    storage_uri="memory://",  # MVP only — resets on every container restart
)