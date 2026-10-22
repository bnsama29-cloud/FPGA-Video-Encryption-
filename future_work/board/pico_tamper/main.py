# main.py -- Raspberry Pi Pico / Pico W (MicroPython): the external "implant" that fires the FPGA tamper
# injector (future_work/board/axis_tamper.v, overlay secure_jpeg_lanes_tamper.bit).
#
# Wiring (3.3 V only, do NOT connect any power pin):
#   Pico GP15 (physical pin 20) --[1 kOhm]--> PYNQ-Z2 PMOD A pin 1 (JA1, FPGA pin Y18, pulled down in the XDC)
#   Pico GND  (physical pin 18) ------------> PYNQ-Z2 PMOD A pin 5 (GND)
# The Pico is powered from the receiver laptop's USB, which also sends the commands, so every shot
# is time-stamped on the same clock as the receiver's frame verdicts (experiments/hw_tamper.py).
#
# Commands on the USB serial port, one per line:
#   S        one shot: 5 ms high pulse on GP15  -> answers "OK <ticks_ms>"
#   B <n> <ms>  burst: n shots, <ms> apart      -> answers "OK <n>"
#   ?        -> answers "PICO-TAMPER 1"
# Copy this file to the Pico as main.py (Thonny: File > Save as > Raspberry Pi Pico), then unplug and
# replug it: it starts on its own and waits for commands.
import sys
import time
import select
from machine import Pin

out = Pin(15, Pin.OUT, value=0)
try:
    led = Pin("LED", Pin.OUT)          # Pico W and recent firmware
except (TypeError, ValueError):
    led = Pin(25, Pin.OUT)             # Pico (older firmware)

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)


def shot():
    out.value(1)
    led.value(1)
    time.sleep_ms(5)
    out.value(0)
    led.value(0)


while True:
    if not poll.poll(200):
        continue
    line = sys.stdin.readline().strip()
    if line == "S":
        shot()
        print("OK", time.ticks_ms())
    elif line.startswith("B"):
        try:
            _, n, gap = line.split()
            for _ in range(int(n)):
                shot()
                time.sleep_ms(int(gap))
            print("OK", n)
        except ValueError:
            print("ERR usage: B <n> <ms>")
    elif line == "?":
        print("PICO-TAMPER 1")
