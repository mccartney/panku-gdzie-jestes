#!/usr/bin/python

import requests
import boto3
import time
import geopy.distance
import xml.etree.ElementTree as ET
import itertools

# special artificial timestamp value for keeping the last known location
LATEST = -1

# AWS DynamoDB limits
DYNAMO_BATCH_SIZE = 100

def grouper(n, iterable):
    # Taken from https://stackoverflow.com/a/1625013/118587
    args = [iter(iterable)] * n
    return ([e for e in t if e != None] for t in itertools.izip_longest(*args))

class Service(object):
  def getSecretName(self):
    pass

  def getCredentials(self):
    secret_name = self.getSecretName()
    region_name = "eu-west-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    return get_secret_value_response["SecretString"].replace('"', '').replace("{","").replace("}", "").split(":")


  def identifierPerRegistration(self, registration):
    pass

  def saveLocations(self, cars):
    now = int(time.time())
    
    table = boto3.resource('dynamodb', region_name='eu-west-1').Table('cars')
    dynamodb = boto3.client('dynamodb', region_name='eu-west-1')
    for batch in grouper(DYNAMO_BATCH_SIZE, cars):
    
       askForLatest = [{'carId': {'S': self.identifierPerRegistration(registration)}, 'date': {'N': str(LATEST)}} for (registration, position) in batch]
       print("Asking for %s" % askForLatest)
       lookupResult = dynamodb.batch_get_item(RequestItems = {'cars': {'Keys': askForLatest}})['Responses']['cars']
    
       lookupByCarId = dict([(lookup['carId']['S'], dict([(key, list(value.items())[0][1]) for key, value in lookup.items()])) for lookup in lookupResult])
       
       for (registration, position) in batch:
         key = self.identifierPerRegistration(registration) 
         lookup = lookupByCarId.get(key)
         shouldAdd = True
         existedBefore = lookup is not None
         if existedBefore:
            prevPosition = (lookup['long'], lookup['lat'])
            currentPosition = (position['lng'], position['lat'])
            distance = geopy.distance.vincenty(prevPosition, currentPosition).km

            if distance < 0.1:
               distanceToBePrinted = "no change"
               if (distance > 0.001):
                 distanceToBePrinted= "distance: %6.3f" % distance
               print("%s %s" % (key, distanceToBePrinted))
               shouldAdd = False

         if shouldAdd:
           print("%s moved" % key)
           if existedBefore:
             print("storing previous")
             r = table.put_item(Item = {'carId' : key, 'date' : now-1,'long': prevPosition[0], 'lat': prevPosition[1]})

           r = table.put_item(Item = {'carId' : key, 'date' : now,    'long': "%8.6f" % position['lng'], 'lat': "%8.6f" % position['lat']})
           r = table.put_item(Item = {'carId' : key, 'date' : LATEST, 'long': "%8.6f" % position['lng'], 'lat': "%8.6f" % position['lat']})

  def getAndSaveLocations(self):
    self.saveLocations(self.getLocations())

class Panek(Service):
  def getSecretName(self):
    return "panek/login"
  def identifierPerRegistration(self, registration):
    return "PANEK " + registration
  def getLocations(self):
    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:64.0) Gecko/20100101 Firefox/64.0",
                      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Language": "en-GB,en;q=0.7,en-US;q=0.3",
                      "Upgrade-Insecure-Requests": "1",
                      "DNT": "1",
                      })
    s.get("https://panel.panekcs.pl/security/login")

    username, password = self.getCredentials()
    r = s.post(url = "https://panel.panekcs.pl/security/login", data={"UserName": username, "Password": password})
    assert r.status_code == 200

    r = s.post(url = "https://panel.panekcs.pl/Home/GetLocations", data = {})
    assert r.status_code == 200
    locations = r.json()

    # Under Vehicles: [u'Category', u'FuelRange', u'Ids', u'Coordinates', u'RegistrationNumber', u'Fuel']
    count = len(locations['Vehicles']['Ids'])

    coordinates = locations['Vehicles']['Coordinates']
    registrations = locations['Vehicles']['RegistrationNumber']

    return zip(registrations, coordinates)

class Veturilo(Service):
  def identifierPerRegistration(self, registration):
    return "VETURILO " + registration
  def getLocations(self):
    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:64.0) Gecko/20100101 Firefox/64.0",
                      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Language": "en-GB,en;q=0.7,en-US;q=0.3",
                      "Upgrade-Insecure-Requests": "1",
                      "DNT": "1",
                      })
    r = s.get("https://nextbike.net/maps/nextbike-official.xml?city=372,210,475")
    assert r.status_code == 200
    
    root = ET.fromstring(r.content)
    
    ret = []
    for place in root.findall(".//place"):
      for bike in place:
        ret.append((bike.get("number"), {"lng" : float(place.get("lng")), "lat": float(place.get("lat"))}))
    
    return ret
     

def lambda_handler(event, context):
  Veturilo().getAndSaveLocations()
  Panek().getAndSaveLocations()
  return "OK"
