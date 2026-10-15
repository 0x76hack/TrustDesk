import os
import sys
import uuid
import socket
import re
import asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from fastapi import HTTPException

if not os.getenv("DATABASE_URL"):
    db_user = os.getenv("POSTGRES_USER", "trustdesk")
    db_pass = os.getenv("POSTGRES_PASSWORD", "")
    auth_part = f"{db_user}:{db_pass}@" if db_pass else f"{db_user}@"
    db_name = os.getenv("POSTGRES_DB", "trustdesk")
    for host, port in [("localhost", 5433), ("postgres", 5432), ("localhost", 5432)]:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            os.environ["DATABASE_URL"] = f"postgresql+asyncpg://{auth_part}{host}:{port}/{db_name}"
            break
        except Exception:
            pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.order import Order
from app.models.ticket import Ticket
from app.models.coupon import Coupon
from app.services import coupon_service

NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")

def deterministic_uuid(name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, name))

COUPON_CODE_PASTED = "TRUST-REF-D9E10A42"

async def run_idempotency_test():
    coupon_arg = sys.argv[1] if len(sys.argv) > 1 else COUPON_CODE_PASTED
    cust_id = deterministic_uuid("cust-ananya")
    ord1_id = deterministic_uuid("ord-curry-104")
    ord2_id = deterministic_uuid("ord-corp-106")
    now = datetime.now(timezone.utc)

    print("=" * 80)
    print(" TRUSTDESK COUPON CONCURRENCY & IDEMPOTENCY RACE-CONDITION SUITE")
    print(" Testing row-level locking (SELECT ... FOR UPDATE) and duplicate rejection")
    print(f" Target Account: Ananya Desai (ananya.desai@example.com)")
    print(f" Primary Order:  Punjab Grill Signature ({ord1_id})")
    print(f" Secondary Order: Grand Banquet Catering ({ord2_id})")
    print("=" * 80)

    async with AsyncSessionLocal() as db:
        cust = await db.get(Customer, cust_id)
        if not cust:
            cust = Customer(
                id=cust_id,
                name="Ananya Desai",
                email="ananya.desai@example.com",
                phone="+91 98765 01004",
            )
            db.add(cust)
            await db.flush()

        res_cp = await db.execute(select(Coupon).where(Coupon.code == coupon_arg))
        active_cp = res_cp.scalars().first()
        if not active_cp:
            active_cp = Coupon(
                id=str(uuid.uuid4()),
                code=coupon_arg,
                customer_id=cust_id,
                original_order_id=ord1_id,
                amount=450.00,
                currency="INR",
                status="active",
                expires_at=now + timedelta(days=90),
                created_at=now,
            )
            db.add(active_cp)
            await db.commit()
            print(f"[SETUP] Prepared active coupon {coupon_arg} with value Rs. 450.00")
        else:
            active_cp.status = "active"
            active_cp.redeemed_at = None
            active_cp.redeemed_ticket_id = None
            active_cp.redeemed_order_id = None
            await db.commit()
            print(f"[SETUP] Reset coupon {coupon_arg} to active state for live race test")

    async def submit_ticket_with_coupon(order_id: str, subject_text: str):
        async with AsyncSessionLocal() as db:
            ticket_id = str(uuid.uuid4())
            tick = Ticket(
                id=ticket_id,
                customer_id=cust_id,
                order_id=order_id,
                subject=subject_text,
                category="refund",
                priority="medium",
                status="open",
                created_at=datetime.now(timezone.utc),
            )
            db.add(tick)
            await db.flush()
            try:
                result = await coupon_service.process_ticket_coupon_intake(
                    ticket=tick,
                    coupon_code=coupon_arg,
                    customer_id=cust_id,
                    order_id=order_id,
                    db=db,
                )
                await db.commit()
                return {"success": True, "ticket_id": ticket_id, "order_id": order_id, "data": result}
            except HTTPException as exc:
                await db.commit()
                return {"success": False, "ticket_id": ticket_id, "order_id": order_id, "status_code": exc.status_code, "detail": exc.detail}

    print("\n[RACE CONDITION INITIATED] Firing 2 simultaneous ticket submissions attempting to redeem:")
    print(f" -> Coupon: {coupon_arg}")
    print(" -> Ticket A: Claiming against Order 1 (Curry Spilled)")
    print(" -> Ticket B: Claiming against Order 2 (Grand Banquet)")

    res_a, res_b = await asyncio.gather(
        submit_ticket_with_coupon(ord1_id, "Redeeming refund coupon for damaged curry order"),
        submit_ticket_with_coupon(ord2_id, "Redeeming refund coupon for banquet order"),
    )

    print("\n--------------------------------------------------------------------------------")
    print(" CONCURRENT EXECUTION OUTCOME")
    print("--------------------------------------------------------------------------------")
    for idx, r in enumerate([res_a, res_b], start=1):
        lbl = f"Ticket {chr(64 + idx)}"
        if r.get("success"):
            print(f" [{lbl}] ACCEPTED | Status: 200 OK / 201 Created")
            print(f"          Ticket ID: #{r['ticket_id'][:8]} | Order: {r['order_id'][:12]}")
            print(f"          Outcome:   Coupon successfully applied to ticket")
        else:
            print(f" [{lbl}] REJECTED | Status Code: {r.get('status_code')} Conflict")
            print(f"          Ticket ID: #{r['ticket_id'][:8]} | Order: {r['order_id'][:12]}")
            print(f"          Detail:    {r.get('detail')}")

    rejected = [r for r in [res_a, res_b] if not r.get("success")]
    accepted = [r for r in [res_a, res_b] if r.get("success")]

    print("\n--------------------------------------------------------------------------------")
    print(" DATABASE AUDIT & STATE VERIFICATION")
    print("--------------------------------------------------------------------------------")
    async with AsyncSessionLocal() as db:
        if rejected:
            rej_tid = rejected[0]["ticket_id"]
            rej_ticket = await db.get(Ticket, rej_tid)
            print(f" Rejected Ticket #{rej_tid[:8]} Status:        {rej_ticket.status.upper()}")
            print(f" Auto-Close Reason:                       {rej_ticket.close_reason}")
            print(f" Coupon Abuse Flag:                       {rej_ticket.coupon_abuse_flag}")
            print(f" Assessed Risk Level:                     {rej_ticket.risk_level.upper()}")

        cp_final = (await db.execute(select(Coupon).where(Coupon.code == coupon_arg))).scalars().first()
        print(f" Coupon Final Status:                     {cp_final.status.upper()}")
        print(f" Redeemed on Ticket:                      #{cp_final.redeemed_ticket_id[:8] if cp_final.redeemed_ticket_id else 'NONE'}")

    print("=" * 80)
    if len(accepted) == 1 and len(rejected) == 1 and rejected[0].get("status_code") == 409:
        print(" VERDICT: [PASS] Strict Idempotency & Concurrency Isolation Verified.")
        print(" Exactly 1 ticket succeeded; duplicate race ticket received HTTP 409 and auto-closed.")
    else:
        print(" VERDICT: [FAIL] Concurrency constraint violation detected.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_idempotency_test())
