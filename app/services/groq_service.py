import json
from groq import Groq
from app.config import settings

class GroqService:
    def __init__(self):
        self.model = settings.GROQ_MODEL or "llama-3.3-70b-versatile"
        self.has_api = True

    def _get_client(self, db, user_id, module, prompt, endpoint):
        from app.models.user import User
        from app.services.security_service import SecurityService
        from fastapi import HTTPException
        
        if not db or not user_id:
            raise HTTPException(status_code=400, detail="Database session and user_id are required for AI features.")
            
        security_service = SecurityService()
        
        # 1. Validation
        security_service.validate_request(db, user_id, prompt, module, endpoint)
        
        # 2. Key retrieval
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.ai_enabled:
            raise HTTPException(status_code=400, detail="AI features are disabled for this user.")
            
        if not user.groq_api_key_encrypted:
            raise HTTPException(status_code=400, detail="Please configure your Groq API key in Settings.")
            
        decrypted_key = security_service.decrypt_key(user.groq_api_key_encrypted)
        if not decrypted_key:
            raise HTTPException(status_code=400, detail="Invalid or corrupted API key.")
            
        client = Groq(api_key=decrypted_key)
        security_service.log_usage(db, user_id, module, endpoint)
        return client

    def parse_audience_query(self, prompt: str, db=None, user_id: int=None) -> dict:
        """
        Parses a natural language audience query and returns filter criteria as JSON.
        """

        client = self._get_client(db, user_id, "audience_builder", prompt, "parse_audience_query")

        default_result = {
            "inactive_days": None,
            "min_spend": None,
            "city": None,
            "segment": None,
            "name": None
        }

        system_prompt = """
You are an AI assistant that extracts customer audience filters from CRM queries.

Return ONLY valid JSON.

Allowed keys:

{
  "inactive_days": number|null,
  "min_spend": number|null,
  "city": string|null,
  "segment": string|null,
  "name": string|null
}

Valid customer segments:

- High Value Customers
- Dormant Customers
- Loyal Customers
- New Customers
- At Risk Customers

Examples:

User:
Show customers from Hyderabad

Output:
{
  "city":"Hyderabad"
}

User:
Show customers from Chennai

Output:
{
  "city":"Chennai"
}

User:
Show customers named Eric Tyler

Output:
{
  "name":"Eric Tyler"
}

User:
Show dormant customers

Output:
{
  "segment":"Dormant Customers"
}

User:
Show loyal customers

Output:
{
  "segment":"Loyal Customers"
}

User:
Show high value customers

Output:
{
  "segment":"High Value Customers"
}

User:
Show at risk customers

Output:
{
  "segment":"At Risk Customers"
}

User:
Show high value customers from Pune

Output:
{
  "segment":"High Value Customers",
  "city":"Pune"
}

User:
Show customers inactive for 60 days who spent more than 5000

Output:
{
  "inactive_days":60,
  "min_spend":5000
}

Return JSON only.
"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0
            )

            content = response.choices[0].message.content.strip()

            print("\n==============================")
            print("PROMPT:", prompt)
            print("GROQ RESPONSE:", content)
            print("==============================\n")

            data = json.loads(content)

            return {**default_result, **data}

        except Exception as e:
            from fastapi import HTTPException
            if isinstance(e, HTTPException):
                raise e
            
            # Fallback Rule-Based Parsing (If Groq API fails)
            print(f"[FALLBACK] Groq audience parsing failed ({e}). Using local regex engine.")
            import re
            prompt_lower = prompt.lower()
            
            # Detect Segment
            segments = {
                "high value": "High Value Customers",
                "dormant": "Dormant Customers",
                "loyal": "Loyal Customers",
                "new": "New Customers",
                "at risk": "At Risk Customers"
            }
            for key, val in segments.items():
                if key in prompt_lower:
                    default_result["segment"] = val
                    break
                    
            # Detect City (basic heuristics for common Indian cities in tests)
            cities = ["hyderabad", "chennai", "pune", "bangalore", "mumbai", "delhi"]
            for city in cities:
                if city in prompt_lower:
                    default_result["city"] = city.title()
                    break
                    
            # Detect Spend
            spend_match = re.search(r'(?:spend|spent|more than|>|rs\.?|₹)\s*(\d+)', prompt_lower)
            if spend_match:
                default_result["min_spend"] = int(spend_match.group(1))
                
            # Detect Inactive Days
            days_match = re.search(r'(?:inactive|not bought|hasn\'t bought).*?(\d+)\s*days?', prompt_lower)
            if days_match:
                default_result["inactive_days"] = int(days_match.group(1))
                
            # Detect Name
            name_match = re.search(r'(?:named|name is)\s+([a-zA-Z\s]+)', prompt_lower)
            if name_match:
                # very basic extraction, split by common stop words if needed
                extracted = name_match.group(1).strip()
                if extracted:
                    default_result["name"] = extracted.split(' ')[0].title() + " " + (extracted.split(' ')[1].title() if len(extracted.split(' ')) > 1 else "")
                    
            return default_result

    def generate_campaign(self, goal: str, segment: str = None, channel: str = None, db = None, user_id: int = None) -> dict:
        """
        Generates copy details for a campaign based on its goal, target segment, and channel.
        Timing is based on real Neon event history (min 5 opened events for the user).
        Falls back to industry benchmark timing if data is insufficient.
        """
        from datetime import datetime, timedelta
        segment = segment or "General Customers"
        channel = channel or "WhatsApp"

        # ---- Industry Benchmark Fallback Timings ----
        BENCHMARK_TIMINGS = {
            "high value": {"window": "7 PM – 9 PM", "peak_hour": 19},
            "loyal": {"window": "6 PM – 8 PM", "peak_hour": 18},
            "new": {"window": "5 PM – 7 PM", "peak_hour": 17},
            "dormant": {"window": "10 AM – 12 PM", "peak_hour": 10},
            "at risk": {"window": "10 AM – 12 PM", "peak_hour": 10},
            "general": {"window": "2 PM – 4 PM", "peak_hour": 14},
        }

        seg_lower = segment.lower()
        benchmark = BENCHMARK_TIMINGS["general"]
        for key, val in BENCHMARK_TIMINGS.items():
            if key in seg_lower:
                benchmark = val
                break

        # Start with benchmark defaults
        recommended_time_window = benchmark["window"]
        recommended_peak_hour = benchmark["peak_hour"]
        timing_source = "benchmark"
        recommended_time_reason = "Insufficient engagement history. Using industry benchmark timing."

        # ---- Try to compute from real Neon event data ----
        MIN_EVENTS_REQUIRED = 5
        if db:
            try:
                from app.models.event import Event
                from app.models.customer import Customer
                from app.models.campaign import Campaign
                from sqlalchemy import func, extract

                # Query opened events for this specific user's customers and segment
                base_query = db.query(
                    extract('hour', Event.event_time).label('hour_val'),
                    func.count(Event.id).label('count_val')
                ).join(Customer, Event.customer_id == Customer.id)\
                 .join(Campaign, Event.campaign_id == Campaign.id)\
                 .filter(
                    Event.event_type == "opened",
                    Campaign.user_id == user_id
                 )

                # Apply segment filter if available
                if segment and segment.lower() != "general customers":
                    base_query = base_query.filter(Customer.segment.ilike(f"%{segment}%"))

                # Count total opened events to check sufficiency
                total_opened = db.query(func.count(Event.id))\
                    .join(Customer, Event.customer_id == Customer.id)\
                    .join(Campaign, Event.campaign_id == Campaign.id)\
                    .filter(
                        Event.event_type == "opened",
                        Campaign.user_id == user_id
                    ).scalar() or 0

                if total_opened >= MIN_EVENTS_REQUIRED:
                    peak_event = base_query\
                        .group_by(extract('hour', Event.event_time))\
                        .order_by(func.count(Event.id).desc())\
                        .first()

                    if peak_event:
                        peak_hour = int(peak_event.hour_val)
                        recommended_peak_hour = peak_hour
                        start_ampm = "AM" if peak_hour < 12 else "PM"
                        start_hour_12 = peak_hour if peak_hour <= 12 else peak_hour - 12
                        if start_hour_12 == 0:
                            start_hour_12 = 12
                        end_hour_24 = peak_hour + 2
                        end_ampm = "AM" if end_hour_24 < 12 or end_hour_24 >= 24 else "PM"
                        end_hour_12 = end_hour_24 if end_hour_24 <= 12 else end_hour_24 - 12
                        if end_hour_12 == 0:
                            end_hour_12 = 12
                        recommended_time_window = f"{start_hour_12} {start_ampm} – {end_hour_12} {end_ampm}"
                        recommended_time_reason = (
                            f"Based on {total_opened} historical open events for your {segment} customers, "
                            f"peak engagement is at {start_hour_12} {start_ampm}. "
                            f"Sending now will maximize open rates."
                        )
                        timing_source = "data"
                else:
                    # Not enough data — keep benchmark, add explicit message
                    print(f"[TIMING] Only {total_opened} opened events found for user_id={user_id}. "
                          f"Minimum required: {MIN_EVENTS_REQUIRED}. Using industry benchmark timing.")

            except Exception as e:
                print(f"[ERROR] Failed to query peak hour from Neon: {e}")

        # ---- Compute recommended_scheduled_time (next occurrence of peak hour) ----
        now = datetime.utcnow()
        # Convert UTC peak hour to a scheduled_time target (next occurrence)
        scheduled_candidate = now.replace(minute=0, second=0, microsecond=0)
        scheduled_candidate = scheduled_candidate.replace(hour=recommended_peak_hour)
        if scheduled_candidate <= now:
            scheduled_candidate += timedelta(days=1)
        recommended_scheduled_time = scheduled_candidate.strftime("%Y-%m-%dT%H:%M")

        # ---- Predicted Open Rates and CTR from Neon ----
        predicted_open_rate = "75.0%"
        predicted_ctr = "15.0%"
        if db and segment and channel:
            try:
                from app.models.event import Event
                from app.models.customer import Customer
                from app.models.campaign import Campaign
                from sqlalchemy import func

                delivered = db.query(func.count(Event.id))\
                    .join(Customer, Event.customer_id == Customer.id)\
                    .join(Campaign, Event.campaign_id == Campaign.id)\
                    .filter(Customer.segment.ilike(f"%{segment}%"), Campaign.channel.ilike(f"%{channel}%"), Event.event_type == "delivered")\
                    .scalar() or 0
                opened = db.query(func.count(Event.id))\
                    .join(Customer, Event.customer_id == Customer.id)\
                    .join(Campaign, Event.campaign_id == Campaign.id)\
                    .filter(Customer.segment.ilike(f"%{segment}%"), Campaign.channel.ilike(f"%{channel}%"), Event.event_type == "opened")\
                    .scalar() or 0
                clicked = db.query(func.count(Event.id))\
                    .join(Customer, Event.customer_id == Customer.id)\
                    .join(Campaign, Event.campaign_id == Campaign.id)\
                    .filter(Customer.segment.ilike(f"%{segment}%"), Campaign.channel.ilike(f"%{channel}%"), Event.event_type == "clicked")\
                    .scalar() or 0

                if delivered > 0:
                    predicted_open_rate = f"{(opened / delivered * 100):.1f}%"
                else:
                    if channel.lower() == "whatsapp": predicted_open_rate = "84.2%"
                    elif channel.lower() == "email": predicted_open_rate = "42.6%"
                    else: predicted_open_rate = "91.5%"
                if opened > 0:
                    predicted_ctr = f"{(clicked / opened * 100):.1f}%"
                else:
                    if channel.lower() == "whatsapp": predicted_ctr = "38.5%"
                    elif channel.lower() == "email": predicted_ctr = "8.6%"
                    else: predicted_ctr = "18.2%"
            except Exception as e:
                print(f"[ERROR] Failed to compute dynamic stats from Neon: {e}")

        default_result = {
            "campaign_name": f"{segment} Re-engagement",
            "subject_line": "Exclusive Rewards Await",
            "message_body": "Let's elevate your shopping experience together. We've got custom recommendations waiting for you.",
            "cta": "Shop Now →",
            "recommended_channel": channel
        }

        client = self._get_client(db, user_id, "campaign_studio", goal, "generate_campaign")
        if True:
            system_prompt = (
                "You are an expert CRM marketer generating a highly personalized, contextual campaign copy.\n"
                f"Target Customer Segment: {segment}\n"
                f"Target Channel: {channel}\n"
                "Return a JSON object with keys:\n"
                "- 'campaign_name': string (concise, professional name)\n"
                "- 'subject_line': string (compelling subject line/headline)\n"
                "- 'message_body': string (highly contextual message body. Tailored to the segment characteristics. No generic placeholders like [Customer Name] or [Discount], use realistic names or values like 'Eric' or '15% off')\n"
                "- 'cta': string (the Call to Action, e.g. 'Claim Reward →' or 'Shop Again →')\n"
                "Return valid JSON only."
            )
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Campaign Goal: {goal}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                data = json.loads(response.choices[0].message.content.strip())
                res = {**default_result, **data}

                # Format dynamic results
                res["timing"] = recommended_time_window
                res["timing_reason"] = recommended_time_reason
                res["timing_source"] = timing_source
                res["recommended_scheduled_time"] = recommended_scheduled_time
                res["predicted_open_rate"] = predicted_open_rate
                res["predicted_ctr"] = predicted_ctr

                # Map channels
                msg = res["message_body"]
                cta_txt = res["cta"]
                subj = res["subject_line"]
                res["whatsapp_message"] = f"*{subj}*\n\n{msg}\n\n👉 {cta_txt}"
                res["email_content"] = f"Subject: {subj}\n\nDear Customer,\n\n{msg}\n\nBest regards,\nReachable Retail Team\n\n{cta_txt}"
                res["sms_content"] = f"{subj}: {msg[:100]}... {cta_txt}"

                res["email_message"] = res["email_content"]
                res["sms_message"] = res["sms_content"]
                return res
            except Exception as e:
                print(f"[ERROR] Groq campaign generation failed: {e}")
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                pass

        # Fallback if offline or missing API key
        res = {**default_result}
        res["timing"] = recommended_time_window
        res["timing_reason"] = recommended_time_reason
        res["timing_source"] = timing_source
        res["recommended_scheduled_time"] = recommended_scheduled_time
        res["predicted_open_rate"] = predicted_open_rate
        res["predicted_ctr"] = predicted_ctr

        msg = res["message_body"]
        cta_txt = res["cta"]
        subj = res["subject_line"]
        res["whatsapp_message"] = f"*{subj}*\n\n{msg}\n\n👉 {cta_txt}"
        res["email_content"] = f"Subject: {subj}\n\nDear Customer,\n\n{msg}\n\nBest regards,\nReachable Retail Team\n\n{cta_txt}"
        res["sms_content"] = f"{subj}: {msg[:100]}... {cta_txt}"

        res["email_message"] = res["email_content"]
        res["sms_message"] = res["sms_content"]
        return res

    def copilot_query(self, query: str, db_context: str, db=None, user_id: int=None) -> str:
        """
        Answers dashboard / strategy questions based on database summary metrics context.
        """
        client = self._get_client(db, user_id, "copilot", query, "copilot_query")
        if True:
            prompt = (
                f"You are a Senior CRM Growth Consultant advising on outreach strategy.\n"
                f"Here is the database context metrics summary:\n{db_context}\n\n"
                f"Answer the user query: {query}"
            )
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.5
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                
                print(f"[FALLBACK] Groq copilot query failed ({e}). Using local generic responses.")
                
                # Simple fallback response based on keywords
                q_lower = query.lower()
                if "revenue" in q_lower or "sales" in q_lower:
                    return "Based on the local fallback analysis, your total revenue and sales are tracking steadily. Please refer to the Analytics page for exact figures, as my advanced AI processing is currently offline."
                elif "segment" in q_lower or "customers" in q_lower:
                    return "Your customer segments include Dormant, High Value, and Loyal customers. Try using the AI Audience Builder to filter them! (Fallback Engine Active)"
                elif "campaign" in q_lower:
                    return "WhatsApp campaigns typically show the highest open rates based on the summary metrics. I recommend focusing your efforts there! (Fallback Engine Active)"
                else:
                    return "I am currently running on my local fallback engine because the Groq AI service is unreachable or rate-limited. I can help you with basic CRM navigation, or you can check the Analytics dashboard directly!"

    def negotiate_price(
        self,
        db,
        user_id,

        chat_history: list,
        original_price: float,
        margin_floor: float,
        user_offer: float,
        current_offer: float = None,
        accepted: bool = False,
        user_message: str = "",
        strategy: str = "Balanced",
        negotiation_id: int = None,
        potential_counter_offer: float = None
    ) -> dict:
        """
        Conversational negotiator using Hidden Backend Tags.
        Returns: {"message": str} (where message contains both customer message and hidden tags)
        """
        from app.services.intent_classifier import classify_intent

        if current_offer is None:
            current_offer = round(max(margin_floor + (original_price - margin_floor) * 0.25, margin_floor), 2)
        
        if potential_counter_offer is None:
            potential_counter_offer = current_offer

        # Calculate rule boundaries
        margin_floor = float(margin_floor)
        original_price = float(original_price)
        user_offer = float(user_offer)
        current_offer = float(current_offer)
        potential_counter_offer = float(potential_counter_offer)

        product_name = "Product"
        max_discount_percent = 30.0
        if negotiation_id:
            try:
                from app.database import SessionLocal
                from app.models.negotiation import Negotiation
                db = SessionLocal()
                neg = db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
                if neg:
                    if neg.product_name:
                        product_name = neg.product_name
                    if neg.max_discount is not None:
                        max_discount_percent = float(neg.max_discount)
                db.close()
            except Exception:
                pass

        if True:
            system_prompt = f"""You are Reachable AI's Retail Negotiation Agent.

