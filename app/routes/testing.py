from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.models.campaign import Campaign
from app.models.event import Event
from app.models.negotiation import Negotiation
from app.models.message import Message
from app.routes.auth import get_current_user
from app.models.user import User
from faker import Faker
import random
from datetime import datetime, timedelta
from decimal import Decimal

router = APIRouter(
    prefix="/testing",
    tags=["Testing & Seeding"]
)

@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_database(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Cleans the existing tables and seeds realistic data for testing and front-end evaluation.
    """
    # 1. Clean existing records safely for this user only
    # Delete events belonging to current user's campaigns or customers
    db.query(Event).filter(
        Event.campaign_id.in_(db.query(Campaign.id).filter(Campaign.user_id == current_user.id)) |
        Event.customer_id.in_(db.query(Customer.id).filter(Customer.user_id == current_user.id))
    ).delete(synchronize_session=False)

    # Delete orders belonging to current user's customers
    db.query(Order).filter(
        Order.customer_id.in_(db.query(Customer.id).filter(Customer.user_id == current_user.id))
    ).delete(synchronize_session=False)

    # Delete messages and negotiations belonging to current user's customers
    db.query(Message).filter(
        Message.negotiation_id.in_(
            db.query(Negotiation.id).filter(
                Negotiation.customer_id.in_(db.query(Customer.id).filter(Customer.user_id == current_user.id))
            )
        )
    ).delete(synchronize_session=False)

    db.query(Negotiation).filter(
        Negotiation.customer_id.in_(db.query(Customer.id).filter(Customer.user_id == current_user.id))
    ).delete(synchronize_session=False)

    # Delete campaigns and customers belonging to current user
    db.query(Campaign).filter(Campaign.user_id == current_user.id).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.user_id == current_user.id).delete(synchronize_session=False)
    db.commit()

    fake = Faker()
    random.seed(42)

    # 2. Seed Customers
    segments = ["High Value Customers", "Loyal Customers", "Dormant Customers", "At Risk Customers", "New Customers"]
    cities = ["Mumbai", "Delhi", "Bangalore", "Kolkata", "Chennai", "Pune", "Hyderabad"]
    
    customers_list = []
    for _ in range(100):
        c = Customer(
            name=fake.name(),
            email=fake.unique.email(),
            phone=fake.phone_number()[:20],
            city=random.choice(cities),
            total_spend=Decimal("0.0"),
            segment=random.choice(segments),
            last_purchase=None,
            user_id=current_user.id,
            created_at=datetime.utcnow() - timedelta(days=random.randint(100, 700))
        )
        db.add(c)
        customers_list.append(c)
    db.commit()

    # 3. Seed Orders & Update Customer Totals
    categories = ["Apparel", "Electronics", "Footwear", "Accessories", "Home Decor"]
    products = {
        "Apparel": ["V-Neck T-Shirt", "Slim Fit Denim", "Leather Jacket", "Designer Saree", "Hooded Sweatshirt"],
        "Electronics": ["Bluetooth Earbuds", "Smart Fitness Band", "Fast Charging Adapter", "Portable Power Bank"],
        "Footwear": ["Running Sneakers", "Formal Leather Shoes", "Casual Loafers", "Sports Sandals"],
        "Accessories": ["Minimalist Wallet", "Aviator Sunglasses", "Classic Leather Belt", "Smartwatch Strap"],
        "Home Decor": ["Scented Candle Set", "Ceramic Flower Vase", "LED Desk Lamp", "Microfiber Cushion"]
    }

    for c in customers_list:
        # Determine number of orders based on segment
        if "High Value" in c.segment:
            order_count = random.randint(5, 12)
            unit_price_range = (2500, 8000)
        elif "Loyal" in c.segment:
            order_count = random.randint(4, 7)
            unit_price_range = (1200, 3500)
        elif "Dormant" in c.segment:
            order_count = random.randint(1, 2)
            unit_price_range = (800, 2500)
        elif "At Risk" in c.segment:
            order_count = random.randint(2, 4)
            unit_price_range = (1000, 3000)
        else: # New
            order_count = 1
            unit_price_range = (500, 1500)

        total_spend = Decimal("0.0")
        last_purchase_date = None

        for i in range(order_count):
            cat = random.choice(categories)
            prod = random.choice(products[cat])
            price = Decimal(str(round(random.uniform(*unit_price_range), 2)))
            qty = random.randint(1, 2)
            amount = price * qty
            total_spend += amount

            # Determine date distribution
            if "Dormant" in c.segment:
                days_ago = random.randint(95, 200)
            elif "At Risk" in c.segment:
                days_ago = random.randint(60, 90)
            elif "New" in c.segment:
                days_ago = random.randint(5, 28)
            else:
                days_ago = random.randint(2, 45) if i == order_count - 1 else random.randint(46, 180)

            purchase_datetime = datetime.utcnow() - timedelta(days=days_ago)
            purchase_date = purchase_datetime.date()
            if last_purchase_date is None or purchase_date > last_purchase_date:
                last_purchase_date = purchase_date

            order = Order(
                customer_id=c.id,
                order_number=f"ORD-{fake.unique.random_number(digits=6)}",
                product_name=prod,
                category=cat,
                quantity=qty,
                unit_price=price,
                total_amount=amount,
                order_status="Completed",
                purchase_date=purchase_datetime,
                created_at=purchase_datetime
            )
            db.add(order)

        c.total_spend = total_spend
        c.last_purchase = last_purchase_date
    db.commit()

    # 4. Seed Campaigns
    campaign_names = [
        ("VIP Exclusive Offer", "WhatsApp", 25, "Completed", 85000.0),
        ("Cart Re-engagement Blast", "SMS", 40, "Completed", 34000.0),
        ("Holiday Discount Blast", "Email", 70, "Completed", 124000.0),
        ("Weekend Special Promo", "WhatsApp", 15, "Completed", 45000.0),
        ("Dormant Win-Back Campaign", "Email", 30, "Draft", 0.0),
    ]

    campaigns_list = []
    for name, channel, size, status, rev in campaign_names:
        target_segment = "Dormant Customers"
        if "vip" in name.lower():
            target_segment = "High Value Customers"
        elif "cart" in name.lower():
            target_segment = "At Risk Customers"
        elif "weekend" in name.lower():
            target_segment = "Loyal Customers"
        elif "holiday" in name.lower():
            target_segment = "New Customers"

        camp = Campaign(
            campaign_name=name,
            channel=channel,
            audience_size=size,
            status=status,
            revenue=Decimal(str(rev)),
            user_id=current_user.id,
            target_segment=target_segment,
            created_at=datetime.utcnow() - timedelta(days=random.randint(5, 30))
        )
        db.add(camp)
        campaigns_list.append(camp)
    db.commit()

    # 5. Seed Events
    for camp in campaigns_list:
        if camp.status == "Completed":
            # Seed events for this campaign
            sampled_custs = random.sample(customers_list, camp.audience_size)
            camp_revenue = Decimal("0.0")
            for cust in sampled_custs:
                # Flow of events
                db.add(Event(customer_id=cust.id, campaign_id=camp.id, event_type="sent", event_time=camp.created_at))
                if random.random() > 0.05: # 95% delivery
                    db.add(Event(customer_id=cust.id, campaign_id=camp.id, event_type="delivered", event_time=camp.created_at + timedelta(seconds=30)))
                    
                    if camp.channel == "WhatsApp" or random.random() > 0.40: # Open rate
                        db.add(Event(customer_id=cust.id, campaign_id=camp.id, event_type="opened", event_time=camp.created_at + timedelta(minutes=random.randint(5, 120))))
                        
                        if random.random() > 0.70: # Click rate
                            db.add(Event(customer_id=cust.id, campaign_id=camp.id, event_type="clicked", event_time=camp.created_at + timedelta(minutes=random.randint(10, 180))))
                            
                            if random.random() > 0.85: # Purchase rate
                                purchase_val = Decimal(str(round(random.uniform(500.0, 5000.0), 2)))
                                db.add(Event(
                                    customer_id=cust.id,
                                    campaign_id=camp.id,
                                    event_type="purchased",
                                    event_time=camp.created_at + timedelta(minutes=random.randint(15, 240)),
                                    revenue=purchase_val
                                ))
                                camp_revenue += purchase_val
            camp.revenue = camp_revenue

    # 6. Seed Negotiations
    some_custs = random.sample(customers_list, 3)
    for cust in some_custs:
        neg = Negotiation(
            customer_id=cust.id,
            product_name="Minimalist Wallet",
            original_price=Decimal("1500.00"),
            negotiated_price=None,
            margin_floor=Decimal("1100.00"),
            status="active",
            created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
        )
        db.add(neg)
        db.commit()

        # Add messages
        db.add(Message(negotiation_id=neg.id, sender="merchant", message="Welcome! The Minimalist Wallet is ₹1500.00. I can offer you a small discount if you want to negotiate."))
        db.add(Message(negotiation_id=neg.id, sender="customer", message="Can I get it for ₹1000?"))
        db.add(Message(negotiation_id=neg.id, sender="merchant", message="Sorry, ₹1000 is below our cost. The best I can do is ₹1250.00."))

    db.commit()
    return {"status": "success", "message": "Database cleared and seeded with fresh, consistent mock data."}
