# Bbo nRF54L15DK Vendor Evidence Register

## Purpose

This directory records source-controlled evidence extracted from the vendor package supplied for the Bbo nRF54L15DK research boards used by PuttTrack.

The raw vendor archive, PDFs, executables and signed firmware binaries are **not** redistributed in this public repository. They may contain third-party/vendor material and they would add unnecessary binary weight to Git history. Instead, the repository stores cryptographic hashes, source-derived facts, explicit inferences and unresolved questions so that later measurements remain traceable to the exact source package inspected.

## Source package

- Package name: `Bbo nRF54L15DK.zip`
- Received/inspected: 2026-08-18
- Size: 86,814,834 bytes
- Archive entries: 306
- Uncompressed payload reported by ZIP directory: 105,172,758 bytes
- SHA-256: `1650f1e38c9022d6a696bc9da285f141707c7fd31ea24ba1f105abd16fd74864`

See [`SOURCE_MANIFEST.md`](SOURCE_MANIFEST.md) for key-file hashes.

## Evidence documents

1. [`HARDWARE_EVIDENCE.md`](HARDWARE_EVIDENCE.md) — FACT / INFERENCE / UNKNOWN register derived from the inspected package.
2. [`CHANNEL_SOUNDING_NOTES.md`](CHANNEL_SOUNDING_NOTES.md) — Phase-0 bring-up contract for the supplied RAS Initiator/Reflector binaries and the transition to source-built PuttTrack firmware.
3. [`SOURCE_MANIFEST.md`](SOURCE_MANIFEST.md) — exact archive and key-file digests.

## Architecture status

The package strengthens the case for Bbo boards as **Phase-0 CS baseline/debug Anchors**. It does not prove production ranging accuracy, tracking rate, NLOS behavior or multi-ball scalability.

The current prototype comparison is intentionally evidence-gated:

| Platform | Intended experimental role | Status |
|---|---|---|
| Bbo nRF54L15DK | vendor-supported single-board/single-RF-feed CS baseline and debug node | source package inspected; measurement pending |
| Seeed XIAO nRF54L15 + external 2.4 GHz FPC | fixed-Anchor antenna/enclosure candidate | candidate; must beat/justify baseline by measured tails/installation value |
| Seeed XIAO nRF54L15 Sense | compact Ball-side CS + motion prototype candidate | candidate; not a production Smart Ball decision |
| Nordic nRF54L15 Tag | moving-target and dual-antenna RF reference | retained benchmark/reference |
| Custom PuttTrack Anchor/Ball PCB | production path | deferred until measurement gates define requirements |

The XIAO and Nordic entries are separate candidate/reference decisions, not claims derived from the Bbo vendor archive. Official external sources are registered in `docs/architecture/REFERENCES.md`.

## Repository policy for vendor artifacts

- Do not commit the raw 83 MiB archive or vendor `.exe`, PDFs and signed binaries by default.
- Preserve the original archive in controlled project storage outside GitHub and verify the SHA-256 before use.
- If licensing later permits selected redistribution, add only the minimum required artifact with provenance and a reason.
- Any performance number from vendor documentation remains a vendor claim until reproduced by a PuttTrack experiment.
