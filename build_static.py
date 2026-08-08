import sqlite3
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = r'c:\Users\coke1\OneDrive\바탕 화면\test\로얄스타일_v4.db'
OUTPUT_DIR = r'c:\Users\coke1\OneDrive\바탕 화면\test'
DATA_DIR = os.path.join(OUTPUT_DIR, 'data')

os.makedirs(DATA_DIR, exist_ok=True)

def format_meso(price):
    if price is None or price == 0:
        return "0 메소"
    
    price = int(price)
    eok = price // 100_000_000
    remainder = price % 100_000_000
    man = remainder // 10_000
    
    parts = []
    if eok > 0:
        parts.append(f"{eok:,}억")
    if man > 0:
        parts.append(f"{man:,}만")
    
    if not parts:
        return f"{price:,} 메소"
    
    return " ".join(parts) + " 메소"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("Building static dataset from 로얄스타일_v4.db ...")

# 1. Categories, Grades, Seasons
categories = [r[0] for r in cur.execute("SELECT DISTINCT category FROM items WHERE category IS NOT NULL AND category != '' ORDER BY category").fetchall()]
grades = [r[0] for r in cur.execute("SELECT DISTINCT grade FROM items WHERE grade IS NOT NULL AND grade != '' ORDER BY grade").fetchall()]
seasons = [r[0] for r in cur.execute("SELECT DISTINCT season FROM user_inventory WHERE season IS NOT NULL ORDER BY season ASC").fetchall()]

# 2. Items list with latest price & inventory
items_raw = cur.execute("""
    WITH LatestPrices AS (
        SELECT item_id, price, date,
               ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
        FROM prices
    ),
    ItemQty AS (
        SELECT item_id, SUM(quantity_obtained) as qty, COUNT(DISTINCT season) as season_count, GROUP_CONCAT(DISTINCT season) as seasons
        FROM user_inventory
        GROUP BY item_id
    )
    SELECT i.id, i.name, i.category, i.grade,
           COALESCE(iq.qty, 0) as qty,
           COALESCE(iq.season_count, 0) as season_count,
           iq.seasons,
           lp.price as latest_price,
           lp.date as latest_price_date,
           (COALESCE(iq.qty, 0) * COALESCE(lp.price, 0)) as total_val
    FROM items i
    LEFT JOIN ItemQty iq ON i.id = iq.item_id
    LEFT JOIN LatestPrices lp ON i.id = lp.item_id AND lp.rn = 1
    ORDER BY total_val DESC
""").fetchall()

items = []
for r in items_raw:
    item = dict(r)
    item['formatted_price'] = format_meso(item['latest_price']) if item['latest_price'] else "시세 미등록"
    item['formatted_total_val'] = format_meso(item['total_val'])
    items.append(item)

# 3. Complete Price Histories
prices_all = [dict(r) for r in cur.execute("SELECT id, item_id, price, date FROM prices ORDER BY date ASC, id ASC").fetchall()]
prices_by_item = {}
for p in prices_all:
    p['formatted_price'] = format_meso(p['price'])
    iid = p['item_id']
    if iid not in prices_by_item:
        prices_by_item[iid] = []
    prices_by_item[iid].append(p)

# 4. Inventory Breakdown by item
inventory_all = [dict(r) for r in cur.execute("SELECT item_id, season, quantity_obtained FROM user_inventory ORDER BY season ASC").fetchall()]
inventory_by_item = {}
for inv in inventory_all:
    iid = inv['item_id']
    if iid not in inventory_by_item:
        inventory_by_item[iid] = []
    inventory_by_item[iid].append(inv)

# 5. Sales Records
sales_all = [dict(r) for r in cur.execute("""
    SELECT s.id, s.item_id, s.quantity_sold, s.sell_price, s.sell_date,
           i.name, i.category, i.grade,
           (s.quantity_sold * s.sell_price) as total_sell_val
    FROM sales s
    JOIN items i ON s.item_id = i.id
    ORDER BY s.sell_date DESC, s.id DESC
""").fetchall()]

total_sales_revenue = 0
sales = []
sales_by_item = {}

for s in sales_all:
    sale = dict(s)
    sale['formatted_price'] = format_meso(sale['sell_price'])
    sale['formatted_total_sell_val'] = format_meso(sale['total_sell_val'])
    sales.append(sale)
    total_sales_revenue += sale['total_sell_val']
    
    iid = sale['item_id']
    if iid not in sales_by_item:
        sales_by_item[iid] = []
    sales_by_item[iid].append(sale)

# 6. Season summaries
season_rows = cur.execute("""
    WITH LatestPrices AS (
        SELECT item_id, price,
               ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
        FROM prices
    )
    SELECT ui.season,
           COUNT(DISTINCT ui.item_id) as item_count,
           SUM(ui.quantity_obtained) as total_qty,
           COALESCE(SUM(ui.quantity_obtained * lp.price), 0) as total_val
    FROM user_inventory ui
    LEFT JOIN LatestPrices lp ON ui.item_id = lp.item_id AND lp.rn = 1
    GROUP BY ui.season
    ORDER BY ui.season DESC
""").fetchall()

seasons_summary = []
for r in season_rows:
    s = dict(r)
    s['formatted_val'] = format_meso(s['total_val'])
    seasons_summary.append(s)

# Bundle into db.json
db_bundle = {
    'metadata': {
        'total_items': len(items),
        'total_quantity': sum(i['qty'] for i in items),
        'total_inventory_val': sum(i['total_val'] for i in items),
        'formatted_inventory_val': format_meso(sum(i['total_val'] for i in items)),
        'total_sales_revenue': total_sales_revenue,
        'formatted_sales_revenue': format_meso(total_sales_revenue),
        'total_sales_count': len(sales),
        'min_season': min(seasons) if seasons else 88,
        'max_season': max(seasons) if seasons else 159,
        'season_count': len(seasons)
    },
    'categories': categories,
    'grades': grades,
    'seasons': seasons,
    'items': items,
    'prices_by_item': prices_by_item,
    'inventory_by_item': inventory_by_item,
    'sales': sales,
    'sales_by_item': sales_by_item,
    'seasons_summary': seasons_summary
}

output_json_path = os.path.join(DATA_DIR, 'db.json')
with open(output_json_path, 'w', encoding='utf-8') as f:
    json.dump(db_bundle, f, ensure_ascii=False, indent=2)

print(f"Static dataset bundle written to {output_json_path} ({os.path.getsize(output_json_path) / 1024:.1f} KB)")
conn.close()
