import sqlite3
import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates', static_folder='static')
DB_PATH = os.path.join(os.path.dirname(__file__), '로얄스타일_v4.db')

# Admin password for write operations (Default: admin123)
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

def verify_admin_auth():
    auth_header = request.headers.get('X-Admin-Password')
    data_password = request.json.get('admin_password') if request.is_json and request.json else None
    input_pw = auth_header or data_password
    if not input_pw or input_pw != ADMIN_PASSWORD:
        return False
    return True

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/categories_and_grades')
def categories_and_grades():
    conn = get_db()
    cur = conn.cursor()
    categories = [r[0] for r in cur.execute("SELECT DISTINCT category FROM items WHERE category IS NOT NULL AND category != '' ORDER BY category").fetchall()]
    grades = [r[0] for r in cur.execute("SELECT DISTINCT grade FROM items WHERE grade IS NOT NULL AND grade != '' ORDER BY grade").fetchall()]
    seasons = [r[0] for r in cur.execute("SELECT DISTINCT season FROM user_inventory WHERE season IS NOT NULL ORDER BY season ASC").fetchall()]
    conn.close()
    return jsonify({
        'categories': categories,
        'grades': grades,
        'seasons': seasons
    })

@app.route('/api/overview')
def overview():
    conn = get_db()
    cur = conn.cursor()
    
    # 1. basic counts
    total_items = cur.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    total_inventory_rows = cur.execute("SELECT COUNT(*) FROM user_inventory").fetchone()[0]
    total_quantity = cur.execute("SELECT COALESCE(SUM(quantity_obtained), 0) FROM user_inventory").fetchone()[0]
    
    sales_res = cur.execute("SELECT COALESCE(SUM(quantity_sold * sell_price), 0) as total_rev, COALESCE(SUM(quantity_sold), 0) as total_sold FROM sales").fetchone()
    total_sales_revenue = sales_res['total_rev']
    total_sales_count = sales_res['total_sold']

    # 2. Total inventory value using latest price
    val_res = cur.execute("""
        WITH LatestPrices AS (
            SELECT item_id, price,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            SELECT item_id, price FROM LatestPrices WHERE rn = 1
        ),
        -- Wait, fixed syntax below
    """).fetchall() if False else None

    inventory_val_query = """
        WITH LatestPrices AS (
            SELECT item_id, price,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            FROM prices
        ),
        ItemQty AS (
            SELECT item_id, SUM(quantity_obtained) as qty
            FROM user_inventory
            GROUP BY item_id
        )
        SELECT COALESCE(SUM(iq.qty * lp.price), 0) as total_val
        FROM ItemQty iq
        JOIN LatestPrices lp ON iq.item_id = lp.item_id AND lp.rn = 1
    """
    total_inventory_val = cur.execute(inventory_val_query).fetchone()[0]

    # 3. Grade breakdown with value
    grade_stats_query = """
        WITH LatestPrices AS (
            SELECT item_id, price,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            FROM prices
        ),
        ItemQty AS (
            SELECT item_id, SUM(quantity_obtained) as qty
            FROM user_inventory
            GROUP BY item_id
        )
        SELECT i.grade,
               COUNT(DISTINCT i.id) as item_count,
               COALESCE(SUM(iq.qty), 0) as total_qty,
               COALESCE(SUM(iq.qty * lp.price), 0) as total_val
        FROM items i
        LEFT JOIN ItemQty iq ON i.id = iq.item_id
        LEFT JOIN LatestPrices lp ON i.id = lp.item_id AND lp.rn = 1
        GROUP BY i.grade
        ORDER BY total_val DESC
    """
    grade_stats = [dict(r) for r in cur.execute(grade_stats_query).fetchall()]
    for g in grade_stats:
        g['formatted_val'] = format_meso(g['total_val'])

    # 4. Category breakdown with value
    cat_stats_query = """
        WITH LatestPrices AS (
            SELECT item_id, price,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            FROM prices
        ),
        ItemQty AS (
            SELECT item_id, SUM(quantity_obtained) as qty
            FROM user_inventory
            GROUP BY item_id
        )
        SELECT i.category,
               COUNT(DISTINCT i.id) as item_count,
               COALESCE(SUM(iq.qty), 0) as total_qty,
               COALESCE(SUM(iq.qty * lp.price), 0) as total_val
        FROM items i
        LEFT JOIN ItemQty iq ON i.id = iq.item_id
        LEFT JOIN LatestPrices lp ON i.id = lp.item_id AND lp.rn = 1
        GROUP BY i.category
        ORDER BY total_val DESC
    """
    cat_stats = [dict(r) for r in cur.execute(cat_stats_query).fetchall()]
    for c in cat_stats:
        c['formatted_val'] = format_meso(c['total_val'])

    # 5. Top 10 most valuable items
    top_items_query = """
        WITH LatestPrices AS (
            SELECT item_id, price, date,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            FROM prices
        ),
        ItemQty AS (
            SELECT item_id, SUM(quantity_obtained) as qty
            FROM user_inventory
            GROUP BY item_id
        )
        SELECT i.id, i.name, i.category, i.grade, iq.qty, lp.price as latest_price, (iq.qty * lp.price) as total_val
        FROM items i
        JOIN ItemQty iq ON i.id = iq.item_id
        JOIN LatestPrices lp ON i.id = lp.item_id AND lp.rn = 1
        ORDER BY total_val DESC
        LIMIT 10
    """
    top_items = [dict(r) for r in cur.execute(top_items_query).fetchall()]
    for item in top_items:
        item['formatted_price'] = format_meso(item['latest_price'])
        item['formatted_total_val'] = format_meso(item['total_val'])

    # 6. Season stats range
    seasons_res = cur.execute("SELECT MIN(season), MAX(season), COUNT(DISTINCT season) FROM user_inventory").fetchone()
    min_season, max_season, season_count = seasons_res[0], seasons_res[1], seasons_res[2]

    conn.close()

    return jsonify({
        'total_items': total_items,
        'total_inventory_rows': total_inventory_rows,
        'total_quantity': total_quantity,
        'total_inventory_val': total_inventory_val,
        'formatted_inventory_val': format_meso(total_inventory_val),
        'total_sales_revenue': total_sales_revenue,
        'formatted_sales_revenue': format_meso(total_sales_revenue),
        'total_sales_count': total_sales_count,
        'min_season': min_season,
        'max_season': max_season,
        'season_count': season_count,
        'grade_stats': grade_stats,
        'category_stats': cat_stats,
        'top_items': top_items
    })

