#nes30
#min - 0.356
#avg - 0.870
#max - 1.380
#stdev - 0.290

import csv
import re
import statistics

from datetime import time

# initializing the titles and rows list
fields = []
rows = []
time_holder = []

bad_counter = 0
counter = 0
start = 0
stop = 0
time_difference = 0

#filename = "C:\\Users\\akagu\\Documents\\usb_lag_testing\\total_phase\\output\\snes-usb_adapter_rand.csv"
#filename = "C:\\Users\\akagu\\Documents\\usb_lag_testing\\total_phase\\output\\8bitdo_rand.csv"
filename = "C:\\Users\\akagu\\Documents\\usb_lag_testing\\total_phase\\output\\xb1_rand.csv"

with open(filename, 'r') as csvfile:
    csvreader = csv.reader(csvfile)
    
    # skip the first six lines for Data Center header
    for i in range(0,5):
        next(csvreader, None)
    
    # extracting field names through first row
    fields = next(csvreader)
 
    # extracting each data row one by one
    for row in csvreader:
        rows.append(row)

for row in rows:
    # check for data packets
    if re.search('DATA[0-1] packet', row[9]):
        # check if 4 rows prior has a "digital input" start timer, and that current packet is "in"
        if (re.search('IN packet', rows[counter-1][9]) and ('Digital input') in rows[counter-4][9]):
            # pull time out when data packet seen, and convert to microseconds
            minutes = int(rows[counter][3].split(':')[0])
            seconds = int(rows[counter][3].split(':')[1].split('.')[0])
            milliseconds = int(rows[counter][3].split(':')[1].split('.')[1])
            microseconds = int(''.join(rows[counter][3].split('.')[2]))
            stop_time = (minutes * 60000000) + (seconds * 1000000) + (milliseconds * 1000) + microseconds
            
            
            # jump back to pull the time of the trigger start, and convert to microseconds
            minutes = int(rows[counter-4][3].split(':')[0])
            seconds = int(rows[counter-4][3].split(':')[1].split('.')[0])
            milliseconds = int(rows[counter-4][3].split(':')[1].split('.')[1])
            microseconds = int(''.join(rows[counter-4][3].split('.')[2]))
            start_time = (minutes * 60000000) + (seconds * 1000000) + (milliseconds * 1000) + microseconds
            
            time_difference = stop_time - start_time
            
            # catch exception when at top of file
            try:
                # figure out a better way of filtering bad inputs
                if (len(rows[counter][10]) == len(rows[counter-6][10])) and (len(rows[counter][10]) == len(rows[counter+6][10])):
                    time_holder.append(time_difference)
                # show bad results
                else:
                    print('Bad Result:')
                    print('Previous - ', rows[counter-6][10])
                    print('Current - ', rows[counter][10])
                    print('Next - ', rows[counter+6][10])
                    print()
                    
                    bad_counter+=1
            
            except (IndexError):
                pass
    
    counter+=1
    
print('Total Results - ', len(time_holder))
print('Bad Results - ', bad_counter)
print('Min - ', round(min(time_holder)/1000, 3), 'ms')
print('Avg - ', round((sum(time_holder)/len(time_holder)/1000), 3), 'ms')
print('Max - ', round(max(time_holder)/1000, 3), 'ms')
print('StDev - ', round(statistics.stdev(time_holder)/1000, 3), 'ms')