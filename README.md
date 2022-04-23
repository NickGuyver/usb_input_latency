The goal of this project is to create a better method for measuring the input latency of USB devices. This is not for measuring end-to-end (physical press to photon) input latency, only input device performance.

There are a lot of other projects that aim to measure input latency in various ways, I had issues with each of them so decided to make my own. The following are my primary goals:

 - Accuracy of measurement above all else
 - Keep as many elements as possible open source
 - Ensure the process is consistent and repeatable
 - Only measure input device latency

In order to more easily define how the measurements in my method differ from others, I have listed the entire input process in a bulleted format to show where each method performs its measurements.

 - 1 physically pushing the button
 - 2 the distance the button must travel
 - 3 impacting the contacts
 - 4 circuit closed
 - 5 process the press (debouncing (hw/sw)/matrix scanning/shift registers/MCU processing)
 - 6 create the usb data
 - 7 send usb data over the wire
 - 8 host process the usb data
 - 9 send the usb data to program
 - 10 program send to screen
 - 11 send screen data over the wire
 - 12 output on the screen

Here is a list of other projects, where they measure, and additional notes from me:

https://twitter.com/jimhejl/status/1045691421594931200
 - Steps 4-11
 - This adds in the processing of the USB data by the host computer and end user programs, and then translated into visual data to be sent as display output. However, this method does remove the latency of the actual display.

https://hci.ur.de/projects/input-device-latency
https://developer.nvidia.com/nvidia-latency-display-analysis-tool
https://www.youtube.com/watch?v=_MaeJbd1xaM&list=PLfOoCUS0PSkVFeagm9C4qjMl0mtikofnz&index=11
 - Steps 4-12
 - Any method that measures pixel changes on a display has a lot of variables which would be very difficult to replicate. The exact settings of the monitor, the firmware revision, the age of the display, and the panel itself are not even consistent within a given specific model number. Unless these are called out in the testing then there is no way for others to verify the results. Additionally, the placement of the sensor itself, which may be altered by the end user program, can also greatly impact the measured latency.
 - This adds in latency for the endpoint to process the USB data by the host computer.
 - The LDAT device appears to be nearly impossible to get.

https://docs.google.com/spreadsheets/d/1KlRObr3Be4zLch7Zyqg6qCJzGuhyGmXaOIUrpfncXIM/edit#gid=1214855193
 - Steps 4-8
 - This adds in latency for the endpoint to process the USB data by the host computer.
 - Alters the host to force a 1 millisecond polling rate which would have inconsistent results with input devices. Some devices may behave differently when polled more frequently than they were designed. There is potential to give advantage to devices which were programmed with a slower bInterval, so they would be faster on a MisTER but slower on anything else.

https://danluu.com/keyboard-latency/
 - Steps 1-7
 - This is limited to USB FS because HS needs a USB protocol analyzer.
 - Measuring the distance required to travel for the button press, as well as the physical pressure needed. This gives an advantage to input devices with minimal press distance. This would skew results where a keyboard may have a better matrix scanning algorithm but a longer key press distance.

https://inputlag.science/
 - Steps 4-8
 - This is very close to my method, and the person here actually mentions leveraging a USB protocol analyzer as an area for improvement.
 - This adds in latency for the endpoint to process the USB data by the host computer, which is an MCU in this instance.
 - For each new input device, you would need to write drivers for Arduino and overtime this would be very cumbersome.
 - Some devices may interact differently based on the host device they are communicating with. One test I'm specifically interested in is if there's a difference in latency for console controllers when comparing them being attached to a user workstation versus a gaming console.
 - When I tested with this method, the lowest possible measurement was 600 microseconds, which is well above the 125 microsecond potential of HS. I do not know if this is a limitation from coding or the relatively weak MCU (compared to a gaming computer).

https://www.rtings.com/mouse/tests/control/latency
 - Steps 1-9
 - This one is a bit different than most because it uses sound where others use sight.
 - This adds in latency for the endpoint to process the USB data by the host computer.
 - Because it is manually reviewed, they only perform 4 tests.

To summarize the above slightly:
 - Methods which process the USB data on the host are going to have added latency from buffering and processing the packet on the host computer.
 - Methods which read the pixels from a display are nearly impossible to replicate.
 - Methods which account for physically pressing the button are outside of this scope. My sole concern is the programming of the input device.

My method:
 - Steps 4-7
 - The quality, condition, and build style of the 3 USB cables needed in the testing method could impact measurements.
 - There could be a difference in the latency between different inputs within a single device. For example, triggers on a gaming controller versus the buttons, or the movement of a mouse versus the buttons. Depending on the scanning method of a keyboard, I could choose a key that is read faster or slower than others.

Description of current method using (link to snes adapter github) as an example:
Testing list:
 - T41: Teensy 4.1 (link to .ino)
 - GP: Modified SNES gamepad (headered wire soldered to right trigger button)
 - T40: SNES to USB adapter (Teensy 4.0, link to .ino)
 - B480: Beagle 480
 - TPDC: Total Phase Data Center (.csv output, link to .csv)
 - PY: .csv parser for Data Center output (Python, link to .py)
 
Connections:
 - T41 pin 32 connected to GP
 - T41 pin 31 connected to B480 INT1 trigger
 - GP connected to T40 over SNES cable
 - T40 connected to target port on B480
 - Host connected to host port on B480
 - Analysis host running TDPC, connected to analysis port on B480
 
How it works:
 - 1 T41 alternates pulling pins 32 and 33, simultaneously, high/low randomly between 400 and 1000 milliseconds.
 - 2 TPDC adds the trigger in from step 1 into the capture interface
 - 3 TDPC adds the USB data IN packet from the controller into the capture interface
 - 4 This is done >1000 times for a large sample size
 - 5 Export the TPDC collected data into a .csv
 - 6 Load the .csv into PY
 - 7 Review PY output for summarized results
 
Notes on testing:
 - 1 400 milliseconds was chosen as the random floor because it was twice the slowest measured latency from the MisTER input latency sheet, nothing should be slower. If you believe your device may be slower than you should increase the random floor, but it will make testing much slower.
 - 1 The pins are pulled simultaneously by leveraging pin registers.
 - 6 The parsing script needs some work. With the XB1 controller I tested, there were a lot of extra IN packets, so I came up with a rough method of trying to only count the correct data.
 
Future goals:
 - Improve button filtering in script, which will be passed on to future improvements
 - Create workflows for open source USB analyzers
   - PhyWhisperer-USB
   - LUNA
   - OpenVizsla
 - Create a simpler setup
   - Leverage USB host on T41 to control and retrieve data from USB analyzers, as if it were an analysis computer.
   - Reprogram open source USB analyzers to remove need for analysis hosts entirely
 - Create an enclosure for measuring wireless dongles
 - Test various USB cable styles from several manufacturers to determine if there is an impact on latency
