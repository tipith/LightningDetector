#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

class GPS(object):
    def __init__(self, lat, lon):
        self.lat, self.lon = float(lat), float(lon)
        
    def __str__(self):
        return '%2.4f %2.4f' % (self.lat, self.lon)

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
        self.ns = {'gml':    'http://www.opengis.net/gml/3.2',
                   'gmlcov': 'http://www.opengis.net/gmlcov/1.0'}
        self.url = 'http://data.fmi.fi/fmi-apikey/' + apikey + '/wfs'
        
    def _request(self, query, params):
        params['request'] = 'getFeature'
        params['storedquery_id'] = query
        data = bytes(urllib.parse.urlencode(params), 'utf8')
        try:
            f = urllib.request.urlopen(self.url, data)
            data = f.read()
            #print(data)
            return ET.fromstring(data)
        except urllib.error.HTTPError:
            return None
    
    def _getUTCString(self, minutes_to_past):
        utc_now = datetime.utcnow()
        utc_now = utc_now.replace(second=0, microsecond=0)
        utc_now = utc_now - timedelta(minutes=minutes_to_past)
        return utc_now.isoformat()
        
    def _getQuery(self, query, params):
        print('Performing query:', query, ':', params)
        root = self._request(query, params)
        
        if root is not None:
            positions = root.find('*//gmlcov:positions', self.ns)
            datas = root.find('*//gml:doubleOrNilReasonTupleList', self.ns)
            
            if positions is not None and datas is not None:
                # split lines first, then whitespaces
                positions = [line.split() for line in positions.text.split('\n')]
                datas = [line.split() for line in datas.text.split('\n')]
                
                if len(positions) == len(datas):
                    # first filter for empty strings from the list and then join
                    return zip(filter(bool, positions), filter(bool, datas))
            
        return None

    def getWeather(self, place):
        query = 'fmi::observations::weather::multipointcoverage'
        params = {'place':place, 'starttime':self._getUTCString(20)}
        weathers = []
        measurements = self._getQuery(query, params)
        
        if measurements is not None:
            for pos, data in measurements:
                weather = {'time': datetime.utcfromtimestamp(float(pos[2])), 
                    'gps':   GPS(pos[0],pos[1]), 't2m':      float(data[0]), 
                    'ws_10min': float(data[1]),  'wg_10min': float(data[2]), 
                    'wd_10min': float(data[3]),  'rh':       float(data[4]), 
                    'td':       float(data[5]),  'r_1h':     float(data[6]), 
                    'ri_10min': float(data[7]),  'snow_aws': float(data[8]), 
                    'p_sea':    float(data[9]),  'vis':      float(data[10]), 
                    'n_man':    float(data[11]), 'wawa':     float(data[12])}
                weathers.append(weather)
                
        return weathers
        
    def getStrikes(self, gps, radius_km):
        query = 'fmi::observations::lightning::multipointcoverage'
        params = {'bbox': str(BoundingBox(gps.lat, gps.lon, radius_km)), 'starttime': self._getUTCString(30)}
        #params = {'bbox': str(BoundingBox(gps.lat, gps.lon, radius_km)), 'starttime': '2015-08-07T00:00:00', 'endtime': '2015-08-10T00:00:00'} # returns thousands
        #params = {'bbox': str(BoundingBox(gps.lat, gps.lon, radius_km)), 'starttime': '2015-08-08T12:00:00', 'endtime': '2015-08-08T14:00:00'} # returns ~100
        strikes = []
        
        measurements = self._getQuery(query, params)
        
        if measurements is not None:
            for pos, data in measurements:
                strike = {'time': datetime.utcfromtimestamp(float(pos[2])), 
                    'gps': GPS(pos[0],pos[1]), 'multiplicity': int(float(data[0])),
                    'current': float(data[1]), 'cloud': bool(float(data[2])), 'ellipse': float(data[3])}
                strikes.append(strike)
                
        return strikes
        
        
if __name__ == "__main__":

    from apikey import APIKEY
    gps_jkl = GPS(62.2447, 25.7472)

    fmi = FMIOpenData(APIKEY)
    
    if False:
        weathers = fmi.getWeather('jyväskylä')
        for weather in weathers:
            print(weather)
    
    if True:
        strikes = fmi.getStrikes(gps_jkl, radius_km=3)
        for strike in strikes:
            print(strike)
        print('Number of lightning strikes returned:', len(strikes))
    
