Results for devices I've tested are below (https://github.com/NickGuyver/usb_input_latency/tree/main/total_phase/results):
  - Microsoft XBOX Series: https://github.com/NickGuyver/usb_input_latency/tree/main/total_phase/results/045e0b12/20221004/165937
   - Avg: 5ms
 - Microsoft XBOX One: https://github.com/NickGuyver/usb_input_latency/tree/main/total_phase/results/045e02ea/20221004/162911
   - Avg: 7ms
 - 8Bitdo NES30: https://github.com/NickGuyver/usb_input_latency/tree/main/total_phase/results/1235ab12/20221004/164441
   - Avg: 15ms
 - GuliKit KingKong 2 Pro: https://github.com/NickGuyver/usb_input_latency/tree/main/total_phase/results/00790122/20221004/160350
   - Avg: 37ms

Description of current method:
Testing list:
 - RPi: Raspberry Pi 4 Model b running 32-bit Raspberry Pi OS (https://downloads.raspberrypi.org/raspios_armhf/images/raspios_armhf-2022-09-26/2022-09-22-raspios-bullseye-armhf.img.xz)
 - USBD: USB device with headered wire soldered to a button leg
 - B480: Beagle 480
 - TPDC: Total Phase API 5.52 shared object and python library (https://github.com/NickGuyver/usb_input_latency/blob/main/total_phase/beagle.so https://github.com/NickGuyver/usb_input_latency/blob/main/total_phase/beagle_py.py)
 - PY: Testing script (https://github.com/NickGuyver/usb_input_latency/blob/main/total_phase/bg480_collect-raspi.py)
 - pigpio will need to be installed and daemon running for PY to work
 
Connections:
 - RPi pin 20 connected to headered wire on USBD
 - RPi pin 21 connected to B480 INT1 trigger
 - USBD connected to target port on B480
 - Host connected to host port on B480, host can be RPi or anything else that will communicate with the USB device being tested, including consoles
 - RPi connected to analysis port on B480
 
How it works:
 - 1 PY alternates pulling pins 20 and 21, simultaneously, high/low randomly between 400 and 1000 milliseconds.
 - 2 While sending triggers in the background, PY starts the B480
 - 3 B480 collects raw USB packets and sends them to the RPi running PY which reads them in
 - 4 PY does a lot of things to streamline the testing process, see the example run below
 - 5 After running the test, all data, including raw packet collection is dumped into a directory. This allows others to validate that the results provided by PY are true and accurate.
 
Notes on testing:
 - 1 400 milliseconds was chosen as the random floor because it was twice the slowest measured latency from the MisTER input latency sheet, nothing should be slower. If you believe your device may be slower than you should increase the random floor, but it will make testing much slower.
 - 1 The pins are pulled simultaneously by leveraging pin registers.
 - 5 Any feedback I can get on improving the analysis and packet cleaning functions would be greatly appreciated. Every new type of device I tested had a different way of working, so I made it work for all of them but I don't have access to thousands of devices for testing.
 
Future goals:
 - Create workflows for open source USB analyzers
   - PhyWhisperer-USB
   - LUNA
   - OpenVizsla
 - Test various USB cable styles from several manufacturers to determine if there is an impact on latency
 - Get access to a Beagle 5000 for testing USB 3.0
