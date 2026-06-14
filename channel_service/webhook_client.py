import urllib.request
import json
import datetime

def send_webhook_callback(webhook_url: str, campaign_id: int, customer_id: int, event_type: str, metadata: dict = None):
    """
    Sends an HTTP POST webhook request back to the CRM backend to record delivery states.
    """
    payload = {
        "campaign_id": campaign_id,
        "customer_id": customer_id,
        "event_type": event_type,
        "event_time": datetime.datetime.utcnow().isoformat(),
        "metadata": metadata or {}
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        print(f"Failed to send webhook callback {event_type} for customer {customer_id}: {e}")
        return False
