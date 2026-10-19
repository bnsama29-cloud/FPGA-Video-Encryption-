# Dashboard and VLC LAN demo

This guide serves the simulated link dashboard and its existing MJPEG previews to
another device on the same trusted Wi-Fi/LAN. The dashboard binds to
`127.0.0.1` by default. LAN access is an explicit opt-in; no router port
forwarding is needed or recommended.

## 1. Prepare the host

From the repository root, install the project's Python dependencies if needed:

```powershell
python -m pip install -r requirements.txt
```

The demo uses a synthetic source by default, so no camera is required. Ensure
the host and test phone/laptop are connected to the same private Wi-Fi/LAN.
Avoid public or untrusted networks: the dashboard has interactive controls and
does not provide user authentication or HTTPS.

## 2. Start the simulation for LAN access

In PowerShell or Command Prompt:

```powershell
python -m link.run_all --set dashboard.bind_host=0.0.0.0
```

This starts the sender, simulated network/attacker, receiver and dashboard. The
dashboard remains available locally at `http://localhost:8000`; `0.0.0.0` is
the listener address, not an address to enter in a browser. To run without LAN
access, omit the override; the dashboard then listens only on localhost.

Stop the simulation with **Ctrl+C** in this terminal.

## 3. Find the host's LAN IPv4 address

On Windows, run:

```powershell
ipconfig
```

Find the active Wi-Fi adapter's **IPv4 Address** (for example,
`192.168.1.24`). Do not use the VPN, virtual-machine or disconnected adapter
address. On Linux, `hostname -I` or `ip -4 addr` can help identify the active
LAN address.

From the second device, open:

```text
http://<host-LAN-IP>:8000
```

For example: `http://192.168.1.24:8000`.

## 4. Windows Firewall and WSL notes

- If Windows Firewall prompts for Python, allow it only on **Private** networks.
  If access is still blocked, add an inbound TCP rule for port 8000 restricted
  to the Private profile and local subnet. In an elevated PowerShell:

  ```powershell
  New-NetFirewallRule -DisplayName "FPGA video dashboard (private LAN)" `
    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 `
    -Profile Private -RemoteAddress LocalSubnet
  ```

  Remove that named rule after the demo if it is no longer needed:

  ```powershell
  Remove-NetFirewallRule -DisplayName "FPGA video dashboard (private LAN)"
  ```

- If the simulation runs in **WSL2**, its NAT network commonly makes the
  service reachable from Windows itself but not directly from other LAN
  devices. First try WSL's supported mirrored networking mode, if available
  with the installed Windows/WSL version. Otherwise forward a Windows LAN
  address to the WSL service and keep the Windows firewall rule scoped to the
  private local subnet. This requires an elevated terminal and the WSL guest IP:

  ```powershell
  # In WSL: hostname -I
  # In Windows (replace both addresses with the active adapter / WSL addresses):
  netsh interface portproxy add v4tov4 listenaddress=<WINDOWS-LAN-IP> `
    listenport=8000 connectaddress=<WSL-IP> connectport=8000
  ```

  The WSL dashboard must itself be started with
  `--set dashboard.bind_host=0.0.0.0`. Port-proxy rules may need updating
  after WSL restarts because its NAT IP can change. Remove a temporary mapping
  with:

  ```powershell
  netsh interface portproxy delete v4tov4 listenaddress=<WINDOWS-LAN-IP> listenport=8000
  ```

- Do not create a router/Internet port-forwarding rule. Do not enable the
  firewall rule for Public networks or open all ports. If you cannot restrict
  access to a trusted private LAN, use localhost only.

## 5. Open the dashboard and inspect the views

On the remote device, load `http://<host-LAN-IP>:8000`. With the default
synthetic sender running, expect:

- **Camera:** plain input frames.
- **On the wire:** the valid JPEG/MJPEG stream after selective encryption
  (scrambled without the receiver's key).
- **Receiver:** frames accepted and verified by the receiver.
- **Eavesdropper:** the attacker's reconstruction, after the channel has
  generated previews.
- **Statistics and charts:** verified/rejected frame counts, attacks, rekeys,
  current protection mode, threat evidence, frame size and latency.
- **Event log and controls:** status events should continue to arrive. Attack,
  stop, policy, mode, rekey and network impairment controls should issue the
  same commands as on the host's local dashboard.

The display can take a few seconds to populate. The sender's
`preview_every` settings control how often images are published. Check the
browser connection indicator and host terminal if the view is empty.

The dashboard uses same-origin HTTP requests and event streams, so opening it
at the host's LAN URL keeps its page, event log, controls and image streams on
the same origin. The endpoints are:

```text
http://<host-LAN-IP>:8000/stream/camera.mjpg
http://<host-LAN-IP>:8000/stream/wire.mjpg
http://<host-LAN-IP>:8000/stream/receiver.mjpg
http://<host-LAN-IP>:8000/stream/attacker.mjpg
```

## 6. Open the wire stream in VLC

On the remote device, in VLC select **Media → Open Network Stream** (or
**Open Network**) and enter:

```text
http://<host-LAN-IP>:8000/stream/wire.mjpg
```

Select **Play**. VLC should display the ongoing JPEG frames on the wire. If
desired, repeat with `/stream/camera.mjpg` or `/stream/receiver.mjpg` to inspect
the other two views. These endpoints already exist in the dashboard server;
this guide does not add another media server or change the JPEG/security
protocol.

## 7. Troubleshooting

| Symptom | Checks |
|---|---|
| Local dashboard works, remote browser times out | Confirm the `dashboard.bind_host=0.0.0.0` override; use the host's active LAN IPv4 address; check both devices are on the same network, Windows Firewall Private-profile rule, VPN/client isolation, and WSL2 networking. |
| Page loads but views/statistics stay empty | Keep `run_all` running; confirm the sender is active and previews are enabled; check that the dashboard's event connection is not reporting a disconnect. |
| Dashboard works but VLC is blank | Try the exact `/stream/wire.mjpg` URL in a browser first; wait for sender frames; check firewall TCP 8000. VLC behavior varies by version and must be confirmed on the demo device. |
| VLC or browser reports connection refused | Confirm the server is running and listening on port 8000; check if another process already owns the port. |
| WSL2 host itself can browse but phone cannot | This is commonly WSL2 NAT rather than an application issue. Use supported mirrored networking or the scoped Windows port-proxy procedure above. |
| Port 8000 already in use | Stop the other service or choose another `dashboard.http_port` consistently, then use that port in the firewall rule and URLs. |

## Verification boundary

Automated tests can check the HTTP page, JSON state, server-sent events,
dashboard control forwarding, still-image route, and multipart MJPEG payloads
for camera, wire, receiver and attacker views. They cannot prove that a
particular Windows firewall, WSL mode, Wi-Fi access-point policy, phone browser
or VLC build permits the connection. Those require a live second-device and
VLC demonstration.
