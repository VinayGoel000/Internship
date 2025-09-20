import random
import requests

def generate_otp():
    return random.randint(100000, 999999)

def send_sms(mobile, otp):
    """
    Example with Fast2SMS (India).
    Replace 'YOUR_API_KEY' with actual Fast2SMS key.
    """
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = f"sender_id=TXTIND&message=Your OTP is {otp}&route=v3&numbers={mobile}"
    headers = {
        'authorization': "YOUR_API_KEY",
        'Content-Type': "application/x-www-form-urlencoded"
    }
    response = requests.request("POST", url, data=payload, headers=headers)
    return response.json()
