import sqlite3
import sys
from datetime import datetime

def add_item_parametrized(name, category, grade, quantity, season, price, date=None):
    db_file = '로얄스타일_v4.db'
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    if date is None:
        today = datetime.now().strftime("%Y-%m-%d")
    else:
        today = date

    try:
        # 1. 아이템 정보 등록
        cur.execute('INSERT OR IGNORE INTO items (name, category, grade) VALUES (?, ?, ?)', (name, category, grade))
        cur.execute('SELECT id FROM items WHERE name = ?', (name,))
        item_id = cur.fetchone()[0]

        # 2. 인벤토리 수량 반영
        cur.execute('SELECT quantity_obtained FROM user_inventory WHERE item_id = ? AND season = ?', (item_id, season))
        row = cur.fetchone()
        if row:
            cur.execute('UPDATE user_inventory SET quantity_obtained = quantity_obtained + ? WHERE item_id = ? AND season = ?', 
                        (quantity, item_id, season))
        else:
            cur.execute('INSERT INTO user_inventory (item_id, season, quantity_obtained) VALUES (?, ?, ?)', 
                        (item_id, season, quantity))

        # 3. 가격 정보 등록
        cur.execute('INSERT INTO prices (item_id, price, date) VALUES (?, ?, ?)', (item_id, price, today))
        
        conn.commit()
        print(f"성공: {name} ({quantity}개, {price:,}원) 반영 완료.")

    except Exception as e:
        conn.rollback()
        print(f"오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("사용법: python add_item.py [이름] [분류] [등급] [개수] [시즌] [가격] [날짜(선택, YYYY-MM-DD)]")
    else:
        name = sys.argv[1]
        category = sys.argv[2]
        grade = sys.argv[3]
        quantity = int(sys.argv[4])
        season = int(sys.argv[5])
        price = int(sys.argv[6])
        date = sys.argv[7] if len(sys.argv) > 7 else None
        add_item_parametrized(name, category, grade, quantity, season, price, date)
