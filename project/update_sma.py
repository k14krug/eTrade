from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, Date
import time
from datetime import datetime

Base = declarative_base()

class SP500HistData(Base):
    __tablename__ = 'sp500_stock_data'
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, index=True)
    date = Column(Date, index=True)
    close_price = Column(Float)
    sma_20 = Column(Float)
    sma_50 = Column(Float)

engine = create_engine('mysql+mysqlconnector://root:admin14@localhost/etrade_db')
Session = sessionmaker(bind=engine)

def get_total_rows(session):
    return session.query(func.count(SP500HistData.id)).scalar()

def update_sma_in_chunks(chunk_size=500000):
    with Session() as session:
        total_rows = get_total_rows(session)
        start_time = time.time()
        processed_rows = 0
        
        print(f"Total rows to process: {total_rows}")

        # Create temporary table for calculations
        session.execute(text("""
        CREATE TEMPORARY TABLE temp_sma AS
        SELECT 
            id,
            stock_id,
            date,
            close_price,
            AVG(close_price) OVER (
                PARTITION BY stock_id 
                ORDER BY date 
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) AS sma_20,
            AVG(close_price) OVER (
                PARTITION BY stock_id 
                ORDER BY date 
                ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
            ) AS sma_50
        FROM sp500_stock_data
        """))

        # Get the maximum ID
        max_id = session.query(func.max(SP500HistData.id)).scalar()

        for start_id in range(1, max_id + 1, chunk_size):
            end_id = min(start_id + chunk_size - 1, max_id)
            
            # Update main table from temporary table for the current chunk
            session.execute(text(f"""
            UPDATE sp500_stock_data AS main
            JOIN temp_sma AS temp ON main.id = temp.id
            SET 
                main.sma_20 = temp.sma_20,
                main.sma_50 = temp.sma_50
            WHERE main.id BETWEEN :start_id AND :end_id
            """), {"start_id": start_id, "end_id": end_id})

            session.commit()
            
            processed_rows += (end_id - start_id + 1)
            elapsed_time = time.time() - start_time
            progress = min((processed_rows / total_rows) * 100, 100)
            eta = (elapsed_time / processed_rows) * (total_rows - processed_rows) if processed_rows > 0 else 0
            
            print(f"Progress: {progress:.2f}% | Rows processed: {min(processed_rows, total_rows)}/{total_rows} | "
                  f"Elapsed time: {elapsed_time:.2f}s | ETA: {eta:.2f}s | "
                  f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Drop temporary table
        session.execute(text("DROP TEMPORARY TABLE IF EXISTS temp_sma"))
        session.commit()

    print("Update completed.")

if __name__ == "__main__":
    update_sma_in_chunks()