@app.route('/api/items')
def list_items():
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    grade = request.args.get('grade', '').strip()
    season = request.args.get('season', '').strip()
    owned_only = request.args.get('owned_only', '').strip().lower() == 'true'
    sort_by = request.args.get('sort_by', 'total_val')
    order = request.args.get('order', 'desc').upper()
    
    if order not in ['ASC', 'DESC']:
        order = 'DESC'

    conn = get_db()
    cur = conn.cursor()

    sql = """
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
        WHERE 1=1
    """
    params = []

    if q:
        sql += " AND i.name LIKE ?"
        params.append(f"%{q}%")
    if category:
        sql += " AND i.category = ?"
        params.append(category)
    if grade:
        sql += " AND i.grade = ?"
        params.append(grade)
    if owned_only:
        sql += " AND COALESCE(iq.qty, 0) > 0"
    if season:
        sql += " AND i.id IN (SELECT item_id FROM user_inventory WHERE season = ?)"
        params.append(season)

    # Sorting
    valid_sorts = {
        'name': 'i.name',
        'category': 'i.category',
        'grade': 'i.grade',
        'qty': 'qty',
        'latest_price': 'latest_price',
        'total_val': 'total_val',
        'season_count': 'season_count'
    }
    sort_column = valid_sorts.get(sort_by, 'total_val')
    sql += f" ORDER BY {sort_column} {order} NULLS LAST"

    rows = cur.execute(sql, params).fetchall()
    items = []
    for r in rows:
        item = dict(r)
        item['formatted_price'] = format_meso(item['latest_price']) if item['latest_price'] else "시세 미등록"
        item['formatted_total_val'] = format_meso(item['total_val'])
        items.append(item)

    conn.close()
    return jsonify({
        'total': len(items),
        'items': items
    })

