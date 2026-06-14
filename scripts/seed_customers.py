import sys
import os

# Add parent directory to sys.path to resolve 'app' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.routes.testing import seed_database

def run():
    print("Initiating full database seed...")
    db = SessionLocal()
    try:
        res = seed_database(db)
        print("Seed Status:", res["message"])
    except Exception as e:
        print("Error during database seed execution:", e)
    finally:
        db.close()

if __name__ == "__main__":
    run()
