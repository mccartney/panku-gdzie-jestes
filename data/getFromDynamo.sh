#!/bin/bash

aws dynamodb scan --table-name cars --query "Items[*].[carId.S,date.N,lat.S,long.S]" --output text

