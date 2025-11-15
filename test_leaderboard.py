import os
import time
import random
import mysql.connector
import requests
from dotenv import load_dotenv
import hashlib

load_dotenv()

cfg = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT") or 3306),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "autocommit": True
}

WS_BROADCAST_URL = "http://localhost:8000/broadcast"

# Simple function to generate a blockchain hash
def generate_block_hash(user_id, score, prev_hash="0"):
    block_data = f"{user_id}-{score}-{prev_hash}-{time.time()}"
    return hashlib.sha256(block_data.encode()).hexdigest()

# Ensure a dummy match exists for the user
def ensure_match(user_id):
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor()
    cur.execute("SELECT id FROM matches WHERE host_user_id=%s", (user_id,))
    result = cur.fetchone()
    if result:
        match_id = result[0]
    else:
        cur.execute(
            "INSERT INTO matches (host_user_id, status) VALUES (%s,'finished')",
            (user_id,)
        )
        match_id = cur.lastrowid
    cur.close()
    conn.close()
    return match_id

# Submit a score for a user
def submit_score(user_id, score):
    match_id = ensure_match(user_id)  # create/get dummy match

    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor()

    # Update leaderboard
    cur.execute("SELECT wins FROM leaderboard WHERE user_id=%s", (user_id,))
    result = cur.fetchone()
    if result:
        cur.execute(
            "UPDATE leaderboard SET wins=wins+1, rating=rating+10 WHERE user_id=%s",
            (user_id,)
        )
    else:
        cur.execute(
            "INSERT INTO leaderboard (user_id, wins, rating) VALUES (%s,1,1200)",
            (user_id,)
        )

    # Get last blockchain hash
    cur.execute("SELECT tx_hash FROM blockchain_records ORDER BY id DESC LIMIT 1")
    last = cur.fetchone()
    prev_hash = last[0] if last else "0"

    # Insert blockchain record
    tx_hash = generate_block_hash(user_id, score, prev_hash)
    cur.execute(
        "INSERT INTO blockchain_records (match_id, tx_hash, data_hash) VALUES (%s,%s,%s)",
        (match_id, tx_hash, f"score:{score}")
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Score submitted for user {user_id}, tx_hash: {tx_hash}")

    # Trigger WebSocket broadcast
    try:
        requests.post(WS_BROADCAST_URL)
    except Exception as e:
        print("Failed to broadcast:", e)

# Simulate multiple players submitting scores
def simulate_players(num_players=3):
    for i in range(1, num_players + 1):
        score = random.randint(1, 100)
        submit_score(i, score)
        time.sleep(0.5)  # small delay

if __name__ == "__main__":
    simulate_players(3)
