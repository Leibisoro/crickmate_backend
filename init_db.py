import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
cfg = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT") or 3306),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "autocommit": True
}

# SQL schema for all tables
sql = """
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    host_user_id INT NOT NULL,
    guest_user_id INT,
    winner_user_id INT,
    target INT DEFAULT 0,
    status ENUM('waiting','in_progress','finished') DEFAULT 'waiting',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (host_user_id) REFERENCES users(id),
    FOREIGN KEY (guest_user_id) REFERENCES users(id),
    FOREIGN KEY (winner_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS innings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT NOT NULL,
    batting_user_id INT NOT NULL,
    innings_number TINYINT NOT NULL,
    runs INT DEFAULT 0,
    wickets INT DEFAULT 0,
    overs_allowed INT DEFAULT 5,
    overs_played INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id),
    FOREIGN KEY (batting_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS moves (
    id INT AUTO_INCREMENT PRIMARY KEY,
    innings_id INT NOT NULL,
    turn_number INT NOT NULL,
    batsman_choice TINYINT NOT NULL,
    bowler_choice TINYINT NOT NULL,
    runs_scored TINYINT DEFAULT 0,
    is_wicket BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (innings_id) REFERENCES innings(id)
);

CREATE TABLE IF NOT EXISTS ai_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_like BOOLEAN DEFAULT FALSE,
    strategy JSON,
    last_trained TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS leaderboard (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    wins INT DEFAULT 0,
    losses INT DEFAULT 0,
    rating FLOAT DEFAULT 1200,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS blockchain_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id INT NOT NULL,
    tx_hash VARCHAR(255) UNIQUE,
    block_time TIMESTAMP NULL,
    data_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(6) UNIQUE NOT NULL,
    host_user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('waiting','in_progress','finished') DEFAULT 'waiting',
    FOREIGN KEY (host_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_guests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id INT NOT NULL,
    guest_user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (guest_user_id) REFERENCES users(id)
);
"""

def run():
    conn = mysql.connector.connect(**cfg)
    cur = conn.cursor()
    
    # Execute each statement
    for stmt in sql.split(";"):
        s = stmt.strip()
        if s:
            cur.execute(s + ";")
    
    # ✅ Insert mock data only in DEV mode
    if os.getenv("ENV") == "DEV":
        # Insert mock users
        cur.execute("""
            INSERT IGNORE INTO users (username, password) 
            VALUES ('Alice','pass'),('Bob','pass'),('Charlie','pass');
        """)
        # Insert mock leaderboard entries
        cur.execute("""
            INSERT IGNORE INTO leaderboard (user_id, wins, losses, rating)
            VALUES (1,5,2,1200),(2,3,4,1100),(3,6,1,1300);
        """)
        # Optional: insert mock blockchain records
        cur.execute("""
            INSERT IGNORE INTO blockchain_records (match_id, tx_hash, data_hash)
            VALUES (1,'mockhash1','datahash1'),(2,'mockhash2','datahash2');
        """)
        print("🟢 DEV mode: mock data inserted.")
    
    cur.close()
    conn.close()
    print("✅ Tables created/verified.")

if __name__ == "__main__":
    run()
