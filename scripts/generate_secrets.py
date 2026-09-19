"""Print fresh local configuration values. Copy into .env; do not commit them."""

import secrets
from cryptography.fernet import Fernet

print("APP_PASSWORD=" + secrets.token_urlsafe(24))
print("SESSION_SECRET=" + secrets.token_urlsafe(48))
print("TOKEN_ENCRYPTION_KEY=" + Fernet.generate_key().decode())
