import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.ticket import Ticket
from app.models.note import TicketNote
from app.models.tool import ToolAction
from app.models.approval import Approval
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.kb import KBDocument, KBChunk
from app.schemas.auth import UserCreate, UserUpdate, UserResponse
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.schemas.order import OrderCreate, OrderResponse
from app.schemas.kb import KBDocumentCreate, KBDocumentResponse
from app.services.auth_service import hash_password

router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    clean_username = user_in.username.strip().lower()
    existing = await db.execute(
        select(User).where(User.username == clean_username)
    )
    user = existing.scalar_one_or_none()
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{clean_username}' is already registered.",
        )

    new_user = User(
        id=str(uuid.uuid4()),
        name=user_in.name.strip(),
        username=clean_username,
        email=user_in.email.strip().lower(),
        phone=user_in.phone.strip() if user_in.phone else None,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        mfa_setup_completed=False,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_in.role is not None:
        valid_roles = ["agent", "senior_agent", "admin"]
        if user_in.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
        if getattr(user, "is_primary_admin", False) and user_in.role != "admin":
            raise HTTPException(status_code=400, detail="The primary administrator account role cannot be demoted.")
        if user.id == current_user.id and user_in.role != "admin":
            raise HTTPException(status_code=400, detail="Administrators cannot demote their own account role.")
        if user.role == "admin" and user_in.role != "admin":
            admin_count_res = await db.execute(
                select(func.count(User.id)).where(User.role == "admin", User.id != user.id)
            )
            remaining_admins = admin_count_res.scalar() or 0
            if remaining_admins < 1:
                raise HTTPException(status_code=400, detail="Cannot demote the last remaining administrator account.")
        user.role = user_in.role

    if user_in.name is not None and user_in.name.strip():
        user.name = user_in.name.strip()

    if user_in.email is not None and user_in.email.strip():
        user.email = user_in.email.strip().lower()

    if user_in.phone is not None:
        user.phone = user_in.phone.strip() if user_in.phone.strip() else None

    if user_in.password is not None and user_in.password.strip():
        user.password_hash = hash_password(user_in.password.strip())

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Administrators cannot delete their own active account.")

    if getattr(user, "is_primary_admin", False):
        raise HTTPException(status_code=400, detail="The primary administrator account cannot be deleted.")

    if user.username == "ai_agent":
        raise HTTPException(status_code=400, detail="The autonomous AI Agent account is required by the system and cannot be deleted.")

    if user.role == "admin":
        admin_count_res = await db.execute(
            select(func.count(User.id)).where(User.role == "admin", User.id != user.id)
        )
        remaining_admins = admin_count_res.scalar() or 0
        if remaining_admins < 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last remaining administrator account.")

    await db.execute(update(Ticket).where(Ticket.assigned_to == user.id).values(assigned_to=None))
    await db.execute(update(TicketNote).where(TicketNote.author_id == user.id).values(author_id=None))
    await db.execute(update(ToolAction).where(ToolAction.proposed_by_id == user.id).values(proposed_by_id=None))
    await db.execute(update(Approval).where(Approval.approver_id == user.id).values(approver_id=current_user.id))
    await db.delete(user)
    await db.commit()
    return {"message": f"Operative account '{user.username}' successfully removed."}


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    cust_in: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "agent"])),
):
    new_cust = Customer(
        id=str(uuid.uuid4()),
        name=cust_in.name,
        email=cust_in.email,
        phone=cust_in.phone,
    )
    db.add(new_cust)
    await db.commit()
    await db.refresh(new_cust)
    return new_cust


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "senior_agent", "agent"])),
):
    result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
    return result.scalars().all()


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "agent"])),
):
    cust_check = await db.execute(select(Customer).where(Customer.id == order_in.customer_id))
    if not cust_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")

    new_order = Order(
        id=str(uuid.uuid4()),
        customer_id=order_in.customer_id,
        restaurant=order_in.restaurant,
        status=order_in.status,
        total=order_in.total,
        currency=order_in.currency,
        placed_at=order_in.placed_at,
        delivered_at=order_in.delivered_at,
    )
    db.add(new_order)

    for item in order_in.items:
        new_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=new_order.id,
            item_name=item.item_name,
            quantity=item.quantity,
            unit_price=item.unit_price,
        )
        db.add(new_item)

    await db.commit()

    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == new_order.id)
    )
    return result.scalar_one()


@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "senior_agent", "agent"])),
):
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).order_by(Order.placed_at.desc())
    )
    return result.scalars().all()


@router.post("/kb/documents", response_model=KBDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_kb_document(
    doc_in: KBDocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "senior_agent"])),
):
    existing = await db.execute(select(KBDocument).where(KBDocument.doc_id == doc_in.doc_id))
    doc = existing.scalar_one_or_none()
    if doc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document with ID {doc_in.doc_id} already exists",
        )

    new_doc = KBDocument(
        doc_id=doc_in.doc_id,
        title=doc_in.title,
        body=doc_in.body,
        category=doc_in.category or "general",
        version=1,
        is_adversarial=doc_in.is_adversarial,
    )
    db.add(new_doc)

    words = doc_in.body.split()
    chunk_size = 300
    overlap = 50
    start = 0
    seq = 0

    while start < len(words) or (start == 0 and len(words) == 0):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words) if chunk_words else doc_in.body

        chunk = KBChunk(
            id=str(uuid.uuid4()),
            doc_id=new_doc.doc_id,
            chunk_seq=seq,
            content=chunk_text,
            metadata_json={
                "title": new_doc.title,
                "category": new_doc.category,
                "is_adversarial": new_doc.is_adversarial,
            },
            version=1,
        )
        db.add(chunk)
        seq += 1

        if end >= len(words):
            break
        start += chunk_size - overlap

    await db.commit()
    await db.refresh(new_doc)
    return new_doc


@router.get("/kb/documents", response_model=List[KBDocumentResponse])
async def list_kb_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "senior_agent", "agent"])),
):
    result = await db.execute(select(KBDocument).order_by(KBDocument.doc_id))
    return result.scalars().all()

