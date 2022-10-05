#!/usr/bin/env python3
#==========================================================================
# IMPORTS
#==========================================================================
import multiprocessing
import os
import time

from beagle_py import *

#==========================================================================
# GLOBALS
#==========================================================================
beagle = 0
samplerate_khz = 0
IDLE_THRESHOLD = 2000
current_datetime = time.strftime("%Y%m%d", time.localtime())
output_dir = f'{os.getcwd()}/UNKNOWN/{current_datetime}'

# Packet groups
SOF = 0
IN_ACK = 1
IN_NAK = 2
PING_NAK = 3
SPLIT_IN_ACK = 4
SPLIT_IN_NYET = 5
SPLIT_IN_NAK = 6
SPLIT_OUT_NYET = 7
SPLIT_SETUP_NYET = 8
KEEP_ALIVE = 9

# States used in collapsing state machine
IDLE = 0
IN = 1
PING = 3
SPLIT = 4
SPLIT_IN = 5
SPLIT_OUT = 7
SPLIT_SETUP = 8

# Size of packet queue.  At most this many packets will need to be alive
# at the same time.
QUEUE_SIZE = 3

# Disable COMBINE_SPLITS by setting to False.  Disabling
# will show individual split counts for each group (such as
# SPLIT/IN/ACK, SPLIT/IN/NYET, ...).  Enabling will show all the
# collapsed split counts combined.
COMBINE_SPLITS = True


##==========================================================================
# CLASSES
##==========================================================================
class TestedDevice:
    vendor_id = ''
    product_id = ''
    manufacturer = ''
    product = ''
    version = ''
    serial = ''
    trigger_byte = ''
    trigger_position = ''
    trigger_length = 0
    trigger_name = ''


class PacketInfo:
    def __init__(self):
        self.data = array_u08(1024)
        self.time_sop = 0
        self.time_sop_ns = 0
        self.time_duration = 0
        self.time_dataoffset = 0
        self.status = 0
        self.events = 0
        self.length = 0

# Used to store the packets that are saved during the collapsing
# process.  The tail of the queue is always used to store
# the current packet.
class PacketQueue:
    def __init__(self):
        self._tail = 0
        self._head = 0
        self.pkt = [PacketInfo() for i in range(QUEUE_SIZE)]

    def __getattr__(self, attr):
        if attr == 'tail':
            return self.pkt[self._tail]
        if attr == 'head':
            return self.pkt[self._head]
        raise AttributeError("%s not an attribute of PacketQueue" % attr)

    def save_packet(self):
        self._tail = (self._tail + 1) % QUEUE_SIZE

    def is_empty(self):
        return self._tail == self._head

    # Clear the queue. If requested, return the dequeued elements.
    def clear(self, dequeue=False):
        if not dequeue:
            self._head = self._tail
            return []

        pkts = []
        while self._head != self._tail:
            pkts.append(self.pkt[self._head])
            self._head = (self._head + 1) % QUEUE_SIZE
        return pkts

class CollapseInfo:
    def __init__(self):
        # Timestamp when collapsing begins
        self.time_sop = 0
        # The number of packets collapsed for each packet group
        self.count = {SOF: 0, PING_NAK: 0, IN_ACK: 0, IN_NAK: 0, SPLIT_IN_ACK: 0, SPLIT_IN_NYET: 0, SPLIT_IN_NAK: 0,
                      SPLIT_OUT_NYET: 0, SPLIT_SETUP_NYET: 0, KEEP_ALIVE: 0}

    def clear(self):
        self.time_sop = 0
        for k in self.count:
            self.count[k] = 0


##==========================================================================
# UTILITY FUNCTIONS
##==========================================================================
def open_beagle():
    # Open the device
    global beagle
    
    port = 0      # open port 0 by default
    samplerate = 0      # in kHz (query)
    timeout = 500    # 500 in milliseconds
    latency = 2000    # 2000 in milliseconds
    
    beagle = bg_open(port)
    if beagle <= 0:
        print("Unable to open Beagle device on port %d" % port)
        print("Error code = %d" % beagle)
        sys.exit(1)

    print("Opened Beagle device on port %d" % port)

    # Query the samplerate since Beagle USB has a fixed sampling rate
    samplerate = bg_samplerate(beagle, samplerate)
    if samplerate < 0:
        print("error: %s" % bg_status_string(samplerate))
        sys.exit(1)

    print("Sampling rate set to %d KHz." % samplerate)

    # Set the idle timeout.
    # The Beagle read functions will return in the specified time
    # if there is no data available on the bus.
    bg_timeout(beagle, timeout)
    print("Idle timeout set to %d ms." % timeout)

    # Set the latency.
    # The latency parameter allows the programmer to balance the
    # tradeoff between host side buffering and the latency to
    # receive a packet when calling one of the Beagle read
    # functions.
    bg_latency(beagle, latency)
    print("Latency set to %d ms." % latency)

    print("Host interface is %s." % (bg_host_ifce_speed(beagle) and "high speed" or "full speed"))

    # Set up the digital input and output lines.
    #setup_digital_lines()
    input_enable_mask = BG_USB2_DIGITAL_IN_ENABLE_PIN1

    # Enable digital input pins
    bg_usb2_digital_in_config(beagle, input_enable_mask)
    print('Configuring digital input with %s' % input_enable_mask)

    print("")
    sys.stdout.flush()
    
    
def timestamp_to_ns(stamp):
    return (stamp * 1000) // (samplerate_khz // 1000)


