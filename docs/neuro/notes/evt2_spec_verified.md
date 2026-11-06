# EVT 2.0: layout checked at the source

Source: Prophesee Metavision SDK Docs 5.3.1, "EVT 2.0 Format",
https://docs.prophesee.ai/stable/data/encoding_formats/evt2.html. Read in Chrome on 6 Nov 2026.

- One word is 32 bits. The 4 most significant bits give the word type. Resolution goes up to 2048x2048.
- Byte order is set by the sensor configuration. IMX636 and GenX320 send little-endian by default.
- Timestamps are 34 bits, in µs, and roll over after 2^34 µs (4 h 46 min).
  - Bits 0..5 travel in each CD and trigger word.
  - Bits 6..33 (28 bits) travel in an EVT_TIME_HIGH word.
  - The full timestamp is the low bits joined to the last EVT_TIME_HIGH.
  - Decoding starts at the first EVT_TIME_HIGH.

| Type | Code | Bits 27..22 | Rest of the word |
|---|---|---|---|
| CD_OFF (polarity 0) | 0000 | ts[5:0] | x = 21..11 (11 bits), y = 10..0 (11 bits) |
| CD_ON (polarity 1) | 0001 | ts[5:0] | x = 21..11, y = 10..0 |
| EVT_TIME_HIGH | 1000 | - | 27..0 = ts[33:6] (28 bits) |
| EXT_TRIGGER | 1010 | ts[5:0] | 21..13 unused, 12..8 id (00000 EXTTRIG, 00001 TDRSTN/PXRSTN), 7..1 unused, 0 = edge value |
| OTHERS | 1110 | ts[5:0] | 21..17 unused, 16 class (0 monitoring), 15..0 subtype (vendor-specific) |
| CONTINUED | 1111 | - | 27..0 depend on the previous word (vendor-specific) |

All other type codes are reserved.

Consequences for the design:
- Polarity is bit 28: the type field is 0000 or 0001 for CD events. XORing that bit with keystream turns CD_OFF and CD_ON into each other and keeps the word valid.
- x and y are 11 bits each, so a permuted coordinate must stay inside the sensor's W x H. Otherwise decoders and datasets can reject the event.
- The low 6 timestamp bits sit in every CD word. XORing them breaks the time order inside each 64 µs window (one EVT_TIME_HIGH step), but not across windows.
