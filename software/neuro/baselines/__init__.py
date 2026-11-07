"""Reimplementations of the published event-encryption baselines (docs/neuro/BASELINES.md).

    du2021     Du et al. 2021, 2D-SIMM position scrambling + polarity flipping (own chaotic generator)
    zhang2024  Zhang, Zhu, Lam 2024, recursive synthetic noise + Szudzik polarity mapping

Neither carries a tag; both work on whole event arrays (EVENT_DTYPE).
"""
