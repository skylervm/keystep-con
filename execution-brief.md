# KeyStep Con for Chroma with Ableton tempo control

Status: plan approved 2026-10-29; build 11 passes offline verification and independent review; exact-artifact flash approval and physical tests remain pending. Fork created. No newly developed firmware may be flashed without separate approval.

intent:
  Run Con on Chroma with bidirectional tempo control: the dedicated knob changes Live BPM and Live changes update both native BPM displays, while Live remains clock master.
said:
  Fork Con for Chroma and add the tempo setting. Use the dedicated Tempo knob and switch freely between controller and laptop. Live BPM edits must also update the KeyStep BPM display, including while stopped.
inferred:
  Preserve the existing Con feature set. Extend the existing Live transport script for tempo. Preserve standalone operation, routing, saved projects, and normal sequencing. A new firmware flash requires separate approval after review.
evidence / current state:
  - Connected unit uses USB product ID 8728, selecting the Chroma images in the official 2.5.20 package.
  - Post-install verification records stock 2.5.20 build 119, with all 158 captured global settings unchanged. Published Con build 8 leaves both Chroma images unchanged.
  - Con source is pinned to 2213071cce1badcea78d02d8b986d3b3542269bc. Its builder targets original-model image names and fixed code/RAM addresses, with expected-instruction checks.
  - The original and Chroma display-image payloads match after the model-specific header. Main firmware code and RAM locations differ. A single address offset is insufficient.
  - Related MIT-licensed keystep-mods source, pinned to 90ad455aaa39a7fab2ed9ff1e992aca997d99def, contains original/Chroma function maps and encoder hooks. These are references to validate, not proof that Con will work on this device.
  - Public repositories, forks, branches, releases, and search results checked did not reveal a public Con Chroma port. The related project offers different features.
  - Existing Live script handles MMC transport. Physical Play and Stop were observed in Live. Physical Record verification remains pending.
  - Passive captures in the tested stock configuration showed no separate Tempo-knob message. Offline probes now establish its encoder path before the external-clock gate; physical timing remains unverified.
required behavior:
  - Build Chroma-specific Con hooks with validated function addresses, RAM layout, model header, image hashes, instruction guards, checksums, and flash-space limits.
  - Preserve Con project names, drum/chord/root pads, bass generator, note lights, recording support, saved chord behavior, and startup/version display.
  - Preserve normal sequencing and the Chroma model's stock LED behavior outside Con's intentional changes.
  - Let the dedicated Tempo knob change Live BPM while stopped or playing and externally synchronized. Laptop tempo edits immediately return BPM feedback to the already-visible project or tempo screen, including while stopped. Menus and note popups retain their screen. Live remains clock master.
  - Use relative changes so the knob cannot jump Live back to a stale stored tempo. Preserve coarse/fine adjustment.
  - Keep remote-tempo messages on USB. Do not send them to DIN outputs or create clock/tempo feedback.
  - Enable remote-tempo behavior through the Live script connection. Without that connection, preserve stock knob behavior. Use a RAM-only expiring lease, explicit disable and a fresh host-instance token to reject queued turns after reconnect.
  - Preserve current transport behavior, device routing, saved projects, and global settings.
likely implementation area:
  - `tools/build_ksp_patch.py` — model selection, guarded Chroma patch sites, package verification, and tempo hook integration.
  - `tools/build_names_patch.py` — per-model names/save/display addresses and image selection.
  - `tools/pad_hooks.S`, `tools/name_hooks.S` — validated per-model firmware functions and RAM references.
  - `tools/bass_gen.c`, `tools/note_show.c` — audit for model-dependent references and assumptions.
  - New model-map and tempo-hook files under `tools/` — keep model differences explicit and independently testable.
  - Existing emulator tests and new focused tests — original-model regressions, Chroma hooks, and tempo protocol behavior.
  - `scripts/build-firmware.sh` and installer generation — produce an identifiable Chroma build and refuse unsupported stock inputs.
  - `KeyStepPro_Transport/__init__.py` in the fork — versioned Live transport/tempo bridge, derived from the existing installed script. Install only after local verification.
  - README, RUNBOOK, PLAN, license notices, and repository setup — document local building, rollback, upstream tracking, and limitations. Keep vendor firmware and personal backups out of Git.
