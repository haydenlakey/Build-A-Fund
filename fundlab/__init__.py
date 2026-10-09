"""fundlab: the maths and data layer behind Build-a-Fund Lab.

Nothing in this package imports Streamlit, so every function here can be
unit-tested and reused outside the app.
"""

PERIODS_PER_YEAR = 52  # all statistics are computed from weekly returns