@app.route('/api/items/<int:item_id>')
def get_item_detail(item_id):
    conn = get_db()
    cur = conn.cursor()

    # 1. Item info
    item_row = cur.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item_row:
        conn.close()
        return jsonify({'error': '아이템을 찾을 수 없습니다.'}), 404

    item = dict(item_row)

    # 2. Price History
    prices = [dict(r) for r in cur.execute("SELECT id, price, date FROM prices WHERE item_id = ? ORDER BY date ASC, id ASC", (item_id,)).fetchall()]
    for p in prices:
        p['formatted_price'] = format_meso(p['price'])

    # 3. Inventory Breakdown
    inventory = [dict(r) for r in cur.execute("SELECT season, quantity_obtained FROM user_inventory WHERE item_id = ? ORDER BY season ASC", (item_id,)).fetchall()]

    # 4. Sales History
    sales = [dict(r) for r in cur.execute("SELECT id, quantity_sold, sell_price, sell_date FROM sales WHERE item_id = ? ORDER BY sell_date DESC", (item_id,)).fetchall()]
    for s in sales:
        s['formatted_price'] = format_meso(s['sell_price'])
        s['total_sold_val'] = format_meso(s['quantity_sold'] * s['sell_price'])

    # 5. Price Stats
    latest_price = prices[-1]['price'] if prices else 0
    avg_price = sum(p['price'] for p in prices) / len(prices) if prices else 0
    min_price = min(p['price'] for p in prices) if prices else 0
    max_price = max(p['price'] for p in prices) if prices else 0
    total_qty = sum(inv['quantity_obtained'] for inv in inventory)
    total_val = total_qty * latest_price

    item_detail = {
        'item': item,
        'prices': prices,
        'inventory': inventory,
        'sales': sales,
        'stats': {
            'latest_price': latest_price,
            'formatted_latest_price': format_meso(latest_price),
            'avg_price': int(avg_price),
            'formatted_avg_price': format_meso(avg_price),
            'min_price': min_price,
            'formatted_min_price': format_meso(min_price),
            'max_price': max_price,
            'formatted_max_price': format_meso(max_price),
            'total_quantity': total_qty,
            'total_value': total_val,
            'formatted_total_val': format_meso(total_val)
        }
    }

    conn.close()
    return jsonify(item_detail)

@app.route('/api/seasons')
def list_seasons():
    conn = get_db()
    cur = conn.cursor()

    query = """
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
    """
    rows = cur.execute(query).fetchall()
    seasons = []
    for r in rows:
        season = dict(r)
        season['formatted_val'] = format_meso(season['total_val'])
        seasons.append(season)

    conn.close()
    return jsonify(seasons)

@app.route('/api/seasons/<int:season_id>')
def get_season_detail(season_id):
    conn = get_db()
    cur = conn.cursor()

    query = """
        WITH LatestPrices AS (
            SELECT item_id, price, date,
                   ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY date DESC, id DESC) as rn
            FROM prices
        )
        SELECT i.id, i.name, i.category, i.grade, ui.quantity_obtained, lp.price as latest_price,
               (ui.quantity_obtained * COALESCE(lp.price, 0)) as total_val
        FROM user_inventory ui
        JOIN items i ON ui.item_id = i.id
        LEFT JOIN LatestPrices lp ON i.id = lp.item_id AND lp.rn = 1
        WHERE ui.season = ?
        ORDER BY total_val DESC
    """
    rows = cur.execute(query, (season_id,)).fetchall()
    items = []
    total_val = 0
    total_qty = 0

    for r in rows:
        item = dict(r)
        item['formatted_price'] = format_meso(item['latest_price']) if item['latest_price'] else "시세 미등록"
        item['formatted_total_val'] = format_meso(item['total_val'])
        items.append(item)
        total_val += item['total_val']
        total_qty += item['quantity_obtained']

    conn.close()
    return jsonify({
        'season': season_id,
        'items': items,
        'total_items': len(items),
        'total_qty': total_qty,
        'total_val': total_val,
        'formatted_total_val': format_meso(total_val)
    })

