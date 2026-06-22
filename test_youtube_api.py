import asyncio
import os
import sys

# add backend-fastapi to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.database import execute, get_pool, close_pool
from models.user import find_user_by_email, create_user
from utils.security import hash_password, create_jwt

async def main():
    await get_pool()
    email = "testrunner@test.com"
    pwd = "password123"
    
    # 1. Ensure user exists and is verified
    user = await find_user_by_email(email)
    if not user:
        phash = hash_password(pwd)
        user = await create_user("Test Runner", email, phash)
    
    await execute("UPDATE users SET is_verified = TRUE WHERE email = $1", [email])
    
    user = await find_user_by_email(email)
    
    # 2. generate token
    token = create_jwt(str(user["id"]), user["email"])
    
    await close_pool()
    
    # 3. Use requests to hit the local server
    import requests
    url = "http://127.0.0.1:8000/api/videos/youtube"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "youtubeUrl": "https://www.youtube.com/watch?v=4YkbZTSoG2g",
        "mode": "frames",
        "intervalSeconds": 5
    }
    
    print("Submitting request to /api/videos/youtube ...")
    resp = requests.post(url, json=data, headers=headers)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
