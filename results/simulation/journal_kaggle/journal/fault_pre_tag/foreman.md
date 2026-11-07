# Faults before and after the tag: foreman, 352x288, E2, 300 faults per site

| Fault site | trials | accepted by the receiver | rejected: tag / undecodable | picture identical | PSNR of accepted (median / min, dB) |
|---|---|---|---|---|---|
| coefficient | 300 | 300 (100 %) | 0 / 0 | 0 | 66.5 / 60.0 |
| ciphertext | 300 | 281 (94 %) | 0 / 19 | 0 | 49.2 / 4.6 |
| after_tag | 300 | 0 (0 %) | 300 / 0 | 0 | - |

A fault before the tag is authenticated with the data: the tag proves the frame left the encoder unchanged, not that the encoder computed it correctly. Detecting those needs redundancy inside the encoder (duplication or parity), which this design does not have.
