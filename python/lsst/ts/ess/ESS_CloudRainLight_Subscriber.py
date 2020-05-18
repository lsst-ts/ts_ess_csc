
import time
import sys
import numpy
from SALPY_ESS import *
mgr = SAL_ESS()
mgr.salTelemetrySub("ESS_CloudRainLight")
myData = ESS_CloudRainLightC()
print("ESS_CloudRainLight_subscriber: Ready")
while True:
  print("ESS_CloudRainLight_subscriber: Waiting ......")
  retval = mgr.getNextSample_CloudRainLight(myData)
  if retval==0:
    print("ESS_CloudRainLight_subscriber: Ambient Temperature = " + str(myData.AmbientTemperature))
    print("ESS_CloudRainLight_subscriber: Sky Temperature = " + str(myData.SkyTemperature))
    print("ESS_CloudRainLight_subscriber: Light Level = " + str(myData.LightLevel))
    print("ESS_CloudRainLight_subscriber: Rain Level = " + str(myData.RainLevel))
  else:
    print("ESS_CloudRainLight_subscriber: getNextSample returned Error ......")

  time.sleep(1.5)

mgr.salShutdown()
exit()


