# Baseline evidence corrections — UI01 local results 0001

Applies to: `UI01_LOCAL_AGENT_RESULTS_0001.zip`  
SHA-256: `3615fa61ea603582c77e56c25def8c0f0a42650b06e747c6ea7b4e6d04c47433`  
Scope: interpretation corrections only. Package 0001 is **not** modified, rewritten, or repackaged. These notes accompany rc.5 results 0002.

## 1. Browser case dispositions (corrected wording)

| Case | Correct disposition | Evidence |
| --- | --- | --- |
| UIB01–UIB09 | PASS (scoped local measurement) | `logs/07_browser.log`, `logs/09_full_rerun.log`; `BROWSER_RESULT.json` `checks` list (9 entries) |
| **UIB10_responsive_render** | **FAIL — `MOBILE_OVERFLOW`** (not NOT_RUN) | `BROWSER_RESULT.json` `error: "MOBILE_OVERFLOW"`, `status: "FAILED"`, `browser_launched: true` |
| **UIB11_runtime_unavailable** | **NOT_RUN** — sealed suite throws at UIB10 and never reaches UIB11 | `tests/browser_smoke.cjs` ordering; no `UIB11` entry in `checks` |

Original `RESULT_SUMMARY.json` listed both UIB10 and UIB11 under `cases_not_run`. That grouping was imprecise: UIB10 executed and failed; only UIB11 was not run.

Measured at 390×844 (baseline rc.4): `document.documentElement.scrollWidth = 997` vs `innerWidth = 390` (`logs/mobile_overflow_metrics.json` in 0001).

## 2. Chromium provisioning history (enumerated from logs)

Original summary wording ("required reinstall after /tmp eviction; first successful install also exit 0") understated the count. Actual official `node …/playwright/cli.js install chromium` invocations recorded:

| # | Log | Target cache | Outcome | Used for |
| --- | --- | --- | --- | --- |
| 1 | `logs/06_chromium_provision.log` | `/tmp/skate-ui01-validation-Lu66K0/browsers` | exit 0; full download (Chrome for Testing 151.0.7922.34, headless shell, ffmpeg) | First browser run (`logs/07_browser.log`): UIB01–09 PASS, UIB10 FAIL. Workspace later lost to `/tmp` eviction. |
| 2 | `logs/09_full_rerun.log` | `/tmp/skate-ui01-validation-mSgPHi/browsers` | exit 0; full download | **Official rerun whose evidence is in 0001** (`UI01_CHECKS_RETURN.zip`, `UI01_BROWSER_RETURN.zip`). Same FAIL at UIB10. |
| 3 | `logs/10_persistent_work_screens.log` | `/root/skate-ui01/work/browsers` (persistent) | exit 0; full download | Supplemental screenshot captures and separate-copy patch diagnostic only; **not** an official `run_validation.py --mode browser` run. |

- All three were full downloads from `https://cdn.playwright.dev/builds/cft/151.0.7922.34/linux64/…`; **no cache reuse** occurred between them (each targeted an empty `PLAYWRIGHT_BROWSERS_PATH`).
- No mirror, version substitution, or system-wide install was used.
- Executable SHA-256 was identical across installs 2 and 3: `0b20b130e7edd9dd51873be867761295fe0cfad490c2b9a64f95bd3cfc08fa71` (install 1 SHA also recorded identical in `logs/06`).
- Invocation 3's cache (`/root/skate-ui01/work/browsers`) is the one **reused** for rc.5 validation (no new install needed unless preflight finds it missing).

Correct statement: **three successful official installer invocations; one official evidence-bearing browser run per /tmp task; the first run's workspace was lost before packaging; results 0001 contains the second run.**

## 3. Unresolved items (explicitly unresolved)

- **Cause of `/tmp` eviction** between agent turns on this WSL2 instance is not determined (no systemd-tmpfiles trigger or reboot was observed by the agent; `/tmp` on the root ext4 volume). Mitigation for rc.5: persistent task root `~/skate-ui01/rc5/`.
- Original log `08_screenshot_capture.log` was not produced (the step failed on the already-evicted path); no evidence was lost that was not re-measured in run 2.

## 4. What remains true from 0001

- Checks (typecheck 3 targets, 3 syntax, adapter 18/18) PASS on rc.4.
- Browser launched with pinned Chromium 151.0.7922.34 rev 1234.
- Official `desktop.png` captured; official `mobile.png` **not** produced.
- Proposed CSS patch measured `scrollWidth = 390` in a **separate working copy** — diagnostic only, not rc.4 acceptance, not rc.5 proof.