Your job is to convince the customer to purchase the product while maintaining a natural, helpful conversation.
You must return your response in the following format:
1. First, write your natural, customer-facing chat message (in plain text, e.g. "I can offer this product for ₹39,999").
2. Immediately after the message, on a new line, append the appropriate hidden backend tags. Each tag must be enclosed in double curly braces (e.g. {{TAG_NAME}} or {{TAG_NAME=VALUE}}), with each tag on its own line.

==================================================
NEGOTIATION CONFIGURATION
=========================

Product Name: {product_name}
Original Price: ₹{original_price}
Margin Floor Price: ₹{margin_floor}
Current Offer Price: ₹{current_offer}
Potential Discounted Offer Price: ₹{potential_counter_offer}
Negotiation Strategy: {strategy}

==================================================
SUPPORTED BACKEND TAGS & RULES
=============================

1. {{{{PRICE=<amount>}}}}
   - Use this tag when the customer asks for a discount, can you reduce the price, offers a lower price (even if it is below the Margin Floor Price), or negotiates the price.
   - Rule: The <amount> inside the tag MUST exactly match the price shown in your customer-facing message.
   - Rule: The <amount> MUST be exactly {potential_counter_offer}. Do NOT invent or calculate any other prices.
   - Example tag: {{{{PRICE={potential_counter_offer}}}}}

