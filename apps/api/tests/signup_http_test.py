import time, json
import httpx

email = f"qa_{int(time.time())}@example.com"
payload = {"name": "QA", "email": email, "password": "Password1234!"}

try:
    r = httpx.post("http://localhost:8000/signup", json=payload, timeout=10.0)
    print("SIGNUP", r.status_code, r.text)
except Exception as e:
    print("SIGNUP_ERR", repr(e))

try:
    r2 = httpx.post("http://localhost:8000/login", json={"email": email, "password": "Password1234!"}, timeout=10.0)
    print("LOGIN", r2.status_code, r2.text)
except Exception as e:
    print("LOGIN_ERR", repr(e))
