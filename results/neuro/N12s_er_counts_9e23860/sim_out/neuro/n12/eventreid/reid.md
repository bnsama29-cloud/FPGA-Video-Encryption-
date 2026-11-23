# N12 person re-identification on Event-ReId

132 recordings, identities 22 train / 11 test; 880 test frames (33.3 ms each, up to 20 per recording), cross-camera retrieval; chance rank-1 about 9 %. Recipe strong: ResNet-50 (ImageNet), input 10 x 240 x 320 (5 time bin(s), 2 x 2 blocks), cross-entropy, AdamW 0.0001 cosine, 40 epochs, seeds [0, 1]; mean and 95 % interval in %.

| view | rank-1, trained on the view | mAP, trained on the view | rank-1, clear-trained net | mAP, clear-trained net |
|---|---|---|---|---|
| clear | 24.9 [19.9, 30.0] | 18.6 [14.9, 22.3] | - | - |
| counts only | 6.1 [2.5, 9.7] | 9.9 [9.5, 10.3] | 6.7 [-0.5, 13.9] | 10.0 [9.3, 10.8] |
| Du 2021 | 10.2 [-2.8, 23.2] | 10.5 [10.2, 10.8] | 7.7 [0.5, 14.9] | 10.0 [9.0, 10.9] |

clear = what the key holder gets (decryption is exact). counts only = every event at a random position and polarity: the public count series alone. Published reference points (their protocol, their split): Ahmad et al. ICCV 2023 Event-ReId re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker, Event-ReId top-1 59.1 % raw / 38.6 % anonymised, DVS Gesture 98.3 % raw / 40.0 % anonymised.
