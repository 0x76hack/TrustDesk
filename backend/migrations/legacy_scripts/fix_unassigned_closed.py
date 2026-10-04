import asyncio
from sqlalchemy import text
from app.database import engine

async def fix_closed():
    async with engine.begin() as conn:
        print("Ensuring all resolved tickets have an assigned operative...")
        admin_res = await conn.execute(text("SELECT id FROM users WHERE username = 'admin' LIMIT 1;"))
        row = admin_res.fetchone()
        if row:
            admin_id = row[0]
            await conn.execute(text(f"UPDATE tickets SET assigned_to = '{admin_id}' WHERE status = 'resolved' AND assigned_to IS NULL;"))
            print(f"Updated unassigned resolved tickets to admin ({admin_id}).")

if __name__ == "__main__":
    asyncio.run(fix_closed())
