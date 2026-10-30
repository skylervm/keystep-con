intent:
  Deliver the approved Chroma Con port with bidirectional Live tempo and a safe IRQ-to-foreground handoff.
said:
  Dedicated knob and laptop change each other while Live stays clock master. Address all review findings.
inferred:
  Cover both native BPM views stopped/playing, silent-disconnect repaint, standalone fallback and session isolation. No saved-project tempo or routing writes. Flash remains a separate exact-artifact approval.
evidence / current state:
  Branch feature/chroma-tempo, baseline upstream 2213071cce1badcea78d02d8b986d3b3542269bc. Previous review of build 9 found two medium and three low items. User approved addressing them. Current working tree builds version 2.5.99 build 11. No firmware flash or installed Live-script change.
  USB drain is timer-interrupt context. The original single-context assumption was false. See docs/chroma-port-findings.md for exact call chains and current qualification.
  Build 10 removes all RX UI calls and foreground-cache writes. RX alone publishes magic/heartbeat/inverse/session/BPM and owns framing. Foreground copies five words under a prior-PRIMASK-preserving short critical section. The plain RAM tick getter is read inside it; if the published lease is expired, foreground clears only its active marker under the same mask, preventing revival after a full tick wrap. RX cannot run during that clear. All remaining validation and UI work occur after restoring the previous mask. Foreground never initializes or clears parser/session/BPM data.
  Foreground service wraps the guarded native UI periodic call (original 0x08016976 → 0x0801F310, Chroma 0x08016B20 → 0x0801F49C). Poll runs AFTER stock returns and preserves return registers/flags. Native loop qualification covers repeated idle calls stopped/playing and both BPM/menu/popup states, with only event scan/LED I/O stubbed. Native queue consumption invokes actual renderers from main-application code. Repeated queue requests coalesce.
  Reset code proves UI pointer zero. Native UI constructor runs after SDRAM setup; RX checks that internal-RAM pointer before any external-RAM access. Boot clear saves/restores PRIMASK after stock SDRAM setup. Unmapped-SDRAM early-USB test passes; do not claim full hardware boot proof or rely on NVIC-enable timing.
required behavior:
  - Dedicated knob sends USB-only relative turns, coarse 1 BPM/fine 0.01, within Live 20..999. Current Song tempo is used. Heartbeats and immediate Song feedback carry current BPM in hundredths and a nonzero 21-bit per-instance token.
  - Strict full-frame bounds and timeout handling. Host lease is 3 seconds. No DIN sends by custom code, no saved-project writes, stock knob behavior without valid lease.
  - Poll and both renderers use coherent snapshots. Only foreground owns DRAWN_BPM/native UI calls. Silent expiry or disable queues stock BPM on visible current-project BPM screens, preserving menus/popup/preview behavior.
  - Preserve original Con features, model identities, exact supported stock hashes, guarded instructions, checksums and flash limits. Preserve info.json bytes except one exactly-checked version replacement.
likely implementation area:
  - tools/tempo_control.c, tempo_hooks.S, firmware_models.py and build_ksp_patch.py contain the correction.
  - Focused tests under tools/ and tests/ plus build script; generated installer data matches the new package.
out of scope:
  - Flash, installed-script replacement, app restart, bootloader/identity changes, new dependencies or new UI.
acceptance:
  scripts/build-firmware.sh passes both full Con model suites, stock/hook/renderer/foreground/feedback/concurrency/metadata tests, 14 bridge/integration tests and 7 installer checks. Preemption test injects real USB receive/drain at every unmasked C instruction boundary across poll/knob/both renderer paths: 520 cases, coherent snapshots, no RX UI effects, prior mask restored. Independent final-diff review must clear build 11 before presenting it for separate flash approval.
assumptions:
  Con scratch gaps remain inherited physical-ownership evidence, not a full-boot proof. Exact 2.5.20 input only. Actual Live beta loading, USB/DIN cable behavior, hardware stack/timing and sequencing remain physical checks.
blocking:
  None from user. Independent final-diff review follow-up remains required; physical installation remains separately gated.
routing:
  Pinned Hybrid and prior model-router advisory unchanged. Fable orchestrator e88029d3-efb8-4638-a763-08dfa8b6e480 approved single-writer repair. Current Sol 6.1 high implements. Independent non-author Opus 5.5 high reviewer a94e3e33-3958-4e08-ac5d-a2c79a69e711 follows up on the final diff. No optional fanout or provider switching. Return every actionable finding with severity/file/line and whether build 11 can be presented as experimental for flash approval. Do not modify files or narrate progress.

Review follow-up: original five findings cleared in Opus report NZxjFD. One new low finding (stale active marker revives after a complete 32-bit millisecond tick wrap) is corrected in build 11 by a serialized expiry-marker clear. New regression tests reproduce full-wrap non-revival and fresh-session recovery on both models, including already-masked entry. Native UI comparison now watches for any caller stack-argument reads during the complete native call and finds none. No extra hardware access or scope expansion. The user's approval to address review findings covers this follow-up correction.
