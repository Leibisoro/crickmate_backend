from passlib.context import CryptContext

# Create a password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to hash password
def get_password_hash(password: str):
    return pwd_context.hash(password)