def print_general_status(status):
    """ General status codes """

    if status == BG_READ_OK:
        print("OK", end=' ')
    if status & BG_READ_TIMEOUT:
        print("TIMEOUT", end=' ')
    if status & BG_READ_ERR_UNEXPECTED:
        print("UNEXPECTED", end=' ')
    if status & BG_READ_ERR_MIDDLE_OF_PACKET:
        print("MIDDLE", end=' ')
    if status & BG_READ_ERR_SHORT_BUFFER:
        print("SHORT BUFFER", end=' ')
    if status & BG_READ_ERR_PARTIAL_LAST_BYTE:
        print("PARTIAL_BYTE(bit %d)" % (status & 0xff), end=' ')


def print_usb_status(status):
    """USB status codes"""
    if status & BG_READ_USB_ERR_BAD_SIGNALS:
        print("BAD_SIGNAL;", end=' ')
    if status & BG_READ_USB_ERR_BAD_SYNC:
        print("BAD_SYNC;", end=' ')
    if status & BG_READ_USB_ERR_BIT_STUFF:
        print("BAD_STUFF;", end=' ')
    if status & BG_READ_USB_ERR_FALSE_EOP:
        print("BAD_EOP;", end=' ')
    if status & BG_READ_USB_ERR_LONG_EOP:
        print("LONG_EOP;", end=' ')
    if status & BG_READ_USB_ERR_BAD_PID:
        print("BAD_PID;", end=' ')
    if status & BG_READ_USB_ERR_BAD_CRC:
        print("BAD_CRC;", end=' ')
    if status & BG_READ_USB_TRUNCATION_MODE:
        print("TRUNCATION_MODE;", end=' ')
    if status & BG_READ_USB_END_OF_CAPTURE:
        print("END_OF_CAPTURE;", end=' ')


def print_usb_events(events):
    """USB event codes"""
    if events & BG_EVENT_USB_HOST_DISCONNECT:
        print("HOST_DISCON;", end=' ')
    if events & BG_EVENT_USB_TARGET_DISCONNECT:
        print("TGT_DISCON;", end=' ')
    if events & BG_EVENT_USB_RESET:
        print("RESET;", end=' ')
    if events & BG_EVENT_USB_HOST_CONNECT:
        print("HOST_CONNECT;", end=' ')
    if events & BG_EVENT_USB_TARGET_CONNECT:
        print("TGT_CONNECT/UNRST;", end=' ')
    if events & BG_EVENT_USB_DIGITAL_INPUT:
        print("INPUT_TRIGGER %X" % (events & BG_EVENT_USB_DIGITAL_INPUT_MASK), end=' ')
    if events & BG_EVENT_USB_CHIRP_J:
        print("CHIRP_J; ", end=' ')
    if events & BG_EVENT_USB_CHIRP_K:
        print("CHIRP_K; ", end=' ')
    if events & BG_EVENT_USB_KEEP_ALIVE:
        print("KEEP_ALIVE; ", end=' ')
    if events & BG_EVENT_USB_SUSPEND:
        print("SUSPEND; ", end=' ')
    if events & BG_EVENT_USB_RESUME:
        print("RESUME; ", end=' ')
    if events & BG_EVENT_USB_LOW_SPEED:
        print("LOW_SPEED; ", end=' ')
    if events & BG_EVENT_USB_FULL_SPEED:
        print("FULL_SPEED; ", end=' ')
    if events & BG_EVENT_USB_HIGH_SPEED:
        print("HIGH_SPEED; ", end=' ')
    if events & BG_EVENT_USB_SPEED_UNKNOWN:
        print("UNKNOWN_SPEED; ", end=' ')
    if events & BG_EVENT_USB_LOW_OVER_FULL_SPEED:
        print("LOW_OVER_FULL_SPEED; ", end=' ')


def usb_print_summary(i, count_sop, summary):
    print("usb_print_summary")
    count_sop_ns = timestamp_to_ns(count_sop)
    print("%d,%u,USB,( ),%s" % (i, count_sop_ns, summary))


##==========================================================================
# USB DUMP FUNCTIONS
##==========================================================================
# Renders packet data for printing.
def usb_print_data_packet(packet, length):
    packetstring = ""

    if length == 0:
        return packetstring

    # Get the packet identifier
    pid = packet[0]

    # Print the packet identifier
    if pid == BG_USB_PID_OUT:
        pidstr = "OUT"
    elif pid == BG_USB_PID_IN:
        pidstr = "IN"
    elif pid == BG_USB_PID_SOF:
        pidstr = "SOF"
    elif pid == BG_USB_PID_SETUP:
        pidstr = "SETUP"
    elif pid == BG_USB_PID_DATA0:
        pidstr = "DATA0"
    elif pid == BG_USB_PID_DATA1:
        pidstr = "DATA1"
    elif pid == BG_USB_PID_DATA2:
        pidstr = "DATA2"
    elif pid == BG_USB_PID_MDATA:
        pidstr = "MDATA"
    elif pid == BG_USB_PID_ACK:
        pidstr = "ACK"
    elif pid == BG_USB_PID_NAK:
        pidstr = "NAK"
    elif pid == BG_USB_PID_STALL:
        pidstr = "STALL"
    elif pid == BG_USB_PID_NYET:
        pidstr = "NYET"
    elif pid == BG_USB_PID_PRE:
        pidstr = "PRE"
    elif pid == BG_USB_PID_SPLIT:
        pidstr = "SPLIT"
    elif pid == BG_USB_PID_PING:
        pidstr = "PING"
    elif pid == BG_USB_PID_EXT:
        pidstr = "EXT"
    else:
        pidstr = "INVALID"

    packetstring += pidstr + ","

    # Print the packet data
    for n in range(length):
        packetstring += "%02x " % packet[n]

    return packetstring

