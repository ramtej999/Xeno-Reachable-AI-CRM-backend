import re
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from app.config import settings
from app.models.security import AiUsageLog, SecurityEvent
from typing import Tuple

class SecurityService:
    def __init__(self):
        # We need a valid 32 url-safe base64-encoded bytes string for Fernet.
        # If not provided or invalid, we generate a random one for dev, but in prod it should be set.
        key = settings.ENCRYPTION_KEY
        if not key or len(key) < 32:
            self.fernet = None
        else:
            try:
                self.fernet = Fernet(key.encode())
            except Exception:
                self.fernet = None

    def encrypt_key(self, api_key: str) -> str:
        if not self.fernet:
            return api_key # Fallback if no valid key is configured
        return self.fernet.encrypt(api_key.encode()).decode()

    def decrypt_key(self, encrypted_key: str) -> str:
        if not self.fernet:
            return encrypted_key
        try:
            return self.fernet.decrypt(encrypted_key.encode()).decode()
        except Exception:
            return ""

    def log_security_event(self, db: Session, user_id: int, event_type: str, prompt: str, module: str):
        event = SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            prompt=prompt[:2000] if prompt else None,
            module=module
        )
        db.add(event)
        db.commit()

    def check_rate_limit_and_quota(self, db: Session, user_id: int, module: str, endpoint: str):
        from datetime import timezone
        now = datetime.now(timezone.utc)

        # 1. Rate Limiting: 5 seconds cooldown
        last_request = db.query(AiUsageLog).filter(
            AiUsageLog.user_id == user_id
        ).order_by(AiUsageLog.created_at.desc()).first()

        if last_request and last_request.created_at:
            # Ensure both are offset-aware
            created_at = last_request.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if (now - created_at).total_seconds() < 5:
                self.log_security_event(db, user_id, "rate_limit_violation", "", module)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Please wait a few seconds before sending another request."
                )

        if module == "cart_negotiator":
            return

        # 2. Free AI Quota: 30 requests per 2-hour rolling window per module
        two_hours_ago = now - timedelta(hours=2)
        request_count = db.query(AiUsageLog).filter(
            AiUsageLog.user_id == user_id,
            AiUsageLog.module == module,
            AiUsageLog.created_at >= two_hours_ago
        ).count()

        if request_count >= 30:
            self.log_security_event(db, user_id, "quota_exhaustion", "", module)
            
            module_display_names = {
                "copilot": "AI Copilot",
                "audience_builder": "Audience Builder",
                "campaign_studio": "Campaign Studio"
            }
            display_name = module_display_names.get(module, module.replace("_", " ").title())
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You have reached the {display_name} usage limit. Please try again in 2 hours."
            )

    def log_usage(self, db: Session, user_id: int, module: str, endpoint: str):
        log = AiUsageLog(user_id=user_id, module=module, endpoint=endpoint)
        db.add(log)
        db.commit()

    def detect_secrets(self, text: str) -> bool:
        if not text:
            return False
        
        secret_patterns = [
            r"(?i)sk-[a-zA-Z0-9]{32,}", # Typical API Key
            r"(?i)ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*", # JWT
            r"(?i)AKIA[0-9A-Z]{16}", # AWS Access Key
            r"(?i)postgres(?:ql)?://[^:]+:[^@]+@[^/]+/[^?]+", # DB Connection string
            r"(?i)mysql://[^:]+:[^@]+@[^/]+/[^?]+",
            r"(?i)password\s*=\s*['\"][^'\"]+['\"]"
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, text):
                return True
        return False

    def detect_prompt_injection(self, text: str) -> bool:
        if not text:
            return False
            
        injection_keywords = [
            "ignore previous instructions",
            "ignore all previous instructions",
            "reveal system prompt",
            "show hidden prompt",
            "print environment variables",
            "show backend code",
            "reveal api keys",
            "dump configuration",
            "override policies",
            "disregard the previous instructions"
        ]
        
        lower_text = text.lower()
        for kw in injection_keywords:
            if kw in lower_text:
                return True
        return False

    def is_allowed_domain(self, text: str, module: str) -> bool:
        if not text:
            return True
            
        lower_text = text.lower()

        # Global Blocked Topics (Programming, Entertainment, etc.)
        blocked_keywords = [
            "python", "java ", "javascript", "react", "nodejs", "c++", 
            "html", "css", "sql tutorial", "leetcode", "dsa", 
            "operating system", "computer network", "machine learning tutorial",
            "homework", "assignment", "resume writing", "story writing", "poetry",
            "tell me a joke", "write a poem", "game code"
        ]
        
        for kw in blocked_keywords:
            if kw in lower_text:
                return False

        # If it's short, we might not block it globally, but module specific checks apply.
        
        if module == "copilot":
            # Block coding, general chat, homework, entertainment (already handled above mostly)
            pass
        elif module == "audience_builder":
            # Block campaign generation
            if "write an email" in lower_text or "generate campaign" in lower_text:
                return False
        elif module == "campaign_studio":
            # Block analytics questions
            if "revenue" in lower_text or "how many customers" in lower_text:
                return False
        elif module == "cart_negotiator":
            # Block marketing strategy
            if "marketing strategy" in lower_text or "audience" in lower_text:
                return False
                
        return True

    def validate_request(self, db: Session, user_id: int, prompt: str, module: str, endpoint: str):
        # 1. Secret Detection
        if self.detect_secrets(prompt):
            self.log_security_event(db, user_id, "secret_detection", prompt, module)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sensitive credentials detected. Remove secrets before continuing."
            )

        # 2. Prompt Injection Defense
        if self.detect_prompt_injection(prompt):
            self.log_security_event(db, user_id, "prompt_injection", prompt, module)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request blocked by security policy."
            )

        # 3. Domain Enforcement
        if module == "cart_negotiator":
            lower_prompt = prompt.lower() if prompt else ""
            blocked_keywords = [
                "python", "java", "javascript", "react", "nodejs", "html", "css", "sql",
                "prompt engineering", "system prompt", "api key", "password", "hacking",
                "joke", "story", "homework", "assignment", "entertainment", "print backend code", "override policies"
            ]
            
            negotiation_intents = [
                "price", "discount", "offer", "coupon", "shipping", "delivery", 
                "checkout", "purchase", "order", "product", "competitor", 
                "amazon", "flipkart", "buy", "deal", "cart", "expensive", 
                "costly", "reduce", "cheaper", "better", "match"
            ]
            
            is_blocked = any(kw in lower_prompt for kw in blocked_keywords)
            has_intent = any(intent in lower_prompt for intent in negotiation_intents)
            has_number = any(char.isdigit() for char in lower_prompt)
            
            if is_blocked or (not has_intent and not has_number):
                self.log_security_event(db, user_id, "domain_violation", prompt, module)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="I can only assist with product pricing, discounts, offers, delivery, checkout, and purchase-related questions."
                )
        else:
            if not self.is_allowed_domain(prompt, module):
                self.log_security_event(db, user_id, "domain_violation", prompt, module)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This AI assistant only supports CRM, sales, marketing, customer analytics, campaign management, audience building, and business performance analysis."
                )

        # 4. Rate Limits & Quotas
        self.check_rate_limit_and_quota(db, user_id, module, endpoint)
