import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.database import execute, get_pool, close_pool

async def main():
    print("Connecting to DB...")
    await get_pool()
    
    schema_path = r"d:\pro2\database\schema.sql"
    m2_path = r"d:\pro2\database\migrations\002_add_notes.sql"
    m3_path = r"d:\pro2\database\migrations\003_add_missing_foreign_key_indexes.sql"
    
    try:
        print("Dropping existing tables to ensure clean schema...")
        await execute("DROP TABLE IF EXISTS notes, outputs, jobs, videos, password_resets, email_verifications, users CASCADE;")
        
        with open(schema_path, "r", encoding="utf-8") as f:
            print("Executing schema.sql...")
            await execute(f.read())
            
        with open(m2_path, "r", encoding="utf-8") as f:
            print("Executing 002_add_notes.sql...")
            await execute(f.read())
            
        with open(m3_path, "r", encoding="utf-8") as f:
            print("Executing 003_add_missing_foreign_key_indexes.sql...")
            await execute(f.read())
            
        print("Schema applied successfully!")
    except Exception as e:
        print(f"Error applying schema: {e}")
    finally:
        await close_pool()

if __name__ == "__main__":
    asyncio.run(main())
