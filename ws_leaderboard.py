from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
import os
from dotenv import load_dotenv
import asyncio
import json

load_dotenv()

cfg = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT") or 3306),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "autocommit": True
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connected WebSocket clients
clients = []

async def broadcast_leaderboard():
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT u.username, l.wins, l.losses, l.rating FROM leaderboard l JOIN users u ON l.user_id=u.id ORDER BY l.wins DESC")
    leaderboard = cur.fetchall()
    cur.close()
    conn.close()
    data = json.dumps(leaderboard)
    for client in clients:
        await client.send_text(data)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(1)  # keep connection alive
    except Exception:
        pass
    finally:
        clients.remove(websocket)

# Optional: endpoint to trigger broadcast after score submission
@app.post("/broadcast")
async def broadcast():
    await broadcast_leaderboard()
    return {"status": "broadcasted"}
