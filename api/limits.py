"""
lexilab — api/limits.py
Rate limit helpers and text validation.
"""

from fastapi import HTTPException

MAX_TEXT_LENGTH      = 999_999_999
MIN_TEXT_LENGTH      = 50
RATE_LIMIT_ANALYZE   = 999_999

def validate_text(text: str) -> str:
    text = text.strip()
    if len(text) < MIN_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail=f"Text too short. Minimum {MIN_TEXT_LENGTH} characters required.")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=422, detail=f"Text too long. Maximum {MAX_TEXT_LENGTH} characters allowed.")
    return text

def check_rate_limit(remaining: int):
    pass
