# Chroma port evidence

Source baseline: upstream 2213071cce1badcea78d02d8b986d3b3542269bc. Official package SHA-256: a01b3d9909182e2b284074469d7bace6862587bfa7ffc2c8730d23aae51dfb32. All work below is offline.

## Review hold
Do not flash build 9. Independent review identified an execution-context gap; follow-up tracing confirms USB draining runs from a timer interrupt, rather than the foreground context assumed during implementation. The RX display-queue call and multiword lease publication need a concurrency-safe design before approval. Offline happy-path tests do not establish interrupt safety.

## Package selection
The package has separate main and display images for PID 536 and PID 8728. Published upstream build 8 modifies only PID 536 images. PID 8728 selects Chroma. Both display payloads are identical after their separate 64-byte model headers.

Original main header is 0x02181C75, payload length 0x551AC. Chroma main header is 0x22181C75, payload length 0x55884. Both use payload length in header word 4 shifted right eight bits. `firmware_models.py` pins the exact main-image hashes. The package builder also pins the full package hash.

## Port differences
The code mapping is nonuniform. Project stride changes from 0xFEC to 0x1000 while the accessed field offsets remain the same. Initialized-data copies are original flash 0x0805CB60 to RAM 0x20000004..0x20000650, Chroma flash 0x0805D234 to RAM 0x20000004..0x20000654. Scale masks at 0x20000004 and track colours at 0x20000058 do not move. Later globals move by four or 32 bytes; use the explicit map.

Chroma has nine direct LED-flush callers versus seven original callers. Its LED lifecycle is handled with its own complete call-site list. The Chroma RAM-project reload function is 0x08046DB8, established from the real commit call at 0x0800BD58. A fuzzy body match at 0x08047518 was a different function and was rejected after the commit-path probe failed.

## Tempo path
Up dispatch: original 0x0801271C, Chroma 0x08012930. Down dispatch: original 0x08013BD2, Chroma 0x08013DE6. Each starts with `ldrb.w r6,[sp,#0x6a]`; encoder index zero branches to the tempo path. Magnitude is `[sp,#0x6b]`.

Clock-mode getter: original 0x0802AA62, Chroma 0x0802AEA6. It reads sequencer +0x8E2. Only value one proceeds to stock tempo editing; other values return to the event loop. The stock fine path changes hundredths of BPM; the coarse path changes whole BPM. The trace probes start at dispatch, so physical scanning and real USB timing remain device checks.

USB-only raw packet enqueue: original 0x0801A49C, Chroma 0x0801A5F8. Its ring is original 0x20004F14, Chroma 0x20004F34. The real enqueue and converter preserve USB-MIDI SysEx packets, and the probe observes writes only to that ring and the stack. The consumer submits four-byte USB-MIDI packets to endpoint 0x81 (Chroma 0x0801A804..0x0801A80A). This is separate from the DIN queues. Multi-packet SysEx must reserve capacity atomically so a full ring cannot emit a partial frame.

Tick getter: original 0x0803E440, Chroma 0x0803E9A0. Tick RAM is original 0x20006218, Chroma 0x20006238. The real getter reads the sentinel in the probe. A second probe runs the actual tick initializer and incrementer: with 216 MHz core clock and frequency byte 1, SysTick reload is 215999, control is 7, and each increment adds one millisecond. Both model images pass. Do not use 0x20000010/14: those addresses contain scale data/inactivity configuration, not the tick.

## Current tests
`test_tempo_paths.py` passes both variants, directions, clock modes and stopped/playing state fixtures. `test_model_hooks.py --model original` and `--model chroma` pass the full upstream pad, name and SysEx chord-save emulator assertions. The adapter changes model constants, not assertions, and runs the real mapped firmware routines where upstream tests run them. It retains upstream hardware stubs; success is not physical-device validation.

