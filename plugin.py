###
# Copyright (c) 2016, Timo Pihlstrom
# All rights reserved.
#
#
###
import xml
import json
import threading
import time

from owslib.wfs import WebFeatureService
from datetime import datetime, timedelta
from supybot.commands import *
import supybot.utils as utils
import supybot.conf as conf
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.log as log
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('LightningDetector')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

class BoundingBox(object):
    def __init__(self, lat, lon, radius_km):
        self.lat = lat
        self.lon = lon
        self.radius = radius_km
    
    def __str__(self):
        # crude approximation which does not factor polar flattening. 1 deg = 110.5 km
        deg = self.radius / 110.5
        left   = self.lon - deg
        right  = self.lon + deg
        bottom = self.lat - deg
        top    = self.lat + deg
        return '%2.4f,%2.4f,%2.4f,%2.4f' % (left,bottom,right,top)
    
class FMIOpenData(object):
    def __init__(self, apikey):
        self.wfs = WebFeatureService(url='http://data.fmi.fi/fmi-apikey/' + apikey + '/wfs', version='2.0.0')
        self.alarms = []
        
    def printStoredQueries(self, filtertext=None):
        for storedquery in self.wfs.storedqueries:
            if filtertext is None or filtertext in storedquery.id:
                print(storedquery.id)
                for parameter in storedquery.parameters:
                    print(' - ' + parameter.name)

    def getLightningStrikes(self, lat, lon, size):
        params = {'bbox':str(BoundingBox(lat, lon, size)), 'starttime':self._getUTCString(30)}
        print('Searching lightning strikes with parameters:', params)
        resp = self.wfs.getfeature(storedQueryID='fmi::observations::lightning::simple', storedQueryParams=params)
        return resp.read()

    def getWeather(self, place, minutes_to_past):
        params = {'place':str(place), 'starttime':self._getUTCString(minutes_to_past)}
        print('Searching weather with parameters:', params)
        resp = self.wfs.getfeature(storedQueryID='fmi::observations::weather::simple', storedQueryParams=params)
        return resp.read()
        
    def getLatestTemperature(self, place):
        xmldata = self.getWeather(place, minutes_to_past=10)
        latest_temp = None
        root = xml.etree.ElementTree.fromstring(xmldata)
        print('Number of weather measurements returned:', root.attrib['numberReturned'])
        for member in root.findall('{http://www.opengis.net/wfs/2.0}member'):
            elem = member.find('{http://xml.fmi.fi/schema/wfs/2.0}BsWfsElement')
            time = elem.find('{http://xml.fmi.fi/schema/wfs/2.0}Time')
            name = elem.find('{http://xml.fmi.fi/schema/wfs/2.0}ParameterName')
            value = elem.find('{http://xml.fmi.fi/schema/wfs/2.0}ParameterValue')
            print(time.text, name.text, value.text)
            if name.text == 't2m':
                latest_temp = float(value.text)
        return latest_temp

    def getStrikeCount(self, lat, lon, radius_km):
        xmldata = self.getLightningStrikes(lat, lon, radius_km)
        root = xml.etree.ElementTree.fromstring(xmldata)
        print('Number of lightning strikes returned:', root.attrib['numberReturned'])
        return int(root.attrib['numberReturned'])
        
    def _getUTCString(self, minutes_to_past):
        utc_now = datetime.utcnow()
        utc_now = utc_now.replace(second=0, microsecond=0)
        utc_now = utc_now - timedelta(minutes=minutes_to_past)
        return utc_now.isoformat()
        


def serialize_alarm(alarm):
    format_ = _('%(user)s %(lat)s %(lon)s %(radius)s')
    return format_ % alarm
        
class LightningDetector(callbacks.Plugin):
    """Detects lightning strikes in based on Finnish Meteorological Institute's open data"""
    threaded = True
    
    def __init__(self, irc):
        self.__parent = super(LightningDetector, self)
        self.__parent.__init__(irc)
        APIKEY = <FMI OPEN DATA API KEY>
        self.fmi = FMIOpenData(APIKEY)
        self.irc = irc
        self.thread = self.AlarmThread(self.irc, self.fmi)
        self.thread.start()

    def _getAlarms(self):
        return json.loads(self.registryValue('alarms'))
        
    def _storeAlarms(self, alarms):
        self.setRegistryValue('alarms', value=json.dumps(alarms))
    
    class AlarmThread(threading.Thread):
        def __init__(self, irc, fmi):
            threading.Thread.__init__(self)
            self.stopEvent = threading.Event()
            self.stopEvent.clear()
            self.fmi = fmi
            self.irc = irc

        def run(self):
            log.info('AlarmThread: starting')
            while not self.stopped():
                alarms = json.loads(conf.supybot.plugins.LightningDetector.get('alarms')())
                
                for alarm in alarms:
                    count = self.fmi.getStrikeCount(alarm['lat'], alarm['lon'], alarm['radius'])
                    log.info('AlarmThread: found %i strikes for alarm %s' % (count, serialize_alarm(alarm)))
 
                    alert = '%s, %i strikes found in last 30 minutes' % (alarm['user'], count)
                    self.irc.queueMsg(ircmsgs.privmsg('#salamatesting', alert))
                    
                self.stopEvent.wait(600.0)
                
            log.info('AlarmThread: stopping')
            
        def stop(self):
            self.stopEvent.set()
        
        def stopped(self):
            return self.stopEvent.is_set()
            
    def weather(self, irc, msg, args, place):
        """<place>
        
        Get the weather for a place in a nordic country.
        """
        temp = self.fmi.getLatestTemperature(place)
        
        if temp is not None:
            irc.reply('Latest temperature for ' + place + ' is ' + str(temp))
        else:
            irc.error('Temperature not found for', place)
    weather = wrap(weather, ['text'])
    
    def addalarm(self, irc, msg, args, lat, lon, radius):
        """<lat> <lon> <km>
        
        Add an alarm for your nick."""
        alarms = self._getAlarms()

        for alarm in alarms:
            if alarm['user'] == msg.nick:
                irc.error(_('Alarm already exists for you: lat %s, lon %s' % (alarm['lat'], alarm['lon'])), Raise=True)
            
        alarm = {'user': msg.nick, 'lat': lat, 'lon': lon, 'radius': radius}
        alarms.append(alarm)
        
        self._storeAlarms(alarms)
        irc.replySuccess()
    addalarm = wrap(addalarm, ['float', 'float', 'int'])

    def removealarm(self, irc, msg, args):
        """takes no arguments
        
        Removes alarm for your nick."""
        alarms = self._getAlarms()
        
        if True not in (alarm['user'] == msg.nick for alarm in alarms):
            irc.error(_('No alarms are found for you'), Raise=True)
        
        for alarm in alarms:
            if alarm['user'] == msg.nick:
                log.info('Remove: alarm found for %s' % msg.nick)
                alarms.remove(alarm)
        
        self._storeAlarms(alarms)
        irc.replySuccess()
    removealarm = wrap(removealarm)
    
    def listalarms(self, irc, msg, args):
        """takes no arguments
        
        Return a list of all alarms."""
        alarms = self._getAlarms()
        
        if len(alarms) == 0:
            irc.reply('Alarm list is empty')
        else:
            irc.replies([serialize_alarm(x) for x in alarms])
    listalarms = wrap(listalarms)
        
    def die(self):
        if self.thread is not None:
            self.thread.stop()
            self.thread.join()
            self.thread = None

Class = LightningDetector


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
