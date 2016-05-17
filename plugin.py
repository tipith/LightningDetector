###
# Copyright (c) 2016, Timo Pihlstrom
# All rights reserved.
#
#
###
import json
import threading
import time
from .fmiapi import FMIOpenData, GPS 
from .apikey import APIKEY # put your apikey into apikey.py with variable name APIKEY

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

def serialize_alarm(alarm):
    format_ = _('%(user)s %(lat)s %(lon)s %(radius)s')
    return format_ % alarm
        
class LightningDetector(callbacks.Plugin):
    """Detects lightning strikes in based on Finnish Meteorological Institute's open data"""
    threaded = True
    
    def __init__(self, irc):
        self.__parent = super(LightningDetector, self)
        self.__parent.__init__(irc)
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
                    gps_loc = GPS(alarm['lat'], alarm['lon'])
                    strikes = self.fmi.getStrikes(gps_loc, alarm['radius'])
                    log.info('AlarmThread: found %i strikes for alarm %s' % (len(strikes), serialize_alarm(alarm)))
 
                    alert = '%s, %i strikes found in last 30 minutes' % (alarm['user'], len(strikes))
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
        weathers = self.fmi.getWeather(place)
        
        if weathers is not None and len(weathers):
            irc.reply('Latest temperature for ' + place + ' is ' + str(weathers[-1]['t2m']))
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
