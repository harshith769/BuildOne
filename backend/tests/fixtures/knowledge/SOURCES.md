# Knowledge fixtures: provenance

Public official documents only, trimmed to the spike S1 gold windows ([S1 report](../../../../docs/spikes/S1-parsing.md)). Rebuilt by `build.py` from the local S1 corpus. Used by the parser regression tests and the CI retrieval gate (`make eval-retrieval`).

| File | Title | Issuing authority | Official URL | Date | Pages kept (of the original) |
|---|---|---|---|---|---|
| `cbdt_tds_notification.pdf` | CBDT Notification 121/2026, G.S.R. 830(E) (Income-tax (Fifth Amendment) Rules, 2026) | Central Board of Direct Taxes | https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-09/Notification-no-121-2026.pdf | 2026-09-22 | pp. 1-4 |
| `cgst_act_2017.pdf` | Central Goods and Services Tax Act, 2017 | Central Board of Indirect Taxes and Customs | https://cbic-gst.gov.in/pdf/CGST-Act-Updated-31082021.pdf | 2017-04-12 | pp. 18-32 |
| `cgst_rules_2017_part_a.pdf` | Central Goods and Services Tax Rules, 2017 | Central Board of Indirect Taxes and Customs | https://cbic-gst.gov.in/pdf/24092021-CGST-Rules-2017-Part-A-Rules.pdf | 2017-06-19 | pp. 4-18 |
| `cgst_rules_2017_part_b_forms.pdf` | Central Goods and Services Tax Rules, 2017, Part B (Forms) | Central Board of Indirect Taxes and Customs | https://cbic-gst.gov.in/pdf/24092021-CGST-Rules-2017-Part-B-Forms.pdf | 2017-06-19 | pp. 18-32 |
| `code_on_social_security_2020.pdf` | Code on Social Security, 2020 | Ministry of Law and Justice / Gazette of India | https://egazette.gov.in/WriteReadData/2020/222111.pdf | 2020-09-29 | pp. 22-36 |
| `companies_accounts_rules_2014.pdf` | Companies (Accounts) Rules, 2014 | Ministry of Corporate Affairs | https://www.mca.gov.in/ | 2014-03-31 | pp. 1-24 |
| `companies_act_2013.pdf` | Companies Act, 2013 | Ministry of Corporate Affairs | https://www.indiacode.nic.in/handle/123456789/2114 | 2013-08-30 | pp. 24-38 |
| `companies_amendment_gazette.pdf` | MCA Notification G.S.R. 300(E), 21 Apr 2026 (Companies (Registration Offices and Fees) Amendment Rules, 2026) | Ministry of Corporate Affairs / Gazette of India | https://egazette.gov.in/ | 2026-04-21 | pp. 1-2 |
| `companies_incorporation_rules_2014.pdf` | Companies (Incorporation) Rules, 2014 | Ministry of Corporate Affairs | https://www.mca.gov.in/ | 2014-03-31 | pp. 1-15 |
| `dpiit_startup_notification_2019.pdf` | DPIIT Notification G.S.R. 127(E), 19 Feb 2019 (startup definition) | Department for Promotion of Industry and Internal Trade | https://www.startupindia.gov.in/ | 2019-02-19 | pp. 6-10 |
| `epf_scheme_2026.pdf` | Employees' Provident Funds Scheme, 2026 | Ministry of Labour and Employment / Gazette of India | https://egazette.gov.in/ | 2026-06-29 | pp. 66-80 |
| `esic_circular.pdf` | ESIC Circular N-15011/4/2021-P&D, 28 Sep 2026 (Code coverage in 25 Madhya Pradesh districts) | Employees' State Insurance Corporation | https://esic.gov.in/ | 2026-09-28 | pp. 1-2 |
| `income_tax_act_2025.pdf` | Income-tax Act, 2025 | Ministry of Law and Justice / Gazette of India | https://egazette.gov.in/ | 2025-08-21 | pp. 396-419 |
| `mca_general_circular.pdf` | MCA General Circular No. 04/2026 (CCFS-2026 extension) | Ministry of Corporate Affairs | https://www.mca.gov.in/ | 2026-08-31 | pp. 1-1 Signature image redacted. |
| `ts_government_order.pdf` | Telangana G.O.Ms.No. 54, LET&F (Lab) Department, 3 Aug 2016 (Shops Rules amendments and fees) | Government of Telangana, LET&F Department | https://labour.telangana.gov.in/content/gos/2016LETF_MS54.PDF | 2016-08-03 | pp. 1-2 |
| `ts_professional_tax_act_1987.zip` | Telangana Tax on Professions, Trades, Callings and Employments Act, 1987 | Government of Telangana, Commercial Taxes Department | https://www.tgct.gov.in/tgportal/AllActs/APPT/APPTAct.aspx | 1987-01-01 | whole |
| `ts_shops_establishments_act_1988.htm` | Telangana Shops and Establishments Act, 1988 | Government of Telangana, Labour Department | https://labour.telangana.gov.in/content/ActsRules/TELANGANASHOPSANDESTABLISHMENTSACT1988.htm | 1988-01-01 | whole |
| `ocr_companies_act_p24.pdf` | Companies Act, 2013, p. 24 rasterised at 300 dpi (no text layer) | Ministry of Corporate Affairs | https://www.indiacode.nic.in/handle/123456789/2114 | 2013-08-30 | p. 24 |
| `ocr_epf_scheme_p66.pdf` | Employees' Provident Funds Scheme, 2026, p. 66 rasterised at 300 dpi (no text layer) | Ministry of Labour and Employment / Gazette of India | https://egazette.gov.in/ | 2026-06-29 | p. 66 |

**Excluded** (personal names or signatures; AGENTS.md rule 16):
- `ts_shops_holidays_2021_scan`: phone scan with signatures and stamps.
- `ts_shops_registration_memo_2019_scan`: scan with a signature.
- `epfo_circular`: scan with a signature.
- `cbdt_circular`: image page with signatures.

Printed names of signing officers in born-digital Gazette notifications and circulars are kept as published; signature images are redacted.