2. {{{{NO_PRICE_CHANGE}}}}
   - Use this tag when you are answering product questions, discussing competitor prices, handling delivery/shipping questions, off-topic chats, or other queries where the price should remain unchanged.
   - Rule: Do NOT propose any new discounts or changes to the price. Keep the offer at ₹{current_offer}.

3. {{{{FREE_DELIVERY=YES}}}} or {{{{FREE_DELIVERY=NO}}}}
   - Use {{{{FREE_DELIVERY=YES}}}} if the customer asks for free delivery/shipping and you decide to grant it under the current conversation. Also include {{{{NO_PRICE_CHANGE}}}} with this tag. Do NOT lower the price when granting free delivery.
   - Use {{{{FREE_DELIVERY=NO}}}} if you choose not to grant it. Also include {{{{NO_PRICE_CHANGE}}}}.

4. {{{{ASK_COMPETITOR_PRICE}}}}
   - Use this tag when the customer compares the price with a competitor (e.g., Amazon, Flipkart) to ask them what price the competitor is offering.
   - Rule: Also include {{{{NO_PRICE_CHANGE}}}}. Do NOT automatically lower the price.
   - Example tag: {{{{ASK_COMPETITOR_PRICE}}}}

5. {{{{OFFER_ACCEPTED}}}}
   - Use this tag when the customer accepts the offer, agrees to the deal, or asks for the checkout/payment link (intent: ACCEPT).
   - Rule: The customer must explicitly accept the offer without asking any additional questions. Do NOT use if there is any question or conditional statement.
   - Rule: The backend will lock the price at ₹{current_offer} and return a checkout link.

