# Secure camera link dashboard

This document explains the live dashboard, the monitor and control panel for
the simulated secure camera link. It displays video previews and telemetry
from the sender, channel, and receiver, and sends controls back to the sender
or channel. It does not perform the encoding, encryption, or frame verification
itself.

## Start the dashboard and link

From the repository root, start the complete simulation:

```bash
python -m link.run_all
```

Open [http://localhost:8000](http://localhost:8000). The simulation starts a
channel, receiver, dashboard, and sender. In the default configuration, the
sender uses a synthetic 320x240 video source, the Python model encoder, mode E2,
the threshold policy, and a target rate of 10 frames per second.

To start only the dashboard process, run `python -m link.dashboard`; the other
nodes must already be running and configured to publish telemetry to the same
bus port. Stop the simulation with Ctrl+C in its terminal.

## Signal flow

1. **Camera to sender:** The sender reads a frame, JPEG-encodes it, selectively
   encrypts data according to the current protection mode, and attaches an
   Ascon-AEAD128 authentication tag and frame metadata.
2. **Sender through channel:** The sender sends the JPEG frame over UDP. The
   channel forwards it to the receiver, optionally applying configured delay,
   jitter, packet loss, or reordering. It also provides the simulated attacker
   and responds to attack commands from the dashboard.
3. **Receiver verification:** The receiver checks the frame's authentication
   tag, session/key epoch, and counter before decrypting and accepting it.
   Rejected frames are not shown as verified receiver output.
4. **Feedback to sender:** The receiver sends authenticated heartbeats and
   alerts back through the channel. The sender uses that evidence to make
   defence decisions and, when appropriate, ratchet to a new key epoch.
5. **Telemetry to dashboard:** Nodes publish events and preview frames over a
   separate telemetry bus. The dashboard receives those events, serves the
   browser's live event stream and MJPEG previews, and updates the views,
   charts, counters, and event log.

The dashboard is a visualization of the running simulation. In the default
setup, encoding uses the Python golden model; this is not automatically a live
connection to the PYNQ-Z2 FPGA.

## Live video views

- **Camera:** The plain input image before encoding and encryption.
- **On the wire:** The JPEG sent over the link, without the decryption key. It
  may appear scrambled depending on the protection mode.
- **Receiver:** The decrypted output from frames that passed authentication.
  A nearby status badge shows the latest frame verdict.
- **Eavesdropper:** A model-generated best reconstruction from the intercepted
  bytes without the key. This illustrates residual visual leakage; it is not a
  claim about every possible attacker or reconstruction method.

## Graphs

All charts show a rolling **last two minutes**. Hover over a chart to inspect
the nearest point or time window. Amber shading indicates when an attack was
reported as running.

### Receiver frame counts

The stacked timeline groups outcomes by the sender's defence windows (one
second by default):

- **Verified:** Frames accepted after authentication and replay checks.
- **Lost:** Missing frame-counter gaps inferred by the receiver. This is
  different from a received frame that failed authentication.
- **Tag failed / malformed:** Received frames that failed integrity checking
  or could not be parsed as valid secure JPEG frames.
- **Replay / old key:** Frames rejected as replays or because they use an old
  key epoch.

The lower, time-aligned strip shows the selected protection mode, from E0 to
E5. The policy's starting mode is its automatic floor. A manual mode selection
can override the policy's chosen mode.

### Attack evidence

This is a score from 0 to 1 derived from observed evidence, such as integrity
failures, replay attempts, suspicious suppression/loss, forged feedback,
flooding, or missing heartbeats. It is an **evidence score, not a probability**
that an attacker is present. Network loss and deliberate jamming can be
indistinguishable in some cases.

### Frame size on the wire

This plots the JPEG size in kilobytes for successfully verified frames. It is
the frame payload size, not total network traffic including UDP and link
headers.

### End-to-end latency

This plots milliseconds from the sender's frame timestamp to the receiver's
frame handling. It includes simulated transport delay and receiver-side work;
it is not a measurement of camera-to-monitor display latency.

