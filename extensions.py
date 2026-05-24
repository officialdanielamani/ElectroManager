"""
Shared Flask extension instances.
Import from here to avoid circular imports between app.py and blueprints.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()

# In-memory storage — no Redis required. Resets on restart, which is acceptable
# for a single-process deployment. Switch storage_uri to 'redis://...' for multi-worker.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],        # no blanket limit; only applied where explicitly declared
    storage_uri='memory://',
)
