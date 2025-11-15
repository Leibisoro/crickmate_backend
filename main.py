from fastapi import FastAPI, HTTPException
from passlib.context import CryptContext
from database import get_connection
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random, string, hashlib, time

app = FastAPI()

# --- CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Password hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# --- Pydantic models ---
class SignupRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RoomRequest(BaseModel):
    username: str
    roomCode: str | None = None  # Optional for creating a room

# --- Root & DB Test ---
@app.get("/")
def root():
    return {"msg": "hello crickmate backend"}

@app.get("/test-db")
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()
        conn.close()
        return {"status": "connected", "database": db_name}
    except Exception as e:
        return {"status": "error", "details": str(e)}

# --- Auth APIs ---
@app.post("/signup")
def signup(data: SignupRequest):
    username = data.username
    password = data.password
    hashed = get_password_hash(password)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
        conn.commit()
        return {"status": "success", "username": username}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/login")
def login(data: LoginRequest):
    username = data.username
    password = data.password

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, password FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        user_id, hashed_password = user
        if not verify_password(password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {"status": "success", "username": username, "user_id": user_id}
    finally:
        cur.close()
        conn.close()

# --- Room APIs ---
@app.post("/create-room")
def create_room(data: RoomRequest):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username=%s", (data.username,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        host_user_id = user[0]

        room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        cur.execute("INSERT INTO rooms (code, host_user_id) VALUES (%s, %s)", (room_code, host_user_id))
        conn.commit()
        return {"status": "success", "roomCode": room_code}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/join-room")
def join_room(data: RoomRequest):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username=%s", (data.username,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        guest_user_id = user[0]

        cur.execute("SELECT id FROM rooms WHERE code=%s", (data.roomCode,))
        room = cur.fetchone()
        if not room:
            raise HTTPException(status_code=404, detail="Room not found")
        room_id = room[0]

        cur.execute("INSERT INTO room_guests (room_id, guest_user_id) VALUES (%s, %s)", (room_id, guest_user_id))
        conn.commit()
        return {"status": "success", "roomCode": data.roomCode}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        cur.close()
        conn.close()

# --- Leaderboard API with blockchain hash ---
@app.get("/leaderboard")
def get_leaderboard():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT u.username, l.wins, l.losses, l.rating, b.data_hash
            FROM leaderboard l
            JOIN users u ON l.user_id = u.id
            LEFT JOIN blockchain_records b ON b.match_id = (
                SELECT MAX(match_id) FROM blockchain_records br2 WHERE br2.match_id = l.user_id
            )
            ORDER BY l.rating DESC
        """)
        data = cur.fetchall()
        for row in data:
            if not row["data_hash"]:
                raw = f"{row['username']}{row['wins']}{row['losses']}{row['rating']}{time.time()}"
                row["data_hash"] = hashlib.sha256(raw.encode()).hexdigest()
        return {"status": "success", "data": data}
    finally:
        cur.close()
        conn.close()
