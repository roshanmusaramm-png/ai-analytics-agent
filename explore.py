import duckdb
import pandas as pd

# Try common encodings until one works
for enc in ['utf-8', 'latin-1', 'cp1252']:
    try:
        df = pd.read_csv('sales.csv', encoding=enc)
        print(f"Loaded successfully with encoding: {enc}")
        break
    except UnicodeDecodeError:
        continue

con = duckdb.connect()
con.register('sales', df)

print("\n=== SCHEMA ===")
print(con.execute("DESCRIBE sales").fetchdf())

print("\n=== SAMPLE ROWS ===")
print(con.execute("SELECT * FROM sales LIMIT 5").fetchdf())

print("\n=== ROW COUNT ===")
print(con.execute("SELECT COUNT(*) FROM sales").fetchdf())