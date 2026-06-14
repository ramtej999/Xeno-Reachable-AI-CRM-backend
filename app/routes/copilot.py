from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.copilot_schema import (
    CopilotRequest, CopilotResponse, CopilotConversationCreate,
    CopilotConversationResponse, CopilotMessageResponse, CopilotCancelRequest
)
from app.services.copilot_service import CopilotService
from app.routes.auth import get_current_user
from app.models.user import User
from app.models.copilot_conversation import CopilotConversation
from app.models.copilot_message import CopilotMessage
from typing import List

router = APIRouter(
    prefix="/copilot",
    tags=["AI Copilot"]
)

# Global thread-safe set to track cancelled conversation queries
cancelled_conversations = set()

def generate_title_from_message(message: str) -> str:
    msg_lower = message.lower().strip()
    if "open rate" in msg_lower:
        return "Improve Open Rates"
    elif "revenue" in msg_lower:
        return "Revenue Growth Analysis"
    elif "dormant" in msg_lower:
        return "Dormant Customer Strategy"
    elif "target" in msg_lower or "who should i" in msg_lower:
        return "Targeting Cohorts"
    
    clean = message.replace('?', '').strip()
    words = clean.split()
    if len(words) > 0:
        stopwords = {"what", "how", "why", "when", "who", "where", "is", "are", "can", "i", "do", "my", "our", "the", "a", "an", "you", "please", "we"}
        filtered_words = [w for w in words if w.lower() not in stopwords]
        if not filtered_words:
            filtered_words = words
        title = " ".join(filtered_words[:4]).title()
        return title
    return "New Chat"

@router.get("/conversations", response_model=List[CopilotConversationResponse])
def get_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conversations = db.query(CopilotConversation).filter(
        CopilotConversation.user_id == current_user.id
    ).order_by(CopilotConversation.updated_at.desc()).all()
    return conversations

@router.get("/conversations/{conversation_id}/messages", response_model=List[CopilotMessageResponse])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership
    conv = db.query(CopilotConversation).filter(
        CopilotConversation.id == conversation_id,
        CopilotConversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(CopilotMessage).filter(
        CopilotMessage.conversation_id == conversation_id
    ).order_by(CopilotMessage.created_at.asc()).all()
    return messages

@router.post("/conversations", response_model=CopilotConversationResponse)
def create_conversation(
    payload: CopilotConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = CopilotConversation(
        user_id=current_user.id,
        title=payload.title or "New Chat"
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = db.query(CopilotConversation).filter(
        CopilotConversation.id == conversation_id,
        CopilotConversation.user_id == current_user.id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation deleted"}

@router.post("/query/cancel")
def cancel_copilot_query(
    payload: CopilotCancelRequest,
    current_user: User = Depends(get_current_user)
):
    conv_id = payload.conversation_id
    if conv_id:
        cancelled_conversations.add(conv_id)
    return {"status": "success", "message": "Query cancellation flagged"}

@router.post("/query", response_model=CopilotResponse)
def query_copilot(
    payload: CopilotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv_id = payload.conversation_id
    conv = None
    
    if conv_id:
        conv = db.query(CopilotConversation).filter(
            CopilotConversation.id == conv_id,
            CopilotConversation.user_id == current_user.id
        ).first()
        
    if not conv:
        # Create a new conversation if missing
        conv = CopilotConversation(
            user_id=current_user.id,
            title="New Chat"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        conv_id = conv.id

    # AUTO-SAVE REQUIREMENT: Save user message first!
    user_msg = CopilotMessage(
        conversation_id=conv_id,
        sender="user",
        message=payload.message
    )
    db.add(user_msg)
    db.commit()

    # Generate response
    service = CopilotService()
    
    # Check cancellation before query
    if conv_id in cancelled_conversations:
        cancelled_conversations.remove(conv_id)
        reply = "Generation stopped by user."
    else:
        reply = service.query_copilot(db, payload.message, current_user.id)
        # Check cancellation after query
        if conv_id in cancelled_conversations:
            cancelled_conversations.remove(conv_id)
            reply = "Generation stopped by user."

    # AUTO-SAVE REQUIREMENT: Save assistant response!
    assistant_msg = CopilotMessage(
        conversation_id=conv_id,
        sender="assistant",
        message=reply
    )
    db.add(assistant_msg)
    db.commit()

    # Auto title check: if this was the first user message (i.e. only 1 user message in this conversation)
    msg_count = db.query(CopilotMessage).filter(
        CopilotMessage.conversation_id == conv_id,
        CopilotMessage.sender == "user"
    ).count()
    
    if msg_count == 1:
        new_title = generate_title_from_message(payload.message)
        conv.title = new_title
        db.commit()
        db.refresh(conv)

    # Touch conversation update time
    from sqlalchemy.sql import func
    conv.updated_at = func.now()
    db.commit()

    return CopilotResponse(
        response=reply,
        conversation_id=conv_id,
        title=conv.title
    )