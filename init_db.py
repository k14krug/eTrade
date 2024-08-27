from app import app, db
from models import User, Transactions, Position, SP500Stock, SP500DailyData, SP500MonthlyStats
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

def init_db():
    with app.app_context():
        # Create an inspector
        inspector = inspect(db.engine)

        # Get existing table names
        existing_tables = inspector.get_table_names()

        # List of all your model classes in order of dependency
        models = [User, SP500Stock, Transactions, Position, SP500DailyData, SP500MonthlyStats]

        # Create tables for models that don't exist
        for model in models:
            if model.__tablename__ not in existing_tables:
                try:
                    model.__table__.create(db.engine)
                    print(f"Created table: {model.__tablename__}")
                except OperationalError as e:
                    print(f"Error creating table {model.__tablename__}: {str(e)}")
            else:
                print(f"Table already exists: {model.__tablename__}")

        print("Database initialization completed.")

if __name__ == "__main__":
    init_db()