out of scope:
  - Unrelated generative features from keystep-mods, a new editor, or a redesigned manual.
  - Bootloader changes, USB identity changes, bypassing model guards, or installing original-model firmware on Chroma.
  - Editing real music sessions, overwriting backups, or changing MIDI routing without a demonstrated requirement.
  - Flashing this newly developed firmware before the separate reviewed-build approval.
acceptance:
  A package built from the exact supported stock input modifies the Chroma images as intended, passes model/instruction/checksum/space guards, and passes emulator and Live-bridge tests. After independent review and separate flash approval, a disposable ZZ test Set demonstrates knob and laptop tempo changes while stopped and playing, with Live still master, no tempo jumps or feedback, working transport, and preserved settings. Con functions and normal sequencing also require physical-device verification; emulator success alone does not close those checks.
assumptions:
  - Target the locally backed-up official 2.5.20 package and current tested Live 12 beta first. Future vendor updates require a new compatibility pass.
  - Keep original-model builds working. Do not claim physical validation on original hardware we do not have.
  - Use the existing Con build tools and its declared Unicorn/Capstone test dependencies in an isolated environment. An ignored isolated environment contains these existing dependencies; no runtime packages were added.
  - Reuse MIT-licensed Chroma mapping work with attribution after checking it against the exact stock binaries.
blocking:
  None. Plan and Music Tools project approved 2026-10-29. Flash approval remains a later gate.
routing:
  Pinned Hybrid: Fable orchestrates, GPT-6.1 Sol at high effort implements, and a separate Opus 5.5 session at high effort reviews. The local model-router advisory selected Hybrid, Sol 6.1 high, and separate Opus 5.5 high. No automatic dispatch or provider switching. Manual fallback only: Claude-only with Opus 5.5 high implementation and a different Opus session for review. Optional parallel agents are not authorized. The route is pinned; unavailable required roles must be reported before implementation.

## Sequential delivery plan

1. **Prove the firmware paths offline.** Validate the borrowed Chroma maps, locate the dedicated Tempo event before the external-sync check, identify a USB-only send path, and establish code/RAM space. Write focused emulator probes. Stop with evidence if a safe hook cannot be established; do not substitute another knob.
2. **Port Con to Chroma.** Add explicit per-model maps and guards. Preserve original-model builds. Validate each Con hook and saved-data layout against the Chroma image. Produce a reproducible local package; do not flash it yet.
3. **Add tempo control.** Add the guarded Tempo hook and host connection protocol. Extend the Live script for relative BPM changes and coarse/fine behavior. Test stopped/playing, simultaneous laptop edits, disconnect/reconnect, invalid messages, bounds, and transport regression.
4. **Review the final build.** Run firmware and bridge checks, inspect the exact package, and obtain independent review. Include a security-focused check of package input validation, memory bounds, and MIDI parsing. Resolve findings through the required review workflow. Keep the existing stock rollback and backups available.
5. **Present the exact build for flash approval.** Provide the package, hashes, review results, known limitations, rollback instructions, and a ready-made disposable test Set. After approval, install and perform physical tests. Compare global settings before/after and remove created test data after confirmation.

Repository setup follows plan approval: fork `canadianblaken/keystep-con` into the authenticated account, retain upstream history/license, add local build/run documentation, and configure the required tracker hook. Do not publish vendor firmware or personal backup files.

## Evidence

- [Con source](https://github.com/canadianblaken/keystep-con/tree/2213071cce1badcea78d02d8b986d3b3542269bc)
- [Existing Chroma mappings](https://github.com/yonie/keystep-mods/blob/90ad455aaa39a7fab2ed9ff1e992aca997d99def/patches/generative/fw.h)
- [Related patch descriptions](https://github.com/yonie/keystep-mods/tree/90ad455aaa39a7fab2ed9ff1e992aca997d99def)
- Local installation evidence: `outputs/KeyStep Con Installation/post-install-verification.json`.
- Read-only discovery and pinned reference sources: `work/keystep-chroma-scope/`.
- Planning gate: `/Users/skyler/.ai/build-protocol.md`, Master Plan: "Do not begin Phase 1 until the master plan is approved."
