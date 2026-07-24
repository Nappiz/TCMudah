import urllib.request
import json

def do_req(url, data=None, cookie=None):
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        print(url, resp.getcode(), resp.read().decode())
        return resp.headers.get("Set-Cookie")
    except Exception as e:
        print(url, "Error:", getattr(e, 'code', str(e)))
        if hasattr(e, 'read'):
            print(e.read().decode())
        return None

# register
do_req("http://localhost:8000/auth/register", {"full_name": "Test", "email": "test99@test.com", "password": "password123"})
cookie = do_req("http://localhost:8000/auth/login", {"email": "test99@test.com", "password": "password123"})
if cookie:
    c = cookie.split(";")[0]
    do_req("http://localhost:8000/me", cookie=c)
    do_req("http://localhost:8000/enrollments/me", cookie=c)
    do_req("http://localhost:8000/me/has-access", cookie=c)
