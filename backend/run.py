import os
from flask import send_from_directory
from app import create_app

app = create_app()

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(file_path):
        return send_from_directory(FRONTEND_DIR, path)
    return {"message": "TRIAD AI DMS Backend Running"}


@app.route("/api/health")
def health():
    return {
        "status": "success"
    }


if __name__ == "__main__":
    app.run(debug=True)