## Status and metrics

### Header

- **Session:** Identifier for the active sender session.
- **Key epoch:** Current ratchet epoch. Rekeying advances the epoch, and the
  receiver erases older epoch keys as it advances.
- **Policy:** Current sender defence policy.
- **Rate:** Measured sender frame rate.
- **Latency:** Most recently reported successful frame latency.
- **Link live:** Indicates recent sender defence-window reports are arriving.
  If reports stop for several seconds, the dashboard marks the link as not
  reporting.

### “So far” counters

- **Frames verified / rejected:** Successful and unsuccessful receiver-frame
  events observed by this browser page. These counters start fresh when the
  page is opened or reloaded.
- **Attacks launched:** Attack-start events observed by this page; this also
  starts the reaction-time measurement.
- **Last reaction time:** Time from the latest observed attack start to the
  first reported increase in protection mode. It stays blank if no increase
  has been observed.
- **Frames attacked, jammed or forged:** Channel-side cumulative total of
  modified, dropped, or injected frames since the channel started. The
  categories can overlap in what they represent, so this is not necessarily a
  count of unique affected frames.
- **Rekeys:** Rekey events observed by this browser page; the count starts
  fresh on page load.

### Protection panel

- **Mode ladder:** Highlights the current mode and marks the configured base
  mode as the automatic floor. The modes progressively encrypt JPEG
  coefficient information: E0 tags but does not encrypt picture data; E1
  encrypts AC signs; E2 adds DC-difference signs; E3 adds AC amplitudes; E4
  adds DC amplitudes; E5 adds keyed block shuffling to E4 in the model.
  E5 is not implemented in the RTL encoder; with the RTL encoder, automatic
  defence is capped at E4. Avoid selecting E5 manually when using RTL.
- **Attack evidence:** The current score described above.
- **Encrypted bits:** Fraction of encoded payload bits encrypted during the
  latest defence window. It is not the percentage of the whole network packet
  and does not include the authentication tag. A hardware board sender may
  report this as unavailable.
- **Encode time:** Sender-reported encoding time per frame. For a board sender,
  this may include FPGA and DMA time.
- **Last heartbeat:** Time since the sender last received valid feedback from
  the receiver.
- **Reason:** The policy's explanation for its latest mode decision. A manual
  override is identified separately.

## Controls

### Attack console

Choose an attack duration and the share of frames it affects, then click an
attack. The buttons cover the video path (bit flip, downgrade, splice, inject,
replay, delay, drop/jam, flood) and feedback path (drop, forge, or replay
feedback). **Stop all attacks** ends active attacks. These are simulated
behaviors, not instructions to attack an external network.

### Defence and network

- **Policy:** *Fixed* stays at the base mode; *Threshold* raises protection in
  response to strong evidence and can hold it after evidence stops; *Learning
  (bandit)* uses experience to choose between modes based on evidence,
  configured leakage, and encryption cost.
- **Protection:** *Automatic* uses the policy's decision. Choosing E0–E5
  applies a manual override, which can select a mode below the automatic
  floor. The current panel and chart show the mode actually selected.
- **Rekey now:** Requests an immediate key ratchet to a new epoch.
- **Packet loss / Delay:** Adjusts channel network impairment independently of
  the attack buttons. Loss is applied to UDP fragments; delay is the channel's
  configured base forwarding delay.
- **Bandit details:** When the bandit policy is active, shows its current
  context, learned mode values, and number of known situations. These are
  internal policy rewards, not direct security measurements.

### Event log

The log summarizes notable events such as attacks starting and ending,
receiver rejections, rekeys, policy changes, and protection-level changes. Use
it with the timeline to connect a graph change to its cause.

## Interpreting results

The dashboard is intended for observing and demonstrating the system
simulation. Outcomes depend on the selected video source, encoder, mode,
policy, channel impairments, and attack settings. Treat the charts as telemetry
from that run—not as standalone security guarantees or paper results.
