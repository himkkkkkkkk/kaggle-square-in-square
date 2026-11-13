# Vendored sqpack core

The files `__init__.py`, `ga.py`, `geometry.py`, `relax.py`, `operators.py`,
`diversity.py`, `history.py`, `records.py`, and `validate.py` are vendored
unchanged from:

- Project: https://github.com/Pdbz199/evolutionary-square-packing
- Commit: `c195727a91e8d7995c703e4b57880b3ce3877149`
- Author: Preston Rozwood
- License: MIT; see `LICENSE` in this directory.

Only the algorithmic core is included. The upstream visualization and CLI layers
are not vendored. `genetic_annealing` provides this project's adapter, certified
scoring, and CSV/JSON output.
