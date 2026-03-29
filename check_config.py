"""配置检查脚本 - 验证 RentWise 环境配置"""

import os
import sys

def check_environment():
    """检查环境变量配置"""
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 50)
    print("RentWise Configuration Check")
    print("=" * 50)

    checks_passed = 0
    checks_failed = 0

    # Check OLLAMA_HOST
    ollama_host = os.getenv("OLLAMA_HOST")
    if ollama_host:
        print(f"[OK] OLLAMA_HOST: {ollama_host}")
        checks_passed += 1
    else:
        print("[FAIL] OLLAMA_HOST: NOT SET")
        checks_failed += 1

    # Check OLLAMA_API_KEY
    ollama_key = os.getenv("OLLAMA_API_KEY")
    if ollama_key:
        print(f"[OK] OLLAMA_API_KEY: {'*' * 8} (set)")
        checks_passed += 1
    else:
        print("[FAIL] OLLAMA_API_KEY: NOT SET")
        checks_failed += 1

    # Check SECRET_KEY
    secret_key = os.getenv("SECRET_KEY")
    if secret_key and secret_key != "your-secret-key-change-in-production":
        print(f"[OK] SECRET_KEY: {'*' * 8} (custom)")
        checks_passed += 1
    elif secret_key == "your-secret-key-change-in-production":
        print("[WARN] SECRET_KEY: Using default value (should change for production)")
        checks_passed += 1
    else:
        print("[FAIL] SECRET_KEY: NOT SET")
        checks_failed += 1

    # Check DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "sqlite:///./rentwise.db")
    print(f"[OK] DATABASE_URL: {db_url}")
    checks_passed += 1

    print()
    return checks_passed, checks_failed


def check_database():
    """检查数据库连接"""
    print("-" * 50)
    print("Database Check")
    print("-" * 50)

    try:
        from database import init_db, engine, DATABASE_URL
        import os

        # Get database path for SQLite
        if DATABASE_URL.startswith("sqlite"):
            db_path = DATABASE_URL.replace("sqlite:///", "")
            print(f"Database path: {os.path.abspath(db_path)}")

        # Try to initialize
        init_db()
        print("[OK] Database initialized successfully")

        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"[OK] Tables found: {tables}")

        return True, []
    except Exception as e:
        print(f"[FAIL] Database error: {e}")
        return False, [str(e)]


def check_llm_connection():
    """检查LLM连接"""
    print("-" * 50)
    print("LLM Connection Check")
    print("-" * 50)

    try:
        from llm_utils import _get_client
        client = _get_client()
        print("[OK] LLM client created successfully")
        return True, []
    except Exception as e:
        print(f"[FAIL] LLM client error: {e}")
        return False, [str(e)]


def main():
    """运行所有检查"""
    print()

    # Environment check
    env_passed, env_failed = check_environment()

    # Database check
    db_ok, db_errors = check_database()

    # LLM check
    llm_ok, llm_errors = check_llm_connection()

    # Summary
    print()
    print("=" * 50)
    print("Summary")
    print("=" * 50)

    if env_failed == 0 and db_ok and llm_ok:
        print("All checks passed! Ready to run RentWise.")
        print("\nTo start the app:")
        print("  streamlit run app.py")
        return 0
    else:
        print("Some checks failed. Please fix the issues above.")

        if not db_ok:
            print("\nDatabase troubleshooting:")
            print("  - Ensure the directory is writable")
            print("  - Check if rentwise.db file exists and is not locked")
            print("  - Try: python -c \"from database import init_db; init_db()\"")

        if not llm_ok:
            print("\nLLM troubleshooting:")
            print("  - Check OLLAMA_HOST is accessible")
            print("  - Verify OLLAMA_API_KEY is correct")

        return 1


if __name__ == "__main__":
    sys.exit(main())