# Print common packet header information
#BG_USB_PID_IN = 0x69
#BG_USB_PID_DATA0 = 0xc3
#BG_USB_PID_DATA1 = 0x4b
#BG_USB_PID_DATA2 = 0x87
def usb_print_packet(packet, error_status, find_caller):
    if error_status == 0:
        error_status = ""
        packet_data = usb_print_data_packet(packet.data, packet.length)
    else:
        packet_data = ""

    # Only collect trigger and data packets
    # 0x00800000 is the value when digital input is released
    if packet.events in (BG_EVENT_USB_DIGITAL_INPUT, 0x00800001):
        if packet.events == BG_EVENT_USB_DIGITAL_INPUT:
            if find_caller:
                print('%s,TRIGGER_ON' % packet.time_sop_ns)
            return f'{packet.time_sop_ns},{packet.length},TRIGGER_ON'
            
        else:
            if find_caller:
                print('%s,TRIGGER_OFF' % packet.time_sop_ns)
            return f'{packet.time_sop_ns},{packet.length},TRIGGER_OFF'
    
    elif packet.data[0] in (BG_USB_PID_DATA0, BG_USB_PID_DATA1):
        if find_caller:
            print('%s,%s' % (packet.time_sop_ns, packet_data))
        return f'{packet.time_sop_ns},{packet.length},{packet_data}'
    
    sys.stdout.flush()

# Dump saved summary information
def usb_print_summary_packet(packet_number, collapse_info, signal_errors):
    offset = 0
    summary = ""

    counts = [collapse_info.count[key] for key in collapse_info.count if collapse_info.count[key] > 0]

    if len(counts) > 0:
        summary += "COLLAPSED "

        if collapse_info.count[KEEP_ALIVE] > 0:
            summary += "[%d KEEP-ALIVE] " %  \
                       collapse_info.count[KEEP_ALIVE]

        if collapse_info.count[SOF] > 0:
            summary += "[%d SOF] " %  \
                       collapse_info.count[SOF]

        if collapse_info.count[IN_ACK] > 0:
            summary += "[%d IN/ACK] " % \
                       collapse_info.count[IN_ACK]

        if collapse_info.count[IN_NAK] > 0:
            summary += "[%d IN/NAK] " % \
                       collapse_info.count[IN_NAK]

        if collapse_info.count[PING_NAK] > 0:
            summary += "[%d PING/NAK] " % \
                       collapse_info.count[PING_NAK]

        if COMBINE_SPLITS:
            split_count = collapse_info.count[SPLIT_IN_ACK] + \
                          collapse_info.count[SPLIT_IN_NYET] + \
                          collapse_info.count[SPLIT_IN_NAK] + \
                          collapse_info.count[SPLIT_OUT_NYET] + \
                          collapse_info.count[SPLIT_SETUP_NYET]

            if split_count > 0:
                summary += "[%d SPLITS] " % split_count
        else:
            if collapse_info.count[SPLIT_IN_ACK] > 0:
                summary += "[%d SPLIT/IN/ACK] " % \
                           collapse_info.count[SPLIT_IN_ACK]

            if collapse_info.count[SPLIT_IN_NYET] > 0:
                summary += "[%d SPLIT/IN/NYET] " % \
                           collapse_info.count[SPLIT_IN_NYET]

            if collapse_info.count[SPLIT_IN_NAK] > 0:
                summary += "[%d SPLIT/IN/NAK] " % \
                           collapse_info.count[SPLIT_IN_NAK]

            if collapse_info.count[SPLIT_OUT_NYET] > 0:
                summary += "[%d SPLIT/OUT/NYET] " % \
                           collapse_info.count[SPLIT_OUT_NYET]

            if collapse_info.count[SPLIT_SETUP_NYET] > 0:
                summary += "[%d SPLIT/SETUP/NYET] " % \
                           collapse_info.count[SPLIT_SETUP_NYET]

        offset += 1

    # Output any signal errors
    if signal_errors > 0:
        summary += "<%d SIGNAL ERRORS>" % signal_errors
        offset += 1

    collapse_info.clear()
    
    return packet_number, 0

# Outputs any packets saved during the collapsing process
def output_saved(packetnum, signal_errors, collapse_info, pkt_q, find_caller):
    (packetnum, signal_errors) = \
                usb_print_summary_packet(packetnum, collapse_info,
                                         signal_errors)

    pkts = pkt_q.clear(dequeue=True)

    for pkt in pkts:
        usb_print_packet(pkt, 0, find_caller)

    return packetnum, signal_errors

# Collapses a group of packets.  This involves incrementing the group
# counter and clearing the queue. If this is the first group to
# be collapsed, the collapse time needs to be set, which marks when
# this collapsing began.
def collapse(group, collapse_info, pkt_q):
    collapse_info.count[group] += 1

    if collapse_info.time_sop == 0:
        if not pkt_q.is_empty:
            collapse_info.time_sop = pkt_q.head.time_sop
        else:
            collapse_info.time_sop = pkt_q.tail.time_sop

    pkt_q.clear()

