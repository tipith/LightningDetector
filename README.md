Detects lightning strikes in based on Finnish Meteorological Institute's open data

This project is a supybot plugin which can be placed into supybot's working folder under plugins. After this, the authorized user can load the plugin with command "load LightningDetector". Available commands are the following.

- addalarm <lat> <lon> <radius_km>
  * Adds the alarm for the user. Each user can have only one alarm.   
- removealarm
  * Removes the alarm for the user
- listalarms
  * Lists all alarms for all users
- weather <place>
  * Returns the latest weather for a city in Finland

In addition to the files contained in this project, the user must create a file 'apikey.py' which contains the variable APIKEY in the following format. 
```
APIKEY = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
```
The api key is a personal key which the user needs to register for at https://ilmatieteenlaitos.fi/rekisteroityminen-avoimen-datan-kayttajaksi
