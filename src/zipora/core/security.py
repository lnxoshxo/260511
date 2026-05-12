"""Security-related helpers."""

from __future__ import annotations

import secrets
import string


def password_strength(password: str) -> tuple[int, str]:
    """Return a simple password strength score and label."""
    score = 0
    score += len(password) >= 10
    score += any(char.islower() for char in password)
    score += any(char.isupper() for char in password)
    score += any(char.isdigit() for char in password)
    score += any(char in string.punctuation for char in password)
    labels = {0: "极弱", 1: "弱", 2: "一般", 3: "良好", 4: "强", 5: "很强"}
    return int(score), labels[int(score)]


def generate_password(length: int = 20) -> str:
    """Generate a strong random password."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(max(12, length)))
