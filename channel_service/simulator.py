import time
import random
from concurrent.futures import ThreadPoolExecutor, wait
from channel_service.webhook_client import send_webhook_callback


def simulate_customer_outreach(
    webhook_url: str,
    campaign_id: int,
    recipient: dict,
    channel: str,
    force_purchase: bool = False
):
    """
    Simulates realistic campaign engagement flow:

    sent
      -> delivered
      -> opened
      -> clicked
      -> purchased

    Purchase can NEVER happen without click.
    Click can NEVER happen without open.
    Open can NEVER happen without delivery.
    """

    customer_id = recipient["customer_id"]
    cust_name = recipient["name"]

    # --------------------------------------------------
    # 1. SENT
    # --------------------------------------------------
    print(
        f"[EVENT] Campaign {campaign_id}: SENT -> {customer_id} ({cust_name})",
        flush=True
    )

    send_webhook_callback(
        webhook_url,
        campaign_id,
        customer_id,
        "sent"
    )

    time.sleep(random.uniform(0.1, 0.3))

    # --------------------------------------------------
    # 2. DELIVERED
    # --------------------------------------------------
    delivered = force_purchase or random.random() <= 0.95

    if not delivered:
        print(
            f"[EVENT] Campaign {campaign_id}: FAILED -> {customer_id}",
            flush=True
        )

        send_webhook_callback(
            webhook_url,
            campaign_id,
            customer_id,
            "failed"
        )
        return

    send_webhook_callback(
        webhook_url,
        campaign_id,
        customer_id,
        "delivered"
    )

    print(
        f"[EVENT] Campaign {campaign_id}: DELIVERED -> {customer_id}",
        flush=True
    )

    time.sleep(random.uniform(0.2, 0.5))

    # --------------------------------------------------
    # 3. OPENED
    # --------------------------------------------------
    if channel.lower() == "whatsapp":
        open_rate = 0.85
    elif channel.lower() == "email":
        open_rate = 0.60
    elif channel.lower() == "sms":
        open_rate = 0.70
    else:
        open_rate = 0.70

    opened = force_purchase or random.random() <= open_rate

    if not opened:
        return

    send_webhook_callback(
        webhook_url,
        campaign_id,
        customer_id,
        "opened"
    )

    print(
        f"[EVENT] Campaign {campaign_id}: OPENED -> {customer_id}",
        flush=True
    )

    time.sleep(random.uniform(0.3, 0.7))

    # --------------------------------------------------
    # 4. CLICKED
    # --------------------------------------------------
    if channel.lower() == "whatsapp":
        click_rate = 0.35
    elif channel.lower() == "email":
        click_rate = 0.20
    elif channel.lower() == "sms":
        click_rate = 0.25
    else:
        click_rate = 0.25

    clicked = force_purchase or random.random() <= click_rate

    if not clicked:
        return

    send_webhook_callback(
        webhook_url,
        campaign_id,
        customer_id,
        "clicked"
    )

    print(
        f"[EVENT] Campaign {campaign_id}: CLICKED -> {customer_id}",
        flush=True
    )

    time.sleep(random.uniform(0.4, 1.0))

    # --------------------------------------------------
    # 5. PURCHASED
    # --------------------------------------------------
    if channel.lower() == "whatsapp":
        purchase_rate = 0.20
    else:
        purchase_rate = 0.15

    purchased = force_purchase or random.random() <= purchase_rate

    if not purchased:
        return

    purchase_value = round(
        random.uniform(500.0, 5000.0),
        2
    )

    metadata = {
        "revenue": purchase_value,
        "product_name": random.choice(
            [
                "Premium Hoodie",
                "Casual Shoes",
                "Wireless Mouse",
                "Designer Mug"
            ]
        ),
        "category": random.choice(
            [
                "Apparel",
                "Footwear",
                "Electronics",
                "Home Decor"
            ]
        )
    }

    send_webhook_callback(
        webhook_url,
        campaign_id,
        customer_id,
        "purchased",
        metadata
    )

    print(
        f"[EVENT] Campaign {campaign_id}: PURCHASED -> {customer_id} | ₹{purchase_value}",
        flush=True
    )


def run_campaign_simulation(
    webhook_url: str,
    campaign_id: int,
    recipients: list,
    channel: str
):
    """
    Runs campaign simulation concurrently.

    First recipient is forced through entire funnel
    so every demo campaign generates at least
    one purchase and revenue.
    """

    print(
        f"[SIMULATION START] campaign={campaign_id} recipients={len(recipients)}",
        flush=True
    )

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        for idx, recipient in enumerate(recipients):
            force_purchase = (idx == 0)

            futures.append(
                executor.submit(
                    simulate_customer_outreach,
                    webhook_url,
                    campaign_id,
                    recipient,
                    channel,
                    force_purchase
                )
            )

        wait(futures)

    print(
        f"[SIMULATION COMPLETE] campaign={campaign_id}",
        flush=True
    )

    send_webhook_callback(
        webhook_url,
        campaign_id,
        None,
        "completed"
    )