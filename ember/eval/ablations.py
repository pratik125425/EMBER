"""EMBER ablations (spec §12.4): each variant changes exactly one design choice.

uniform_eps  every phenomenon uses uniform weights (drops the Ruff 2021 elasticities)
no_Q         granularity prior Q = 1 for all records
no_Mf        fuel prior M_f = 1 for all records
no_Mphi      phenomenon prior M_φ = 1 for all records
midpoint     distance to the tested range's midpoint instead of to the interval
linear       fractional deviation |x − edge| / x instead of a log ratio
"""

from __future__ import annotations

from ember import config

ABLATIONS: dict[str, dict] = {
    "uniform_eps": {"elasticity": {phen: dict(config.UNIFORM) for phen in config.ELASTICITY}},
    "no_Q": {"q_prior": dict.fromkeys(config.Q_PRIOR, 1.0)},
    "no_Mf": {"m_f": dict.fromkeys(config.M_F, 1.0)},
    "no_Mphi": {"m_phi": dict.fromkeys(config.M_PHI, 1.0)},
    "midpoint": {"distance": "midpoint_log"},
    "linear": {"distance": "interval_linear"},
}
