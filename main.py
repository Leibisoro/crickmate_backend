from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from passlib.context import CryptContext
from database import get_connection
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import random, string, hashlib, time
import json
from typing import Dict, List

app = FastAPI()

# --- CORS middleware ---
# --- CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://crickmate-frontend.vercel.app"
    ],
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

# --- WebSocket Room Manager ---
class ConnectionManager:
    def __init__(self):
        # room_code -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # room_code -> game state
        self.game_states: Dict[str, dict] = {}

    async def connect(self, websocket: WebSocket, room_code: str):
        await websocket.accept()
        if room_code not in self.active_connections:
            self.active_connections[room_code] = []
            self.game_states[room_code] = {
                "players": [],
                "toss": {},
                "game_data": {}
            }
        self.active_connections[room_code].append(websocket)

    def disconnect(self, websocket: WebSocket, room_code: str):
        if room_code in self.active_connections:
            self.active_connections[room_code].remove(websocket)
            if len(self.active_connections[room_code]) == 0:
                del self.active_connections[room_code]
                del self.game_states[room_code]

    async def send_to_room(self, room_code: str, message: dict):
        if room_code in self.active_connections:
            for connection in self.active_connections[room_code]:
                try:
                    await connection.send_json(message)
                except:
                    pass

    def get_player_count(self, room_code: str) -> int:
        return len(self.active_connections.get(room_code, []))

manager = ConnectionManager()

# --- Pydantic models ---
class SignupRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RoomRequest(BaseModel):
    username: str
    roomCode: str | None = None

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

# --- WebSocket endpoint for multiplayer ---
@app.websocket("/ws/multiplayer/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str):
    await manager.connect(websocket, room_code)
    
    try:
        # Send player count on join
        player_count = manager.get_player_count(room_code)
        await manager.send_to_room(room_code, {
            "type": "player_joined",
            "player_count": player_count
        })
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Handle different message types
            if msg_type == "toss_choice":
                # Player chose odd/even
                await manager.send_to_room(room_code, {
                    "type": "toss_choice",
                    "player": data.get("player"),
                    "choice": data.get("choice")
                })
                
            elif msg_type == "toss_number":
                # Player picked a number
                await manager.send_to_room(room_code, {
                    "type": "toss_number",
                    "player": data.get("player"),
                    "number": data.get("number")
                })
                
            elif msg_type == "toss_result":
                # Send toss result to both players
                await manager.send_to_room(room_code, {
                    "type": "toss_result",
                    "winner": data.get("winner"),
                    "player1_number": data.get("player1_number"),
                    "player2_number": data.get("player2_number")
                })
                
            elif msg_type == "bat_bowl_choice":
                # Winner chose to bat or bowl
                await manager.send_to_room(room_code, {
                    "type": "bat_bowl_choice",
                    "player": data.get("player"),
                    "choice": data.get("choice")
                })
                
            elif msg_type == "game_action":
                # In-game actions (batting, bowling, etc.)
                await manager.send_to_room(room_code, {
                    "type": "game_action",
                    "action": data.get("action"),
                    "data": data.get("data")
                })
                
            else:
                # Echo any other messages
                await manager.send_to_room(room_code, data)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        player_count = manager.get_player_count(room_code)
        if player_count > 0:
            await manager.send_to_room(room_code, {
                "type": "player_left",
                "player_count": player_count
            })

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