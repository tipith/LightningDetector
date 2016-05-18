This project is a supybot plugin which detects lightning strikes based on Finnish Meteorological Institute's open weather data.

Clone this plugin into supybot's run directory under plugins. After this, the authorized user can load the plugin with command "load LightningDetector". Available commands are the following.

- **alarmadd** _lat lon radius_km_
  - Adds an alarm for the user -- each user can have only one alarm.
  - Once an alarm is set, the plugin will periocally check if any lighting strikes are detected in the vicinity. The user will be alarmed to the channel where the alarm was originally set. The plugin tries not to spam and has a three hour blocking period after user has been alarmed.
  - Example: alarmadd 62.2321 24.2455 50
- **alarmremove**
  - Removes alarm for the user
- **alarmlist**
  - Lists all alarms
  - Output format is the following: _user channel lat lon radius unix_ts_until_next_alarm_
  - Example: tipi^ #salamatesting 62.2447 25.7472 50 1463528267
- **alarmstatus**
  - Forces the alarm to be shown regardless blocking period
- **weather** _place_
  - Returns the weather for a city in Finland

In addition to the files contained in this project, the user must create a file 'apikey.py' which contains the variable APIKEY in the following format. 
```
APIKEY = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
```
The API key is a personal key which the user can register for [here] (https://ilmatieteenlaitos.fi/rekisteroityminen-avoimen-datan-kayttajaksi).