# The main packet dump routine
def usb_dump(num_packets):
    import inspect
    
    packet_collection = []
    completion = [90, 80, 70, 60, 50, 40, 30, 20, 10]
    
    # Only print raw packets from find_trigger() function, to help debug weird devices
    if 'find_trigger' in inspect.stack()[1][3]:
        find_caller = True
    else:
        find_caller = False
    
    # Start trggering function in the background
    if __name__ == "__main__":
        print('Start triggering...\n')
        
        trigger_process = multiprocessing.Process(target=trigger_on)
        
        trigger_process.start()
    
    print('Connect to analyzer...\n')
    open_beagle()
    
    # Collapsing counts and the time the collapsing started
    collapse_info = CollapseInfo()

    # Packets are saved during the collapsing process
    pkt_q = PacketQueue()

    signal_errors = 0
    packetnum = 0

    # Collapsing packets is handled through a state machine.
    # IDLE is the initial state.
    state = IDLE

    global samplerate_khz
    samplerate_khz = bg_samplerate(beagle, 0)
    idle_samples = IDLE_THRESHOLD * samplerate_khz

    # Configure Beagle 480 for realtime capture
    bg_usb2_capture_config(beagle, BG_USB2_CAPTURE_REALTIME)
    bg_usb2_target_config(beagle, BG_USB2_AUTO_SPEED_DETECT)
    bg_usb_configure(beagle, BG_USB_CAPTURE_USB2, BG_USB_TRIGGER_MODE_IMMEDIATE)

    # Filter out our own packets.  This is only relevant when
    # one host controller is used.
    bg_usb2_hw_filter_config(beagle, BG_USB2_HW_FILTER_SELF)

    # Open the connection to the Beagle.  Default to port 0.
    if bg_enable(beagle, BG_PROTOCOL_USB) != BG_OK:
        print("error: could not enable USB capture; exiting...")
        sys.exit(1)

    print('Start USB collection...\n')
    
    # Output the header...
    if find_caller:
        print('time(ns),pid,data0 ... dataN(*)')
        sys.stdout.flush()

    # ...then start decoding packets
    while packetnum < num_packets:
        if not find_caller:
            packet_tracker = round((packetnum / num_packets) * 100)
            
            if packet_tracker in completion:
                print(f'{packet_tracker}% complete')
                completion.remove(packet_tracker)
        
        # Info for the current packet
        cur_packet = pkt_q.tail

        (cur_packet.length, cur_packet.status, cur_packet.events, cur_packet.time_sop, cur_packet.time_duration,
         cur_packet.time_dataoffset, cur_packet.data) = bg_usb2_read(beagle, cur_packet.data)

        cur_packet.time_sop_ns = timestamp_to_ns(cur_packet.time_sop)

        # Exit if observed end of capture
        if cur_packet.status & BG_READ_USB_END_OF_CAPTURE:
            usb_print_summary_packet(packetnum, collapse_info, signal_errors)

            break

        # Check for invalid packet or Beagle error
        if cur_packet.length < 0:
            error_status = "error=%d" % cur_packet.length
            usb_print_packet(cur_packet, error_status, find_caller)

            break

        # Check for USB error
        if cur_packet.status == BG_READ_USB_ERR_BAD_SIGNALS:
            signal_errors += 1

        # Set the PID for collapsing state machine below.  Treat
        # KEEP_ALIVEs as packets.
        if cur_packet.length > 0:
            pid = cur_packet.data[0]
        elif cur_packet.events & BG_EVENT_USB_KEEP_ALIVE and not cur_packet.status & BG_READ_USB_ERR_BAD_PID:
            pid = KEEP_ALIVE
        else:
            pid = 0

        # Collapse these packets appropriately:
        # SOF* (IN (ACK|NAK))* (PING NAK)*
        # (SPLIT (OUT|SETUP) NYET)* (SPLIT IN (ACK|NYET|NACK))*

        # If the time elapsed since collapsing began is greater than
        # the threshold, output the counts and zero out the counters.
        if cur_packet.time_sop - collapse_info.time_sop >= idle_samples:
            (packetnum, signal_errors) = \
                usb_print_summary_packet(packetnum, collapse_info,
                                         signal_errors)

        while True:
            
            re_run = False

            # The initial state of the state machine.  Collapse SOFs
            # and KEEP_ALIVEs.  Save IN, PING, or SPLIT packets and
            # move to the next state for the next packet.  Otherwise,
            # print the collapsed packet counts and the current packet.
            if state == IDLE:
                if pid == KEEP_ALIVE:
                    collapse(KEEP_ALIVE, collapse_info, pkt_q)
                elif pid == BG_USB_PID_SOF:
                    collapse(SOF, collapse_info, pkt_q)
                elif pid == BG_USB_PID_IN:
                    pkt_q.save_packet()
                    state = IN
                elif pid == BG_USB_PID_PING:
                    pkt_q.save_packet()
                    state = PING
                elif pid == BG_USB_PID_SPLIT:
                    pkt_q.save_packet()
                    state = SPLIT
                else:
                    (packetnum, signal_errors) = \
                                usb_print_summary_packet(packetnum,
                                                         collapse_info,
                                                         signal_errors)

                    if (cur_packet.length > 0 or cur_packet.events or
                        (cur_packet.status != 0 and
                         cur_packet.status != BG_READ_TIMEOUT)):

                        # Send to packet collector if testing button
                        # Only increment counter if a trigger is seen
                        if cur_packet.events in (BG_EVENT_USB_DIGITAL_INPUT, 0x00800001):
                            packet_collection.append(usb_print_packet(cur_packet, 0, find_caller))
                            packetnum += 1
                        
                        # We still want to collect data packets
                        elif cur_packet.data[0] in (BG_USB_PID_DATA0, BG_USB_PID_DATA1):
                            packet_collection.append(usb_print_packet(cur_packet, 0, find_caller))

            # Collapsing IN+ACK or IN+NAK.  Otherwise, output any
            # saved packets and rerun the collapsing state machine
            # on the current packet.
            elif state == IN:
                state = IDLE
                if pid == BG_USB_PID_ACK:
                    collapse(IN_ACK, collapse_info, pkt_q)
                elif pid == BG_USB_PID_NAK:
                    collapse(IN_NAK, collapse_info, pkt_q)
                else:
                    re_run = True

            # Collapsing PING+NAK
            elif state == PING:
                state = IDLE
                if pid == BG_USB_PID_NAK:
                    collapse(PING_NAK, collapse_info, pkt_q)
                else:
                    re_run = True

            # Expecting an IN, OUT, or SETUP
            elif state == SPLIT:
                if pid == BG_USB_PID_IN:
                    pkt_q.save_packet()
                    state = SPLIT_IN
                elif pid == BG_USB_PID_OUT:
                    pkt_q.save_packet()
                    state = SPLIT_OUT
                elif pid == BG_USB_PID_SETUP:
                    pkt_q.save_packet()
                    state = SPLIT_SETUP
                else:
                    state = IDLE
                    re_run = True

            # Collapsing SPLIT+IN+NYET, SPLIT+IN+NAK, SPLIT+IN+ACK
            elif state == SPLIT_IN:
                state = IDLE
                if pid == BG_USB_PID_NYET:
                    collapse(SPLIT_IN_NYET, collapse_info, pkt_q)
                elif pid == BG_USB_PID_NAK:
                    collapse(SPLIT_IN_NAK, collapse_info, pkt_q)
                elif pid == BG_USB_PID_ACK:
                    collapse(SPLIT_IN_ACK, collapse_info, pkt_q)
                else:
                    re_run = True

            # Collapsing SPLIT+OUT+NYET
            elif state == SPLIT_OUT:
                state = IDLE
                if pid == BG_USB_PID_NYET:
                    collapse(SPLIT_OUT_NYET, collapse_info, pkt_q)
                else:
                    re_run = True

            # Collapsing SPLIT+SETUP+NYET
            elif state == SPLIT_SETUP:
                state = IDLE
                if pid == BG_USB_PID_NYET:
                    collapse(SPLIT_SETUP_NYET, collapse_info, pkt_q)
                else:
                    re_run = True

            if not re_run:
                break

            # The state machine is about to be re-run.  This
            # means that a complete packet sequence wasn't collapsed
            # and there are packets in the queue that need to be
            # output before we can process the current packet.
            (packetnum, signal_errors) = output_saved(packetnum, signal_errors, collapse_info, pkt_q, find_caller)

    # Stop the background triggering function, capturing, and close the analyzer
    trigger_process.terminate()
    bg_disable(beagle)
    bg_close(beagle)
    
    print('\nDone. Stopping triggers and collection.\n')
    
    return packet_collection


