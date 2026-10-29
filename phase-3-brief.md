intent:
  Deliver the approved Chroma Con port with bidirectional Ableton tempo and no saved-project tempo writes.
said:
  Dedicated Tempo knob changes Live, laptop edits update the controller, and Live stays master. Preserve Con features and standalone operation.
inferred:
  Display feedback covers both native BPM screens while stopped or playing. Do not steal menus/note popups. New firmware needs separate exact-artifact approval.
evidence / current state:
  Branch feature/chroma-tempo, upstream baseline 2213071cce1badcea78d02d8b986d3b3542269bc. No firmware flash or installed Live-script overwrite. See docs/chroma-port-findings.md for mappings and offline evidence.
  Actual buffered USB caller is original 0x08018B58 / Chroma 0x08018CB4. It sees full F0/F7 framing and parser engine+0x164. DIN uses engine+0x214 and remains unhooked. A pure tap preserves original byte parsing.
  Boot hook wraps original 0x08016482 / Chroma 0x0801667E and clears reserved state only AFTER stock SDRAM initialization returns. Post-review timer-IRQ discovery requires rechecking timer-enable ordering as part of the concurrency correction.
  State uses existing Con gaps: pad+8 host BPM, pad+12 last-rendered BPM, pad+484..511 lease/framing. Pad magic bumped in all consumers. Bass scratch starts at pad+512.
  Both native renderers are covered: project screen 0 (original 0x080264F0, Chroma 0x080267FC) and dedicated tempo screen 1 (0x08026624 / 0x08026930). Their discarded descriptor slots provide eight stack bytes at renderer-SP+16 / +8, proven by access watchpoints. Synthetic records preserve real project data; the real native formatter handles full-width hundredths through 999.00 BPM.
  Changed valid feedback queues the visible BPM renderer through native queue-only primitives (0x0802546C / 0x08025494, mapped for Chroma). These do not change UI edit flags. Full page-selection helpers were rejected for RX feedback because they clear other cached edit flags. Physical knob movement still uses the normal tempo-page selector with stock menu guards.
required behavior:
  - Strict USB heartbeat F0 7D 4B 53 01 01 enabled token[3] bpm[3] F7, seven-bit little-endian groups, BPM in hundredths 2000..99900. Only full valid frames renew a 3-second lease. Fragments expire after 250 tick units; real-time MIDI can interleave. Matching explicit disable or expiry restores stock behavior.
  - Relative turns F0 7D 4B 53 01 02 token[3] flags magnitude[2] F7, magnitude 1..255. Flag bit0 down, bit1 fine. Fresh 21-bit nonzero token isolates host instances, not authentication.
  - USB-only atomic whole-frame ring publication, preserving prior interrupt mask, dropping whole turns when full. No DIN send, clock-source change or persistent tempo write.
  - Immediate Song tempo listener feedback plus one-second heartbeat. Relative changes use current Live tempo. Keep transport behavior.
likely implementation area:
  - tools/firmware_models.py and build_ksp_patch.py: exact supported hashes, explicit model mappings, expected instructions, branch/checksum/space guards.
  - tools/tempo_control.c, tempo_hooks.S, tempo_layout.h: protocol, lease, encoder hooks, display reads and queue scheduling.
  - KeyStepPro_Transport/__init__.py: transport, listener, session and relative tempo.
  - Offline tests under tools/ and tests/; build script and regenerated installer data.
out of scope:
  - Flash, app restart or installation, bootloader/USB identity changes, unrelated editor or generative features.
acceptance:
  scripts/build-firmware.sh passes both complete model Con suites, focused stock-path/hook/display tests, fake-Live tests and byte-for-byte installer/package comparison. Watchpoints cover stack-slot lifetime/source protection and queued refresh in deep USB RX context. Physical tests remain a separate gate.
assumptions:
  Supported Arturia 2.5.20 input only. Existing Con scratch ownership is inherited and cross-checked against a public author's reported free range; not a physical proof. Clock/display/USB timing and Live beta loading remain physical checks.
blocking:
  Independent review is complete and withholds flash clearance. Follow-up tracing confirms RX is a timer interrupt. A concurrency-safe state/display handoff, package-format correction and review follow-up require the user review decision before runtime changes. See docs/chroma-port-findings.md.
routing:
  Pinned Hybrid: Fable orchestrator, current Sol 6.1 high implementer, fresh Opus 5.5 high final reviewer. Manual fallback only; no optional agents. Reviewer must inspect final source/diff, especially RAM ownership, ARM register/stack preservation, MIDI framing/queue atomicity, session lifecycle and model guards. Return every actionable finding with severity and file/line, or state no findings; distinguish device-only gaps. Do not modify files or narrate progress.