@app.route('/api/sales', methods=['GET'])
def list_sales():
    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT s.id, s.item_id, s.quantity_sold, s.sell_price, s.sell_date,
               i.name, i.category, i.grade,
               (s.quantity_sold * s.sell_price) as total_sell_val
        FROM sales s
        JOIN items i ON s.item_id = i.id
        ORDER BY s.sell_date DESC, s.id DESC
    """
    rows = cur.execute(sql).fetchall()
    sales = []
    total_revenue = 0

    for r in rows:
        sale = dict(r)
        sale['formatted_price'] = format_meso(sale['sell_price'])
        sale['formatted_total_sell_val'] = format_meso(sale['total_sell_val'])
        sales.append(sale)
        total_revenue += sale['total_sell_val']

    conn.close()
    return jsonify({
        'sales': sales,
        'total_revenue': total_revenue,
        'formatted_total_revenue': format_meso(total_revenue),
        'total_sales_count': len(sales)
    })

@app.route('/api/items', methods=['POST'])
def add_item_api():
    if not verify_admin_auth():
        return jsonify({'error': '권한이 없습니다. 관리자 비밀번호가 필요합니다.'}), 403

    data = request.json or {}
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    grade = data.get('grade', '').strip()
    quantity = int(data.get('quantity', 1))
    season = int(data.get('season', 88))
    price = int(data.get('price', 0))
    date = data.get('date') or datetime.now().strftime("%Y-%m-%d")

    if not name or not category or not grade:
        return jsonify({'error': '이름, 카테고리, 등급은 필수 입력 항목입니다.'}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        # 1. 아이템 등록 (또는 조회)
        cur.execute('INSERT OR IGNORE INTO items (name, category, grade) VALUES (?, ?, ?)', (name, category, grade))
        cur.execute('SELECT id FROM items WHERE name = ?', (name,))
        item_id = cur.fetchone()[0]

        # 2. 인벤토리 수량 등록
        if quantity > 0:
            cur.execute('SELECT quantity_obtained FROM user_inventory WHERE item_id = ? AND season = ?', (item_id, season))
            row = cur.fetchone()
            if row:
                cur.execute('UPDATE user_inventory SET quantity_obtained = quantity_obtained + ? WHERE item_id = ? AND season = ?', 
                            (quantity, item_id, season))
            else:
                cur.execute('INSERT INTO user_inventory (item_id, season, quantity_obtained) VALUES (?, ?, ?)', 
                            (item_id, season, quantity))

        # 3. 시세 등록
        if price > 0:
            cur.execute('INSERT INTO prices (item_id, price, date) VALUES (?, ?, ?)', (item_id, price, date))

        conn.commit()
        conn.close()
        return jsonify({'message': f'{name} 등록/업데이트 완료', 'item_id': item_id}), 201
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item_api(item_id):
    if not verify_admin_auth():
        return jsonify({'error': '권한이 없습니다. 관리자 비밀번호가 필요합니다.'}), 403

    data = request.json or {}
    grade = data.get('grade')
    category = data.get('category')
    name = data.get('name')

    conn = get_db()
    cur = conn.cursor()
    try:
        if grade:
            cur.execute("UPDATE items SET grade = ? WHERE id = ?", (grade, item_id))
        if category:
            cur.execute("UPDATE items SET category = ? WHERE id = ?", (category, item_id))
        if name:
            cur.execute("UPDATE items SET name = ? WHERE id = ?", (name, item_id))
        
        conn.commit()
        conn.close()
        return jsonify({'message': '아이템 정보가 수정되었습니다.'}), 200
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/prices', methods=['POST'])
def add_price_api():
    if not verify_admin_auth():
        return jsonify({'error': '권한이 없습니다. 관리자 비밀번호가 필요합니다.'}), 403

    data = request.json or {}
    item_id = data.get('item_id')
    price = data.get('price')
    date = data.get('date') or datetime.now().strftime("%Y-%m-%d")

    if not item_id or price is None:
        return jsonify({'error': 'item_id와 price는 필수 입력 항목입니다.'}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO prices (item_id, price, date) VALUES (?, ?, ?)', (item_id, price, date))
        conn.commit()
        conn.close()
        return jsonify({'message': '시세 기록 추가 성공'}), 201
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales', methods=['POST'])
def add_sales_api():
    if not verify_admin_auth():
        return jsonify({'error': '권한이 없습니다. 관리자 비밀번호가 필요합니다.'}), 403
    data = request.json or {}
    item_id = data.get('item_id')
    quantity_sold = int(data.get('quantity_sold', 1))
    sell_price = int(data.get('sell_price', 0))
    sell_date = data.get('sell_date') or datetime.now().strftime("%Y-%m-%d")

    if not item_id or sell_price <= 0:
        return jsonify({'error': 'item_id와 유효한 판매가는 필수 입력 항목입니다.'}), 400

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO sales (item_id, quantity_sold, sell_price, sell_date) VALUES (?, ?, ?, ?)',
                    (item_id, quantity_sold, sell_price, sell_date))
        conn.commit()
        conn.close()
        return jsonify({'message': '판매 내역 추가 성공'}), 201
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Serving MapleStory Royal Style DB Explorer on http://127.0.0.1:5000 ...")
    app.run(host='127.0.0.1', port=5000, debug=True)
