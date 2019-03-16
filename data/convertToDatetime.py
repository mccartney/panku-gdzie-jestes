#!/usr/bin/python

import fileinput
from datetime import datetime


for line in fileinput.input():
    trimmed = line.strip()
    elements = trimmed.split(",")
    ts = int(elements[1])
    elements[1] = datetime.utcfromtimestamp(ts).strftime("%Y/%m/%d %H:%M:%S")
    print(",".join(elements))
    
    
    