## Limits
No new firmware is installed. Scratch RAM at 0xC01EF800..0xC01F0000 is inherited from Con; a separate public patch project reports both-model boot/workload observations covering the surrounding free region. Those observations are author-reported, not our own full-boot or physical-memory ownership proof. Physical tests are still required. No vendor firmware, derived binary dumps, or personal backups belong in Git.


## Bidirectional tempo and display
The USB byte tap is at original 0x08018B58 / Chroma 0x08018CB4, before the untouched stock raw-byte parser. DIN uses a separate caller and parser object. A strictly framed USB-only heartbeat carries a host-instance token and BPM in hundredths. A complete valid frame enables a RAM-only 3-second lease. The Live bridge sends immediate tempo-listener feedback and a one-second heartbeat. Turns are relative, token-tagged, whole-frame USB ring writes. Disconnect or timeout restores the stock encoder path. No clock-source or saved-project tempo is changed.

The normal project screen (0x080264F0 / 0x080267FC) and dedicated tempo screen (0x08026624 / 0x08026930) use separate guarded load hooks. Watchpoints prove the reused eight-byte descriptor slots are dead after their original call; native formatting renders the full Live range, including values beyond a 16-bit hundredths field. Only a synthetic stack record carries host values. Real source records, project data and unrelated UI edit fields remain unchanged in the probes.

Feedback queues an already-visible BPM page through native asynchronous queue primitives. Calling full page selectors from receive was rejected because those routines clear cached edit fields. Native queue calls are exercised from inside the real USB-drain context with an extra call frame; they schedule without synchronous rendering or UI-owner edits. Menus and note popups are not switched. Physical knob movement retains the stock tempo-page selector and its guards.

## Verification scope
The build script runs both complete upstream Con emulator suites using explicit model constants, stock path probes, tempo/parser/queue tests, both native renderer probes, feedback tests, fake-Live transport tests and an integrated firmware-to-bridge-to-display test stopped/playing. A headless browser reconstructs exactly the locally built firmware package from the official input. These tests never grant Web MIDI permissions or contact the device.

Actual Live 12 beta loading, physical USB/display timing, sequencing, settings preservation and full-boot scratch ownership remain device checks. No new firmware is installed. The public free-memory observations cited above are contextual evidence, not our own physical proof.


## Post-review evidence
The handled-event sentinel 0xFF is accepted by both stock dispatch continuations. The new test executes each original/Chroma up/down continuation with r6=0xFF until its event-loop exit; all four paths write no memory and invoke no tempo/menu callee. A second test checks both native tempo selectors call the expected clear-flags routine four times, the model tempo getter once, and the page-1 queue once.

USB execution context is NOT foreground. Exact stock call chains:
- Original vector slot 71: 0x0803D1F1; wrapper BL at 0x0803D1F4 to timer handler 0x0804259A; callback BL at 0x080426AE to 0x0804953C; USB drain BL at 0x08049602 to 0x08018B24; tapped parser call 0x08018B58.
- Chroma vector slot 71: 0x0803D751; wrapper BL at 0x0803D754 to timer handler 0x08042AFA; callback BL at 0x08042C0E to 0x08049BBC; USB drain BL at 0x08049C82 to 0x08018C80; tapped parser call 0x08018CB4.
- The wrapper passes timer handle 0x2000168C / 0x20001690. The callback selects that handle before draining USB.
- By contrast, the encoder event worker 0x08012338 / 0x0801254C is called from main application code at 0x08016954 / 0x08016B04 (and later main-loop sites). The original reset/application chain was traced during boot qualification.

These image facts invalidate the prior single-context assumption. No runtime fix has been applied. The review hold remains while the user decides on the review-driven behavioral change. The package and Live bridge are not installed.

Known display limitation: silent lease expiry does not schedule an idle repaint. A stale host BPM may remain visible until a native redraw or knob turn. Explicit disable does queue repaint. The physical checklist must cover silent loss without forcing a renderer call.
