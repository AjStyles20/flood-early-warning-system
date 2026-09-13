"""
risk_engine.py
===============

The decision-support layer. Converts a raw sensor reading (and, optionally,
a machine-learning risk probability) into one of four categorical risk
levels, each with a pre-written, safety-reviewed message.

Design principle (see Chapter 2, Section 2.2.5 and the NOAH AI review
discussed with the supervisor): this module NEVER issues an autonomous
command such as "evacuate now." It issues *preparedness recommendations*
and, at the top level, tells human responders to verify and activate
official procedures. The distinction matters both academically and
ethically: a false positive here should never trigger an unsupervised
evacuation order.
"""

from dataclasses import dataclass


@dataclass
class RiskAssessment:
    risk_level: str          # "Low" | "Moderate" | "High" | "Severe"
    ratio: float              # water_level / danger_level, for transparency
    ml_probability: float     # model-estimated probability of exceedance (0-1), if available
    message: str               # safe, plain-language preparedness message
    color: str                 # hex color for the GIS dashboard marker
    should_alert: bool         # whether this reading warrants a notification


# Thresholds are expressed as a fraction of each station's own danger level,
# so the same logic works regardless of the station's absolute baseline —
# this is part of what makes the architecture portable across deployment
# contexts (Section 1.5 / Section 2.4), since a new country's stations just
# need their own danger_level calibrated locally, not new threshold logic.
_THRESHOLDS = {
    "Low": 0.0,
    "Moderate": 0.5,
    "High": 0.75,
    "Severe": 1.0,
}

_MESSAGES = {
    "Low": "No immediate flood risk detected. Continue normal monitoring.",
    "Moderate": (
        "Heavy rainfall or a rising water level has been detected. Monitor official "
        "advisories and prepare household emergency items."
    ),
    "High": (
        "High flood-risk conditions detected. Avoid waterways and low-lying routes. "
        "Move valuables and essential documents to a safer location. Follow official "
        "instructions."
    ),
    "Severe": (
        "Critical flood-risk conditions detected. Emergency agencies should verify "
        "field conditions and activate approved response procedures. Residents should "
        "follow NEMA/SEMA or local-authority guidance."
    ),
}

_COLORS = {
    "Low": "#2E7D32",       # green
    "Moderate": "#F9A825",  # amber
    "High": "#EF6C00",      # orange
    "Severe": "#C62828",    # red
}


def classify(water_level_m: float, danger_level_m: float, ml_probability: float = None) -> RiskAssessment:
    """
    Compute a risk assessment for one reading.

    ratio: how close the current water level is to the station's own danger
    threshold (>= 1.0 means at or past the danger level).

    ml_probability, if supplied by ml_model.py, is a model-estimated
    probability that this reading represents flood-risk conditions; it is
    blended in as a secondary signal (whichever of ratio/probability is
    higher decides the category), so a rising trend the raw water level
    alone hasn't yet crossed can still escalate the category early. This is
    a deliberately simple, explainable rule -- not a black-box decision --
    so it can be defended directly to a panel.
    """
    if danger_level_m <= 0:
        raise ValueError("danger_level_m must be positive")

    ratio = round(water_level_m / danger_level_m, 4)
    score = ratio
    if ml_probability is not None:
        score = max(ratio, ml_probability)

    level = "Low"
    for name, threshold in _THRESHOLDS.items():
        if score >= threshold:
            level = name

    return RiskAssessment(
        risk_level=level,
        ratio=ratio,
        ml_probability=round(ml_probability, 4) if ml_probability is not None else None,
        message=_MESSAGES[level],
        color=_COLORS[level],
        should_alert=level in ("Moderate", "High", "Severe"),
    )