6. {{{{DEAL_REJECTED}}}}
   - Use this tag when the customer explicitly rejects the deal, says they won't buy, or is not interested (intent: REJECT).
   - Rule: Politely acknowledge the rejection.

7. {{{{END_NEGOTIATION}}}}
   - Use this tag if you need to lock the session or end further pricing discussions.

==================================================
EXAMPLES OF CORRECT OUTPUTS
===========================

Customer: "Can I have free delivery?"
Output:
Yes, I can include free delivery.
{{{{NO_PRICE_CHANGE}}}}
{{{{FREE_DELIVERY=YES}}}}

Customer: "Amazon is cheaper."
Output:
What price is Amazon offering? We'll see if we can match it.
{{{{ASK_COMPETITOR_PRICE}}}}
{{{{NO_PRICE_CHANGE}}}}

Customer: "Deal. Send me the link."
Output:
Thank you for accepting the offer. Here is your checkout link.
{{{{OFFER_ACCEPTED}}}}

Customer: "Can I get it for 3000?"
Output:
I understand you're looking for a good deal, but I can't go as low as Rs.3000. I can offer this product to you for ₹{potential_counter_offer}.
{{{{PRICE={potential_counter_offer}}}}}

Customer: "Too expensive, can you reduce price?"
Output:
I understand. I can offer this product to you for ₹{potential_counter_offer}.
{{{{PRICE={potential_counter_offer}}}}}

