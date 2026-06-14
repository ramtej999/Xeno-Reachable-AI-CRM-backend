from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.negotiation import Negotiation
from app.models.message import Message
from app.services.groq_service import GroqService
from decimal import Decimal

class NegotiationService:
    def __init__(self):
        self.groq_service = GroqService()

    def start_negotiation(self, db: Session, customer_id: int, product_name: str, original_price: float, margin_floor: float, max_discount: float = 30.0, strategy: str = "Balanced"):
        """
        Starts a new price negotiation session for a product.
        """
        # Calculate initial current_offer
        allowed_minimum = max(original_price - (original_price * max_discount / 100.0), margin_floor)
        initial_offer = max(original_price * 0.95, allowed_minimum)
        initial_offer = round(initial_offer / 10.0) * 10.0
        initial_offer = max(initial_offer, allowed_minimum)

        negotiation = Negotiation(
            customer_id=customer_id,
            product_name=product_name,
            original_price=Decimal(str(original_price)),
            margin_floor=Decimal(str(margin_floor)),
            max_discount=Decimal(str(max_discount)),
            strategy=strategy,
            current_offer=Decimal(str(initial_offer)),
            status="active"
        )
        db.add(negotiation)
        db.commit()
        db.refresh(negotiation)
        return negotiation

    def process_message(self, db: Session, negotiation_id: int, user_message: str, user_offer: float, strategy: str = "Balanced"):
        """
        Saves the shopper's offer, runs negotiation calculations (via backend rules),
        saves the response, and updates session status using the Hidden Backend Tag system.
        """
        negotiation = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
        if not negotiation:
            return None, "Negotiation session not found."

        # Safeguard #1 - Lock Accepted/Lost Deals
        if negotiation.status == "accepted":
            return negotiation, f"This negotiation has already been completed at ₹{negotiation.negotiated_price}."
        if negotiation.status == "lost":
            return negotiation, "This negotiation has ended."

        # Safeguard #2 - 50 message session limit
        message_count = db.query(Message).filter(Message.negotiation_id == negotiation.id).count()
        if message_count >= 50:
            return negotiation, "This negotiation session has reached its maximum message limit. Please start a new negotiation."

        # Save customer offer message
        db_user_msg = Message(
            negotiation_id=negotiation.id,
            sender="customer",
            message=user_message
        )
        db.add(db_user_msg)
        db.commit()

        # Update strategy if user passed it, otherwise use stored strategy
        if strategy and strategy != negotiation.strategy:
            negotiation.strategy = strategy
            db.commit()

        original_price = float(negotiation.original_price)
        margin_floor = float(negotiation.margin_floor)
        max_discount = float(negotiation.max_discount) if negotiation.max_discount is not None else 30.0
        current_strategy = negotiation.strategy or "Balanced"

        # Calculate allowed minimum price
        allowed_minimum = max(original_price - (original_price * max_discount / 100.0), margin_floor)

        # Initialize current_offer if it's None
        if negotiation.current_offer is None:
            initial_offer = max(original_price * 0.95, allowed_minimum)
            initial_offer = round(initial_offer / 10.0) * 10.0
            initial_offer = max(initial_offer, allowed_minimum)
            negotiation.current_offer = Decimal(str(initial_offer))
            db.commit()

        current_offer = float(negotiation.current_offer)

        # Retrieve chat history
        db_messages = db.query(Message).filter(Message.negotiation_id == negotiation.id).order_by(Message.created_at.asc()).all()
        chat_history = []
        for m in db_messages:
            chat_history.append({
                "sender": m.sender,
                "message": m.message
            })

        # Parse message numbers to determine customer explicit offers
        import re
        clean_msg = user_message.replace(',', '')
        message_numbers = []
        for s in re.findall(r'\d+(?:\.\d+)?', clean_msg):
            try:
                message_numbers.append(float(s))
            except ValueError:
                pass

        has_explicit_offer = any(100 < num <= original_price for num in message_numbers) or (user_offer != current_offer)
        message_offer = max([num for num in message_numbers if 100 < num <= original_price], default=user_offer)

        # Calculate negotiable margin and step reduction (potential counter offer)
        if has_explicit_offer and message_offer >= allowed_minimum:
            next_offer_clamped = message_offer
        else:
            negotiable_margin = original_price - allowed_minimum
            if current_strategy.lower() == "conservative":
                step_pct = 0.10
            elif current_strategy.lower() == "aggressive":
                step_pct = 0.30
            else:
                step_pct = 0.18

            step = negotiable_margin * step_pct
            next_offer = current_offer - step
            next_offer_rounded = round(next_offer / 10.0) * 10.0
            next_offer_clamped = max(next_offer_rounded, allowed_minimum)

        # Call Groq Service to get the reply with hidden backend tags
        user_id = negotiation.customer.user_id if negotiation.customer else None
        negotiation_result = self.groq_service.negotiate_price(
            db=db,
            user_id=user_id,
            chat_history=chat_history,
            original_price=original_price,
            margin_floor=margin_floor,
            user_offer=user_offer,
            current_offer=current_offer,
            potential_counter_offer=next_offer_clamped,
            user_message=user_message,
            strategy=current_strategy,
            negotiation_id=negotiation.id
        )
        response_msg = negotiation_result.get("message", "")
        print("GROQ RESPONSE MSG:", repr(response_msg.replace('\u20b9', 'Rs.')))

        # Parse hidden backend tags from LLM response (robust case-insensitive parsing supporting both single and double curly braces, and decimal values)
        tags = {}
        tag_pattern = r"\{{1,2}\s*([A-Za-z0-9_]+)\s*(?:=\s*([A-Za-z0-9_\.\-]+)\s*)?\}{1,2}"
        matches = re.findall(tag_pattern, response_msg)
        for tag_name, val in matches:
            key = tag_name.upper().strip()
            if val:
                tags[key] = val.upper().strip()
            else:
                tags[key] = True
        print("PARSED TAGS:", tags)

        # DEFENSE IN DEPTH: Override or inject tags based on local high-confidence classifiers
        from app.services.intent_classifier import is_explicit_acceptance, classify_intent
        local_intent = classify_intent(user_message)
        local_is_accepted = is_explicit_acceptance(user_message)

        if local_is_accepted or local_intent == "ACCEPT":
            tags["OFFER_ACCEPTED"] = True
        elif local_intent == "PRICE_COMPARISON":
            tags["ASK_COMPETITOR_PRICE"] = True
            tags["NO_PRICE_CHANGE"] = True
        elif local_intent == "DELIVERY":
            if "FREE_DELIVERY" not in tags:
                tags["FREE_DELIVERY"] = "YES"
            tags["NO_PRICE_CHANGE"] = True
        elif local_intent == "REJECT":
            tags["DEAL_REJECTED"] = True
        elif local_intent == "OFF_TOPIC":
            tags["NO_PRICE_CHANGE"] = True
            response_msg = "I'd be happy to help with your purchase decision. Let's continue discussing the product and find the best option for you.\n{NO_PRICE_CHANGE}"

        # Link placeholder safeguard: if message contains a link placeholder, force acceptance
        placeholder_pattern = r"\[[^\]]*link[^\]]*\]"
        if re.search(placeholder_pattern, response_msg, re.IGNORECASE):
            tags["OFFER_ACCEPTED"] = True

        # Question Safeguard: If the message contains a question mark or question intent, ACCEPT is impossible
        # EXCEPT when the LLM has explicitly outputted a link placeholder [link]!
        normalized_msg = user_message.lower().strip()
        has_question_indicator = (
            "?" in normalized_msg or
            any(qw in normalized_msg for qw in ["but", "what", "how", "why", "when", "who", "where", "whether"]) or
            any(qt in normalized_msg for qt in ["warranty", "shipping", "delivery", "cashback", "installation", "return", "refund", "other offer", "any other", "additional"])
        )
        if has_question_indicator and not re.search(placeholder_pattern, response_msg, re.IGNORECASE):
            if "OFFER_ACCEPTED" in tags:
                del tags["OFFER_ACCEPTED"]

        # Check if the returned negotiation_result dictionary has counter_offer key (for old test mocks compatibility)
        if "PRICE" not in tags and "counter_offer" in negotiation_result:
            tags["PRICE"] = str(negotiation_result["counter_offer"])

        # Ensure locally forced/injected tags are kept in `tags` dict.
        # We do not append them to `response_msg` because we want to hide them from the frontend.
        # Instead, we strip any existing tags from the LLM response.
        response_msg = re.sub(r"\{{1,2}\s*[A-Za-z0-9_]+(?:\s*=\s*[A-Za-z0-9_\.\-]+)?\s*\}{1,2}", "", response_msg).strip()


        # Database update rules
        intent = "PRICE_NEGOTIATION"
        accepted = False
        reason = ""

        # OFFER ACCEPTED
        if "OFFER_ACCEPTED" in tags:
            negotiation.status = "accepted"
            # Final price is either the newly parsed PRICE tag, the current offer, or explicit valid user offer
            accepted_price = current_offer
            if "PRICE" in tags:
                accepted_price = float(tags["PRICE"])
            elif has_explicit_offer and message_offer >= allowed_minimum:
                accepted_price = message_offer
            
            negotiation.negotiated_price = Decimal(str(accepted_price))
            negotiation.current_offer = Decimal(str(accepted_price))
            db.commit()

            # Ensure the reply has the checkout URL
            checkout_url = f"https://checkout.reachableai.demo/order/{negotiation.id}"
            if re.search(placeholder_pattern, response_msg, re.IGNORECASE):
                response_msg = re.sub(
                    placeholder_pattern,
                    checkout_url,
                    response_msg,
                    flags=re.IGNORECASE
                )
            elif checkout_url not in response_msg:
                # Append link to the cleaned message
                response_msg = response_msg + f"\n\nCheckout Link:\n{checkout_url}\n\n# This is only for demo purposes."

            
            accepted = True
            intent = "ACCEPT"
            reason = f"Offer Accepted: status set to accepted at Rs.{accepted_price:.2f}."

        # DEAL REJECTED
        elif "DEAL_REJECTED" in tags:
            negotiation.status = "lost"
            db.commit()
            intent = "REJECT"
            reason = "Deal Rejected: status set to lost."

        # END_NEGOTIATION
        elif "END_NEGOTIATION" in tags:
            negotiation.status = "lost"
            db.commit()
            intent = "REJECT"
            reason = "End Negotiation: status set to lost/locked."

        # PRICE (only reduce price when PRICE tag is present)
        elif "PRICE" in tags:
            try:
                new_price = float(tags["PRICE"])
                # Clamp for safety
                new_price_clamped = max(new_price, allowed_minimum)
                negotiation.current_offer = Decimal(str(new_price_clamped))
                db.commit()
                intent = "PRICE_NEGOTIATION"
                reason = f"Price updated to Rs.{new_price_clamped:.2f}."
            except Exception:
                # Fallback to backend calculation if parsing failed
                negotiation.current_offer = Decimal(str(next_offer_clamped))
                db.commit()
                intent = "PRICE_NEGOTIATION"
                reason = "Price tag parse failed. Used next calculated counter offer."

        # NO PRICE CHANGE / DELIVERY / COMPETITOR / OTHER
        else:
            # Keep current_offer unchanged (NO PRICE CHANGE)
            intent = "NO_ACTION"
            if "ASK_COMPETITOR_PRICE" in tags:
                intent = "PRICE_COMPARISON"
                reason = "Competitor query: price remains unchanged."
            elif "FREE_DELIVERY" in tags:
                intent = "DELIVERY"
                reason = f"Free Delivery query (Value: {tags['FREE_DELIVERY']}): price remains unchanged."
            else:
                intent = "PRODUCT_QUESTION"
                reason = "General query or product question: price remains unchanged."

        # Save merchant message (cleaned of hidden tags)
        db_merchant_msg = Message(
            negotiation_id=negotiation.id,
            sender="merchant",
            message=response_msg
        )
        db.add(db_merchant_msg)
        db.commit()
        db.refresh(negotiation)

        # Log debugging information in the requested format
        print(f"Customer Message: {user_message.replace('₹', 'Rs.') if user_message else ''}\n")
        print(f"Detected Intent: {intent}\n")
        print(f"Offer: {user_offer}\n")
        print(f"Accepted:\n{'true' if accepted else 'false'}\n")
        print(f"Reason: {reason.replace('₹', 'Rs.') if reason else ''}\n")

        return negotiation, response_msg
