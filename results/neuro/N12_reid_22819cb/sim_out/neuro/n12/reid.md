# N12 person re-identification on Event-ReId

132 recordings, persons 22 train / 11 test (seed 0); 1752 test frames (33.3 ms each, up to 40 per recording), cross-camera retrieval; chance rank-1 about 9 %. ResNet-50 (ImageNet), 30 epochs, seeds [0, 1, 2]; mean and 95 % interval in %.

| view | rank-1, trained on the view | mAP, trained on the view | rank-1, clear-trained net | mAP, clear-trained net |
|---|---|---|---|---|
| clear | 23.4 [21.3, 25.5] | 16.3 [15.2, 17.5] | - | - |
| V1 | 22.4 [13.5, 31.3] | 15.7 [14.6, 16.8] | 20.9 [19.5, 22.2] | 14.5 [14.1, 15.0] |
| V2 | 7.2 [5.5, 8.9] | 9.7 [9.7, 9.8] | 7.4 [5.2, 9.6] | 9.8 [9.6, 9.9] |
| V3 | 6.9 [4.1, 9.7] | 9.7 [9.5, 9.9] | 7.2 [6.3, 8.2] | 9.7 [9.6, 9.9] |
| Du 2021 | 7.5 [6.8, 8.1] | 9.9 [9.8, 9.9] | 7.1 [6.2, 7.9] | 9.7 [9.6, 9.8] |

clear = what the key holder gets (decryption is exact). Published reference points (their protocol, their split): Ahmad et al. ICCV 2023 re-id rank-1 63.7 % on raw events; AnonyNoise WACV 2025 retrained attacker top-1 59.1 % raw, 38.6 % anonymised.
