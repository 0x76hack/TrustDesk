from fastapi import APIRouter, Depends, HTTPException, status, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.customer import Customer
from app.models.coupon import Coupon
from app.schemas.coupon import CouponResponse, CouponRedeemRequest, CouponRedeemResponse
from app.services import coupon_service
from app.routes.customer_portal import get_current_customer
from sqlalchemy import select

router = APIRouter()


@router.post("/redeem", response_model=CouponRedeemResponse, status_code=status.HTTP_200_OK)
async def redeem_coupon(
    req: CouponRedeemRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_customer: Optional[Customer] = Depends(get_current_customer),
):
    cust_id = current_customer.id if current_customer else "cust-ananya"
    coupon, is_replay = await coupon_service.redeem_coupon(
        coupon_code=req.coupon_code,
        customer_id=cust_id,
        order_id=req.order_id,
        db=db,
        idempotency_key=idempotency_key or req.idempotency_key,
    )
    if is_replay:
        response.headers["Idempotent-Replay"] = "true"

    return CouponRedeemResponse(
        success=True,
        coupon_code=coupon.code,
        order_id=req.order_id,
        discount_amount=coupon.amount,
        message=f"Coupon {coupon.code} successfully applied to Order {req.order_id}.",
        status="redeemed",
        is_replay=is_replay,
    )


@router.get("/my", response_model=List[CouponResponse])
async def list_my_coupons(
    db: AsyncSession = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    coupons = await coupon_service.list_customer_coupons(current_customer.id, db)
    return coupons


@router.get("/{code}", response_model=CouponResponse)
async def get_coupon(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    clean_code = code.strip().upper()
    stmt = select(Coupon).where(Coupon.code == clean_code)
    res = await db.execute(stmt)
    coupon = res.scalar_one_or_none()
    if not coupon:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Coupon '{clean_code}' not found.",
        )
    return coupon
