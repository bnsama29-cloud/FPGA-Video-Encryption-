# N12 person re-identification on DVS Gesture (users)

564 recordings, identities 23 train / 6 test; 264 test recordings (one sample each), retrieval against every other test recording except the same user and gesture (AnonyNoise's gallery rule); chance rank-1 about 17 %. Recipe strong: ResNet-50 (ImageNet), input 10 x 128 x 128 (5 time bin(s), 1 x 1 blocks), cross-entropy, AdamW 0.0001 cosine, 40 epochs, seeds [0, 1, 2]; mean and 95 % interval in %.

| view | rank-1, trained on the view | mAP, trained on the view | rank-1, clear-trained net | mAP, clear-trained net |
|---|---|---|---|---|
| clear | 70.6 [62.5, 78.7] | 36.7 [30.1, 43.3] | - | - |
| V3 | 20.1 [10.1, 30.0] | 18.9 [18.5, 19.4] | 17.3 [13.1, 21.5] | 18.9 [18.2, 19.7] |
| Du 2021 | 22.2 [12.2, 32.3] | 18.8 [18.2, 19.4] | 16.7 [10.5, 22.8] | 18.3 [18.1, 18.6] |
| counts only | 18.2 [9.8, 26.5] | 18.6 [17.9, 19.4] | 17.7 [13.4, 21.9] | 18.9 [18.5, 19.4] |

clear = what the key holder gets (decryption is exact). counts only = every event at a random position and polarity: the public count series alone. Published reference points (their protocol, their split): Ahmad et al. ICCV 2023 Event-ReId re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker, Event-ReId top-1 59.1 % raw / 38.6 % anonymised, DVS Gesture 98.3 % raw / 40.0 % anonymised.
