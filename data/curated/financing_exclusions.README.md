# financing_exclusions.csv — European bank/insurer upstream oil & gas exclusion policies

Hand-curated table of **public upstream oil & gas exclusion/restriction policies** at major
European financial institutions (7 banks, 3 insurers). Feeds the ERDA financing-conditions
panel. Per spec §7: every row carries a `policy_url` that was actually accessed during
compilation; all quotes in `notes` are transcribed from those documents, not from memory.

- Compiled: **2026-07-19** (all `date_checked` values).
- Row count: **10** (7 `bank`, 3 `insurer`). Columns: 7
  (`institution,type,policy_scope,upstream_oil_excluded,policy_url,date_checked,notes`).
- `upstream_oil_excluded` semantics: `true` = full exclusion of upstream oil financing/cover;
  `partial` = exclusion limited to new/greenfield fields, dedicated transactions, pure-play
  companies, or unconventionals. **All 10 rows are `partial`** — no institution surveyed
  fully excludes all upstream oil business; treat the column as "has a binding upstream
  restriction" and read `notes` for the operative scope.

## Verification method

Each `policy_url` was downloaded (curl) or fetched and the document text extracted (pypdf)
or read (HTML) on the compilation date. Document dates/versions were read from the documents
themselves:

| Institution | Document verified | Document date/version |
|---|---|---|
| BNP Paribas | Sector Policy – Oil & Gas (PDF, 12 pp) | 10 May 2023 (version still served May 2026) |
| Société Générale | Oil & Gas Sector Policy (PDF, 13 pp) | April 2026 |
| Crédit Agricole | Group CSR Sector Policy – Oil and Gas (PDF, 5 pp) | November 2024 |
| ING | "Oil & gas industry" stance page (HTML) | undated; describes Sept 2024 policy step |
| HSBC | Sustainability Risk Policies Framework (PDF, 20 pp) | November 2025 |
| Barclays | Climate Change Statement (PDF, 12 pp) | December 2025 |
| NatWest Group | Energy Supply Sectors E&S Risk Acceptance Criteria (PDF, 5 pp) | 27 February 2026 |
| Allianz | Statement on oil and gas business models (PDF, 6 pp) | Version 2025, valid from 10 Oct 2025 |
| AXA | AXA Group Energy Policy (PDF, 7 pp) | July 2023 (gas restriction effective 1 Sep 2025) |
| Munich Re | Approach to fossil fuels in investments and (re)insurance (PDF, 2 pp) | references Climate Ambition 2030 launched Dec 2025 |

Discovery searches used the open web (bank/insurer sites, BankTrack, Reclaim Finance,
ShareAction, press coverage) but **no numbers or quotes were taken from secondary sources** —
they only pointed to the primary documents above.

## Caveats

- **BNP Paribas access**: the live PDF
  (`https://cdn-group.bnpparibas.com/uploads/file/bnpparibas_csr_sector_policy_oil_gas.pdf`)
  serves to interactive browsers but returns Akamai 403 to automated clients. `policy_url`
  therefore cites the **Wayback Machine snapshot of 2026-05-13** (HTTP 200) of that exact URL,
  whose content (10 May 2023 policy) was extracted and quoted. The May 2023 commitments were
  cross-checked against BNP's 2023-05-11 press release, accessed live in a browser:
  `https://group.bnpparibas/en/press-release/bnp-paribas-details-and-strengthens-its-energy-transition-ambitions`.
- **AXA version risk**: the July 2023 Energy Policy is the most recent policy document found
  and its restrictions phase in through 1 Sep 2025 (so it remains operative), but AXA's
  publications page was not exhaustively crawled; a later revision could exist.
- **NatWest softening**: the 27 Feb 2026 RAC reflects a 2025 review that *weakened* earlier
  criteria (transition-plan requirement removed; new-field development/production no longer
  expressly prohibited — only "exploration for new oil and gas reserves"). Press coverage of
  the change (edie, CSO Futures) was seen but not used as a source; the row quotes the RAC.
- **ING page undated**: the stance page carries no publication date; `date_checked` is the
  access date. The Sept 2024 policy step is described on the page itself.
- **Policies churn**: 2024–2026 saw frequent revisions (HSBC consolidated its Energy Policy
  into the Nov 2025 framework; Barclays reissued its statement Dec 2025; SocGen reissued
  Apr 2026). Re-verify `policy_url` liveness and version before quoting downstream.
- **Scope**: financing/underwriting policies of the group entities as stated; asset-management
  arm policies (e.g. BNP Paribas AM bond exclusions) are out of scope of this file.

## Omitted / unverified (not in the CSV)

- **Allianz direct fetch**: allianz.com is Cloudflare-gated for plain curl; the PDF was
  retrieved via the fetch tool (binary saved locally) and its text extracted — included, but
  note the access path.
- **Other candidates not included** (no policy document accessed this session, so omitted
  rather than approximated): Zurich Insurance, Swiss Re, Generali, La Banque Postale,
  Danske Bank, Lloyds, Standard Chartered, UniCredit, Santander, Deutsche Bank.
- No candidate institution was dropped for *failing* verification; the 10 rows are simply the
  institutions whose current policy documents were successfully accessed.
