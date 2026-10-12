::: {.column-body-outset .fe-static}
<div class="tbl-note">Static table (no JavaScript needed): the default view. Latest archived run (24 Feb 2026; sample from 2001); 3-month horizon; common window (forecast origins 2016-01 to 2025-09, n = 117). Relative RMSE = 100 × (model RMSE ÷ M2 RMSE − 1); negative means smaller errors than M2. DM = HLN-corrected statistic with its two-sided p-value (long-run variance with equal weights on the first h − 1 autocovariances); M0, M1 and M6 are nested with M2, so their p-values are indicative only.</div>

::: {.table-scroll .tbl-num}
| Model | RMSE vs M2 | n | RMSE | MAE | Direction hit rate | DM (HLN) | p-value |
|:--|--:|--:|--:|--:|--:|--:|--:|
| M0 no change | +6.95% | 117 | 0.535 | 0.396 | 0.13 | 1.25 | 0.21 |
| M1 AR(1) | +8.93% | 117 | 0.544 | 0.396 | 0.51 | 1.53 | 0.13 |
| M2 baseline | — | 117 | 0.500 | 0.370 | 0.56 | — | — |
| M3 slack → smoothed persistence | +2.78% | 117 | 0.514 | 0.372 | 0.62 | 0.62 | 0.53 |
| M4 slack → durable signal | +2.99% | 117 | 0.515 | 0.397 | 0.62 | 0.70 | 0.48 |
| M5 slack → rolling persistence | −4.05% | 117 | 0.480 | 0.347 | 0.62 | −0.67 | 0.50 |
| M6 M4v2 | +2.82% | 117 | 0.514 | 0.395 | 0.59 | 1.28 | 0.20 |
:::

<div class="tbl-note">Version sensitivity: M4's RMSE relative to M2 (%), by output version, horizon and comparison window; in brackets the matched origins n and the DM p-value. Own-window columns: RMSE ratio, n and p-value all on the origins where M4 and M2 overlap. The last row scores the latest run's own archived forecasts on the research-summary run's common window, which isolates the effect of the evaluation window.</div>

::: {.table-scroll .tbl-num}
| Version | 3m, own window | 3m, common window | 6m, own window | 6m, common window |
|:--|--:|--:|--:|--:|
| Latest run, 24 Feb 2026 (sample from 2001) | −1.86%<br>(232; p = 0.55) | +2.99%<br>(117; p = 0.48) | −2.01%<br>(229; p = 0.75) | +3.40%<br>(114; p = 0.71) |
| Research-summary run, 23 Feb 2026 (sample from 2005) | −3.15%<br>(184; p = 0.36) | −0.68%<br>(69; p = 0.86) | −2.64%<br>(181; p = 0.69) | −3.09%<br>(66; p = 0.70) |
| Latest inputs, trained only on observed outcomes | −2.67%<br>(230; p = 0.45) | +2.82%<br>(115; p = 0.56) | −4.91%<br>(224; p = 0.51) | +1.64%<br>(109; p = 0.89) |
| Latest run on the research-summary run's common window (from 2020-01) | — | +0.51%<br>(69; p = 0.91) | — | −4.04%<br>(66; p = 0.61) |
:::
:::
