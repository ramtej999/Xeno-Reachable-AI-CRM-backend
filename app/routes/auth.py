from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth_schema import UserCreate, UserLogin, UserResponse, UserUpdate
from app.utils.auth_utils import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Reads the authorization header automatically
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency injection helper to validate the JWT token and return the logged-in User model.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = decode_access_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User session not found")
    return user

@router.post("/signup", response_model=dict)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Creates a new user account if the email is not already registered.
    """
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please sign in instead."
        )

    hashed = hash_password(payload.password)
    db_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hashed,
        org=payload.org
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token(db_user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(db_user)
    }

@router.post("/login", response_model=dict)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Verifies user credentials and returns a valid JWT token.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token(user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user)
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns profile information for the authenticated active user.
    """
    return current_user

@router.put("/update", response_model=UserResponse)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Updates the current user's name and/or org in the database.
    """
    if payload.name is not None:
        current_user.name = payload.name
    if payload.org is not None:
        current_user.org = payload.org
    db.commit()
    db.refresh(current_user)
    return current_user

from pydantic import BaseModel
class ApiKeyPayload(BaseModel):
    api_key: str

@router.get("/api-key", response_model=dict)
def get_api_key_status(current_user: User = Depends(get_current_user)):
    """
    Returns the status of the user's Groq API key (configured or not). Does not return the actual key.
    """
    return {"configured": bool(current_user.groq_api_key_encrypted)}

@router.post("/api-key", response_model=dict)
def update_api_key(payload: ApiKeyPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Encrypts and saves the user's Groq API key.
    """
    from app.services.security_service import SecurityService
    security_service = SecurityService()
    
    if not payload.api_key:
        current_user.groq_api_key_encrypted = None
    else:
        # Validate that it looks like a Groq key (starts with gsk_)
        if not payload.api_key.startswith("gsk_"):
            raise HTTPException(status_code=400, detail="Invalid Groq API Key format. Must start with 'gsk_'")
        current_user.groq_api_key_encrypted = security_service.encrypt_key(payload.api_key)
        
    db.commit()
    return {"status": "success", "message": "API Key updated successfully."}

@router.delete("/api-key", response_model=dict)
def delete_api_key(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Deletes the user's Groq API key.
    """
    current_user.groq_api_key_encrypted = None
    db.commit()
    return {"status": "success", "message": "API Key deleted successfully."}

from datetime import datetime, timedelta
from sqlalchemy import func
from app.models.security import AiUsageLog

@router.get("/ai-usage", response_model=dict)
def get_ai_usage(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns AI token usage counts per module for the last 2 hours.
    """
    from datetime import timezone
    now = datetime.now(timezone.utc)
    two_hours_ago = now - timedelta(hours=2)
    
    logs = db.query(AiUsageLog.module, func.count(AiUsageLog.id)).filter(
        AiUsageLog.user_id == current_user.id,
        AiUsageLog.created_at >= two_hours_ago
    ).group_by(AiUsageLog.module).all()
    
    usage = {
        "copilot": 0,
        "audience_builder": 0,
        "campaign_studio": 0
    }
    
    for module, count in logs:
        if module in usage:
            usage[module] = count
            
    return usage

@router.delete("/delete")
def delete_account(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Permanently deletes the user account and all associated data.
    """
    from app.models.customer import Customer
    from app.models.campaign import Campaign
    from app.models.copilot_conversation import CopilotConversation
    
    # Unlink customers immediately
    db.query(Customer).filter(Customer.user_id == current_user.id).update({"user_id": None}, synchronize_session=False)
        
    # Unlink campaigns immediately
    db.query(Campaign).filter(Campaign.user_id == current_user.id).update({"user_id": None}, synchronize_session=False)
        
    # Cascade delete copilot conversations using ORM to trigger message cascades
    conversations = db.query(CopilotConversation).filter(CopilotConversation.user_id == current_user.id).all()
    for conv in conversations:
        db.delete(conv)
        
    # Flush updates to the database before deleting the user
    db.flush()
    
    db.delete(current_user)
    db.commit()
    return {"status": "success", "message": "Account deleted permanently."}