#=========================================================================
# DIGITAL INPIT/OUTPUT CONFIG
# ========================================================================
def setup_digital_lines():
    # Digital input mask
    input_enable_mask = BG_USB2_DIGITAL_IN_ENABLE_PIN1

    # Enable digital input pins
    bg_usb2_digital_in_config(beagle, input_enable_mask)
    print('Configuring digital input with %s' % input_enable_mask)


#==========================================================================
# LATENCY TESTING FUNCTIONS
# =========================================================================
# Find the trigger button details by comparing the data on and data off arrays
def find_button(packet_data_off, data_off_matches, packet_data_on, data_on_matches):
    button_change = []
    
    for i in range(len(data_off_matches)):
        # Check to see if position is unchanged for both lists
        if (data_off_matches[i]) and (data_on_matches[i]):
            # Check if there is a difference between the lists
            if packet_data_off[0][i] != packet_data_on[0][i]:
                # Find where byte gets cleared out
                if (packet_data_off[0][i] == '00') or (packet_data_on[0][i] == '00'):
                    button_change.append(i)
    
    # Check for errors
    # Sometimes more than one byte changes during a trigger
    if len(button_change) > 1:
        print('Multiple triggered bytes found')
        print('Chose the correct triggered byte position:\n')
        
        # List out all the possible trigger byte choices
        for i in range(0, len(button_change)):
            # Check if the DATA packets make sense
            if packet_data_on[0][button_change[i]] >= packet_data_off[0][button_change[i]]:
                print(f'{i+1} - 0x{packet_data_on[0][button_change[i]]} at position {button_change[i] + 1}')
                
            else:
                print(f'{i+1} - 0x{packet_data_off[0][button_change[i]]} at position {button_change[i] + 1}')
            
        print('')
        choice = int(input('Enter Choice #'))
             
        return int(button_change[choice - 1])
   
    elif len(button_change) == 0:
        print('Unable to determine triggered button. Review raw collection and enter manually.')
        
        test_button()
    
    return int(button_change[0])


# Create the data on and data off arrays for comparison
def find_matches(packet_data_in):
    import random
    
    packet_data = packet_data_in
    data0_test_list = []
    test_tracker = []

    # Create a new shuffled list for comparing data points
    shuffled_data = packet_data.copy()
    random.shuffle(shuffled_data)

    for i in range(0, len(packet_data[0])):
        data0_test_list.append(None)
        test_tracker.append(False)

    # Search for matches between the normal bytes and shuffled to discover bytes that do not change
    for i in range(0, len(packet_data)):
        for x in range(0, len(packet_data[i])):
            # Check for mismatched data packets that were collected
            if len(packet_data[i]) > len(shuffled_data[i]):
                pass
            
            elif (i == 0) or (test_tracker[x]):
                if packet_data[i][x] == shuffled_data[i][x]:
                    data0_test_list[x] = packet_data[i][x]
                    test_tracker[x] = True
    
    return test_tracker


