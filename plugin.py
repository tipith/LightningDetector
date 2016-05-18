###
# Copyright (c) 2016, Timo Pihlstrom
# All rights reserved.
#
#
###
import json
import threading
import time
import calendar
import math

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
    
def gpsbearing(lat1, lon1, lat2, lon2):
    return math.atan2(math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(lon2-lon1), math.sin(lon2-lon1)*math.cos(lat2)) 
    
def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

def is_between_angle(deg, ref_angle):      
    ref_high = ref_angle + 22.5
    ref_low = ref_angle - 22.5
    
    if ref_angle == 180:
        if math.fabs(deg) > 180 - 22.5:
            return True
    elif deg <= ref_high and deg > ref_low:
        return True

    return False
        
def bearing_to_str(bearing):
    deg = math.floor(math.degrees(bearing))

    if is_between_angle(deg, 0):
        return 'east'
    if is_between_angle(deg, -45):
        return 'south-east'
    if is_between_angle(deg, -90):
        return 'south'
    if is_between_angle(deg, -135):
        return 'south-west'
    if is_between_angle(deg, 180):
        return 'west'
    if is_between_angle(deg, 135):
        return 'north-west'
    if is_between_angle(deg, 90):
        return 'north'
    if is_between_angle(deg, 45):
        return 'north-east'
    
