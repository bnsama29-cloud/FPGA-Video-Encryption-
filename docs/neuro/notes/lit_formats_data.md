# Event data formats, sensors, datasets and tools (paper 2 notes)

Checked 2026-11-06. Every item below was opened at the cited URL unless it is marked
**UNVERIFIED**. Quotes are short. Where a value is my inference rather than a stated
fact, it says "inference". No numbers in this file come from memory.

---

## 0. Findings that change the draft plan

1. **EVT 2.0 is not what the IMX636 outputs.** Prophesee's format index lists the
   IMX636 (Gen4.1, inside the EVK4) as supporting **EVT 2.1 and EVT 3.0, with EVT 3.0 as the default**.
   Only the **GenX320** offers EVT 2.0, and Prophesee describes it as "32-bit non-vectorized format for low event rate"
   ([format index](https://docs.prophesee.ai/stable/data/encoding_formats/index.html)). The IMX636
   product brief lists "EVT 2.1 (64-bit based event output format), EVT 3.0 (16-bit encoding event
   output format)" ([brief](https://prophesee.ai/wp-content/uploads/2024/05/IMX636-Product-Brief-2024-v3.0.pdf)).
   *Consequence:* EVT 2.0 is still a sound choice for the **on-chip / wire format** of the encryptor,
   because each word is one self-contained event with fixed-width fields, which suits format-preserving
   encryption. The paper must state this choice honestly, though: an IMX636 front end would need an
   EVT 3.0/2.1 to EVT 2.0 unpacker, and that unpacker sits outside the encryption core. EVT 2.1 keeps the same
   x/y/ts field widths, but its 32-bit validity mask packs up to 32 events into one word. A position
   permutation on (x,y) would have to break such vectors apart.
2. **The EVT 2.0 coordinate fields are 11 bits** (0..2047, inference from the field widths), so a keyed permutation must
   stay inside the sensor's W x H (for example 1280x720, 346x260 or 128x128), not inside 2048x2048.
   This is why cycle walking (or another fixed-latency domain-restricted permutation) is needed.
3. **The timestamp is split:** the CD words carry only 6 LSBs (µs), and EVT_TIME_HIGH words carry bits 33..6.
   Encrypting the "low timestamp bits" (level V3) therefore means encrypting a 6-bit field. The order of
   events inside a 64 µs EVT_TIME_HIGH epoch then becomes ambiguous, but no event moves into another
   epoch, so the EVT_TIME_HIGH words can stay in clear text.
4. Datasets: **N-MNIST is 34x34 in Tonic, and DVS Gesture is 128x128 in Tonic with ms timestamp precision**
   (Tonic uses a preprocessed version). Neither dataset is in EVT 2.0, so our pipeline must re-encode
   them to EVT 2.0 words. Use our own packer, which the golden model owns. Do not rely on a third-party writer.

---

## 1. Prophesee EVT 2.0 (32-bit words)

Source: <https://docs.prophesee.ai/stable/data/encoding_formats/evt2.html> (opened).

"In each 32-bit EVT 2.0 word, the 4 Most Significant Bits (MSB) are used to define the word type."

### 1.1 Type codes (bits 31..28)

| Type | Code (bin) | Hex nibble |
|---|---|---|
| CD_OFF | 0000 | 0x0 |
| CD_ON | 0001 | 0x1 |
| EVT_TIME_HIGH | 1000 | 0x8 |
| EXT_TRIGGER | 1010 | 0xA |
| OTHERS | 1110 | 0xE |
| CONTINUED | 1111 | 0xF |

All other codes are not defined on that page.

### 1.2 Word layouts

```
CD_OFF / CD_ON
 31..28  type      (0000 = OFF, 0001 = ON)   -> polarity is encoded in the TYPE nibble
 27..22  ts[5:0]   6 LSBs of the µs timestamp
 21..11  x         11 bits
 10..0   y         11 bits

EVT_TIME_HIGH
 31..28  1000
 27..0   ts[33:6]  28 MSBs of the 34-bit µs timestamp

EXT_TRIGGER
 31..28  1010
 27..22  ts[5:0]
 21..13  unused
 12..8   id        5 bits: 00000 = EXTTRIG, 00001 = TDRSTN/PXRSTN
 7..1    unused
 0       value     0 = falling edge, 1 = rising edge

OTHERS
 31..28  1110
 27..22  ts[5:0]
 21..17  unused
 16      class     0 = Monitoring, 1 = TBD
 15..0   subtype   (vendor specific)

CONTINUED
 31..28  1111
 27..0   depends on previous event (vendor specific)
```

Python decode (written from the layout above; it is ours and must be checked against the golden model):

```python
w = int(word)                      # uint32, after little-endian load
typ = w >> 28
if typ in (0x0, 0x1):
    p  = typ                       # CD_OFF=0, CD_ON=1
    tl = (w >> 22) & 0x3F
    x  = (w >> 11) & 0x7FF
    y  =  w        & 0x7FF
    t  = (t_high << 6) | tl        # t_high from last EVT_TIME_HIGH
elif typ == 0x8:
    t_high = w & 0x0FFF_FFFF
```

### 1.3 Time reconstruction and ordering

- The timestamp is 34 bits in µs. The page says "decoding of the event stream should start after receiving the first event of type EVT_TIME_HIGH".
  The full timestamp is the 28 MSBs of the most recent EVT_TIME_HIGH concatenated with the 6 LSBs of the event.
- The page states no other ordering rule. It does not say that events inside an epoch are monotonic. The 6-bit
  LSB field implies (inference) that a new EVT_TIME_HIGH must be emitted at least every 64 µs while events flow,
  otherwise the reconstruction becomes ambiguous.
- 34-bit rollover is 2^34 µs, about 4 h 46 min (the EVT 2.1 page states this figure for the same 34-bit split).
- **Byte order:** this is a sensor configuration setting. The page says that IMX636 and GenX320 default to **little-endian** (LSB first).
- Maximum supported sensor: "up to 2048x2048 resolution".

## 2. EVT 2.1 (64-bit, vectorized). Brief.

Source: <https://docs.prophesee.ai/stable/data/encoding_formats/evt21.html> (opened).

```
EVT_NEG(0000) / EVT_POS(0001)
 63..60 type | 59..54 ts[5:0] | 53..43 x (aligned on 32) | 42..32 y | 31..0 valid mask
 bit n of the mask = valid event at (x+n, y)
EVT_TIME_HIGH(1000): 59..32 ts[33:6], 31..0 zero
EXT_TRIGGER(1010):   59..54 ts, 44..40 id, 32 value
```
The IMX636 sends each 64-bit word as two little-endian 32-bit halves. Example from the page: 0x0102030405060708 is
transmitted as 0x0403020108070605. The GenX320 sends the full 64-bit word little-endian.

## 3. EVT 3.0 (16-bit, vectorized, stateful). Brief.

Source: <https://docs.prophesee.ai/stable/data/encoding_formats/evt3.html> (opened). Type field in bits 15..12.

| Type | Code | Payload |
|---|---|---|
| EVT_ADDR_Y | 0000 | 11 system_type (0 master/1 slave); 10..0 y |
| EVT_ADDR_X | 0010 | 11 pol; 10..0 x (one CD event) |
| VECT_BASE_X | 0011 | 11 pol; 10..0 x (sets base, not an event) |
| VECT_12 | 0100 | 11..0 valid; base += 12 |
| VECT_8 | 0101 | 7..0 valid; base += 8 |
| EVT_TIME_LOW | 0110 | 11..0 = time[11:0] |
| CONTINUED_4 | 0111 | 3..0 extra |
| EVT_TIME_HIGH | 1000 | 11..0 = time[23:12] |
| EXT_TRIGGER | 1010 | 11..8 id; 0 value |
| OTHERS | 1110 | 11..0 subtype |
| CONTINUED_12 | 1111 | 11..0 extra |

The timestamp is **24 bits**, in µs (wrap at about 16.8 s per the page). The decoder is *stateful*: y, base x, polarity and time
persist across words. For this reason EVT 3.0 is a poor fit for word-local format-preserving encryption (my design argument, not a claim from the page).
The page's EXT_TRIGGER id field is 4 bits wide, but its value list shows 5-bit codes. This is an inconsistency in the source.

## 4. File containers

### 4.1 Prophesee RAW (.raw)
Source: <https://docs.prophesee.ai/stable/data/file_formats/raw.html> (opened).
- An ASCII header, then binary event data. Each header line is `% <keyword> <value>\n` (0x25 0x20 ... 0x0A).
- The optional terminator is `% end`. A parser treats the data as starting at the first line that does not begin with `% `.
- Keywords: `date` (YYYY-MM-DD HH:MM:SS), `camera_integrator_name`, `plugin_integrator_name`,
  `plugin_name`, `serial_number`, `system_ID`, `format`, `end`. The preferred form is
  `format EVTn;height=y;width=x`. `evt` is a legacy synonym of `format`.
- The documented EVK4 example includes:
  ```
  % camera_integrator_name Prophesee
  % format EVT3;height=720;width=1280
  % geometry 1280x720
  % evt 3.0
  % end
  ```
  For our files: `% format EVT2;height=H;width=W` then `% end`, followed by little-endian uint32 words.

### 4.2 Prophesee DAT (.dat)
Source: <https://docs.prophesee.ai/stable/data/file_formats/dat.html> (opened) plus Prophesee's
automotive-dataset toolbox loader
<https://raw.githubusercontent.com/prophesee-ai/prophesee-automotive-dataset-toolbox/master/src/io/dat_events_tools.py> (opened).
- The header is `% Key Value` lines (`Date`, `Version` (currently 2, mandatory), `Width`, `Height`). It is followed by **1 byte event type**
  (Event2d 0x00, EventCd 0x0C, EventExtTrigger 0x0E) and **1 byte event size** (0x08). The data is little-endian.
- Each event is 8 bytes: `uint32 t` followed by `int32 packed`. The toolbox decodes them as
  `x = packed & 0x3FFF`, `y = (packed & 0x0FFFC000) >> 14`, `p = (packed & 0x10000000) >> 28`.
  The Prophesee doc page itself shows the CD bitfield only as an image and refers to `event_cd.h`. The bit
  layout above therefore rests on the toolbox code, not on the doc page text.

### 4.3 AEDAT (iniVation)
Source: <https://docs.inivation.com/software/software-advanced-usage/file-formats/aedat-4.0.html> (opened).
- AEDAT 4.0 (July 2019) has the version line `#!AER-DAT4.0\r\n`, then a size-prefixed (4-byte LE) FlatBuffer IOHeader with
  `compression` (NONE, LZ4, LZ4_HIGH, ZSTD, ZSTD_HIGH), `dataTablePosition` (int64, -1 means none) and `infoNode` (XML).
  Each packet has an 8-byte header (StreamID, Size), followed by a FlatBuffer. Timestamps are int64 Unix µs.
- **UNVERIFIED:** the polarity-event struct fields and sizes (a third-party Rust reader says 16-byte `Event`
  structs with the `EVTS` identifier). The AEDAT 2.0/3.1 bit layouts are on pages I did not open.
- v2e writes AEDAT-2.0 (`--dvs_aedat2`), text, or HDF5 (see §7).

## 5. Sensors

| Sensor | Resolution | Peak event rate | Other | Source (opened) |
|---|---|---|---|---|
| Sony/Prophesee IMX636 | 1280x720 (approx. 0.92 MP) | **1.06 Geps** (FRAMOS news page, quoting Sony's launch) | 4.86 µm pixel; contrast threshold 25 %; latency <100 µs @1000 lux, <1000 µs @5 lux; DR >86 dB (5 lux-100 klux), >120 dB (80 mlux-100 klux); max clock 100 MHz; max power 150 mW; MIPI/SLVS; EVT 2.1, EVT 3.0 | [IMX636 brief](https://prophesee.ai/wp-content/uploads/2024/05/IMX636-Product-Brief-2024-v3.0.pdf), [FRAMOS news](https://framos.com/news/sony-launches-the-new-imx636-and-imx637-event-based-vision-sensors/), [EVK4 page](https://www.prophesee.ai/event-camera-evk4/) |
| iniVation DAVIS346 | 346x260 | **12 MEPS** | 18.5 µm pixel; latency <1 ms; DR ~120 dB; contrast sensitivity 14.3 % on / 22.5 % off; APS frames 40 FPS | [DAVIS346 doc](https://docs.inivation.com/hardware/current-products/davis346.html) |
| DVS128 (Lichtsteiner, Posch, Delbruck) | 128x128 | **UNVERIFIED** (not on the pages I opened) | >120 dB; min latency 15 µs at >1 klux; 23 mW (per AIT record / search summary, abstract not opened) | IEEE JSSC 43(2):566-576, 2008, DOI 10.1109/JSSC.2007.914337 (DOI confirmed via OpenAlex; [AIT record](https://publications.ait.ac.at/en/publications/a-128x128-120db-15%C2%B5s-latency-asynchronous-temporal-contrast-visio/)) |
| Prophesee GenX320 | 320x320, 6.3 µm | **UNVERIFIED** (product-brief figures seen only in a search summary: ~100 kEPS ULP CPI, 1 MEPS CPI, 10 MEPS MIPI) | the only current sensor with EVT 2.0 | [GenX320 doc](https://docs.prophesee.ai/stable/hw/sensors/genx320.html) |

Sizing note (inference): EVT 2.0 at 1.06 Geps x 32 bit is about 34 Gbit/s, which a 100 MHz single-word-per-clock core
(100 Mev/s) cannot sustain. Our claim should be "sensor-rate" for DAVIS346-class (12 MEPS) and typical
scene rates, not the IMX636 peak. This must be measured by script before it is written in the paper.

## 6. Tonic (datasets)

Sources (opened): PyPI JSON <https://pypi.org/pypi/tonic/json>, source files
`tonic/datasets/dvsgesture.py`, `tonic/datasets/nmnist.py`, `tonic/io.py`, `tonic/transforms.py`
on <https://github.com/neuromorphs/tonic> (main), docs page for DVSGesture.

- **Version 1.7.0**, uploaded 2026-10-03, `requires_python >=3.10`. Runtime deps: numpy>=1.24, h5py>=3.8,
  importRosbag>=1.0.4, scipy>=1.10, tqdm>=4.65, typing-extensions>=4.5, librosa>=0.10, expelliarmus>=1.0.
  Extra `torch`: torch>=2.4.1, torchvision>=0.19.1, torchaudio>=2.4.1.
- **Python 3.11 / Kaggle:** the requires_python constraint allows 3.11. The only compiled dependency, expelliarmus 1.1.12, ships
  `cp311-manylinux x86_64` and `cp311-win_amd64` wheels (checked on PyPI). importRosbag 1.0.4 is py3-none-any.
  I did **not** run an install on a Kaggle image, so "installs on Kaggle" is **UNVERIFIED** until the first
  Kaggle smoke run (`pip install tonic==1.7.0`).

### DVSGesture
```python
import tonic
ds = tonic.datasets.DVSGesture(save_to="./data", train=True)   # (events, target)
tonic.datasets.DVSGesture.sensor_size   # (128, 128, 2)
# dtype: [("x", int16), ("y", int16), ("p", bool), ("t", int64)]
```
- 11 classes: Hand clapping, Right hand wave, Left hand wave, Right arm cw, Right arm ccw, Left arm cw,
  Left arm ccw, Arm roll, Air drums, Air guitar, Other gestures.
- "(exceptionally) a preprocessed version of the original dataset ... temporal precision is reduced to ms".
  `__getitem__` multiplies t by 1000 (ms to µs). This means the 6-bit ts LSB field would be almost always 0
  for re-encoded Gesture data: **V3 timestamp encryption must be evaluated on data with real µs timing too**
  (N-MNIST or v2e output).
- Downloads (figshare, sizes from HTTP Content-Range, measured 2026-11-06):
  `ibmGestureTrain.tar.gz` = 2,443,675,558 B; `ibmGestureTest.tar.gz` = 691,455,012 B.
  md5 train `3a8f0d4120a166bac7591f77409cb105`, test `56070e45dadaa85fff82e0fbfbc06de5`.
- The original dataset (IBM page, opened): 11 gestures, 29 subjects, 3 illumination conditions, and "96.5%
  out-of-sample accuracy" (<https://research.ibm.com/interactive/dvsgesture/>). Paper: Amir et al.,
  "A Low Power, Fully Event-Based Gesture Recognition System", CVPR 2017, DOI 10.1109/CVPR.2017.781
  (OpenAlex). The CVF page returned 403, so the abstract was not opened.

### NMNIST
```python
ds = tonic.datasets.NMNIST(save_to="./data", train=True, first_saccade_only=False)
tonic.datasets.NMNIST.sensor_size   # (34, 34, 2)
# dtype: [("x", int), ("y", int), ("t", int), ("p", int)]
# first_saccade_only -> events[events["t"] < 1e5]
```
- Binary .bin decoding (tonic/io.py `read_mnist_file`), 5 bytes per event:
  `x = b0`, `y = b1`, `p = (b2 & 0x80) >> 7`, `ts = ((b2 & 0x7F) << 16) | (b3 << 8) | b4` (µs, 23 bits).
- Downloads (Mendeley, Content-Length measured 2026-11-06): `Train.zip` = 1,011,893,601 B,
  `Test.zip` = 169,674,850 B.
- Paper: Orchard, Jayawant, Cohen, Thakor, "Converting Static Image Datasets to Spiking Neuromorphic
  Datasets Using Saccades", Front. Neurosci. 2015, DOI 10.3389/fnins.2015.00437 (OpenAlex).

### Transforms (dataclass fields, from transforms.py)
```python
tonic.transforms.ToFrame(sensor_size, time_window=None, event_count=None, n_time_bins=None,
                         n_event_bins=None, overlap=0, include_incomplete=False, ...)
tonic.transforms.Denoise(filter_time)
tonic.transforms.Downsample(time_factor=1, spatial_factor=1, sensor_size=None, target_size=None)
tonic.transforms.RefractoryPeriod(delta)
tonic.transforms.ToVoxelGrid(sensor_size, n_time_bins)     # for E2VID/FireNet input
tonic.transforms.DropEvent(p)
tonic.transforms.SpatialJitter(sensor_size, var_x=1, var_y=1, sigma_xy=0, clip_outliers=False)
tonic.transforms.TimeJitter(std, clip_negative=True, sort_timestamps=False)
```

### expelliarmus (Tonic dependency; EVT2/EVT3/DAT reader and writer)
Source: <https://github.com/open-neuromorphic/expelliarmus> README (opened). This is useful as an *independent*
cross-check of our EVT 2.0 packer (it is not the referee):
```python
from expelliarmus import Wizard
arr = Wizard(encoding="evt3").read("file.raw")          # structured array with t, x, y, p
Wizard(encoding="evt2").save(fpath="out_evt2.raw", arr=arr)
```

## 7. Generating events from Xiph / our clips

### v2e (Hu, Liu, Delbruck)
- "v2e: From Video Frames to Realistic DVS Events", CVPRW 2021 (Third Int. Workshop on Event-Based
  Vision), arXiv 2006.07722 (<https://arxiv.org/abs/2006.07722>, opened). The model covers per-pixel Gaussian
  threshold mismatch, finite intensity-dependent bandwidth, and intensity-dependent noise.
- Method (from `v2ecore/emulator.py`, opened): the frame is converted with `lin_log`, then passes through a 1st-order IIR lowpass
  whose cutoff depends on intensity. Each pixel keeps a memorized `base_log_frame`. It computes `diff = lp_log + noise - base`, and
  `compute_event_map(diff, pos_thres, neg_thres)` gives ON/OFF counts. Timestamps are spread
  linearly over the frame interval in `max(count)` sub-steps, and a refractory filter is applied. The base is updated by
  `count x threshold` ("don't add the remainder"). A leak drift (`leak_rate_hz`) and random shot-noise events are added.
  The exact count formula and `lin_log` live in `emulator_utils` (not opened, **UNVERIFIED**).
- Defaults (`v2ecore/v2e_args.py`, opened): `pos_thres=0.2`, `neg_thres=0.2` (log_e units),
  `sigma_thres=0.03`, `cutoff_hz=300`, `leak_rate_hz=0.01`, `shot_noise_rate_hz=0.001`,
  `refractory_period=0.0005` s, `leak_jitter_fraction=0.1`, `noise_rate_cov_decades=0.1`,
  `dvs_exposure=['duration','0.01']`, `timestamp_resolution=None`. The `--dvs_params clean|noisy` presets are
  described qualitatively only.
- Sensor presets: `--dvs128`, `--dvs240`, `--dvs346`, `--dvs640`, `--dvs1024`. Outputs: `--dvs_aedat2`,
  `--dvs_text` (t[s] x y p per line), `--dvs_h5`. `--disable_slomo` skips SuperSloMo interpolation.
- Install: the README says to clone and run `pip install -e .`. PyTorch (CUDA recommended) and the
  `SuperSloMo39.ckpt` checkpoint (151 MB) are needed. **There is no `v2e` project on PyPI** (the PyPI JSON API returned no
  project, checked 2026-11-06).

### ESIM
- Rebecq, Gehrig, Scaramuzza, "ESIM: an Open Event Camera Simulator", CoRL 2018 (OpenAlex record,
  ZORA repository, DOI 10.5167/uzh-175993). It is a ROS/C++ simulator. I did **not** open the paper or the repository,
  so its method details are **UNVERIFIED** here.

### Light-weight alternative (recommended for our pipeline, design proposal)
To avoid torch, SuperSloMo and ROS on the laptop, implement a small numpy event generator in
`software/` (the golden-model side) that follows the v2e core idea with its noise sources disabled. Steps:
1. Compute L = log(I + eps) per Y frame (Xiph clips are already decoded to Y by paper 1 tooling).
2. Keep a per-pixel memory M. For each frame pair, n = floor(|L - M| / C) with C = 0.2 (v2e default).
3. Emit n events with linearly interpolated µs timestamps across the frame interval.
4. Set M += sign x n x C.
5. Optionally add a refractory period of 0.5 ms (the v2e default).

Deterministic and seeded, so its output can be a test vector. The paper should say that it is "v2e-style
without noise/bandwidth model", and should state that any real-sensor statistics come from DVS Gesture / N-MNIST.
On Kaggle (GPU) the real v2e can be run once for a realism cross-check.

## 8. SNN frameworks and reference accuracies

| Package | Latest (PyPI, checked) | requires_python | Runtime deps |
|---|---|---|---|
| snntorch | 1.0.0 (2026-06-29) | >=3.9 | none declared (torch expected to be preinstalled) |
| spikingjelly | 2.0.0 (2026-10-17) | >=3.11 | torch>=2.6.0, torchvision, torchaudio, h5py, loguru, matplotlib, numpy, packaging, requests, SciencePlots, scipy, tensorboard, tqdm |

Both declare support for Python 3.11. snnTorch is the lighter choice and pairs with Tonic in its own tutorials.

snnTorch tutorial 7 (<https://snntorch.readthedocs.io/en/latest/tutorials/tutorial_7.html>, opened), N-MNIST:
```python
import tonic, tonic.transforms as transforms
sensor_size = tonic.datasets.NMNIST.sensor_size
frame_transform = transforms.Compose([transforms.Denoise(filter_time=10000),
                                      transforms.ToFrame(sensor_size=sensor_size, time_window=1000)])
trainset = tonic.datasets.NMNIST(save_to='./data', transform=frame_transform, train=True)
# CSNN 12C5-MP2-32C5-MP2-800FC10, num_iters = 50 -> "~60% accuracy" (demo only, ~1/10 epoch)
```

Reference accuracies (opened):
- PLIF (Fang et al., "Incorporating Learnable Membrane Time Constant to Enhance Learning of Spiking
  Neural Networks", ICCV 2021, DOI 10.1109/ICCV48922.2021.00266; arXiv 2007.05785 HTML opened):
  **N-MNIST 99.61 % (T=10), DVS128 Gesture 97.57 % (T=20)**. These are the maximum test accuracy during training. With a
  15 % validation split the paper gives 99.57 % / 96.53 %.
- Amir et al. CVPR 2017 (IBM page): 96.5 % out-of-sample on DVS Gesture.
- snnTorch paper: Eshraghian et al., "Training Spiking Neural Networks Using Lessons From Deep
  Learning", Proc. IEEE 2023, DOI 10.1109/JPROC.2023.3308088 (OpenAlex). I did not open it for accuracies.
- SpikingJelly paper: Fang et al., Science Advances 2023, DOI 10.1126/sciadv.adi1480 (OpenAlex), not opened.

For N8 (accuracy with / without key), the paper must report **our own** trained-model accuracy from a script
(clear, V1, V2, V3, and decrypted). The published numbers above are only for context.

---

## 9. UNVERIFIED list (do not cite until opened)
- DVS128 peak event rate. DVS128 abstract text.
- GenX320 event-rate figures (search summary only).
- AEDAT 4.0 polarity event struct and AEDAT 2.0/3.1 bit layouts.
- v2e `lin_log` and `compute_event_map` exact formulas. ESIM method details.
- Tonic actually installing on the current Kaggle image (wheels exist for cp311, but no install was run).
- Amir et al. CVPR 2017 abstract (CVF page 403). Its accuracy is quoted from the IBM page only.
