# Spike S1: Parsing official Indian legal sources

- **Date:** 2026-10-07 · **Time spent:** about 2 days (6–7 Oct 2026), including gold outlines
- **Question:** which parser (or combination) turns official Indian legal sources, including scanned notifications, into a faithful `DocumentTree` ([data-pipeline.md §4](../data-pipeline.md#4-normalisation-and-chunking)); below what OCR confidence a scan is sent to manual review ([data-pipeline.md §7](../data-pipeline.md#7-operational-rules)). Fixes the `Parser` seam ([build-plan.md §1.2](../build-plan.md)).
- **Setup:** laptop, AMD Ryzen 7 7435HS (16 threads), WSL2 with 9.7 GiB RAM. Python 3.13.15, PyMuPDF 1.28.2, Docling 2.134.0 (docling-core 2.100.0, torch 2.14.1+cpu), Tesseract 5.5.0 (`eng`, `hin`), rapidfuzz 3.14.6. Public government documents only; nothing personal. Spike code lives in `spikes/s1/` (gitignored, kept locally).

## Result in one paragraph

**Partial pass** (the plan's middle outcome). On born-digital PDFs, **PyMuPDF's text layer plus a small layout heuristic** passes: 99.4% section recall, 97.7% precision, no reading-order errors in any source, 100% table integrity, 0.07 s per page and 97 MB peak RSS. Official HTML parsed with the standard-library HTML parser also passes (99.5% recall, 100% precision). On **scans, nothing passes**. PyMuPDF + Tesseract reaches 48.7% section recall and 4.3% mean CER; only the cleanest scan (a one-page memo, 1.0% CER, 90% recall) meets the bar. So scans go to manual review, as data-pipeline §7 already plans. **Docling is rejected.** It peaked at 3.19 GB in one process and was OOM-killed under a 2 GB cap. Run one document per process, it peaked at 2.07–2.15 GB, right at the cap. It was 29× slower, and its layout model merges whole Gazette pages into one paragraph (53.4% recall on born-digital). Its one advantage was tables on scans (83% vs 0%).

## Method

### Corpus: 21 sources obtained (22 listed, 1 missing)

All are official public documents, downloaded free and kept in `spikes/s1/data/` (never committed). The window is the scored page range: 15 pages for long acts, all pages for short documents. **Type** says how the text was obtained: *born-digital* (text layer from the publisher), *scan* (no text layer), *OCR layer* (page image with the publisher's own OCR text), *HTML*.

| Key | What it is | Authority / source | Pages (window) | Type |
|---|---|---|---|---|
| companies_act_2013 | Companies Act, 2013, Chapters II–III (ss. 3–30) | MCA / India Code | 288 (24–38) | born-digital |
| companies_incorporation_rules_2014 | Companies (Incorporation) Rules, 2014 | MCA | 89 (1–15) | born-digital |
| companies_accounts_rules_2014 | Companies (Accounts) Rules, 2014, with annexed forms | MCA | 24 (1–24) | born-digital |
| mca_general_circular | General Circular 04/2026 (CCFS-2026 extension) | MCA | 1 | born-digital |
| companies_amendment_gazette | G.S.R. 300(E), 21 Apr 2026, bilingual Gazette | MCA / Gazette of India | 2 | born-digital, bilingual |
| cgst_act_2017 | CGST Act, 2017 (updated to 31 Aug 2021), Chapters I–IV | CBIC, [PDF](https://cbic-gst.gov.in/pdf/CGST-Act-Updated-31082021.pdf) | 236 (18–32) | born-digital |
| cgst_rules_2017_part_a | CGST Rules, 2017, Part A, rules 1–16 | CBIC, [PDF](https://cbic-gst.gov.in/pdf/24092021-CGST-Rules-2017-Part-A-Rules.pdf) | 172 (4–18) | born-digital |
| cgst_rules_2017_part_b_forms | CGST Rules, Part B, forms GST REG-01 to REG-03 | CBIC, [PDF](https://cbic-gst.gov.in/pdf/24092021-CGST-Rules-2017-Part-B-Forms.pdf) | 455 (18–32) | born-digital |
| income_tax_act_2025 | Income-tax Act, 2025 as enacted (Act 30 of 2025): ss. 392–394 (TDS/TCS) | Gazette of India | 572 (396–419) | born-digital |
| cbdt_tds_notification | Notification 121/2026, G.S.R. 830(E): Income-tax (Fifth Amendment) Rules, 2026 | CBDT, [PDF](https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-09/Notification-no-121-2026.pdf) | 4 | born-digital |
| cbdt_circular | Circular 2/2026, F. No. 275/10/2026-IT(B) (under the 1961 Act: FY 2025-26 transitional matter) | CBDT | 1 | OCR layer |
| epf_scheme_2026 | EPF Scheme, 2026, G.S.R. 525(E), 29 Jun 2026 | MoLE / Gazette of India | 129 (66–80) | born-digital, bilingual |
| code_on_social_security_2020 | Code on Social Security, 2020 (No. 36 of 2020) as enacted, ss. 13–41 | Gazette of India, [PDF](https://egazette.gov.in/WriteReadData/2020/222111.pdf) | 116 (22–36) | born-digital |
| esic_circular | ESIC circular N-15011/4/2021-P&D, 28 Sep 2026 (Code coverage in 25 MP districts) | ESIC | 2 | born-digital, bilingual |
| epfo_circular | EPFO circular INV-11/2/2021-INV, 3 Jun 2022 (interest rate 2021-22) | EPFO | 2 | **scan**, bilingual |
| ts_shops_establishments_act_1988 | Telangana Shops and Establishments Act, 1988, Chapters I–IV (ss. 1–19) | TS Labour Dept, [HTML](https://labour.telangana.gov.in/content/ActsRules/TELANGANASHOPSANDESTABLISHMENTSACT1988.htm) | HTML | HTML |
| ts_professional_tax_act_1987 | Telangana (AP) Tax on Professions … Act, 1987, all 37 sections | TS Commercial Taxes Dept, [HTML](https://www.tgct.gov.in/tgportal/AllActs/APPT/APPTAct.aspx) (index + 37 pages) | HTML | HTML |
| ts_government_order | G.O.Ms.No. 54, 3 Aug 2016 (TS Shops Rules amendments, fees) | TS LET&F Dept, [PDF](https://labour.telangana.gov.in/content/gos/2016LETF_MS54.PDF) | 2 | born-digital |
| dpiit_startup_notification_2019 | G.S.R. 127(E), 19 Feb 2019 (startup definition), English half | DPIIT | 10 (6–10) | born-digital, bilingual |
| ts_shops_holidays_2021_scan | Lr. No. H2/4860/2020 + three zonal holiday proceedings for 2021 (phone scan) | TS Labour Dept, [PDF](https://labour.telangana.gov.in/content/cos/CamScanner%2012-17-2020%2013.41.30.pdf) | 7 | **scan** |
| ts_shops_registration_memo_2019_scan | Memo 337, 8 Mar 2019 (registration and renewal, BRAP 2019) | TS LET&F Dept, [PDF](https://labour.telangana.gov.in/content/gos/Memo%20337%20%20dated.%2008.03.2019%20dispensing%20with%20renewals%20one%20day%20registration.pdf) | 1 | **scan** |
| cbic_central_tax_notification | A bilingual Central Tax notification | CBIC | – | **missing**: needs a hand download that was not done |

**Notes on the sources:**
- **Telangana Acts (both HTML):** India Code returned HTTP 504 on 6 and 7 Oct 2026 for both Telangana Acts and for the Code on Social Security. The Code was taken from the Gazette instead. Both Telangana Acts were taken from the departments' official HTML. Both are the 1988 / 1987 Andhra Pradesh texts as enacted, not consolidated.
- **Companies Act copy:** `companies_act_2013` is a **pre-2019 copy without s.10A**. That is fine for parsing, but it is not the current text.
- **Income-tax Act:** taken as enacted, before the Finance Act 2026 amendments.

Requirements met: at least 3 scans with no text layer (3), and at least 1 bilingual notification (5).

### Ground truth

- **What a gold outline is:** one per source, listing the ordered section, sub-section and paragraph identifiers in the window, with headings **exactly as printed**. A block with no printed heading has no heading and is scored on its identifier only (Lr./Proc. No., G.S.R. number). Tables have row counts and printed header rows; an unprinted header is recorded as `null` and the table is scored on rows only. Owner rule, 2026-10-06.
- **Owner check:** the owner cross-checked 5 outlines against OCR of the rendered pages. Companies Act, CGST Rules and EPF Scheme 2026 were confirmed. Two outlines carried descriptive headings that are not printed (DPIIT, holiday scan); these were fixed, and the same rule was applied to all outlines.
- **Typed references:** one page per scan was typed out (CER reference), plus a Hindi passage of 481 characters from the bilingual Gazette.
- **New outlines this session:** four outlines were drafted (Code on Social Security, the CBDT TDS notification, both Telangana HTML Acts). The Code's sub-section counts were checked against Tesseract OCR of the rendered main column. In every disagreement the text layer was right: Tesseract reads the italic "(1)" as "(/)" or "(J)".
- **Corrections found during scoring:** scoring exposed gold errors, and each was checked against the page image before the gold was changed. The changes are written out in `gold/build.py`:
  - CBDT circular: paragraphs 2–3 and Copy-to items 2–11 are numbered on the page.
  - G.O. 54: "A B S T R A C T" is printed above the G.O. number, and ORDER paragraphs 2–3 are numbered.
  - CGST Rules: inserted or substituted sub-rules 3(3A), 8(4A), 9(5) and 12(1A) were missing.
  - PT Act s.23: (a)/(b) belong to an Explanation list, not sub-sections.
  - ESIC: an invented "status" identifier was turned into an unscored paragraph.
  - ESIC and holiday-scan tables: invented column names were removed (no printed header).

### Parsers

All candidates run over each source's window. One adapter maps their output to lines, and one scorer reads them (`parsers.py`, `score.py`).

| Id | Candidate |
|---|---|
| a | **PyMuPDF text layer + layout heuristic.** Narrow blocks in the outer 24% of the page are margin notes (section headings) and are emitted just before the body line they sit beside, except blocks that start with a list number. Fragments on one baseline are joined left to right. Running heads and feet are dropped: text, digits ignored, that repeats in the top or bottom two lines of 3 or more window pages, keeping the real chapter heading on its first page. Footnotes are dropped: wide lower-half blocks set in less than 85% of the page's median font size. Plus the PyMuPDF table finder. |
| a0 | Baseline: PyMuPDF `get_text(sort=True)` with no heuristic. |
| b | (a), plus Tesseract at 300 dpi (`eng`, or `eng+hin` for bilingual sources) on pages with fewer than 50 text-layer characters. |
| c | Docling's default PDF pipeline (layout model + TableFormer, Tesseract CLI OCR, `eng`/`hin`); items labelled page_header/page_footer/footnote dropped. Docling's HTML backend for HTML sources. |
| h | HTML sources: stdlib `html.parser`. Block elements end a line; `<ol>` items get their rendered number. The PT Act's index page supplies each section page's printed number (the same adapter feeds Docling's HTML output). |

**Shared tree-builder rules.** The scorer applies these to every parser's lines. M5's adapter needs the same rules (see *DocumentTree mapping notes*).
- Split "14. (1) …" and "3. Registration :- (1) …" into the section and its first sub-section.
- Join a section heading that wraps onto the next line.
- A line that starts "(n)" right after "sub-rule", "section", "column" and similar continues the previous line.
- Split "Ref: 1. …" into the label and its first item.
- Strip OCR debris from line starts (stamps, underscores).
- Drop an "Arrangement of Sections" table of contents.

### Metrics (how each number is measured)

- **Section recall:** gold identifiers found at the start of a parser line, in gold order.
  - The search is limited to the pages between the neighbouring page-tagged gold entries.
  - A sub-section is never searched past the next plausible section start.
  - A plausible section start is a number within the window's section range ±1.
- **Reading-order errors:** gold identifiers present in the output but only out of order.
- **Precision (acts, rules, schemes; scored span only):** matched / (matched + unexplained structure-looking lines).
  - A structure-looking line starts with "N." or "(n)".
  - A numbered line counts only if a monotone tree builder would accept it as the current or next section, so serial numbers in tables and forms are ignored.
  - Out-of-scope sections printed on the same pages are excluded (e.g. s.391 and s.395 around ss.392–394).
- **Heading recall (reported, not gated):** gold heading found by fuzzy match (≥ 95) within two lines before to four lines after its identifier (anywhere on the page for unnumbered blocks).
- **Table integrity:** for each gold table, a detected table within ±1 page that has the gold row count (+ header row, + printed column-number row) and ≥ 50 token-set similarity to the printed header. Tables that run over several pages are scored on detection only.
- **CER:** Levenshtein distance between the normalised page-1 text and the typed reference, divided by the reference length. Order-sensitive.
- **RAM:** peak RSS from `/usr/bin/time -v` for one process running all sources. The 2 GB check runs the same command in a cgroup v2 scope with `MemoryMax=2G` and `MemorySwapMax=0` (`systemd-run --user --scope`). A 2.6 GB allocation in that scope is OOM-killed, so the cap is real. Docker is not available in this WSL distro (Docker Desktop's WSL integration is off), so this replaced `docker --memory=2g`.
- **Speed:** the parser's own wall time per source, summed and divided by pages, ×100.

## Results

### Per parser and source type (gate in brackets)

| Parser | Type (sources) | Recall micro [≥ 95%; scans ≥ 90%] | Sources ≥ recall gate | Precision micro [≥ 95%] | Sources ≥ 95% precision | Max order errors / source [≤ 1] | Tables [≥ 90%] | CER mean [≤ 2%] | Peak RSS, all sources | s / 100 pages |
|---|---|---|---|---|---|---|---|---|---|---|
| a0 PyMuPDF raw | born-digital (15) | 95.2% | 11/15 | 95.8% | 10/13 | 15 | 100% | – | 96 MB | 7 |
| **a PyMuPDF + heuristic** | **born-digital (15)** | **99.4%** | **13/15** | **97.7%** | **11/13** | **0** | **100%** | – | **97 MB** | **7** |
| a | OCR layer (1) | 93.3% | 0/1 | 100% | 1/1 | 0 | – | – | | |
| **b + Tesseract** | **scan (3)** | **48.7%** | **1/3** | 100% | 2/2 | 37 | **0%** | **4.3%** | **276 MB** | **69** on OCR pages |
| c Docling | born-digital (15) | 53.4% | 1/15 | 93.0% | 10/13 | 42 | 100% | – | **3.19 GB**; OOM at 2 GB cap | 207 |
| c Docling | scan (3) | 30.4% | 0/3 | 100% | 2/2 | 41 | 83% | 8.9% | | |
| c Docling | HTML (2) | 97.8% | 2/2 | 82.7% | 1/2 | 0 | – | – | | |
| **h stdlib HTML** | **HTML (2)** | **99.5%** | **2/2** | **100%** | **2/2** | 1 | – | – | **56 MB** | < 1 |

- **Memory under the 2 GB cap:**
  - (a), (b) and (h) ran within the cap unchanged (97 MB, 276 MB and 56 MB).
  - Docling over all sources in one process was **OOM-killed** after 49 s, on the 4th source.
  - Run as one process per document, Docling peaked at **1.15 GB** for a 1-page circular, **2.15 GB** for CGST Rules (15 pages) and **2.07 GB** for Accounts Rules (24 pages). Those runs finished only because the kernel reclaimed page cache at the limit.
  - **Budget it is measured against:** [ADR-0012](../adr/0012-hosting-after-student-pack-change.md) gives the server ~900 MiB for API + worker. Ingestion runs on the laptop ([data-pipeline.md §2](../data-pipeline.md#2-where-it-runs)), but a parser that needs the whole 2 GB still rules out any server-side fallback.
- **Speed:** (a) 12.9 s for 180 pages. Tesseract adds 0.69 s per OCR page. Docling took 376 s for 182 pages (6 min 48 s with model loading), using all 16 threads.

### Per source

Each parser cell shows recall / precision / order errors. Precision only exists for acts, rules and schemes. (b) equals (a) on every born-digital page (no OCR is triggered).

| Source | Type | Scored entries | (a) PyMuPDF + heuristic | (b) + Tesseract | (c) Docling | HTML parser | Tables (a)/(b)/(c) | CER (b)/(c) |
|---|---|---|---|---|---|---|---|---|
| cbdt_tds_notification | born digital | 10 | 100% / – / 0 | 100% / – / 0 | 70% / – / 2 | – | 100%/100%/100% | – |
| cgst_act_2017 | born digital | 66 | 100% / 99% / 0 | 100% / 99% / 0 | 70% / 78% / 11 | – | – | – |
| cgst_rules_2017_part_a | born digital | 75 | 100% / **94.9%** / 0 | 100% / 94.9% / 0 | 33% / 68% / 34 | – | 100%/100%/100% | – |
| cgst_rules_2017_part_b_forms | born digital | 11 | **91%** / – / 0 | 91% / – / 0 | 91% / – / 0 | – | – | – |
| code_on_social_security_2020 | born digital | 131 | 100% / 100% / 0 | 100% / 100% / 0 | 16% / 100% / 40 | – | – | – |
| companies_accounts_rules_2014 | born digital | 46 | 100% / **74%** / 0 | 100% / 74% / 0 | 50% / 72% / 23 | – | – | – |
| companies_act_2013 | born digital | 132 | 100% / 100% / 0 | 100% / 100% / 0 | 100% / 100% / 0 | – | – | – |
| companies_amendment_gazette | born digital | 10 | 100% / 100% / 0 | 100% / 100% / 0 | 60% / 100% / 0 | – | 100%/100%/100% | – |
| companies_incorporation_rules_2014 | born digital | 134 | 100% / 100% / 0 | 100% / 100% / 0 | 41% / 100% / 39 | – | – | – |
| dpiit_startup_notification_2019 | born digital | 82 | 99% / 100% / 0 | 99% / 100% / 0 | 50% / 100% / 21 | – | – | – |
| epf_scheme_2026 | born digital | 145 | 100% / 100% / 0 | 100% / 100% / 0 | 57% / 99% / 42 | – | 100%/100%/100% | – |
| esic_circular | born digital | 6 | **50%** / 100% / 0 | 50% / 100% / 0 | 67% / 100% / 0 | – | 100%/100%/100% | – |
| income_tax_act_2025 | born digital | 29 | 100% / 100% / 0 | 100% / 100% / 0 | 90% / 100% / 1 | – | 100%/100%/100% | – |
| mca_general_circular | born digital | 7 | 100% / 100% / 0 | 100% / 100% / 0 | 29% / 100% / 0 | – | – | – |
| ts_government_order | born digital | 20 | 100% / 100% / 0 | 100% / 100% / 0 | 10% / 100% / 8 | – | – | – |
| cbdt_circular | OCR layer | 15 | 93% / 100% / 0 | 93% / 100% / 0 | 13% / 100% / 0 | – | – | – |
| ts_professional_tax_act_1987 | HTML | 103 | – | – | 96% / 73% / 0 | 99% / 100% / 1 | – | – |
| ts_shops_establishments_act_1988 | HTML | 83 | – | – | 100% / 99% / 0 | 100% / 100% / 0 | – | – |
| epfo_circular | scan | 25 | 0% | 36% / 100% / 0 | 12% / 100% / 0 | – | – | 3.8% / 10.2% |
| ts_shops_holidays_2021_scan | scan | 80 | 0% | 48% / – / 37 | 32% / – / 41 | – | 0%/0%/83% | 8.0% / 13.2% |
| ts_shops_registration_memo_2019_scan | scan | 10 | 0% | 90% / 100% / 0 | 60% / 100% / 0 | – | – | 1.0% / 3.4% |

**Where (a) misses the per-source bar** (the aggregate passes):
- **Accounts Rules (precision 74%):** the window includes annexed forms (AOC-1, balance-sheet schedules), whose numbered rows look like rules and sub-rules.
- **CGST Rules (94.9%):** CBIC's long amendment footnotes reprint superseded sub-rules in body-size type ("(2) Vide Notf. no. 94/2020 …"). One table row of column numbers also counts.
- **Part B forms (91%):** one block title ("Verification (by authorised signatory)") is printed inside a form table cell.
- **ESIC (50%):** the Hindi text layer has broken Unicode mapping ("परप" for परिपत्र), so the Hindi identifiers can't match. The English parts are intact.

**Why Docling scores low:** on Gazette and CBIC pages its layout model returns one text item per page or per long run. Page 23 of the Code on Social Security came back as a single 3,176-character item. So sub-sections never start a line, and margin-note headings land at the top of the page. This is Docling's own output, not the adapter: list markers are kept, and the HTML numbering issue below was fixed for Docling too. On the PT Act HTML it loses the section titles, because they sit in a layout `<table>` that it emits as a TableItem (heading recall 8%).

### OCR confidence vs correctness (sets the review threshold)

**Lines.** On the three typed reference pages, each Tesseract line (pymupdf_ocr) was aligned to the reference and counted correct when its own CER is ≤ 2% (`ocr_conf.py`). Of 101 lines, 80 were correct (mean word confidence 94.4) and 21 wrong (mean 83.5).

| Line flagged when mean word confidence < | 85 | 88 | 90 | 92 | 94 |
|---|---|---|---|---|---|
| Wrong lines caught (of 21) | 9 | 11 | 14 | 17 | 21 |
| Correct lines flagged (of 80) | 2 | 4 | 8 | 12 | 22 |

**Pages.** Mean word confidence vs CER:

| Page | Mean confidence | CER |
|---|---|---|
| Memo p.1 | 93.8 | 1.0% |
| EPFO p.1 | 90.9 | 3.8% |
| Holiday p.1 | 90.7 | 8.0% |
| Holiday pp.2–7 | 80.1–87.6 | not typed |

### Hindi and bilingual (reported, not gated)

| Measure | Value |
|---|---|
| Hindi CER, Gazette text layer (G.S.R. 300(E), 481-character passage) | 11.2%: legacy font encoding gives wrong glyphs ("सा.का.जन." for सा.का.नि., "िारा" for धारा) |
| Hindi CER, Tesseract `hin` on the same region | 2.3%, but **digits are misread**: "2013" → "2043", "18" → "48", "(1)" → "()" |
| English CER on a bilingual scan (EPFO p.1, English lines only) | **3.7% with `eng+hin`** vs 11.7% with `eng` alone (Devanagari lines become Latin garbage) |

### Worked examples

1. **Best: Code on Social Security, ss. 13–41 (131 entries).** Headings are margin notes that alternate between the left and right margins.
   - The raw text layer glues them before the number ("Entrustment 13. Notwithstanding…") and scores 75% with 15 order errors.
   - With the margin-note rule, (a) scores 100% recall, 100% precision, 0 order errors and 94% heading recall. It misses 2 of 31 headings (ss. 19 and 20), whose margin notes are interrupted by marginal Act citations ("31 of 2016.", "2 of 1912.") and so get split.
2. **Typical: CGST Rules Part A, rules 1–16 (75 entries).** (a) finds every rule and sub-rule, including the inserted 3(3A), 8(4A) and 12(1A).
   - Precision is 94.9%. Four extra lines remain:
     - the rate table's column-number row;
     - a body-size amendment footnote ("(2) Vide Notf. no. 94/2020 …"), which is taken as rule 9(2) and so pushes the real 9(2) into the extra count;
     - two superseded versions of rule 11's sub-rules, reprinted in footnotes that survive the font-size filter.
   - The rule-7 rate table is intact (4 rows plus header plus column-number row) in (a) and Docling.
3. **Worst: TS holiday proceedings, phone scan, 7 pages (80 entries).**
   - Tesseract text is readable (page-1 CER 8.0%, mostly the two-column From/To block read across).
   - Stamps and handwriting leave debris at line starts ("~ Sub:«", "__Proc No. B/982/'2020") and break identifiers. Recall is 48% with 37 order errors.
   - (b) finds no tables on OCR pages. Docling's table model found 5 of the 6 holiday tables, but its text was worse (CER 13.2%).

## Decision

| Source type | Parser | Why |
|---|---|---|
| Born-digital PDF (text layer) | **PyMuPDF text layer + the layout heuristic (a)**, PyMuPDF table finder | Passes the gate in aggregate. Fastest. 97 MB. No ML models. |
| Page without a text layer (< 50 characters) | **Tesseract 5 at 300 dpi** through PyMuPDF rendering. `eng`, or `eng+hin` when the source is bilingual | Only practical OCR within the RAM budget. Fails the scan gate, so every OCR'd page goes through the review rule below. |
| Image page with the publisher's OCR text layer (e.g. CBDT circular) | The existing text layer, **treated as a scan for review** | 93% recall, but the layer has its own errors ("IT (8)" for "IT (B)", "lndia"). |
| Official HTML | **stdlib `html.parser`** with list numbering | 99.5% recall, 100% precision. Prefer HTML when India Code's PDF is unavailable; record that the text may be unconsolidated. |
| Docling | **Not used** | Over the RAM budget, 29× slower, and it merges Gazette pages into single paragraphs. Revisit only for scanned tables (Follow-ups). |

**OCR review threshold:** a page is sent to manual review before activation when its **mean Tesseract word confidence is below 93**.
- **On the reference pages:** it flags the two pages with CER > 2% (90.9 and 90.7) and passes the memo (93.8, 1.0%).
- **Inside a page that passes:** lines with mean confidence below **90** are marked low-confidence in the ingestion report. On the reference pages, that catches 14 of 21 wrong lines and flags 8 of 80 correct ones.
- **Review load:** 9 of the 10 scanned pages in this corpus (all of the holiday scan and the EPFO circular). That is about 5% of the 182 window pages, so in practice almost every scan is reviewed by hand.
- **Caution:** the threshold is fitted on only 3 typed pages; re-check it when M5 ingests more scans.
- **Hindi:** `hin` OCR is never trusted for numbers.
- **Bilingual pages:** citations use the English text. Hindi Gazette text layers use a legacy font encoding and are not indexed.

**Outcome against the plan: Partial.** Born-digital passes, scans don't, and scans are routed to manual review per data-pipeline §7.

### `DocumentTree` mapping notes for M5

These rules come from the scorer's shared tree-builder rules and the heuristic's failure cases:
1. **Margin notes are section headings.** Attach a narrow block in the outer margin to the section whose first line it sits beside (Gazette Acts, the Code, the Income-tax Act, DPIIT side-headings). Never treat a margin block that starts with a list number as a heading.
2. **Split inline units.** "14. (1) …", "3. Registration of establishments :- (1) …" and "12. Exemption … . - (1) …" each carry a section and its first sub-section. Join a heading that wraps onto the next line before splitting.
3. **Continuations.** A line starting "(n)" right after "sub-rule", "sub-section", "section", "clause", "column" or "rule" is a wrapped cross-reference, not a new unit.
4. **Monotone numbering.** Accept a numbered line as a section only if its number is the current or next one (allowing inserted "10A"). This rejects table serials ("1. Commission or brokerage" inside s.393) and form rows.
5. **Annexures and forms.** Start a separate node at "FORM …", "Annexure" or "Schedule" headings, so their numbered rows never become rules (Accounts Rules precision).
6. **Drop:** running heads and feet (keep the real chapter heading on its first page), small-type footnotes, and "Arrangement of Sections". Keep CBIC amendment footnotes as notes on the section (they carry amendment history), never as structure.
7. **Identifiers vary in print:** "CHAPTER - I", "CHAPTER-IV", "5-A:", "18-A:", "[(3A)", "Part –A", "A B S T R A C T". Normalise before building `path` (e.g. `Act > CHAPTER III > 15 > (1)`).
8. **HTML:** `<ol type=1>` items are sub-sections (the rendered numbers); a site index can be the only place a section number is printed (PT Act). Layout tables are containers, not data tables.
9. **Bilingual Gazettes:** take the English half. Use the text layer for English. Hindi text layers are not trustworthy (legacy encoding, or broken ToUnicode as in the ESIC circular).
10. **Scans:** strip line-start debris (stamps, underscores). Table extraction on OCR pages is not solved; keep the OCR text and mark the page for review.

## Reproduce

```bash
cd spikes/s1
uv sync                                                   # CPU torch index pinned in pyproject.toml
uv run python fetch.py                                    # 21/22 present; HTML sources saved by hand (sources.yaml notes)
uv run python gold/build.py                               # gold outlines from drafts + recorded corrections
for p in pymupdf_raw pymupdf pymupdf_ocr html docling; do /usr/bin/time -v uv run python parsers.py $p; done
uv run python score.py pymupdf_raw pymupdf pymupdf_ocr html docling   # results/<parser>.json, results/summary.md
uv run python aggregate.py                                # results/aggregate.md
uv run python ocr_conf.py                                 # results/ocr_conf.json (threshold sweep)
uv run python hindi.py                                    # results/hindi.json
systemd-run --user --scope -p MemoryMax=2G -p MemorySwapMax=0 /usr/bin/time -v uv run python parsers.py docling   # 2 GB cap
uv run python trace.py <parser> <key>                     # per-entry match trace for any source
```

## Follow-ups

- **Doc updates in this change:**
  - [tech-stack.md §3](../tech-stack.md#3-open-decisions-resolved-by-spikes): parser decided.
  - [data-pipeline.md §1](../data-pipeline.md#1-stages) and [§7](../data-pipeline.md#7-operational-rules): parser per source type, and the review threshold.
  - [status.md](../status.md): D-8 parser part.
- **Before M5:**
  - **Scanned tables:** a table extractor for OCR pages. Options are Tesseract layout analysis, or Docling's TableFormer on one cropped table at a time on the laptop, if its RAM fits per table.
  - **CBIC notification:** fetch the missing bilingual Central Tax notification by hand, and rerun `score.py` on it.
- **M5:** implement the mapping notes above in the `Parser` adapter, with the 21 gold outlines as its regression tests (public data, no personal data). Re-fit the 93 / 90 confidence values once more scans are typed.
- **Content:**
  - The Companies Act copy predates s.10A. Use a current consolidated text for ingestion.
  - The Telangana Acts are unconsolidated AP texts. Track that in `knowledge/sources.yaml` until a consolidated official copy is available.
  - The EPFO circular in the corpus applies the EPF Scheme 1952. It is in the corpus for parsing only; see status.md "Before M6" on the 2026 Scheme.
