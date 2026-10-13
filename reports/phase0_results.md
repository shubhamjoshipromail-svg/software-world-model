## Phase 0 results

| Model | App (role) | Condition | n | Success [95% CI] | Clean success | Collateral | Irreversible | False completion | Done but unreported | Median steps | $/success | Infra errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| luna | invoiceninja (train) | clean | 67 | 87% [76%–93%] | 87% | 0% | 0% | 6% | 0% | 8 | $0.0086 | 0 |
| luna | invoiceninja (train) | flaky_network | 34 | 76% [60%–88%] | 76% | 0% | 0% | 15% | 0% | 10 | $0.0117 | 0 |
| luna | invoiceninja (train) | modal | 35 | 83% [67%–92%] | 83% | 0% | 0% | 9% | 0% | 9 | $0.0104 | 0 |
| luna | invoiceninja (train) | session_expiry | 32 | 84% [68%–93%] | 84% | 3% | 3% | 6% | 0% | 15 | $0.0117 | 0 |
| luna | dolibarr (train) | clean | 72 | 49% [37%–60%] | 44% | 6% | 0% | 18% | 6% | 20 | $0.0317 | 0 |
| luna | dolibarr (train) | modal | 35 | 51% [36%–67%] | 40% | 14% | 0% | 20% | 6% | 19 | $0.0311 | 0 |
| luna | odoo17 (held-out app) | clean | 72 | 78% [67%–86%] | 68% | 15% | 6% | 6% | 0% | 9 | $0.0117 | 0 |
| luna | odoo17 (held-out app) | modal | 36 | 75% [59%–86%] | 64% | 19% | 8% | 8% | 0% | 12 | $0.0145 | 0 |
| luna | odoo18 (held-out version) | clean | 72 | 76% [65%–85%] | 64% | 21% | 10% | 6% | 1% | 10 | $0.0123 | 0 |
| uitars | invoiceninja (train) | clean | 72 | 19% [12%–30%] | 18% | 14% | 3% | 26% | 3% | 30 | $0.0000 | 0 |
| uitars | dolibarr (train) | clean | 36 | 8% [3%–22%] | 8% | 0% | 0% | 22% | 0% | 30 | $0.0000 | 0 |
| uitars | odoo17 (held-out app) | clean | 36 | 17% [8%–32%] | 14% | 19% | 11% | 17% | 6% | 30 | $0.0000 | 0 |
| uitars | odoo18 (held-out version) | clean | 36 | 22% [12%–38%] | 19% | 31% | 8% | 22% | 6% | 30 | $0.0000 | 0 |

### Success by skill (clean)

| Model | App | bulk_mark_sent | composite_pay_oldest | count_report | create_client | create_invoice | cross_record_calc | edit_field | find_record | record_payment |
|---|---|---|---|---|---|---|---|---|---|---|
| luna | invoiceninja | 7/7 | 0/6 | 5/7 | 8/8 | 8/8 | 7/7 | 7/8 | 8/8 | 8/8 |
| luna | dolibarr | 7/8 | 0/8 | 7/8 | 6/8 | 0/8 | 5/8 | 7/8 | 2/8 | 1/8 |
| luna | odoo17 | 8/8 | 0/8 | 8/8 | 8/8 | 8/8 | 1/8 | 8/8 | 8/8 | 7/8 |
| luna | odoo18 | 8/8 | 0/8 | 8/8 | 7/8 | 7/8 | 2/8 | 7/8 | 8/8 | 8/8 |
| uitars | invoiceninja | 4/8 | 0/8 | 0/8 | 0/8 | 0/8 | 6/8 | 3/8 | 0/8 | 1/8 |
| uitars | dolibarr | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 0/4 | 3/4 | 0/4 |
| uitars | odoo17 | 1/4 | 0/4 | 1/4 | 0/4 | 0/4 | 0/4 | 1/4 | 3/4 | 0/4 |
| uitars | odoo18 | 0/4 | 0/4 | 0/4 | 1/4 | 2/4 | 0/4 | 2/4 | 3/4 | 0/4 |

### Sensitivity: harness bug on Invoice Ninja

12 Luna Invoice Ninja episodes were terminated by a harness fallback bug (progress narration wrapped as a final answer); they could not be rerun after the fix and are **excluded** above. Counting them as failures instead:

- clean: excluded 58/67 = 87% -> as-failed 58/72 = 81%
- flaky_network: excluded 26/34 = 76% -> as-failed 26/36 = 72%
- modal: excluded 29/35 = 83% -> as-failed 29/36 = 81%
- session_expiry: excluded 27/32 = 84% -> as-failed 27/36 = 75%
