from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.negotiation import Negotiation
from app.models.customer import Customer
from app.schemas.negotiation_schema import (
    NegotiationCreate, NegotiationResponse, NegotiateMessageRequest
)
from app.services.negotiation_service import NegotiationService
from app.routes.auth import get_current_user
from app.models.user import User
from typing import List

router = APIRouter(
    prefix="/negotiations",
    tags=["Cart Negotiator"]
)

@router.get("/", response_model=List[NegotiationResponse])
def get_negotiations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Order negotiations by created_at desc so latest appear first
    negotiations = db.query(Negotiation).join(Customer).filter(Customer.user_id == current_user.id).order_by(Negotiation.created_at.desc()).all()
    return negotiations

@router.get("/{id}", response_model=NegotiationResponse)
def get_negotiation(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    negotiation = db.query(Negotiation).join(Customer).filter(Negotiation.id == id, Customer.user_id == current_user.id).first()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation session not found")
    return negotiation

@router.post("/start", response_model=NegotiationResponse, status_code=status.HTTP_201_CREATED)
def start_negotiation(
    payload: NegotiationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify customer belongs to the user
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.user_id == current_user.id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    service = NegotiationService()
    negotiation = service.start_negotiation(
        db,
        customer_id=payload.customer_id,
        product_name=payload.product_name,
        original_price=payload.original_price,
        margin_floor=payload.margin_floor,
        max_discount=payload.max_discount,
        strategy=payload.strategy
    )
    return negotiation

@router.post("/{id}/message")
def send_negotiation_message(
    id: int,
    payload: NegotiateMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify negotiation belongs to user
    negotiation = db.query(Negotiation).join(Customer).filter(Negotiation.id == id, Customer.user_id == current_user.id).first()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")

    service = NegotiationService()
    negotiation, reply = service.process_message(
        db,
        negotiation_id=id,
        user_message=payload.message,
        user_offer=payload.offer,
        strategy=payload.strategy
    )
    if not negotiation:
        raise HTTPException(status_code=404, detail=reply)
        
    return {
        "reply": reply,
        "current_offer": int(negotiation.current_offer) if negotiation.current_offer is not None else (int(negotiation.negotiated_price) if negotiation.negotiated_price is not None else None),
        "status": negotiation.status,
        "negotiation": NegotiationResponse.model_validate(negotiation)
    }

@router.post("/{id}/stop")
def stop_negotiation(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify negotiation belongs to user
    negotiation = db.query(Negotiation).join(Customer).filter(Negotiation.id == id, Customer.user_id == current_user.id).first()
    if not negotiation:
        raise HTTPException(status_code=404, detail="Negotiation not found")
        
    negotiation.status = "lost"
    db.commit()
    db.refresh(negotiation)
    return {
        "status": negotiation.status,
        "negotiation": NegotiationResponse.model_validate(negotiation)
    }