## Hardware results from Vivado (post-route, xc7z020clg400-1)

| Design | LUT | FF | BRAM | DSP | Clock (MHz) | WNS (ns) | Timing met | Est. fmax (MHz) | Power total / dynamic (W) |
|---|---|---|---|---|---|---|---|---|---|
| overlay_lanestamper | 12811 (24.1%) | 10342 (9.7%) | 54.5 (38.9%) | 46 (20.9%) | 100 | 1.021 | yes | 111.4 | 1.961 / 1.808 |

Power is Vivado's vectorless estimate (confidence shown in power.txt); measure the board for real power.
Est. fmax = 1000 / (period - WNS): a single-run estimate, confirm by re-running at that period.

### Worst setup paths (block of source -> destination)

| Design | Clock (MHz) | Paths (slack ns: from -> to) |
|---|---|---|
| overlay_lanestamper | 100 | +1.021: system_i -> system_i; +1.098: system_i -> system_i; +1.181: system_i -> system_i; +1.240: system_i -> system_i; +1.240: system_i -> system_i |

### Resource breakdown: overlay_lanestamper

| Block | Module | LUT | FF | BRAM | DSP |
|---|---|---|---|---|---|
| system_wrapper | (top) | 12811 | 10342 | 54.5 | 46 |
| &nbsp;&nbsp;(system_wrapper) | (top) | 0 | 0 | 0 | 0 |
| &nbsp;&nbsp;system_i | system | 12811 | 10342 | 54.5 | 46 |
| &nbsp;&nbsp;&nbsp;&nbsp;tamper | system_tamper_0 | 52 | 47 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;axi_mem_intercon | system_axi_mem_intercon_0 | 655 | 781 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;buttons | system_buttons_0 | 62 | 123 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;dma | system_dma_0 | 1396 | 2033 | 2.5 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;ps7_axi_periph | system_ps7_axi_periph_0 | 537 | 676 | 0 | 0 |
| &nbsp;&nbsp;&nbsp;&nbsp;sjpeg | system_sjpeg_0 | 10094 | 6648 | 52 | 46 |

