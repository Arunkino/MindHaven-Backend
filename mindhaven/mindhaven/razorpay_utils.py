# razorpay_utils.py

import razorpay
from django.conf import settings

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount, currency='INR'):
    data = {
        'amount': int(amount * 100),  # Razorpay expects amount in paise
        'currency': currency,
    }
    order = client.order.create(data=data)
    return order

def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        return True
    except:
        return False