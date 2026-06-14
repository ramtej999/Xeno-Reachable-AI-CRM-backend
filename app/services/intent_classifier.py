import re

def is_explicit_acceptance(message: str) -> bool:
    """
    Determines if the shopper explicitly accepted the deal.
    Only returns True for predefined accepted phrases.
    """
    normalized = message.lower().strip()
    
    # Question safeguard: If a message contains '?' or question/conditional indicators, ACCEPT is impossible
    if "?" in normalized:
        return False
        
    if "but" in normalized or "if" in normalized:
        return False
        
    question_words = ["what", "how", "why", "when", "who", "where", "whether"]
    if any(qw in normalized for qw in question_words):
        return False
        
    question_topics = ["warranty", "shipping", "delivery", "cashback", "installation", "return", "refund", "other offer", "any other", "additional"]
    if any(qt in normalized for qt in question_topics):
        return False

    accepted_phrases = [
        "yes",
        "ok",
        "okay",
        "accept",
        "accepted",
        "deal",
        "sounds good",
        "i'll take it",
        "i will take it",
        "ill take it",
        "go ahead",
        "send checkout link",
        "send me checkout link",
        "send the checkout link",
        "send me the checkout link",
        "send me the link",
        "purchase now",
        "buy now",
        "done",
        "confirmed",
        "proceed",
        "checkout",
        "send me payment link",
        "let's do it",
        "okay i will take it",
        "link",
        "send link",
        "send me link",
        "send the link",
        "where is the link",
        "give me the link",
        "give me link",
        "checkout link"
    ]
    normalized = message.lower().strip()
    
    for phrase in accepted_phrases:
        # Clean standard punctuation except apostrophes and spaces to handle punctuation boundary
        cleaned_msg = re.sub(r"[^\w\s']", " ", normalized)
        cleaned_msg = " ".join(cleaned_msg.split())
        
        # Match phrase with boundary checks
        pattern = r"(?:^|\s)" + re.escape(phrase) + r"(?:\s|$)"
        if re.search(pattern, cleaned_msg):
            return True
            
    return False

def is_off_topic_or_abuse(message: str) -> bool:
    """
    Detects if the user is asking off-topic, programming, code, bug-fixing, 
    or jailbreak queries to ensure the AI negotiation agent is not misused.
    """
    msg_lower = message.lower().strip()
    
    # Triple backticks indicates code block formatting attempt
    if "```" in msg_lower:
        return True
        
    abuse_keywords = [
        "python", "javascript", "typescript", "rust", "c++", "csharp", "database", "sql", 
        "system prompt", "ignore instructions", "ignore previous instructions", "prompt injection", 
        "ignore the above", "write a script", "write a function", "programming", "coding", 
        "bug fix", "fix this bug", "fix the bug", "software developer", "web developer", "jailbreak",
        "bug", "html", "css", "hack", "exploit", "developer", "system instructions", "system configuration",
        "instruction limit", "instruction manual", "model instructions", "underlying instructions"
    ]
    if any(kw in msg_lower for kw in abuse_keywords):
        return True
        
    # Check for "code" word in a programming context rather than coupon/promo/zip code
    if "code" in msg_lower:
        shopping_code_patterns = ["promo", "discount", "coupon", "checkout", "order", "postal", "zip", "area", "pin"]
        if not any(pat in msg_lower for pat in shopping_code_patterns):
            dev_context = ["write", "get", "fix", "source", "program", "run", "execute", "give me", "show me", "explain", "code to"]
            if any(dc in msg_lower for dc in dev_context):
                return True
                
    return False

def classify_intent(message: str) -> str:
    """
    Classifies the latest customer message intent.
    Possible intents:
    - OFF_TOPIC
    - ACCEPT
    - PRICE_NEGOTIATION
    - PRICE_COMPARISON
    - DELIVERY
    - REJECT
    - PRODUCT_QUESTION
    """
    msg_lower = message.lower().strip()
    
    if is_off_topic_or_abuse(message):
        return "OFF_TOPIC"
        
    if is_explicit_acceptance(message):
        return "ACCEPT"
    
    # PRICE_COMPARISON
    competitor_words = ["amazon", "flipkart", "ebay", "walmart", "cheaper", "elsewhere", "competitor", "other store", "site", "online", "price match", "retailer"]
    if any(word in msg_lower for word in competitor_words):
        return "PRICE_COMPARISON"
        
    # DELIVERY
    shipping_words = ["shipping", "delivery", "courier", "postage", "ship"]
    if any(word in msg_lower for word in shipping_words):
        return "DELIVERY"

    # PRICE_NEGOTIATION (includes discount requests)
    discount_words = ["discount", "reduce more", "lower price", "bigger discount", "can you reduce", "do better", "better deal", "less", "more discount", "reduce", "negotiate"]
    if any(word in msg_lower for word in discount_words):
        return "PRICE_NEGOTIATION"

    # REJECT
    rejection_words = ["no thanks", "no way", "not interested", "forget it", "nevermind", "reject", "cancel", "don't want", "dont want", "don't need", "dont need", "stop"]
    if any(word in msg_lower for word in rejection_words) or msg_lower == "no":
        return "REJECT"

    # If it contains digits (like matching a price counter offer), it's a price negotiation
    if re.search(r'\d+', msg_lower):
        return "PRICE_NEGOTIATION"

    # PRODUCT_QUESTION
    question_words = ["what", "how", "why", "when", "who", "where", "info", "details", "product", "material", "size", "color", "quality", "warranty", "guarantee"]
    if any(word in msg_lower for word in question_words) or "?" in msg_lower:
        return "PRODUCT_QUESTION"
        
    # default fallback
    return "PRICE_NEGOTIATION"
