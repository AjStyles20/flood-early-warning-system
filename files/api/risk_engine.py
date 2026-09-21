"""Explainable current-state threshold assessment for FloodWatch.

Forecast probability is retained as separate information only. It is never
combined numerically with a threshold ratio because the two quantities have
different meanings and scales.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskAssessment:
    """The complete, display-ready outcome of one risk assessment."""

    risk_level: str
    ratio: float
    ml_probability: Optional[float]
    message: str
    color: str
    should_alert: bool


# Station-specific danger levels make this rule portable: a new deployment
# supplies its locally calibrated threshold instead of changing application code.
_THRESHOLDS = {"Low": 0.0, "Moderate": 0.5, "High": 0.75, "Severe": 1.0}

# These messages are recommendations, never autonomous emergency orders. Each
# language keeps the same four-tier decision logic and preserves the boundary
# that residents should follow official guidance.
_MESSAGES = {
    "en": {
        "Low": "The current local level is below the configured threshold bands. Continue monitoring and follow official guidance.",
        "Moderate": "The current local level has entered the moderate threshold band. Continue close monitoring and follow official guidance.",
        "High": "The current local level has entered the high threshold band. Exercise caution around waterways and follow official guidance.",
        "Severe": "The current local level has reached or exceeded the configured threshold. Verify conditions and follow official guidance.",
    },
    "ha": {
        "Low": "Babu hadarin ambaliya na nan take. Ci gaba da kulawa kuma bi jagorancin hukumomi.",
        "Moderate": "Ana samun hauhawar ruwa ko yawan ruwan sama. Shirya kayan gaggawa kuma bi jagorancin hukumomi.",
        "High": "Yanayin hadarin ambaliya ya yi tsanani. Ka guje wa hanyoyin ruwa, kiyaye kayayyaki, kuma bi jagorancin hukumomi.",
        "Severe": "Yanayin hadarin ambaliya na cikin tsanani. Masu ba da agaji su tabbatar da yanayin; mazauna su bi jagorancin hukumomi.",
    },
    "fr": {
        "Low": "Aucun risque immédiat d'inondation détecté. Continuez la surveillance et suivez les consignes officielles.",
        "Moderate": "Une hausse du niveau d'eau ou de fortes pluies a été détectée. Préparez des fournitures d'urgence et suivez les consignes officielles.",
        "High": "Des conditions de risque élevé d'inondation ont été détectées. Évitez les voies d'eau, protégez les biens essentiels et suivez les consignes officielles.",
        "Severe": "Des conditions critiques d'inondation ont été détectées. Les services d'urgence doivent vérifier les conditions; les résidents doivent suivre les consignes officielles.",
    },
    "ig": {
        "Low": "Enweghị ihe egwu ide mmiri ozugbo achọpụtara. Gaa n'ihu na nlekota ma soro ntuziaka gọọmentị.",
        "Moderate": "Achọpụtala ịrị elu mmiri ma ọ bụ oke mmiri ozuzo. Kwadebe ihe mberede ma soro ntuziaka gọọmentị.",
        "High": "Achọpụtala ọnọdụ ihe egwu ide mmiri dị elu. Zere ụzọ mmiri, chekwaa ihe dị mkpa, ma soro ntuziaka gọọmentị.",
        "Severe": "Achọpụtala ọnọdụ ihe egwu ide mmiri dị oke njọ. Ndị ọrụ mberede kwesiri ịlele ọnọdụ; ndị bi ebe ahụ kwesiri iso ntuziaka gọọmentị.",
    },
    "yo": {
        "Low": "Ko si ewu iṣan omi lẹsẹkẹsẹ ti a rii. Tẹsiwaju abojuto ki o tẹle itọsọna osise.",
        "Moderate": "A ti rii omi ti n ga soke tabi ojo lile. Mura awọn ohun pajawiri ki o tẹle itọsọna osise.",
        "High": "A ti rii ipo ewu iṣan omi giga. Yago fun oju omi, daabobo awọn ohun pataki, ki o tẹle itọsọna osise.",
        "Severe": "A ti rii ipo ewu iṣan omi to ṣe pataki. Awọn oṣiṣẹ pajawiri gbọdọ jẹrisi ipo naa; awọn olugbe gbọdọ tẹle itọsọna osise.",
    },
}

_COLORS = {"Low": "#2E7D32", "Moderate": "#F9A825", "High": "#EF6C00", "Severe": "#C62828"}


def classify(
    water_level_m: float,
    danger_level_m: float,
    ml_probability: Optional[float] = None,
    language: str = "en",
) -> RiskAssessment:
    """Assess current threshold state; keep any ML probability informational.

    ml_probability is accepted for backward-compatible display only. It does
    not raise or lower the current-state tier. A future validated forecast
    policy must define its own decision semantics explicitly.
    """
    if danger_level_m <= 0:
        raise ValueError("danger_level_m must be positive")
    if ml_probability is not None and not 0.0 <= ml_probability <= 1.0:
        raise ValueError("ml_probability must be between 0 and 1")

    selected_language = (language or "en").lower()
    messages = _MESSAGES.get(selected_language, _MESSAGES["en"])

    ratio = round(water_level_m / danger_level_m, 4)
    level = max(
        (name for name, threshold in _THRESHOLDS.items() if ratio >= threshold),
        key=lambda name: _THRESHOLDS[name],
    )
    probability = round(ml_probability, 4) if ml_probability is not None else None
    return RiskAssessment(level, ratio, probability, messages[level], _COLORS[level], level != "Low")
