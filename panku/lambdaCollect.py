#!/usr/bin/python

import requests
import boto3
import time
import geopy.distance
import xml.etree.ElementTree as ET
import itertools
import sys
import pickle

S3_BUCKET = "panku-gdzie-jestes-latest-storage"

class LatestPositionStorage(object):
  def __init__(self, service):
    self.objectName = "%s.latest" % service

  def getLatestPositionsForService(self):
    s3 = boto3.resource('s3')

    try:
      obj = s3.Object(S3_BUCKET, self.objectName)
      ret = pickle.loads(obj.get()['Body'].read())
      print("Read %d positions from S3" % len(ret))
      return ret
    except:
      print("Unexpected error:", sys.exc_info())  
      return {}
  def saveLatestPositionsForService(self, positions):
    s3 = boto3.resource('s3')
    print("Saving %d positions to S3" % (len(positions)))
    pickle_byte_obj = pickle.dumps(positions)
    s3.Object(S3_BUCKET, self.objectName).put(Body=pickle_byte_obj)

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
    
  def serviceId(self): 
    # TODO: reverse it, let subclasses override this, and implement `identifierPerRegistration` here in the superclass
    return self.identifierPerRegistration("").strip()
    
  def getLatestPositions(self):
    return LatestPositionStorage(self.serviceId()).getLatestPositionsForService()
  def saveLatestPositions(self, positions):
    return LatestPositionStorage(self.serviceId()).saveLatestPositionsForService(positions)

  def saveLocations(self, cars):
    now = int(time.time())
    
    latestPositions = self.getLatestPositions()
    newPositions = latestPositions.copy()
    
    table = boto3.resource('dynamodb', region_name='eu-west-1').Table('cars')
    dynamodb = boto3.client('dynamodb', region_name='eu-west-1')
    for (registration, position) in cars:
       key = self.identifierPerRegistration(registration) 
       latestPosition = latestPositions.get(key)
       shouldAdd = True
       existedBefore = latestPosition is not None
       if existedBefore:
          prevPosition = (latestPosition['long'], latestPosition['lat'])
          currentPosition = (position['lng'], position['lat'])
          distance = geopy.distance.vincenty(prevPosition, currentPosition).km

          if distance < 0.1:
           shouldAdd = False

       if shouldAdd:
         print("%s moved" % key)
         if existedBefore:
           print("storing previous")
           r = table.put_item(Item = {'carId' : key, 'date' : now-1,'long': prevPosition[0], 'lat': prevPosition[1]})

         r = table.put_item(Item = {'carId' : key, 'date' : now,    'long': "%8.6f" % position['lng'], 'lat': "%8.6f" % position['lat']})
         
         newPositions[key] = {'long': "%8.6f" % position['lng'], 'lat': "%8.6f" % position['lat']}
    self.saveLatestPositions(newPositions)         

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

class Traficar(Service):
  def identifierPerRegistration(self, registration):
    return "TRAFICAR " + registration
    
  def getLocations(self):
    s = requests.Session()
    s.headers.update({"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:64.0) Gecko/20100101 Firefox/64.0",
                      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                      "Accept-Language": "en-GB,en;q=0.7,en-US;q=0.3",
                      "Upgrade-Insecure-Requests": "1",
                      "DNT": "1",
                      })
    r = s.get("https://api.traficar.pl/eaw-rest-api/car?shapeId=2")
    data = r.json()
    return [(car['regNumber'], {"lng": car['longitude'], "lat":car['latitude']}) for car in data['cars']]

def lambda_handler(event, context):
  services = [Traficar, Veturilo, Panek]
  for service in services:
   print("==== Service %s" % service)
   service().getAndSaveLocations()
  return "OK"
