import urllib.request
import json
import urllib.error

SUPABASE_URL = "https://ldzfrrlwejdvrrjpsiwm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxkemZycmx3ZWpkdnJyanBzaXdtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1OTY1NDY5NywiZXhwIjoyMDc1MjMwNjk3fQ.Q9ZeUv4Kl9ea0Od-zALGqAppoIAi5ZdwThmbBFOrXA8"

# 1. Update user to admin using Supabase REST API directly
req_sb = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/users?email=eq.test99@test.com", data=b'{"role": "admin"}', method="PATCH")
req_sb.add_header("apikey", SUPABASE_KEY)
req_sb.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
req_sb.add_header("Content-Type", "application/json")
req_sb.add_header("Prefer", "return=representation")
try:
    resp = urllib.request.urlopen(req_sb)
    print("Supabase update:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("Supabase update error:", e.read().decode())

# 2. Login to local API
req_login = urllib.request.Request("http://localhost:8000/auth/login", data=b'{"email": "test99@test.com", "password": "password123"}', headers={"Content-Type": "application/json"})
resp_login = urllib.request.urlopen(req_login)
cookie = resp_login.headers.get("Set-Cookie").split(";")[0]

# 3. Hit /admin/classes
req_admin = urllib.request.Request("http://localhost:8000/admin/classes")
req_admin.add_header("Cookie", cookie)
try:
    resp_admin = urllib.request.urlopen(req_admin)
    print("/admin/classes:", resp_admin.getcode())
except urllib.error.HTTPError as e:
    print("/admin/classes Error:", e.code)
    print(e.read().decode())

req_enr = urllib.request.Request("http://localhost:8000/enrollments/me")
req_enr.add_header("Cookie", cookie)
try:
    resp_enr = urllib.request.urlopen(req_enr)
    print("/enrollments/me:", resp_enr.getcode())
except urllib.error.HTTPError as e:
    print("/enrollments/me Error:", e.code)
    print(e.read().decode())
