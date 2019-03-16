#!/usr/bin/python

import fileinput
from datetime import datetime


currentCar = ""
for line in fileinput.input():
    trimmed = line.strip()
    elements = trimmed.split("\t")
    if (elements[0] != currentCar):
      # TODO should we generate EOT end here? (yes, but with what date?)
      currentCar = elements[0]
      first = True
      previous = []
    if first:
      print(trimmed.replace("\t",","))
    else:
      ts = int(elements[1])
      previous[1] = "%d" % (int(elements[1]) - 1)
      print(",".join(previous))
      print(",".join(elements))
    previous = elements
    first = False
