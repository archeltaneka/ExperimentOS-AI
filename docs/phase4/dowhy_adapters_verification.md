# Issue #105 verification record

Branch: `feature/issue-105-dowhy-adapters`, linked to issue #105 and based on the completed #104
adapter branch. No commit, manual push, PR, merge, or branch-protection change is part of this work.

Context7 resolved `/py-why/dowhy`; current release metadata selected DoWhy 0.14. Python 3.12 is
incompatible because DoWhy caps SciPy at 1.15.3 while ExperimentOS requires SciPy >=1.16.1.
An isolated Python 3.13.15 probe passed with NumPy 2.5.0, pandas 3.0.3, SciPy 1.18.0,
scikit-learn 1.9.0, statsmodels 0.15.0, and NetworkX 3.6.1.

## Verification results

| Check | Result |
| --- | --- |
| Core Python 3.12 DoWhy contract suite | 20 passed, 1 expected optional-runtime skip |
| Python 3.13.15 + DoWhy 0.14 integration suite | 21 passed; 100 upstream pandas-copy warnings |
| Full repository suite with PostgreSQL | 1,725 passed, 36 expected EconML skips, 2 warnings |
| Phase 4 statistical baseline v3.0.0 | pass; 0 blocking and 0 numerical-reference failures |
| Ruff format/check | 472 files formatted; no lint findings |
| Mypy | no issues in 123 source files |
| Lock/install consistency | 219 packages resolved; 184 installed packages compatible |

The deterministic known-confounding fixture recovers the declared ATE of 2.0 within an absolute
tolerance of 0.15 and repeats identically, including refutation evidence. Repository-owned IPW,
DML, HTE, identification, propensity, DiD, observational reliability, randomized reliability,
EconML boundary, and Phase 3 regressions are included in the full-suite result. The DoWhy linear
regression handoff is not asserted equal to IPW or DML because those estimators have different
finite-sample semantics.

The dependency group adds DoWhy 0.14 only for Python 3.13 and its lock closure; it does not change
the core Python 3.12 installation. Remaining limitations are deliberate: one ATE/backdoor path,
one linear-regression handoff, three bounded refuters, no causal discovery, no graph-truth claim,
and no interpretation of a passed refuter as proof of causal validity.
