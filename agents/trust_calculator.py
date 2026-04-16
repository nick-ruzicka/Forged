"""
Trust tier calculator — pure function, no Claude calls.
Rules per SPEC.md § TRUST TIER SYSTEM.
"""

VALID_TIERS = ("trusted", "verified", "caution", "restricted", "unverified")


def compute_trust_tier(reliability: int, safety: int, data_sensitivity: str,
                       complexity: int = 0, verified: int = 0,
                       security_tier: int = 1) -> str:
    """Return one of trusted/verified/caution/restricted/unverified."""
    try:
        r = int(reliability or 0)
        s = int(safety or 0)
        v = int(verified or 0)
        sec_tier = int(security_tier or 1)
    except (TypeError, ValueError):
        return "unverified"

    data_sensitivity = (data_sensitivity or "").lower()

    # Restricted dominates: sensitive data or high security tier means gated access
    if data_sensitivity in ("pii", "confidential") or sec_tier >= 3:
        return "restricted"

    if r >= 80 and s >= 80 and v >= 75:
        return "trusted"

    if r >= 60 and s >= 60 and v >= 50:
        return "verified"

    if r < 60 or s < 60:
        return "caution"

    return "unverified"