def serialize_alarm(alarm):
    format_ = _('%(user)s %(channel)s %(lat)s %(lon)s %(radius)s %(next_alarm)s')
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
            self.notifyEvent = threading.Event()
            self.notifyEvent.clear()
            self.fmi = fmi
            self.irc = irc

        def run(self):
            log.info('AlarmThread: starting')
            while not self.stopped():
                alarms = json.loads(conf.supybot.plugins.LightningDetector.get('alarms')())
                now = calendar.timegm(time.gmtime())
                
                for alarm in alarms:
                    # check alarms every 20 minutes and have an 3 hour blocking period after an alarm per user
                    if now > int(alarm['next_alarm']) or int(alarm['next_alarm']) == 0:
                        gps_loc = GPS(alarm['lat'], alarm['lon'])
                        strikes = self.fmi.getStrikes(gps_loc, alarm['radius'])
                        
                        if len(strikes):
                            log.info('AlarmThread: alerting user %s at %s. Found %i strikes' % (alarm['user'], alarm['channel'], len(strikes)))
                        
                            distance_mean = 0
                            distance_closest = 10000000 # some random big value
                            bearing_mean = 0
                            bearing_closest = 0
                            
                            ground_strikes = 0
                            current_strongest = 0
                            current_mean = 0
                            
                            unit_vectors = []

                            for strike in strikes:
                                distance = haversine(alarm['lat'], alarm['lon'], strike['gps'].lat, strike['gps'].lon)
                                bearing = gpsbearing(alarm['lat'], alarm['lon'], strike['gps'].lat, strike['gps'].lon)
                                
                                if distance_closest > distance:
                                    distance_closest = distance
                                    bearing_closest = bearing
                                if math.fabs(current_strongest) < math.fabs(strike['current']):
                                    current_strongest = strike['current']
                                if not strike['cloud']:
                                    ground_strikes += 1
                                
                                current_mean += math.fabs(strike['current'])
                                distance_mean += distance

                                unit_vectors.append((math.cos(bearing), math.sin(bearing)))
                                
                            current_mean /= float(len(strikes))
                            distance_mean /= float(len(strikes))
                            
                            vector_mean = [sum(i) for i in zip(*unit_vectors)]
                            vector_mean = [x / len(unit_vectors) for x in vector_mean]
                            bearing_mean = math.atan2(vector_mean[1], vector_mean[0])
                            
                            alert = '%s, %i strikes during last 30 minutes. %i ground strikes, closest %i km to %s, \
                                mean %i km to %s, peak current %.1f kA, |mean| %.1f kA' % \
                                (alarm['user'], len(strikes), ground_strikes, distance_closest,
                                bearing_to_str(bearing_closest), distance_mean, bearing_to_str(bearing_mean),
                                current_strongest, current_mean)
                            self.irc.queueMsg(ircmsgs.privmsg(alarm['channel'], alert))
                        
                            # store the next alarm time, todo add configurable
                            alarm['next_alarm'] = now + 3*3600
                            conf.supybot.plugins.LightningDetector.alarms.setValue(json.dumps(alarms))
                            
                        elif int(alarm['next_alarm']) == 0:
                            # user expects output here even if no strikes are found
                            self.irc.queueMsg(ircmsgs.privmsg(alarm['channel'], '%s, no strikes are currently found in the vicinity' % (alarm['user']) ))
                            
                            # this denotes that next_alarm value is not in its initial state
                            alarm['next_alarm'] = 1
                            conf.supybot.plugins.LightningDetector.alarms.setValue(json.dumps(alarms))
                    else:
                        log.info('AlarmThread: alarm blocking period not passed for user %s, next check in %i s' % (alarm['user'], int(alarm['next_alarm']) - now))
                        
                self.notifyEvent.wait(20*60.0) # todo add configurable
                self.notifyEvent.clear()

            log.info('AlarmThread: stopping')
            
        def stop(self):
            self.stopEvent.set()
            self.notifyEvent.set()
        
        def stopped(self):
            return self.stopEvent.is_set()
            
        def notify(self):
            return self.notifyEvent.set()
            
    def weather(self, irc, msg, args, place):
        """<place>
        
        Get the weather for a place in a nordic country.
        """
        weathers = self.fmi.getWeather(place)
        
        if weathers is not None and len(weathers):
            latest = weathers[-1]
            
            reply = "Weather for %s at %s: " % (place.title(), ircutils.bold(latest['time'].strftime("%H:%M")))
            
            try:
                if not math.isnan(latest['t2m']):
                    reply += 'temperature %s C' % (ircutils.bold('%.1f' % (latest['t2m'])))
                if not math.isnan(latest['rh']):
                    reply += ', humidity %s %%' % (ircutils.bold('%.0f' % (latest['rh'])))
                if not math.isnan(latest['ws_10min']):
                    reply += ', wind %s m/s' % (ircutils.bold('%.1f' % (latest['ws_10min'])))
                if not math.isnan(latest['wg_10min']):
                    reply += ', gusts %s m/s' % (ircutils.bold('%.1f' % (latest['wg_10min'])))
                if not math.isnan(latest['wd_10min']):
                    reply += ', direction %s deg' % (ircutils.bold('%.0f' % (latest['wd_10min'])))
                if not math.isnan(latest['p_sea']):
                    reply += ', pressure %s hPa' % (ircutils.bold('%.1f' % (latest['p_sea'])))
                if not math.isnan(latest['r_1h']):
                    reply += ', rain %s mm/h' % (ircutils.bold('%.1f' % (latest['r_1h'])))
                if not math.isnan(latest['vis']):
                    reply += ', visibility %s km' % (ircutils.bold('%.1f' % (latest['vis'] / 1000)))
            except KeyError:
                pass

            irc.reply(reply)
        else:
            irc.error('Temperature not found for ' + place)
    weather = wrap(weather, ['text'])
    
    def addalarm(self, irc, msg, args, lat, lon, radius):
        """<lat> <lon> <km>
        
        Add an alarm for your nick."""
        alarms = self._getAlarms()
        
        for alarm in alarms:
            if alarm['user'] == msg.nick:
                irc.error(_('Alarm already exists for you: lat %s, lon %s' % (alarm['lat'], alarm['lon'])), Raise=True)
        
        alarm = {'user': msg.nick, 'channel': msg.args[0], 'lat': lat, 'lon': lon, 'radius': radius, 'next_alarm': 0}
        alarms.append(alarm)
        
        self._storeAlarms(alarms)
        self.thread.notify()
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
    
    def statusalarm(self, irc, msg, args):
        """takes no arguments
        
        Bypass blocking delay for alarm. Returns immediate alarm if strikes are found."""
        alarms = self._getAlarms()
        
        if True not in (alarm['user'] == msg.nick for alarm in alarms):
            irc.error(_('No alarms are found for you'), Raise=True)
        
        for alarm in alarms:
            if alarm['user'] == msg.nick:
                alarm['next_alarm'] = 0
        
        self._storeAlarms(alarms)
        self.thread.notify()
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
