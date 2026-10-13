## Track 2 seed: does a latent dynamics model of software transfer?

Top-1 retrieval of the true next state among 10 candidates (chance = 10%), on transitions where the screen changed. Mean over 3 seeds (± std across seeds). *Hard* = all candidates are on the same page type, so the prediction must preserve record-specific content (K2 proxy). K1 margin = action-conditioned − identity.

| Trained on | Tested on | Mode | n | identity | mean delta | action-blind | action-conditioned | K1 margin |
|---|---|---|---|---|---|---|---|---|
| A: train InvoiceNinja+Dolibarr | same apps, unseen episodes | easy | 251 | 51% ± 1 | 52% ± 1 | 53% ± 1 | 71% ± 1 | +20 pts |
| A: train InvoiceNinja+Dolibarr | same apps, unseen episodes | hard | 51 | 6% ± 0 | 6% ± 0 | 20% ± 2 | 42% ± 1 | +37 pts |
| A: train InvoiceNinja+Dolibarr | held-out app (Odoo 17) | easy | 840 | 55% ± 1 | 55% ± 1 | 52% ± 1 | 51% ± 0 | -4 pts |
| A: train InvoiceNinja+Dolibarr | held-out app (Odoo 17) | hard | 748 | 33% ± 1 | 33% ± 1 | 33% ± 1 | 33% ± 1 | -1 pts |
| A: train InvoiceNinja+Dolibarr | held-out app (Odoo 18) | easy | 750 | 56% ± 1 | 56% ± 1 | 53% ± 1 | 52% ± 2 | -4 pts |
| A: train InvoiceNinja+Dolibarr | held-out app (Odoo 18) | hard | 688 | 37% ± 1 | 37% ± 1 | 35% ± 2 | 34% ± 1 | -3 pts |
| B: train Odoo 17 | same app, unseen episodes | easy | 167 | 55% ± 2 | 55% ± 2 | 54% ± 2 | 64% ± 2 | +9 pts |
| B: train Odoo 17 | same app, unseen episodes | hard | 142 | 23% ± 1 | 22% ± 1 | 25% ± 2 | 35% ± 2 | +12 pts |
| B: train Odoo 17 | next version (Odoo 18) | easy | 750 | 56% ± 1 | 56% ± 0 | 53% ± 1 | 65% ± 1 | +8 pts |
| B: train Odoo 17 | next version (Odoo 18) | hard | 688 | 37% ± 1 | 36% ± 1 | 35% ± 1 | 43% ± 1 | +7 pts |
| B: train Odoo 17 | other apps (IN+Dolibarr) | easy | 1216 | 44% ± 1 | 44% ± 1 | 43% ± 1 | 43% ± 1 | -1 pts |
| B: train Odoo 17 | other apps (IN+Dolibarr) | hard | 915 | 23% ± 1 | 24% ± 1 | 23% ± 1 | 24% ± 1 | +1 pts |
