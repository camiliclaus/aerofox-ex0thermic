# Data sources, provenance and licensing

## Primary: NASA Physical Sciences Informatics (PSI)

- Search API `https://psi.nasa.gov/geode-py/ws/repo/search` (Research Area = combustion science) → 24 investigations.
- Metadata `…/repo/investigations/<PSI-nn>`; file catalogs `…/files/v2`; files via presigned S3 URLs from
  `…/studies/<acc>/download`.
- Retrieved 14 Nov 2026 (runs 22:07Z and 22:11Z). **677 files, all `verified_this_run`**, listed in
  `data/raw/psi/manifest.json` with URL, SHA-256, size, PSI S3 version and time.
- Licenses: CC0-1.0 for 23 investigations; PSI-10 (ACME Flame Design) has no license field in its PSI record. AeroFox
  redistributes only its two small experiment tables, as public U.S. Government data with attribution; remove them if your
  event requires an explicit license. Attribution: "Data courtesy of NASA Physical Sciences Informatics".

| Layer | Path | In git |
|---|---|---|
| Investigation metadata, search index | `data/raw/psi/investigations`, `search_combustion.json` | yes |
| 22 experiment tables | `data/raw/psi/tables/` | yes |
| File catalogs (66,567 entries, gzipped CSV) | `data/raw/psi/catalog/` | yes |
| Curated raw files: FLEX/CFI DropletData + TestSheets, FLEX-035 LLUV/color, PSI-117 CSVs, BASS matrices, DAFT, SAME-R results | `data/raw/psi/files/` (603 files) | yes |
| Saffire I/II/III telemetry workbooks (44 MB) | `data/cache/psi/` | **no** (re-downloadable; derivatives committed) |
| Processed tables | `data/processed/` | yes |

### Catalog figures verified against the inherited audit

| Quantity | Inherited audit | This run |
|---|---|---|
| Combustion investigations | ≈24 | 24 |
| Experiment tables | 22 | 22 |
| Catalog entries before dedup | 66,567 | 66,567 |
| After dedup | ≈60,866 | 60,797 unique object keys (rule of the earlier audit undocumented) |
| Referenced volume | 13.47 TB | 13.50 TB raw; 13.47 TB after removing duplicate objects |

None of the referenced terabytes are downloaded; video/imagery stays in PSI.

## NASA Technical Reports Server (NTRS)

24 records (`data/raw/ntrs/*.json`, metadata + abstracts, committed). Full texts are cached locally
(`data/cache/ntrs`, not redistributed) because several NTRS records flag possible third-party material. Each record
states why it was included (`aerofox_reason`). Key: NASA/TP-2015-216046 (FLEX detailed results), 20170008805 (Saffire),
20210011385 (BASS-II TM), 20130000422 (SAME-2), 20250010653 (LUCI), 20240008623 (FM²), 20260002050 (exploration atmospheres).

## NASA web pages (context, not data)

Apollo 1 and Apollo 13 lessons learned (sma.nasa.gov), "25 Years Ago: Fire Aboard Space Station Mir" (nasa.gov),
A Researcher's Guide to Combustion Science (2015), GRC Combustion Science overview, and three NASA Spinoff articles
(fire detector, firefighter air tanks, fire attire). Used as short attributed quotations in
`data/curated/literature_evidence.json`. The Mir incident is cited only through NASA's own article.

## Scope decisions

- Complementary sources were limited to NASA and U.S./allied agencies, per the team brief. No JAXA/ESA/NIST datasets were
  ingested in this version (time); their inclusion is listed as future work.
- Not obtained: NASA-STD-6001 material test databases, battery thermal-runaway data, SoFIE results (not public in PSI),
  official challenge page and rules (the site could not be reached from the build environment — verify manually).

## Status labels used in the app

`measured` (PSI data re-analysed by AeroFox) · `model_of_measurements` · `published_statement / measurement / interpretation`
(NASA literature) · `incident_record` · `metadata` · `synthetic` (example inputs to the compartment model).
