import sys
import os
import pymysql

# Step 1: Connect to MySQL server and ensure database 'radhu_db' exists
def ensure_mysql_db(host="127.0.0.1", user="root", password="123456", port=3306, db_name="radhu_db"):
    try:
        conn = pymysql.connect(host=host, user=user, password=password, port=port)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        print(f"✅ MySQL database '{db_name}' ensured on {host}:{port}!")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ Could not connect to MySQL server with provided credentials ({e}).")
        return False

if __name__ == '__main__':
    pw = sys.argv[1] if len(sys.argv) > 1 else '123456'
    ensure_mysql_db(password=pw)