# Filter through the packet collection to remove bad trigger and data packets
def clean_data_packets(packets):
    data_len = []
    data_off_test = ''
    data_on_test = ''
    packet_data_off = []
    packet_data_on = []
    clean_input = []
    first_run = True
        
    # Figure out the correct length of data packets
    if TestedDevice.trigger_length == 0:
        # Find most common byte length for data packets
        for i in packets:
            split_packets = i.split(',')
            packet_type = split_packets[2].strip()
            
            if packet_type.startswith('DATA'):
                data_len.append(int(split_packets[1]))
        
        # Drop out if no DATA packets were collected
        if len(data_len) == 0:
            print('No DATA packets found, make sure trigger wire is connected to testing device\n')
            
            test_button()
        
        # Originally tried finding most common data length.
        # When plugged into an xbox console, there were a lot of bad packets
        trigger_choice_1 = max(set(data_len), key=data_len.count)
        trigger_choice_2 = max(data_len)
        
        if trigger_choice_1 != trigger_choice_2:
            print('Most common and largest DATA packets are not equal')
            print('Chose the correct DATA packet length:')
            print(f'1 - {trigger_choice_1} bytes')
            print(f'2 - {trigger_choice_2} bytes')
            print('')
            choice = input('Enter Choice #')
                    
            if choice == '1':
                TestedDevice.trigger_length = trigger_choice_1
            
            else:
                TestedDevice.trigger_length = trigger_choice_2
                
        else:
            TestedDevice.trigger_length = trigger_choice_1

    # Clean up data packets that might swap during collection
    for line in packets:
        
        split_line = line.split(',')
        packet_type = split_line[2].strip()
        
        # First packet will always be trigger off
        # Check previous packet to enure it makes sense
        if packet_type == 'TRIGGER_OFF' and (data_on_test or first_run):
            data_off_test = False
            data_on_test = False
            first_run = False
            clean_input.append(f'{split_line[0]},{split_line[2]}')
            
        elif packet_type == 'TRIGGER_ON' and data_off_test:
            data_off_test = False
            data_on_test = False
            clean_input.append(f'{split_line[0]},{split_line[2]}')
            
        # Watch for trigger packets with no matching data packet
        elif packet_type.startswith('DATA') and (not first_run):
            # Drop off data packets that are not the right length
            byte_data = split_line[3].strip('\n').split(' ')[:-1]
            
            if TestedDevice.trigger_length == len(byte_data):
                if clean_input[-1].split(',')[1] == 'TRIGGER_OFF':
                    packet_data_off.append(byte_data)
                    data_off_test = True
                    data_on_test = False
                    clean_input.append(f'{split_line[0]},{split_line[2]},{split_line[3]}')
                    
                elif clean_input[-1].split(',')[1] == 'TRIGGER_ON':
                    packet_data_on.append(byte_data)
                    data_off_test = False
                    data_on_test = True
                    clean_input.append(f'{split_line[0]},{split_line[2]},{split_line[3]}')
        
        # If misaligned packets are found, wait for the next trigger off and start collecting again
        elif not first_run:
            clean_input.pop()
            clean_input.append(f'{split_line[0]},{split_line[2]}')

    return packet_data_off, packet_data_on


# Function for handling all the automated trigger detail functions
def find_trigger():
    print('\nRunning 10 test triggers to find trigger button details...\n')
            
    packet_list = usb_dump(10)
    
    packet_data_off, packet_data_on = clean_data_packets(packet_list)
    
    data_off_matches = find_matches(packet_data_off)
    data_on_matches = find_matches(packet_data_on)
    
    # Add 1 to account for leading byte
    TestedDevice.trigger_position = find_button(packet_data_off, data_off_matches, packet_data_on, data_on_matches) + 1
    
    # Convert string to hex for comparison to figure out which data packets are on
    data_off_trigger = hex(int(packet_data_off[0][TestedDevice.trigger_position - 1], 16))
    data_on_trigger = hex(int(packet_data_on[0][TestedDevice.trigger_position - 1], 16))
    
    if data_on_trigger >= data_off_trigger:
        byte_val = packet_data_on[0][TestedDevice.trigger_position - 1]
    
    else:
        byte_val = packet_data_off[0][TestedDevice.trigger_position - 1]

    TestedDevice.trigger_byte = byte_val


