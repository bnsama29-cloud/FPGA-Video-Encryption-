# N12 person re-identification on Event-ReId

132 recordings, identities 22 train / 11 test; 880 test frames (33.3 ms each, up to 20 per recording), cross-camera retrieval; chance rank-1 about 9 %. Recipe e2vid: ResNet-50 (ImageNet), input 1 x 240 x 320 (E2VID image, 2 x 2 blocks), cross-entropy, AdamW 0.0001 cosine, 40 epochs, seeds [0, 1, 2]; mean and 95 % interval in %.

| view | rank-1, trained on the view | mAP, trained on the view | rank-1, clear-trained net | mAP, clear-trained net |
|---|---|---|---|---|
| clear | 40.5 [34.9, 46.0] | 27.6 [25.7, 29.4] | - | - |
| V3 | 10.0 [8.8, 11.1] | 11.9 [10.9, 12.9] | 6.7 [3.4, 10.0] | 10.8 [10.4, 11.3] |
| counts only | 5.5 [0.5, 10.4] | 11.3 [9.8, 12.9] | 3.7 [2.2, 5.1] | 10.7 [10.0, 11.3] |

clear = what the key holder gets (decryption is exact). counts only = every event at a random position and polarity: the public count series alone. Published reference points (their protocol, their split): Ahmad et al. ICCV 2023 Event-ReId re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker, Event-ReId top-1 59.1 % raw / 38.6 % anonymised, DVS Gesture 98.3 % raw / 40.0 % anonymised.
