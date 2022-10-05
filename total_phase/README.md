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
   - 1 Collect the USB device details with lsusb
   - 2 Runs 10 test triggers and tries to figure out what good data packets look like, then saves the "on" data packet details
   - 3 Runs some number of tests, filtering out data packets that are out of order or do not match the previously determined good packets
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

Example usage:
```
pi@raspberrypi:~/Desktop/total_phase $ sudo python3 bg480_collect-raspi.py 
===================
-----Main Menu-----
===================
Output Directory - /home/pi/Desktop/total_phase/UNKNOWN/20221004

1 - Device Info
2 - Output Settings
3 - Test Button
4 - Test Latency
5 - Exit
===================

Enter Choice #1


==========================
-----Device Info Menu-----
==========================
Device ID - :
Manufacturer - 
Product - 
Version - 
Serial - 

1 - Manually Enter USB Details
2 - Pull USB details with lsusb
3 - Return to Main Menu
==========================

Enter Choice #2
1 - Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
2 - Bus 001 Device 009: ID 0461:4e67 Primax Electronics, Ltd HP USB Multimedia Keyboard
3 - Bus 001 Device 084: ID 413c:301a Dell Computer Corp. Dell MS116 Optical Mouse
4 - Bus 001 Device 090: ID 045e:0b12 Microsoft Corp. Controller
5 - Bus 001 Device 071: ID 1679:2001 Total Phase Beagle Protocol Analyzer
6 - Bus 001 Device 002: ID 2109:3431 VIA Labs, Inc. Hub
7 - Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub

Choose USB device: 4


==========================
-----Device Info Menu-----
==========================
Device ID - 045e:0b12
Manufacturer - Microsoft
Product - Controller
Version - 5.09
Serial - 3039373030303739393933323132

1 - Manually Enter USB Details
2 - Pull USB details with lsusb
3 - Return to Main Menu
==========================

Enter Choice #3



===================
-----Main Menu-----
===================
Output Directory - /home/pi/Desktop/total_phase/045e0b12/20221004

1 - Device Info
2 - Output Settings
3 - Test Button
4 - Test Latency
5 - Exit
===================

Enter Choice #3


==========================
-----Test Button Menu-----
==========================
Device ID - 045e:0b12
Manufacturer - Microsoft
Product - Controller
Version - 5.09
Serial - 3039373030303739393933323132
Trigger Button Position: 
Trigger Button Value: 
Trigger Button Packet Length: 0
Trigger Button Name: 

1 - Manually Enter Trigger Button Details
2 - Automatically Find Trigger Button Details
3 - Return to Main Menu
==========================

Enter Choice #2
Enter Trigger Button Name (eg., A, B, X,...): RB

Running 10 test triggers to find trigger button details...

Start triggering...

Connect to analyzer...

Opened Beagle device on port 0
Sampling rate set to 60000 KHz.
Idle timeout set to 500 ms.
Latency set to 2000 ms.
Host interface is high speed.
Configuring digital input with 1

Start USB collection...

time(ns),pid,data0 ... dataN(*)
786837750,TRIGGER_OFF
793184466,DATA0,c3 20 00 0a 2c 00 00 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1b d8 b2 01 f8 da b2 01 88 19 
1256412683,TRIGGER_ON
1261245000,DATA1,4b 20 00 0b 2c 00 20 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 28 06 ba 01 05 09 ba 01 fc dc 
1964445316,TRIGGER_OFF
1973337050,DATA0,c3 20 00 0c 2c 00 00 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 90 e3 c4 01 4e e6 c4 01 e3 50 
2677427983,DATA1,4b 03 20 0c 04 83 01 00 00 57 6b 
2815758250,TRIGGER_ON
2821446650,DATA0,c3 20 00 0d 2c 00 20 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 c6 d4 d1 01 84 d7 d1 01 8d d3 
3286480600,TRIGGER_OFF
3962497033,TRIGGER_ON
3965594466,DATA0,c3 20 00 0f 2c 00 20 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 0a 4a e3 01 e7 4c e3 01 a1 df 
4586399350,TRIGGER_OFF
4589675083,DATA1,4b 20 00 10 2c 00 00 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 e3 cf ec 01 a1 d2 ec 01 ea 0e 
5426343450,TRIGGER_ON
5429783600,DATA0,c3 20 00 11 2c 00 20 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 7c a1 f9 01 3a a4 f9 01 21 5b 
6227189883,TRIGGER_OFF
6229886966,DATA1,4b 20 00 12 2c 00 00 00 00 00 00 dd 00 aa 01 59 ff 51 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 cf d6 05 02 8d d9 05 02 65 a1 
6932247133,TRIGGER_ON

Done. Stopping triggers and collection.



==========================
-----Test Button Menu-----
==========================
Device ID - 045e:0b12
Manufacturer - Microsoft
Product - Controller
Version - 5.09
Serial - 3039373030303739393933323132
Trigger Button Position: 7
Trigger Button Value: 20
Trigger Button Packet Length: 51
Trigger Button Name: RB

1 - Manually Enter Trigger Button Details
2 - Automatically Find Trigger Button Details
3 - Return to Main Menu
==========================

Enter Choice #3



===================
-----Main Menu-----
===================
Output Directory - /home/pi/Desktop/total_phase/045e0b12/20221004

1 - Device Info
2 - Output Settings
3 - Test Button
4 - Test Latency
5 - Exit
===================

Enter Choice #4


===========================
-----Test Latency Menu-----
===========================
Trigger Button Position: 7
Trigger Button Value: 20
Trigger Button Packet Length: 51

1 - Run 25 Tests (~18s)
2 - Run 100 Tests (~1m10s)
3 - Run 500 Tests (~5m50s)
4 - Run 1000 Tests (~11m40s)
5 - Return to Main Menu
===========================

Enter Choice #1

Running 25 test triggers...

Start triggering...

Connect to analyzer...

Opened Beagle device on port 0
Sampling rate set to 60000 KHz.
Idle timeout set to 500 ms.
Latency set to 2000 ms.
Host interface is high speed.
Configuring digital input with 1

Start USB collection...

20% complete
40% complete
60% complete
80% complete

Done. Stopping triggers and collection.

Elapsed time to collect 25 packets - 17.85s.


Saving raw collection to /home/pi/Desktop/total_phase/045e0b12/20221004/164745/raw_output.txt

Cleaning collected packets, and analyzing...

Done.

Saving cleaned collection to /home/pi/Desktop/total_phase/045e0b12/20221004/164745/clean_output.txt


22 clean times collected, out of 25 triggers sent.

Results:
	Min - 2.0757 ms
	Max - 9.424266 ms
	Avg - 5.346689545454546 ms
	StDev - 2.0000294713037587 ms

Saving results to /home/pi/Desktop/total_phase/045e0b12/20221004/164745/results-25.txt



===========================
-----Test Latency Menu-----
===========================
Trigger Button Position: 7
Trigger Button Value: 20
Trigger Button Packet Length: 51

1 - Run 25 Tests (~18s)
2 - Run 100 Tests (~1m10s)
3 - Run 500 Tests (~5m50s)
4 - Run 1000 Tests (~11m40s)
5 - Return to Main Menu
===========================

Enter Choice #4

Running 1000 test triggers...

Start triggering...

Connect to analyzer...

Opened Beagle device on port 0
Sampling rate set to 60000 KHz.
Idle timeout set to 500 ms.
Latency set to 2000 ms.
Host interface is high speed.
Configuring digital input with 1

Start USB collection...

10% complete
20% complete
30% complete
40% complete
50% complete
60% complete
70% complete
80% complete
90% complete

Done. Stopping triggers and collection.

Elapsed time to collect 1000 packets - 700.86s.


Saving raw collection to /home/pi/Desktop/total_phase/045e0b12/20221004/165937/raw_output.txt

Cleaning collected packets, and analyzing...

Done.

Saving cleaned collection to /home/pi/Desktop/total_phase/045e0b12/20221004/165937/clean_output.txt


806 clean times collected, out of 1000 triggers sent.

Results:
	Min - 1.451184 ms
	Max - 10.487116 ms
	Avg - 5.504124062034739 ms
	StDev - 2.2455031977956175 ms

Saving results to /home/pi/Desktop/total_phase/045e0b12/20221004/165937/results-1000.txt



===========================
-----Test Latency Menu-----
===========================
Trigger Button Position: 7
Trigger Button Value: 20
Trigger Button Packet Length: 51

1 - Run 25 Tests (~18s)
2 - Run 100 Tests (~1m10s)
3 - Run 500 Tests (~5m50s)
4 - Run 1000 Tests (~11m40s)
5 - Return to Main Menu
===========================

Enter Choice #5
===================
-----Main Menu-----
===================
Output Directory - /home/pi/Desktop/total_phase/045e0b12/20221004

1 - Device Info
2 - Output Settings
3 - Test Button
4 - Test Latency
5 - Exit
===================

Enter Choice #5
```
