
import time
import sys
import numpy
from SALPY_ESS import *
mgr = SAL_ESS()
mgr.salTelemetrySub("ESS_Temperature4Ch")
myData = ESS_Temperature4ChC()
print("ESS_Temperature4Ch subscriber ready")
while True:
  retval = mgr.getNextSample_Temperature4Ch(myData)
  if retval==0:
    print("TemperatureC01 = " + str(myData.TemperatureC01))
    print("TemperatureC02 = " + str(myData.TemperatureC02))
    print("TemperatureC03 = " + str(myData.TemperatureC03))
    print("TemperatureC04 = " + str(myData.TemperatureC04))
  time.sleep(1)

mgr.salShutdown()
exit()

