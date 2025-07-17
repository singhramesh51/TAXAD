import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DB_URL')

create_table_sql = '''
CREATE TABLE IF NOT EXISTS UserFinancials (
    session_id UUID PRIMARY KEY,
    gross_salary NUMERIC(15, 2),
    basic_salary NUMERIC(15, 2),
    hra_received NUMERIC(15, 2),
    rent_paid NUMERIC(15, 2),
    deduction_80c NUMERIC(15, 2),
    deduction_80d NUMERIC(15, 2),
    standard_deduction NUMERIC(15, 2),
    professional_tax NUMERIC(15, 2),
    tds NUMERIC(15, 2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
'''

def main():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(create_table_sql)
        conn.commit()
        print('UserFinancials table created or already exists.')
        cur.close()
        conn.close()
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    main() 