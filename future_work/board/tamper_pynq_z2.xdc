# tamper_pynq_z2.xdc -- pins of the tamper injector (future_work/board/axis_tamper.v), overlay
# secure_jpeg_lanes_tamper.bit only. PYNQ-Z2 pins from the board's master constraints (Xilinx PYNQ base
# overlay): BTN0-3 D19 D20 L20 L19, SW0-1 M20 M19, LED0-3 R14 P14 N16 M14, PMOD A pin 1 (JA1) Y18.
# All 3.3 V (LVCMOS33): never drive PMOD A from a 5 V board (Arduino Uno) without a level shifter.
set_property -dict {PACKAGE_PIN D19 IOSTANDARD LVCMOS33} [get_ports {btn[0]}]
set_property -dict {PACKAGE_PIN D20 IOSTANDARD LVCMOS33} [get_ports {btn[1]}]
set_property -dict {PACKAGE_PIN L20 IOSTANDARD LVCMOS33} [get_ports {btn[2]}]
set_property -dict {PACKAGE_PIN L19 IOSTANDARD LVCMOS33} [get_ports {btn[3]}]
set_property -dict {PACKAGE_PIN M20 IOSTANDARD LVCMOS33} [get_ports {sw[0]}]
set_property -dict {PACKAGE_PIN M19 IOSTANDARD LVCMOS33} [get_ports {sw[1]}]
set_property -dict {PACKAGE_PIN R14 IOSTANDARD LVCMOS33} [get_ports {led[0]}]
set_property -dict {PACKAGE_PIN P14 IOSTANDARD LVCMOS33} [get_ports {led[1]}]
set_property -dict {PACKAGE_PIN N16 IOSTANDARD LVCMOS33} [get_ports {led[2]}]
set_property -dict {PACKAGE_PIN M14 IOSTANDARD LVCMOS33} [get_ports {led[3]}]
# an open PMOD pin must read 0: pull-down (the Pico drives it high for a shot)
set_property -dict {PACKAGE_PIN Y18 IOSTANDARD LVCMOS33 PULLDOWN true} [get_ports pmod_trig]
# buttons, switches and the trigger are asynchronous (two-flip-flop synchronisers in axis_tamper.v), LEDs are slow
set_false_path -from [get_ports {btn[*] sw[*] pmod_trig}]
set_false_path -to   [get_ports {led[*]}]