# Function for handling latency testing
def latency_test(test_count):
    from statistics import fmean, stdev
    import time
    
    print(f'\nRunning {test_count} test triggers...\n')
    
    start = time.time()
    packets = usb_dump(test_count)
    end = time.time()
    
    print(f'Elapsed time to collect {test_count} packets - {round(end - start, 2)}s.\n')
    
    test_time = time.strftime("%H%M%S", time.localtime())
    raw_output = f'{output_dir}/{test_time}/raw_output.txt'
    print(f'\nSaving raw collection to {raw_output}\n')
    
    # Create directory if missing
    os.makedirs(os.path.dirname(raw_output), exist_ok=True)
    
    # Export raw dump to csv with controller details for verification and debugging
    with open(raw_output, 'w') as out_file:
        for line in packets:
            out_file.write(f'{line}\n')

    print('Cleaning collected packets, and analyzing...\n')
    
    data_off_test = ''
    data_on_test = ''
    packet_data_off = []
    packet_data_on = []
    clean_input = []
    first_run = True
    time_keeper = []
    trigger_position = int(TestedDevice.trigger_position) - 1
    clean_times = []
    
    for line in packets:
        
        split_line = line.split(',')
        line_time = int(split_line[0])
        packet_type = split_line[2].strip()
        
        # Check previous packet to enure it makes sense
        if packet_type == 'TRIGGER_OFF' and (data_on_test or first_run):
            data_off_test = False
            data_on_test = False
            first_run = False
            time_keeper.append(line_time)
            clean_input.append(f'{split_line[0]},{split_line[2]}')
            
        elif packet_type == 'TRIGGER_ON' and data_off_test:
            data_off_test = False
            data_on_test = False
            time_keeper.append(line_time)
            clean_input.append(f'{split_line[0]},{split_line[2]}')
            
        # Watch for trigger packets with no matching data packet
        elif packet_type.startswith('DATA') and (not first_run):
            byte_data = split_line[3].strip('\n').split(' ')[:-1]
            
            # Drop off data packets that are not the right length
            if TestedDevice.trigger_length == len(byte_data):
                # Make sure we only collect valid packets and times
                if ('00' == byte_data[trigger_position]) and clean_input[-1].split(',')[1] == 'TRIGGER_OFF':
                    packet_data_off.append(byte_data)
                    data_off_test = True
                    data_on_test = False
                    time_keeper.append(line_time)
                    clean_input.append(f'{split_line[0]},{split_line[2]},{split_line[3]}')
                
                elif (TestedDevice.trigger_byte == byte_data[trigger_position]) \
                        and clean_input[-1].split(',')[1] == 'TRIGGER_ON':
                    packet_data_on.append(byte_data)
                    data_off_test = False
                    data_on_test = True
                    time_keeper.append(line_time)
                    clean_input.append(f'{split_line[0]},{split_line[2]},{split_line[3]}')
        
        # If misaligned packets are found, wait for the next trigger off and start collecting again
        elif not first_run:
            time_keeper.pop()
            time_keeper.append(line_time)
            clean_input.pop()
            clean_input.append(f'{split_line[0]},{split_line[2]}')

    print('Done.')
    
    clean_output = f'{output_dir}/{test_time}/clean_output.txt'
    print(f'\nSaving cleaned collection to {clean_output}\n')
    
    with open(clean_output, 'w') as out_file:
        for line in clean_input:
            out_file.write(f'{line}\n')
    
    if len(time_keeper) == 0:
        print('No clean triggers found.')

    for i in range(0, len(time_keeper) - 1, 2):
        clean_times.append(time_keeper[i + 1] - time_keeper[i])

    print(f'\n{len(clean_times)} clean times collected, out of {test_count} triggers sent.\n')
    print(f'Results:')
    print(f'\tMin - {min(clean_times)/1000000} ms')
    print(f'\tMax - {max(clean_times)/1000000} ms')
    print(f'\tAvg - {fmean(clean_times)/1000000} ms')
    print(f'\tStDev - {stdev(clean_times)/1000000} ms')
    
    results = f'{output_dir}/{test_time}/results-{test_count}.txt'
    print(f'\nSaving results to {results}\n')
    
    with open(results, 'w') as out_file:
        out_file.write(f'Device ID - {TestedDevice.vendor_id}:{TestedDevice.product_id}\n')
        out_file.write(f'Manufacturer - {TestedDevice.manufacturer}\n')
        out_file.write(f'Product - {TestedDevice.product}\n')
        out_file.write(f'Version - {TestedDevice.version}\n')
        out_file.write(f'Serial - {TestedDevice.serial}\n')
        out_file.write(f'Trigger Button Position: {TestedDevice.trigger_position}\n')
        out_file.write(f'Trigger Button Value: {TestedDevice.trigger_byte}\n')
        out_file.write(f'Trigger Button Packet Length: {TestedDevice.trigger_length}\n')
        out_file.write(f'Trigger Button Name: {TestedDevice.trigger_name}\n')
        out_file.write('\n')
        out_file.write(f'Triggers sent - {test_count} \n')
        out_file.write('\n')
        out_file.write('Results:\n')
        out_file.write(f'\tMinimum - {min(clean_times)/1000000} ms\n')
        out_file.write(f'\tMaximum - {max(clean_times)/1000000} ms\n')
        out_file.write(f'\tAverage - {fmean(clean_times)/1000000} ms\n')
        out_file.write(f'\tSample Standard Deviation - {stdev(clean_times)/1000000} ms\n')


# Function for pulling the Raspberry Pi pins simultaneously, leveraging pigpiod
def trigger_on():
    
    import pigpio

    from random import randrange
    
    # GPIO on the Raspberry Pi
    first_pin = 20
    second_pin = 21
    
    # See documentation for why these values were chosen
    min_delay = 400
    max_delay = 1000

    pi = pigpio.pi()
    
    # Change pins as needed for your testing setup
    pi.set_mode(first_pin, pigpio.OUTPUT)
    pi.set_mode(second_pin, pigpio.OUTPUT)

    while True:
        test = randrange(min_delay, max_delay)
        time.sleep(test / 1000)
        pi.set_bank_1((1 << first_pin) | (1 << second_pin))
        
        test = randrange(min_delay, max_delay)
        time.sleep(test / 1000)
        pi.clear_bank_1((1 << first_pin) | (1 << second_pin))


#=========================================================================
# MENU FUNCTIONS
# ========================================================================
# Gather the basic tested device information
def device_info():
    import subprocess
        
    while True:
        print('\n\n==========================')
        print('-----Device Info Menu-----')
        print('==========================')
        print(f'Device ID - {TestedDevice.vendor_id}:{TestedDevice.product_id}')
        print(f'Manufacturer - {TestedDevice.manufacturer}')
        print(f'Product - {TestedDevice.product}')
        print(f'Version - {TestedDevice.version}')
        print(f'Serial - {TestedDevice.serial}')
        #print('Polling Interval - [display polling interval]')
        print('')
        print('1 - Manually Enter USB Details')
        print('2 - Pull USB details with lsusb')
        print('3 - Return to Main Menu')
        print('==========================')
        print('')
        choice = input('Enter Choice #')
        
        if choice == '1':
            TestedDevice.vendor_id = input('Enter Device VID: ')
            TestedDevice.product_id = input('Enter Device PID: ')
            TestedDevice.manufacturer = input('Enter Manufacturer: ')
            TestedDevice.product = input('Enter Product: ')
            TestedDevice.version = input('Enter Version: ')
            TestedDevice.serial = input('Enter Serial: ')
            
        elif choice == '2':
            lsusb_out = subprocess.run('lsusb', capture_output=True)
            usb_list = str(lsusb_out.stdout)[2:-1].split('\\n')[:-1]

            for counter, i in enumerate(usb_list, start=1):
                print(counter, '-', i)

            usb_choice = input('\nChoose USB device: ')

            usb_split = usb_list[int(usb_choice)-1].split(" ")

            TestedDevice.vendor_id = usb_split[5].split(':')[0]
            TestedDevice.product_id = usb_split[5].split(':')[1]

            usb_busdev = f'{usb_split[1]}:{usb_split[3][:-1]}'
            usb_query = f'lsusb -s {usb_busdev} -v'
            
            lsusb_out = subprocess.run(usb_query, shell=True, capture_output=True)
            usb_details = str(lsusb_out.stdout)[2:-1].split('\\n')[:-1]
            
            for i in usb_details:
                line = i.split()
                
                if 'bcdDevice' in line:
                    TestedDevice.version = ' '.join(line[1:])
                elif 'iManufacturer' in line:
                    TestedDevice.manufacturer = ' '.join(line[2:])
                elif 'iProduct' in line:
                    TestedDevice.product = ' '.join(line[2:])
                elif 'iSerial' in line:
                    TestedDevice.serial = ' '.join(line[2:])
        
        else:
            print('\n\n')
            main_menu()
            
            
