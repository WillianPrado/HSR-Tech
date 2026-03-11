from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from services.db_handler import get_db
from services.stripe.payment_use_cases import PaymentUseCases

router = APIRouter(tags=["Payment"])


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    payload = await request.body()
    return PaymentUseCases(db).process_webhook(payload=payload, sig_header=sig_header)
