# Stationary beta message sequence

The active runtime changes two fields on camera bus 2. Both directions use the same outgoing message types; the receiving vehicle logic uses the genuine physical stalk signal to select the camera.

| Relative timing | ID | Example payload | Meaning in this experiment |
|---|---|---|---|
| Signal rising edge, after eligibility/neutral checks | `0x227` | `00 00 FC 00 80 00 12 40` | Captured short trailer-length field |
| At least 350 ms later | `0x443` | `80 00 10 FF FC 00 00 00` | Trailer connection bit set |
| About 1 s after the preceding length frame | `0x227` | `00 00 FC 00 80 00 12 40` | Refresh length/forwarding lease |
| About 1 s after the preceding connection frame | `0x443` | `80 00 10 FF FC 00 00 00` | Refresh connection/forwarding lease |
| Eligible cancellation/toggle OFF/eight-second timeout | `0x443` | `00 00 10 FF FC 00 00 00` | Restore fresh genuine connection baseline |
| Same cleanup cycle, after connection cleanup | `0x227` | `00 00 FC 00 80 00 FC 40` | Restore fresh genuine length baseline |

Exact timing follows controller updates. A recognized baseline variant has byte 2 of `0x443` equal to `00` instead of `10`; the runtime preserves it in activation and cleanup. It does not invent a baseline for an unknown input.

`0x12` is the encoded byte containing the seven-bit length field: the field is `0x12 >> 1 = 9`, with scaling 0.1 m, giving approximately 0.9 m / 3 ft. It is not 1.8 m. `0xFC` in that field represents NoData. This experiment uses the captured value rather than accepting arbitrary user lengths.

The two main-to-camera forwarding leases expire 1.2 seconds after their last accepted respective modified frame. Refreshing once per second maintains those leases and keeps the genuine baseline from competing on that path during the attempt. This cadence is an implementation choice; it is not proof that a Ford receiver requires exactly one-second refresh.

The Python attempt lasts at most eight seconds. Native code separately bounds rate, count and window. Signal cancellation before the connection frame was sent needs only length cleanup. Unknown/stale baselines are not retransmitted as cleanup. Loss of eligibility stops new experimental frames; normal forwarding resumes as leases are relinquished/expire. A neutral interval is required before rearming, and holding a signal does not restart attempts indefinitely.

The following are **received factory status examples**, not injected view commands:

```text
Right: 0x3EE  00 30 08 1B 80 00 00 00
Left:  0x3EE  00 2F 08 1B 80 00 00 00
Exit:  0x3EE  00 00 08 1B 80 00 00 00
```

A matching status is not proof of the displayed video. The user must visually identify the actual feed. Likewise, reported CTA ON or an absent warning is not proof of detection performance.
