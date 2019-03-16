#!/bin/bash

cat cars1.csv | grep -v "\-1" | sort -t, -k1,2 | python ./generateEnds.py | python ./convertToDatetime.py >/tmp/z
