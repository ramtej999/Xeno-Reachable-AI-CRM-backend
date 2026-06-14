from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.customer_schema import CustomerCreate, CustomerResponse
from app.schemas.order_schema import OrderResponse
from app.routes.auth import get_current_user
from app.models.user import User
from typing import List

router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)

@router.get("/by-segment", response_model=List[CustomerResponse])
def read_customers_by_segment(
    segment: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    customers = db.query(Customer).filter(
        Customer.user_id == current_user.id,
        Customer.segment == segment
    ).all()
    return customers

@router.get("/orders", response_model=List[OrderResponse])
def read_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Order).join(Customer).filter(Customer.user_id == current_user.id).all()

@router.get("/", response_model=List[CustomerResponse])
def read_customers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customers = db.query(Customer).filter(Customer.user_id == current_user.id).all()
    return customers


@router.get("/{id}", response_model=CustomerResponse)
def read_customer(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.id == id, Customer.user_id == current_user.id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(customer: CustomerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_customer = Customer(
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        city=customer.city,
        total_spend=customer.total_spend,
        segment=customer.segment,
        last_purchase=customer.last_purchase,
        user_id=current_user.id
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_customers(customers: List[CustomerCreate], db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    imported_count = 0
    for c in customers:
        db_customer = Customer(
            name=c.name,
            email=c.email,
            phone=c.phone,
            city=c.city,
            total_spend=c.total_spend,
            segment=c.segment,
            last_purchase=c.last_purchase,
            user_id=current_user.id
        )
        db.add(db_customer)
        imported_count += 1
    db.commit()
    return {"status": "success", "imported": imported_count}

@router.put("/{id}", response_model=CustomerResponse)
def update_customer(id: int, updated: CustomerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.id == id, Customer.user_id == current_user.id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer.name = updated.name
    customer.email = updated.email
    customer.phone = updated.phone
    customer.city = updated.city
    customer.total_spend = updated.total_spend
    customer.segment = updated.segment
    customer.last_purchase = updated.last_purchase
    
    db.commit()
    db.refresh(customer)
    return customer

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_customer(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.id == id, Customer.user_id == current_user.id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()
    return {"status": "success", "message": "Customer deleted successfully"}

from pydantic import BaseModel
from typing import Optional
import random
import string
from datetime import date, timedelta

class GenerateCustomersRequest(BaseModel):
    count: int = 100
    city: Optional[str] = None

@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_fake_customers(
    payload: GenerateCustomersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    first_names_male = ["Aarav", "Vihaan", "Vivaan", "Rahul", "Amit", "Raj", "Sanjay", "Vijay", "Arjun", "Aditya", "Sai", "Vikram", "Rohan", "Kabir", "Manish"]
    first_names_female = ["Neha", "Pooja", "Priya", "Kriti", "Anjali", "Riya", "Sneha", "Aditi", "Shruti", "Kavya", "Divya", "Ishita", "Meera", "Swati", "Tanya"]
    last_names = ["Sharma", "Verma", "Kumar", "Singh", "Patel", "Gupta", "Mehta", "Joshi", "Rao", "Nair", "Iyer", "Reddy", "Choudhury", "Das", "Banerjee", "Sen"]
    cities_pool = ["Mumbai", "Delhi", "Bengaluru", "Kolkata", "Chennai", "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kochi", "Chandigarh"]

    existing_emails = set(row[0].lower() for row in db.query(Customer.email).all() if row[0])
    existing_phones = set(row[0] for row in db.query(Customer.phone).all() if row[0])

    segments_to_create = []
    distribution = [
        ("New Customers", 0.20),
        ("Regular Customers", 0.25),
        ("Loyal Customers", 0.20),
        ("High Value Customers", 0.15),
        ("Dormant Customers", 0.10),
        ("At Risk Customers", 0.10)
    ]

    for segment_name, pct in distribution:
        cnt = int(payload.count * pct)
        segments_to_create.extend([segment_name] * cnt)

    while len(segments_to_create) < payload.count:
        segments_to_create.append(random.choice([d[0] for d in distribution]))

    random.shuffle(segments_to_create)

    def get_spend_and_date(segment: str):
        today = date.today()
        if segment == "New Customers":
            spend = random.randint(0, 5000)
            purchase_days_ago = random.randint(0, 30)
        elif segment == "Regular Customers":
            spend = random.randint(5000, 10000)
            purchase_days_ago = random.randint(0, 90)
        elif segment == "Loyal Customers":
            spend = random.randint(10000, 20000)
            purchase_days_ago = random.randint(0, 60)
        elif segment == "High Value Customers":
            spend = random.randint(20000, 80000)
            purchase_days_ago = random.randint(0, 30)
        elif segment == "Dormant Customers":
            spend = random.randint(5000, 20000)
            purchase_days_ago = random.randint(180, 365)
        elif segment == "At Risk Customers":
            spend = random.randint(5000, 15000)
            purchase_days_ago = random.randint(90, 180)
        else:
            spend = random.randint(0, 5000)
            purchase_days_ago = random.randint(0, 30)

        purchase_date = today - timedelta(days=purchase_days_ago)
        return spend, purchase_date

    new_customers = []
    for segment in segments_to_create:
        gender = random.choice(["male", "female"])
        if gender == "male":
            first_name = random.choice(first_names_male)
        else:
            first_name = random.choice(first_names_female)
        last_name = random.choice(last_names)
        full_name = f"{first_name} {last_name}"

        email = ""
        attempts = 0
        while attempts < 100:
            rand_num = random.randint(100, 99999)
            email_candidate = f"{first_name.lower()}.{last_name.lower()}{rand_num}@gmail.com"
            if email_candidate not in existing_emails:
                email = email_candidate
                existing_emails.add(email)
                break
            attempts += 1
        if not email:
            email = f"user_{random.choice(string.ascii_lowercase)}{random.randint(100000, 999999)}@gmail.com"

        phone = ""
        attempts = 0
        while attempts < 100:
            phone_candidate = f"98{random.randint(10000000, 99999999)}"
            if phone_candidate not in existing_phones:
                phone = phone_candidate
                existing_phones.add(phone)
                break
            attempts += 1
        if not phone:
            phone = f"98{random.randint(10000000, 99999999)}"

        if payload.city:
            cust_city = payload.city
        else:
            cust_city = random.choice(cities_pool)

        spend, purchase_date = get_spend_and_date(segment)

        db_customer = Customer(
            name=full_name,
            email=email,
            phone=phone,
            city=cust_city,
            total_spend=spend,
            segment=segment,
            last_purchase=purchase_date,
            user_id=current_user.id
        )
        new_customers.append(db_customer)

    db.add_all(new_customers)
    db.commit()
    return {"status": "success", "count": len(new_customers)}