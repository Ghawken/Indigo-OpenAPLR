#! /usr/bin/env python
# -*- coding: utf-8 -*-

import string,cgi,time
#from os import curdir, sep
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
#from urlparse import urlparse
#from cgi import parse_qs
import simplejson as json
import threading
#import datetime
#import fnmatch

# Code Base retasked badly from github/flic/beecon with thanks!

def updateVar(name, value):
    if not ('OpenALPR' in indigo.variables.folders):
        # create folder
        folderId = indigo.variables.folder.create('OpenALPR')
        folder = folderId.id
    else:
        folder = indigo.variables.folders.getId('OpenALPR')


    if name not in indigo.variables:
        NewVar= indigo.variable.create(name, value=value, folder=folder)
    else:
        indigo.variable.updateValue(name, value)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class httpHandler(BaseHTTPRequestHandler):
   def __init__(self, plugin,*args):
      self.plugin = plugin
      self.plugin.debugLog(u"New httpHandler thread: "+threading.currentThread().getName()+", total threads: "+str(threading.activeCount()))
      BaseHTTPRequestHandler.__init__(self,*args)



   def deviceUpdate(self,device,deviceAddress,event, site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL):
      self.plugin.debugLog(u"deviceUpdate called")

      if (self.plugin.createVar):
         updateVar("OpenALPR_deviceID",str(device.id))
         updateVar("OpenALPR_ID",site_id.lower()+"@@"+camera_id.lower() )
         updateVar("OpenALPR_Plate", best_plate_number)


      indigo.server.log("Enter OpenALPR notification received from sender/location "+deviceAddress)

      device.updateStateOnServer('site_id', value=site_id)
      device.updateStateOnServer('camera_id', value=camera_id)
      device.updateStateOnServer('epoch_start', value=float(epoch_start))
      device.updateStateOnServer('PlateNumber', value=best_plate_number)
      device.updateStateOnServer('Confidence', value=best_confidence)
      device.updateStateOnServer('uuid', value=uuid)
      device.updateStateOnServer('VehicleColor', value=vehicle_color)
      device.updateStateOnServer('VehicleMake', value=vehicle_make)
      device.updateStateOnServer('CloudURLImage', value=CloudURL)

      #device.updateStateImageOnServer(indigo.kStateImageSel.MotionSensorTripped)

      self.triggerEvent(device)

      #self.triggerEvent("newPlate",best_plate_number)
      return


   def triggerEvent(self, device):
       self.plugin.debugLog(u"triggerEvent called")
       self.plugin.debugLog(u'Okay triggerEvent called')
       try:
           self.plugin.debugLog(u"About to check self.triggers")
           for triggerId, trigger in sorted(self.plugin.triggers.iteritems()):
               self.plugin.debugLog("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

               #if trigger.pluginProps["deviceID"] != str(device.id):
               #    self.debugLog("\t\tSkipping Trigger %s (%s), wrong device: %s" % (trigger.name, trigger.id, device.id))
               #else:
               if trigger.pluginTypeId == "newPlate":
                   #self.debugLog("Executing Trigger %s (%d)" % (trigger.name, trigger.id))
                   indigo.trigger.execute(trigger)

               #else:
                   #self.debugLog("Unknown Trigger Type %s (%d), %s" % (trigger.name, trigger.id, trigger.pluginTypeId))

       except Exception as e:
           self.plugin.debugLog(u'Error'+str(e))


       return


   def deviceCreate(self,site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL):
      self.plugin.debugLog(u"deviceCreate called")
      deviceName = site_id+"@@"+camera_id
      device = indigo.device.create(address=deviceName,deviceTypeId="OpenALPRCamera",name=deviceName,folder="OpenALPR", protocol=indigo.kProtocol.Plugin)

      self.plugin.deviceList[device.id] = {'ref':device,'name':device.name,'address':device.address}
      self.plugin.debugLog(u"Created new device, "+ deviceName)

      #return
      return device.id
 
   def parseResult(self,site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL):
      self.plugin.debugLog(u"parseResult called")

      deviceAddress = site_id +"@@"+ camera_id
      event = 'OpenALPR DataReceived'
      foundDevice = False
      if self.plugin.deviceList:
         for b in self.plugin.deviceList:
            if (self.plugin.deviceList[b]['address'] == deviceAddress):
               self.plugin.debugLog(u"Found device: " + self.plugin.deviceList[b]['name'])

               self.deviceUpdate(self.plugin.deviceList[b]['ref'],deviceAddress, event, site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL)

               foundDevice = True

      if foundDevice == False:
         self.plugin.debugLog(u"No device found")
         indigo.server.log("Received "+event+" from "+deviceAddress+" but no corresponding device exists",isError=True)
         if self.plugin.createDevice:
            newdev = self.deviceCreate(site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL)

            self.deviceUpdate(self.plugin.deviceList[newdev]['ref'],deviceAddress,event, site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL)

   def do_POST(self):
      global rootnode
      foundDevice = False
      self.plugin.debugLog(u"Received HTTP POST")
      self.plugin.debugLog(u"Sending HTTP 200 response")
      self.send_response(200)
      self.end_headers()

      try:
         ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
         uagent = str(self.headers.getheader('user-agent'))
         self.plugin.debugLog(u"User-agent: %s, Content-type: %s" % (uagent, ctype))
         data = self.rfile.read(int(self.headers['Content-Length']))
         data = data.decode('utf-8')
         self.plugin.debugLog(u"Data (UTF-8 decoded):  %s" % data)
# Custom
# Locative
         datajson = json.loads(data)
         self.plugin.debugLog(unicode(datajson))

         if (('Mozilla' in uagent) or ('OpenALPR' in uagent)):
            self.plugin.debugLog(u"Recognised OpenALPR")

            if (ctype == 'application/x-www-form-urlencoded') or (ctype=='application/json'):
                site_id = "Unknown"
                camera_id = "Unknown"
                epoch_start = "0"
                best_plate_number = "No Data"
                best_confidence = "0"
                uuid = "Unknown"
                vehicle_color = "Unknown"
                vehicle_make = "Unknown"
                CloudURL = "Unknown"

                if 'site_id' in datajson:
                    site_id = datajson['site_id']
                    self.plugin.debugLog(unicode(datajson['site_id']))
                if 'camera_id' in datajson:
                    camera_id = repr(datajson['camera_id'])
                    self.plugin.debugLog(unicode(datajson['camera_id']))
                if 'epoch_start' in datajson:
                    epoch_start = datajson['epoch_start']
                    self.plugin.debugLog(unicode(datajson['epoch_start']))

                if 'best_plate_number' in datajson:
                    best_plate_number = datajson['best_plate_number']
                    self.plugin.debugLog(unicode(datajson['best_plate_number']))
                if 'best_confidence' in datajson:
                    best_confidence = datajson['best_confidence']
                    self.plugin.debugLog(unicode(datajson['best_confidence']))
                if 'uuids' in datajson:
                    uuid = datajson['uuids'][0]
                    self.plugin.debugLog(unicode(datajson['uuids'][0]))
                if 'name' in datajson['vehicle']['color'][0]:
                    vehicle_color = datajson['vehicle']['color'][0]['name']
                    self.plugin.debugLog(unicode(datajson['vehicle']['color'][0]['name']))
                if 'name' in datajson['vehicle']['make'][0]:
                    vehicle_make = datajson['vehicle']['make'][0]['name']
                    self.plugin.debugLog(unicode(datajson['vehicle']['make'][0]['name']))
                if 'agent_uid' in datajson:
                    CloudURL = "https://cloud.openalpr.com/img/" + datajson['agent_uid'] +'/' + uuid + ".jpg"

                self.parseResult(site_id, camera_id, epoch_start, best_plate_number, best_confidence, uuid, vehicle_color, vehicle_make, CloudURL)
            else:
                indigo.server.log(u"Received OpenALPR data but wrong c-type")

      except Exception as e:
          indigo.server.log(u"Exception: %s" % str(e), isError=True)
          indigo.server.log(u'Error:'+str(e) )
          pass

class Plugin(indigo.PluginBase):
   def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
      indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
      self.deviceList = {}

      self.triggers = {}
      #self.events["newPlate"] = dict()


   def __del__(self):
      indigo.PluginBase.__del__(self)

   def startup(self):
      self.loadPluginPrefs()
      self.debugLog(u"Startup called")
      self.myThread = threading.Thread(target=self.listenHTTP, args=())
      self.myThread.daemon = True
      self.myThread.start()

   def deviceCreated(self, device):
      self.debugLog(device.name + ": Created device of type \"%s\"" % device.deviceTypeId)

      self.deviceList[device.id] = {'ref':device,'name':device.name,'address':device.address}

   def deviceStartComm(self, device):
      self.debugLog(device.name + ": Starting device")
      self.deviceList[device.id] = {'ref':device,'name':device.name,'address':device.address}

   def deviceStopComm(self, device):
      self.debugLog(device.name + ": Stopping device")
      if (device.deviceTypeId == u'OpenALPRCamera'):
         del self.deviceList[device.id]

   def shutdown(self):
      self.debugLog(u"Shutdown called")

   def triggerStartProcessing(self, trigger):
       self.debugLog("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
       assert trigger.id not in self.triggers
       self.triggers[trigger.id] = trigger
       return

   def triggerStopProcessing(self, trigger):
       self.debugLog("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
       assert trigger.id in self.triggers
       del self.triggers[trigger.id]
       return

   def actionControlSensor(self, action, device):
      self.debugLog(u"Manual sensor state change request: " + device.name)


   def validatePrefsConfigUi(self, valuesDict):	
      self.debugLog(u"validating Prefs called")
      port = int(valuesDict[u'listenPort'])
      if (port <= 0 or port>65535):
         errorMsgDict = indigo.Dict()
         errorMsgDict[u'port'] = u"Port number needs to be a valid TCP port (1-65535)."
         return (False, valuesDict, errorMsgDict)

      return (True, valuesDict)

   def closedPrefsConfigUi ( self, valuesDict, UserCancelled):
      if UserCancelled is False:
         indigo.server.log ("Preferences were updated.")
         if not (self.listenPort == int(self.pluginPrefs['listenPort'])):
            indigo.server.log("New listen port configured, reload plugin for change to take effect",isError=True)
         self.loadPluginPrefs()

   def loadPluginPrefs(self):
      self.debugLog(u"loadpluginPrefs called")
      self.debug = self.pluginPrefs.get('debugEnabled',False)
      self.createDevice = self.pluginPrefs.get('createDevice',True)
      self.listenPort = int(self.pluginPrefs.get('listenPort',6192))
      self.beecon = self.pluginPrefs.get('beecon',True)
      self.geofancy = self.pluginPrefs.get('geofancy',True)
      self.geohopper = self.pluginPrefs.get('geohopper',True)
      self.geofency = self.pluginPrefs.get('geofency',True)
      self.createVar = self.pluginPrefs.get('createVar',False)
      self.custom = self.pluginPrefs.get('custom',False)
      self.customSender = self.pluginPrefs.get('customSender','sender')
      self.customLocation = self.pluginPrefs.get('customLocation','location')
      self.customAction = self.pluginPrefs.get('customAction','action')
      self.customEnter = self.pluginPrefs.get('customEnter','enter')
      self.customExit = self.pluginPrefs.get('customExit','exit')
      self.testTrigger = self.pluginPrefs.get('testTrigger',False)
      self.testTriggeraction = self.pluginPrefs.get('testTriggeraction','toggle')

   def listenHTTP(self):
      self.debugLog(u"Starting HTTP listener thread")
      indigo.server.log(u"Listening on TCP port " + str(self.listenPort))
      self.server = ThreadedHTTPServer(('', self.listenPort), lambda *args: httpHandler(self, *args))
      self.server.serve_forever()
      return

   def runConcurrentThread(self):
      while True:
         self.sleep(1)


 
