import asyncio
from sqlalchemy import text
from app.database import engine

async def fix_queues():
    async with engine.begin() as conn:
        print("Cleaning up and normalizing ticket statuses and queues...")
        await conn.execute(text("UPDATE tickets SET status = 'resolved' WHERE status = 'automated';"))
        await conn.execute(text("UPDATE tickets SET status = 'open' WHERE status IN ('draft_ready', 'triaged');"))
        await conn.execute(text("UPDATE tickets SET status = 'working' WHERE status IN ('assisted', 'action_proposed') AND assigned_to IS NOT NULL;"))
        await conn.execute(text("UPDATE tickets SET status = 'open' WHERE status IN ('assisted', 'action_proposed') AND assigned_to IS NULL;"))
        await conn.execute(text("UPDATE tickets SET escalation_flag = TRUE WHERE status = 'escalated';"))
        await conn.execute(text("UPDATE tickets SET escalation_flag = FALSE WHERE status != 'escalated';"))
        await conn.execute(text("UPDATE tickets SET assigned_to = NULL, assigned_at = NULL WHERE status = 'open';"))
        await conn.execute(text("UPDATE tickets SET assigned_to = NULL, assigned_at = NULL WHERE status = 'escalated';"))
        default_agent_res = await conn.execute(text("SELECT id FROM users WHERE username = 'admin' LIMIT 1;"))
        row = default_agent_res.fetchone()
        agent_id = row[0] if row else None
        if agent_id:
            await conn.execute(text(f"UPDATE tickets SET assigned_to = '{agent_id}', assigned_at = COALESCE(assigned_at, updated_at, NOW()) WHERE status = 'working' AND assigned_to IS NULL;"))
        await conn.execute(text("UPDATE tickets SET resolved_at = COALESCE(resolved_at, updated_at, NOW()) WHERE status = 'resolved' AND resolved_at IS NULL;"))
        print("Database cleanup completed successfully.")

if __name__ == "__main__":
    asyncio.run(fix_queues())
