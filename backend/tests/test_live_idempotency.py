import asyncio
import os
import sys
import re
import socket
import uuid
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select

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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
if os.getenv("DATABASE_URL"):
    settings.DATABASE_URL = os.environ["DATABASE_URL"]

from app import database
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
database.engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=20, max_overflow=10, pool_pre_ping=True)
database.AsyncSessionLocal = async_sessionmaker(database.engine, class_=AsyncSession, expire_on_commit=False)
AsyncSessionLocal = database.AsyncSessionLocal
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.coupon import Coupon
from app.services.coupon_service import redeem_coupon
from fastapi import HTTPException

async def run_live_test():
    async with AsyncSessionLocal() as db:
        cust_res = await db.execute(select(Customer).limit(1))
        customer = cust_res.scalars().first()
        if not customer:
            customer = Customer(
                id=str(uuid.uuid4()),
                name="Ananya Desai",
                email="ananya.desai@example.com",
                phone="+91 98765 01004",
                address="304 Green Valley, Whitefield, Bengaluru",
                membership_tier="Pro Tier VIP",
            )
            db.add(customer)
            await db.flush()

        order_a = Order(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            restaurant="Punjab Grill Signature",
            restaurant_address="Whitefield Main Road, Bengaluru",
            delivery_address=customer.address,
            status="delivered",
            total=650.00,
            payment_method="NetBanking",
        )
        order_b = Order(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            restaurant="Lotus Thai Pavilion",
            restaurant_address="MG Road, Bengaluru",
            delivery_address=customer.address,
            status="delivered",
            total=920.00,
            payment_method="UPI",
        )
        db.add(order_a)
        db.add(order_b)
        await db.flush()

        db.add(OrderItem(
            id=str(uuid.uuid4()),
            order_id=order_a.id,
            item_name="Dal Makhani Special (2 Portions)",
            quantity=1,
            unit_price=450.00,
        ))
        db.add(OrderItem(
            id=str(uuid.uuid4()),
            order_id=order_a.id,
            item_name="Butter Naan (4 Pieces)",
            quantity=1,
            unit_price=200.00,
        ))
        db.add(OrderItem(
            id=str(uuid.uuid4()),
            order_id=order_b.id,
            item_name="Pad Thai Noodles",
            quantity=1,
            unit_price=540.00,
        ))
        await db.flush()

        ticket_id = str(uuid.uuid4())
        ticket = Ticket(
            id=ticket_id,
            customer_id=customer.id,
            order_id=order_a.id,
            subject="Order Damaged: Curry spilled entirely through carton",
            category="refund",
            priority="high",
            status="working",
            risk_level="medium",
            escalation_flag=False,
        )
        db.add(ticket)
        await db.flush()

        msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            sender_type="customer",
            content="The delivery bag arrived soaked and torn. Both containers of Dal Makhani burst open inside the package. Everything is spoiled and inedible. Please issue refund.",
            created_at=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.commit()

        print("\n" + "=" * 76)
        print(" [LIVE TEST STEP 1] Created Ticket for Live Approval")
        print(f" Ticket ID: {ticket.id}")
        print(f" Linked Order A: {order_a.id} (Total: Rs. {order_a.total:.2f})")
        print(f" Target Order B: {order_b.id} (Total: Rs. {order_b.total:.2f})")
        print(" ACTION REQUIRED:")
        print(f" Open TrustDesk in your browser, select Ticket #{ticket.id[:8]}, and click 'Issue Refund'.")
        print(" Waiting for live coupon issuance in dashboard (polling every 2s)...")
        print("=" * 76 + "\n")

    issued_coupon_code = None
    while not issued_coupon_code:
        await asyncio.sleep(2)
        async with AsyncSessionLocal() as db_check:
            t = await db_check.get(Ticket, ticket_id)
            if t and t.coupon_code:
                issued_coupon_code = t.coupon_code
                print(f"\n[LIVE TEST STEP 2] Detected Live Coupon Issued from Dashboard: {issued_coupon_code}")
                break

    print("\n" + "=" * 76)
    print(" [LIVE TEST STEP 3] Executing 2 Simultaneous Concurrent Redemption Requests")
    print(f" Using live coupon code: {issued_coupon_code}")
    print(" Request 1: Redeem on Order A (Valid order)")
    print(" Request 2: Redeem on Order B (Concurrent reuse attempt on another order)")
    print("=" * 76 + "\n")

    async def attempt_order_a():
        async with AsyncSessionLocal() as session_a:
            try:
                cp, is_replay = await redeem_coupon(
                    coupon_code=issued_coupon_code,
                    customer_id=customer.id,
                    order_id=order_a.id,
                    db=session_a,
                    ticket_id=ticket_id,
                    idempotency_key=f"live_idemp_key_{ticket_id}",
                )
                await session_a.commit()
                return {"status": "success", "order": "A", "code": cp.code, "is_replay": is_replay}
            except HTTPException as exc:
                return {"status": "error", "order": "A", "code": exc.status_code, "detail": exc.detail}

    async def attempt_order_b():
        async with AsyncSessionLocal() as session_b:
            try:
                cp, is_replay = await redeem_coupon(
                    coupon_code=issued_coupon_code,
                    customer_id=customer.id,
                    order_id=order_b.id,
                    db=session_b,
                    ticket_id=ticket_id,
                    idempotency_key=f"live_idemp_key_b_{ticket_id}",
                )
                await session_b.commit()
                return {"status": "success", "order": "B", "code": cp.code, "is_replay": is_replay}
            except HTTPException as exc:
                return {"status": "error", "order": "B", "code": exc.status_code, "detail": exc.detail}

    res_a, res_b = await asyncio.gather(attempt_order_a(), attempt_order_b())

    print(f" Result on Order A: {res_a}")
    print(f" Result on Order B: {res_b}")

    print("\n" + "=" * 76)
    print(" [LIVE TEST STEP 4] Executing Idempotent Replay on Order A with Same Key")
    print("=" * 76 + "\n")

    async with AsyncSessionLocal() as session_replay:
        replay_res = await redeem_coupon(
            coupon_code=issued_coupon_code,
            customer_id=customer.id,
            order_id=order_a.id,
            db=session_replay,
            ticket_id=ticket_id,
            idempotency_key=f"live_idemp_key_{ticket_id}",
        )
        replay_coupon, is_replay_flag = replay_res
        print(f" Replay Result: Code={replay_coupon.code}, Status={replay_coupon.status}, IsReplay={is_replay_flag}")

    print("\n" + "=" * 76)
    print(" [IDEMPOTENCY VERIFICATION SUMMARY]")
    print(f" 1. Coupon Issued Live: {issued_coupon_code} (Ticket #{ticket_id[:8]})")
    print(f" 2. Order A Redemption: {'PASS' if res_a.get('status') == 'success' else 'FAIL'}")
    print(f" 3. Order B Concurrent Reuse Blocked: {'PASS (409 Conflict)' if res_b.get('status') == 'error' and res_b.get('code') == 409 else 'FAIL'}")
    print(f" 4. Order A Idempotent Replay: {'PASS (Replay detected)' if is_replay_flag is True else 'FAIL'}")
    print("=" * 76 + "\n")

if __name__ == "__main__":
    asyncio.run(run_live_test())
