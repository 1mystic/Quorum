"""
Efron and Morris (1975), the eighteen batters. The textbook shrinkage fixture.

Bradley Efron and Carl Morris, "Data Analysis Using Stein's Estimator and its
Generalizations", JASA 70:311 (1975), and the same table in their 1977
Scientific American article. Eighteen major league players who each had exactly
45 at-bats early in the 1970 season; `HITS` is that first-45 count and `SEASON`
is the batting average each player finished the remainder of the season on,
which stands in for the truth the early estimate was trying to hit.

PROVENANCE, STATED PLAINLY. This table is reconstructed from training knowledge,
not transcribed from a vendored file the way `lung`, `rossi`, `nile`, `heart`,
`mgus2` and `karate` in this directory were: there is no network access in this
environment and no CSV to vendor. It is here on that footing and can be swapped
for a proper CSV without touching a test, since every assertion reads these two
tuples and nothing else.

Because it is reconstructed, three PUBLISHED aggregates are asserted against it
in test_bayes.py before it is used for anything, and they are strong checks: a
transcription error in any single row moves at least one of them.

  * the grand mean of the first-45 rates is .265, and the mean of the season
    averages is also about .265;
  * the total squared error of the raw rates against the season averages is
    .0755;
  * the total squared error of the James-Stein estimates is .0214, which is the
    published factor of about 3.5 better that made this dataset famous.

The James-Stein figure is not an accident of our arithmetic: it is computed in
the test from the published shrinkage formula, so agreeing with .0214 on data
this small requires the whole table to be right.
"""

# (player, hits in the first 45 at-bats, remainder-of-season batting average)
PLAYERS = (
    ("Clemente", 18, 0.346),
    ("F Robinson", 17, 0.298),
    ("F Howard", 16, 0.276),
    ("Johnstone", 15, 0.222),
    ("Berry", 14, 0.273),
    ("Spencer", 14, 0.270),
    ("Kessinger", 13, 0.263),
    ("L Alvarado", 12, 0.210),
    ("Santo", 11, 0.269),
    ("Swoboda", 11, 0.230),
    ("Unser", 10, 0.264),
    ("Williams", 10, 0.256),
    ("Scott", 10, 0.303),
    ("Petrocelli", 10, 0.264),
    ("E Rodriguez", 10, 0.226),
    ("Campaneris", 9, 0.285),
    ("Munson", 8, 0.316),
    ("Alvis", 7, 0.200),
)

AT_BATS = 45

HITS = tuple(h for _name, h, _season in PLAYERS)
SEASON = tuple(s for _name, _h, s in PLAYERS)

# The published aggregates the fixture is checked against.
PUBLISHED_GRAND_MEAN = 0.265
PUBLISHED_TSE_RAW = 0.0755
PUBLISHED_TSE_JAMES_STEIN = 0.0214
PUBLISHED_ERROR_RATIO = 3.5