# Change the location for outputting the raw collection, clean collection, and testing results
def output_settings():
    global output_dir
    
    while True:
        print('\n\n==============================')
        print('-----Output Settings Menu-----')
        print('==============================')
        print(f'Output Directory - {output_dir}')
        print('')
        print('1 - Manually Enter Output Directory')
        print('2 - Main Menu')
        print('==============================')
        print('')
        choice = input('Enter Choice #')
        
        if choice == '1':
            output_dir = input('Enter Output Directory: ')
        
        elif choice == '2':
            main_menu()
            

# Function for gathering all the trigger button details, other functions to be added later
def test_button():
    while True:
        print('\n\n==========================')
        print('-----Test Button Menu-----')
        print('==========================')
        print(f'Device ID - {TestedDevice.vendor_id}:{TestedDevice.product_id}')
        print(f'Manufacturer - {TestedDevice.manufacturer}')
        print(f'Product - {TestedDevice.product}')
        print(f'Version - {TestedDevice.version}')
        print(f'Serial - {TestedDevice.serial}')
        print(f'Trigger Button Position: {TestedDevice.trigger_position}')
        print(f'Trigger Button Value: {TestedDevice.trigger_byte}')
        print(f'Trigger Button Packet Length: {TestedDevice.trigger_length}')
        print(f'Trigger Button Name: {TestedDevice.trigger_name}')
        print('')
        print('1 - Manually Enter Trigger Button Details')
        print('2 - Automatically Find Trigger Button Details')
        #print('3 - Pulse Trigger Button')
        #print('4 - Pull Trigger Button')
        print('3 - Return to Main Menu')
        print('==========================')
        print('')
        choice = input('Enter Choice #')
        
        if choice == '1':
            TestedDevice.trigger_position = input('Enter Trigger Button Position (count from 1): ')
            TestedDevice.trigger_byte = input('Enter Trigger Button Value (0x): ')
            TestedDevice.trigger_length = int(input('Enter Trigger Button Packet Length (count from 1): '))
            TestedDevice.trigger_name = input('Enter Trigger Button Name (eg., A, B, X,...): ')
            
        elif choice == '2':
            if not TestedDevice.trigger_name:
                TestedDevice.trigger_name = input('Enter Trigger Button Name (eg., A, B, X,...): ')
            
            find_trigger()
            
        elif choice == '3':
            print('\n\n')
            main_menu()
            

# Menu for latency testing function
def test_latency():
    while True:
        print('\n\n===========================')
        print('-----Test Latency Menu-----')
        print('===========================')
        print(f'Trigger Button Position: {TestedDevice.trigger_position}')
        print(f'Trigger Button Value: {TestedDevice.trigger_byte}')
        print(f'Trigger Button Packet Length: {TestedDevice.trigger_length}')
        print('')
        print('1 - Run 25 Tests (~18s)')
        print('2 - Run 100 Tests (~1m10s)')
        print('3 - Run 500 Tests (~5m50s)')
        print('4 - Run 1000 Tests (~11m40s)')
        print('5 - Return to Main Menu')
        print('===========================')
        print('')
        choice = input('Enter Choice #')
        
        if choice == '1':
            latency_test(25)
            
        elif choice == '2':
            latency_test(100)
            
        elif choice == '3':
            latency_test(500)
            
        elif choice == '4':
            latency_test(1000)
            
        elif choice == '5':
            main_menu()
            
            
# Main function
def main_menu():
    global output_dir
    
    # Path should have vid and pid in path for easy searching
    if ('UNKNOWN' in output_dir) and TestedDevice.vendor_id:
        output_dir = f'{os.getcwd()}/{TestedDevice.vendor_id}{TestedDevice.product_id}/{current_datetime}'
    
    print('===================')
    print('-----Main Menu-----')
    print('===================')
    print(f'Output Directory - {output_dir}')
    print('')
    print('1 - Device Info')
    print('2 - Output Settings')
    print('3 - Test Button')
    print('4 - Test Latency')
    print('5 - Exit')
    print('===================')
    print('')
    choice = input('Enter Choice #')
    
    if choice == '1':
        device_info()        
    elif choice == '2':
        output_settings()
    elif choice == '3':
        test_button()
    elif choice == '4':
        # Without trigger details the testing would be inaccurate
        if ('' in (TestedDevice.trigger_position, TestedDevice.trigger_byte)) or (TestedDevice.trigger_length == 0):
            print('\nMissing trigger details, run "Test Button" first.\n')
            main_menu()
        else:
            test_latency()
    elif choice == '5':
        sys.exit(0)
        

main_menu()