Customer: "I dont want this product."
Output:
I understand you are not interested. Thank you for your time.
{{{{DEAL_REJECTED}}}}

Customer: "Tell me a joke."
Output:
I'd be happy to help with your purchase decision. Let's continue discussing the product and find the best option for you.
{{{{NO_PRICE_CHANGE}}}}
"""
            try:
                client = self._get_client(db, user_id, "cart_negotiator", user_message, "negotiate_price")
                # Format chat history for Groq messages list, excluding the latest user message
                messages = [{"role": "system", "content": system_prompt}]
                history_to_send = chat_history[:-1] if (chat_history and chat_history[-1]["sender"] == "customer") else chat_history
                for m in history_to_send:
                    role = "assistant" if m["sender"] == "merchant" else "user"
                    messages.append({"role": role, "content": m["message"]})
                
                # Add the latest user message
                messages.append({"role": "user", "content": f"Customer Message: {user_message}"})

                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7
                )
                data = response.choices[0].message.content.strip()
                return {"message": data}
            except Exception as e:
                print(f"[ERROR] Groq negotiation failed: {e}")
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    raise e
                pass

        # Fallback Negotiation Logic (No API or Call Error)
        local_intent = classify_intent(user_message)
        
        if local_intent == "PRICE_COMPARISON":
            message = "What price is Amazon offering?\n\n{{ASK_COMPETITOR_PRICE}}\n{{NO_PRICE_CHANGE}}"
        elif local_intent == "DELIVERY":
            message = "Yes, I can include free delivery.\n\n{{NO_PRICE_CHANGE}}\n{{FREE_DELIVERY=YES}}"
        elif local_intent == "ACCEPT":
            message = "Thank you for accepting the offer. Here is your checkout link.\n\n{{OFFER_ACCEPTED}}"
        elif local_intent == "REJECT":
            message = "I understand you're not interested. Thank you for your time.\n\n{{DEAL_REJECTED}}"
        elif local_intent == "OFF_TOPIC":
            message = "I'd be happy to help with your purchase decision. Let's continue discussing the product and find the best option for you.\n\n{{NO_PRICE_CHANGE}}"
        elif local_intent == "PRODUCT_QUESTION":
            message = f"This product features premium materials and high durability. The price is currently ₹{current_offer:.0f}.\n\n{{NO_PRICE_CHANGE}}"
        else: # PRICE_NEGOTIATION
            message = f"I can offer this product to you at ₹{potential_counter_offer:.0f}.\n\n{{PRICE={potential_counter_offer:.0f}}}"

        return {
            "message": message
        }
