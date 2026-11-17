
from app import create_app,extensions
from werkzeug.security import generate_password_hash
from getpass import getpass

app = create_app()

with app.app_context():

    if extensions.db.users.find_one({"role": "super_admin"}):
        print("A Super Admin already exists.")
        raise SystemExit

    name = input("Enter admin name: ").strip()
    email = input("Enter admin email: ").strip().lower()
    division = input("Enter admin division: ").strip()

    password = getpass("Enter admin password: ")
    confirm = getpass("Confirm admin password: ")

    if not all([name, email, division, password]):
        print("All fields are required.")
        raise SystemExit

    if password != confirm:
        print("Passwords do not match.")
        raise SystemExit

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        raise SystemExit

    if extensions.db.users.find_one({"email": email}):
        print("This email is already registered.")
        raise SystemExit

    if not extensions.db.divisions.find_one({
        "name": division,
        "active": True
    }):
        print("Division does not exist.")
        raise SystemExit

    admin = {
        "name": name,
        "email": email,
        "password": generate_password_hash(password),
        "division": division,
        "role": "super_admin",
        "is_active": True
    }

    extensions.db.users.insert_one(admin)

    print("Super Admin created successfully.")
