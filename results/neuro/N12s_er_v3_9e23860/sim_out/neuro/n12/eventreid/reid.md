# N12 person re-identification on Event-ReId

132 recordings, identities 22 train / 11 test; 880 test frames (33.3 ms each, up to 20 per recording), cross-camera retrieval; chance rank-1 about 9 %. Recipe strong: ResNet-50 (ImageNet), input 10 x 240 x 320 (5 time bin(s), 2 x 2 blocks), cross-entropy, AdamW 0.0001 cosine, 40 epochs, seeds [0, 1, 2]; mean and 95 % interval in %.

| view | rank-1, trained on the view | mAP, trained on the view | rank-1, clear-trained net | mAP, clear-trained net |
|---|---|---|---|---|
| clear | 25.3 [22.9, 27.7] | 17.8 [15.6, 19.9] | - | - |
| V3 | 7.0 [4.2, 9.9] | 9.9 [9.7, 10.1] | 6.2 [3.8, 8.7] | 9.9 [9.7, 10.1] |

clear = what the key holder gets (decryption is exact). counts only = every event at a random position and polarity: the public count series alone. Published reference points (their protocol, their split): Ahmad et al. ICCV 2023 Event-ReId re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker, Event-ReId top-1 59.1 % raw / 38.6 % anonymised, DVS Gesture 98.3 % raw / 40.0 % anonymised.
