#!/usr/bin/python

import requests
import boto3
import time

def getLocations():
  s = requests.Session()
  s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:64.0) Gecko/20100101 Firefox/64.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.7,en-US;q=0.3",
                    "Upgrade-Insecure-Requests": "1",
                    "DNT": "1",
                    })
  s.get("https://panel.panekcs.pl/security/login")

  r = s.post(url = "https://panel.panekcs.pl/security/login", data={"UserName": "", "Password": ""})
  assert r.status_code == 200

  r = s.post(url = "https://panel.panekcs.pl/Home/GetLocations", data = {})
  assert r.status_code == 200
  locations = r.json()

  # Under Vehicles: [u'Category', u'FuelRange', u'Ids', u'Coordinates', u'RegistrationNumber', u'Fuel']
  count = len(locations['Vehicles']['Ids'])

  coordinates = locations['Vehicles']['Coordinates']
  registrations = locations['Vehicles']['RegistrationNumber']

  return zip(registrations, coordinates)

def saveLocations(cars):  
  now = int(time.time())
  dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
  table = dynamodb.Table('cars')
  for (registration, position) in cars:
     key = "PANEK " + registration
     
     r = table.put_item(Item = {'carId' : key, 'date' : now, 'long': "%8.6f" % position['lng'], 'lat': "%8.6f" % position['lat']})

locations = getLocations()
print(locations[:10])
saveLocations(locations)

		



