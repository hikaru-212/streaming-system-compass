"""Identity generation helpers.

This module centralizes ID generation so future identity policy changes
such as UUIDv7 adoption can be made in one place.
"""

from __future__ import annotations

import uuid


def generate_event_id() -> str:
    """Generate a new event identity.

    The current implementation uses UUIDv4 canonical string form.

    UUIDv7 or another time-ordered UUID strategy may be evaluated later,
    but the rest of the codebase should depend on this boundary instead
    of calling uuid.uuid4() directly.
    """
    return str(uuid.uuid4())