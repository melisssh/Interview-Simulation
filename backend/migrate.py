"""
Veritabanı migration scripti.
Terminalde çalıştır:  python migrate.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])

migrations = [
    "ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS stt_data_json VARCHAR(10000);",
]

with engine.connect() as conn:
    for sql in migrations:
        print(f"▶ {sql}")
        conn.execute(text(sql))
    conn.commit()

print("✅ Migration tamamlandı.")
