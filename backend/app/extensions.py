
import gridfs
from pymongo import MongoClient
from flask_jwt_extended import JWTManager

mongo_client = None
db = None
fs = None

jwt = JWTManager()


def init_db(app):
    global mongo_client, db, fs

    mongo_client = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=5000
    )

    mongo_client.admin.command("ping")

    db = mongo_client[app.config["DATABASE_NAME"]]
    fs = gridfs.GridFS(db)

    # Unique email index
    db.users.create_index(
        "email",
        unique=True
    )

    db.users.update_many(
        {"is_active": {"$exists": False}},
        {"$set": {"is_active": True}}
    )

    # Unique division name
    db.divisions.create_index(
        "name",
        unique=True
    )

    # Document upload indexes
    db.document_uploads.create_index(
        [("division", 1), ("created_at", -1)]
    )

    db.document_uploads.create_index(
        "uploaded_by"
    )

    # Access request indexes
    db.access_requests.create_index(
        [("document_id", 1), ("user_id", 1), ("status", 1)]
    )
    db.access_requests.create_index(
        [("document_division", 1), ("status", 1)]
    )
    db.access_requests.create_index(
        "user_id"
    )

    # Text index for search
    try:
        db.document_uploads.create_index([
            ("title", "text"),
            ("extracted_text", "text"),
            ("original_name", "text")
        ])
    except Exception:
        pass

    # Initial divisions
    initial_divisions = [
        "Finance",
        "HR",
        "Technical",
        "Division A",
        "Division B"
    ]

    for division in initial_divisions:
        db.divisions.update_one(
            {"name": division},
            {
                "$setOnInsert": {
                    "name": division,
                    "active": True
                }
            },
            upsert=True
        )
