#!/usr/bin/env python

# import normal packages
import platform
import time
import logging
import sys
import os
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
#import time
#import math
#import requests # for http GET
import configparser # for config/ini file
import serial
import minimalmodbus


# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService


"""
com.victronenergy.evcharger

/Ac/Power                  --> Write: AC Power (W)
/Ac/L1/Power               --> Write: L1 Power used (W)
/Ac/L2/Power               --> Write: L2 Power used (W)
/Ac/L3/Power               --> Write: L3 Power used (W)
/Ac/Energy/Forward         --> Write: Charged Energy (kWh)

/Current                   --> Write: Actual charging current (A)
/MaxCurrent                --> Read/Write: Max charging current (A)
/SetCurrent                --> Read/Write: Charging current (A)

/AutoStart                 --> Read/Write: Start automatically (number)
    0 = Charger autostart disabled
    1 = Charger autostart enabled
/ChargingTime              --> Write: Total charging time (seconds)
/EnableDisplay             --> Read/Write: Lock charger display (number)
    0 = Control disabled
    1 = Control enabled
/Mode                      --> Read/Write: Charge mode (number)
    0 = Manual
    1 = Automatic
    2 = Scheduled
/Model                     --> Model, e.g. AC22E or AC22NS (for No Screen)
/Position                  --> Write: Charger position (number)
    0 = AC Output
    1 = AC Input
/Role                      --> Unknown usage
/StartStop                 --> Read/Write: Enable charging (number)
    0 = Enable charging: False
    1 = Enable charging: True
/Status                    --> Write: Status (number)
    0 = Disconnected
    1 = Connected
    2 = Charging
    3 = Charged
    4 = Waiting for sun
    5 = Waiting for RFID
    6 = Waiting for start
    7 = Low SOC
    8 = Ground test error
    9 = Welded contacts test error
    10 = CP input test error (shorted)
    11 = Residual current detected
    12 = Undervoltage detected
    13 = Overvoltage detected
    14 = Overheating detected
    15 = Reserved
    16 = Reserved
    17 = Reserved
    18 = Reserved
    19 = Reserved
    20 = Charging limit
    21 = Start charging
    22 = Switching to 3-phase
    23 = Switching to 1-phase
    24 = Stop charging

Heidelberg Status; data[1]
    2=A1 No vehicle plugged Wallbox doesn't allow charging
    3=A2 No vehicle plugged Wallbox allows charging
    4=B1 Vehicle plugged without charging request Wallbox doesn't allow charging
    5=B2 Vehicle plugged without charging request Wallbox allows charging
    6=C1 Vehicle plugged with charging request Wallbox doesn't allow charging
    7=C2 Vehicle plugged with charging request Wallbox allows charging
    8=derating
    9=E
    10=F
    11=ERR


"""

class DbusHeidelbergChargerService:
    def __init__(self, config, servicename, paths, productname='HeidelbergRTUService', connection='Heidelberg-Charger Modbus RTU service'):
        global modbusClient
        deviceinstance = int(config['DEFAULT']['Deviceinstance'])
        customname = config['DEFAULT']['CustomName']
        self.charging_time = {"start": None, "calculate": False, "stopped_since": 0}        
        self.STOP_CHARGING_COUNTER_AFTER = 10
        self.charging_current = 0
        self.ret_current = 0
        self.Energy = 0
        self.heidelberg_status = 0
        self.StatusOld = 0
        self.Status = 0
        devicename = config['ModbusRTU']['Devicename']
        iDisableStandby = int(config['ModbusRTU']['DisableStandby'])
        logging.info("iDisableStandby = %i" % (iDisableStandby))
        if iDisableStandby != 0:
           iDisableStandby = 4
        else:
           iDisableStandby = 0 
        devicepath = os.popen('readlink -f /dev/serial/by-id/%s' %devicename).read().replace('\n', '')
        ttyname = devicepath.replace('/dev/', '')
        os.system('/opt/victronenergy/serial-starter/stop-tty.sh %s' %ttyname)
        
        self.bDebug=False
        if int(config['ModbusRTU']['DebugModbus']) == 1:
            self.bDebug=True
        modbusClient = minimalmodbus.Instrument(devicepath, 1,close_port_after_each_call=True, debug=self.bDebug)  # port name, slave address (in decimal)
        modbusClient.serial.baudrate = 19200  # baudrate
        modbusClient.serial.bytesize = 8
        modbusClient.serial.parity   = serial.PARITY_EVEN
        modbusClient.serial.stopbits = 1
        modbusClient.serial.timeout  = 0.1      # seconds
        modbusClient.address         = 1        # this is the slave address number
        modbusClient.mode = minimalmodbus.MODE_RTU # rtu or ascii mode
        modbusClient.clear_buffers_before_each_transaction = True
        self.acposition = int(config['DEFAULT']['Position'])

        self._dbusservice = VeDbusService("{}.{}".format(servicename, devicename), register=False)
        self._paths = paths

        self.enable_charging = True # start/stop

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

    # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'V 1.0.1, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0xFFFF)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/FirmwareVersion', 'FirmwareVersion')
        self._dbusservice.add_path('/Serial', devicename)
        self._dbusservice.add_path('/HardwareVersion', 'Energy Control')
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/UpdateIndex', 0)
        self._dbusservice.add_path('/Position', self.acposition) # 0: ac out, 1: ac in
        # add path values to dbus
        for path, settings in self._paths.items():
            self._dbusservice.add_path(path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
 

        try:
            data = modbusClient.read_registers(100, 2,functioncode=4)  # Registernumber, number of decimals
            self._dbusservice['/MaxCurrent'] = data[0]
            self._dbusservice['/MinCurrent'] = data[1]
            time.sleep(1)
            data = modbusClient.read_registers(4, 15,functioncode=4)  # Registernumber, number of decimals
            self._dbusservice['/FirmwareVersion'] = "Modbus Register-Layouts Version %x" % data[0] 
            self.Energy =  ((data[14] + (data[13]*65536))/1000 )
            
            modbusClient.write_register(258, iDisableStandby ,functioncode=6) 
            logging.info("Read Heidelberg Wallbox Current Settings - MinCurrent=%i MaxCurrent=%i self.Energy=%f iDisableStandby=%i" % (self._dbusservice['/MinCurrent'],self._dbusservice['/MaxCurrent'],self.Energy,iDisableStandby))
 
        except minimalmodbus.NoResponseError:
            time.sleep(60)
            sys.exit()
        except Exception as e:
            logging.critical('Error at %s', '_init', exc_info=e)
            sys.exit()

  
        self._dbusservice.add_path('/History/Ac/Energy/Forward',self.Energy)
        self._dbusservice.add_path('/Ac/Energy/ForwardStart',self.Energy)

    


        logging.info("init devicepath=%s ttyname=%s devicename=%s"   % (devicepath, ttyname,devicename))

        self._dbusservice.register()
    
     

        # last update
        self._lastUpdate = 0
        self._lastUpdateOld = 0
        # charging time in float
        self._chargingTime = 0.0

        # add _update function 'timer'
        gobject.timeout_add(1000, self._update) # pause 2000ms before the next request

        gobject.timeout_add( int(config['DEFAULT']['SignOfLifeLog'])*60*1000, self._signOfLife)

   
   
    def _handlechangedvalue(self, path, value):
        #logging.critical("someone else updated %s to %s" % (path, value))

        if path == '/MaxCurrent':
            self._dbusservice['/MaxCurrent'] = value
        elif path == '/SetCurrent':
            self._dbusservice['/SetCurrent'] = value
        elif path == '/AutoStart':
            self._dbusservice['/AutoStart'] = value
        elif path == '/Mode':
            self._dbusservice['/Mode'] = value
        elif path == '/StartStop':
            self._dbusservice['/StartStop'] = value

    def _signOfLife(self):
        logging.info("---sol Last: %s Energy: %f" % (self._dbusservice['/Ac/Power'], self.Energy))
        return True

    def _update(self):
        try:
            now = int(time.time())
            #logging.info("Update")
            data = modbusClient.read_registers(4, 15,functioncode=4)  # Registernumber, number of decimals
            self._dbusservice['/FirmwareVersion'] = "Modbus Register-Layouts Version %x" % data[0] 
            self.Energy =  ((data[14] + (data[13]*65536))/1000 )
            
            self._dbusservice['/History/Ac/Energy/Forward'] =  self.Energy
            self._dbusservice['/Ac/Energy/Forward'] =  self.Energy - self._dbusservice['/Ac/Energy/ForwardStart'] 
            self._dbusservice['/MCU/Temperature'] = data[5]/10.0          

            self._dbusservice['/Ac/L1/Power'] = data[2]*data[6]/10
            self._dbusservice['/Ac/L2/Power'] = data[3]*data[7]/10
            self._dbusservice['/Ac/L3/Power'] = data[4]*data[8]/10




            self._dbusservice['/Ac/Power'] = self._dbusservice['/Ac/L1/Power'] + self._dbusservice['/Ac/L2/Power'] + self._dbusservice['/Ac/L3/Power']

            self._dbusservice['/Ac/L1/Voltage'] = data[6]
            self._dbusservice['/Ac/L2/Voltage'] = data[7]
            self._dbusservice['/Ac/L3/Voltage'] = data[8]
  
            self._dbusservice['/Ac/L1/Current'] = data[2]/10
            self._dbusservice['/Ac/L2/Current'] = data[3]/10
            self._dbusservice['/Ac/L3/Current'] = data[4]/10
 
            self._dbusservice['/Ac/Voltage'] = data[6]

            self._dbusservice['/Current'] = float(data[2])/10.0


  

            self.StatusOld = self._dbusservice['/Status']

            if self.StatusOld  != 3:
                if data[1] == 0 or data[1] == 1 or data[1] == 2 or data[1] == 3: # not connected
                     self.Status  = 0 # not connected
                elif  data[1] == 4 or data[1] == 5  or data[1] == 6: # connected - wait for ok
                     if self.StatusOld == 2:
                        self.Status = 3 # Charged
                     else:
                        self.Status = 1 # connected
                elif data[1] == 7: # ready to charge
                    if self._dbusservice["/Ac/Power"] > 0 or self.charging_current > 0:
                        self.Status = 2 # charge
                    else:
                        if self.StatusOld < 2: # noch nicht geladen
                            self.Status = 6 # waiting for start
                        else: # 
                            self.Status = 3 # Charged
                else:
                    self.Status = 8 # PLACEHOLDER: ground test error

            #logging.info("self.Status=%i old=%i" % (self.Status,self._dbusservice['/Status']))


            if self.Status == 2 and self.StatusOld == 1:
                self.charging_time["start"] = now
                logging.info("Start Charging: Energy: %f" % (self.Energy))
 

            if (self.Status == 3 or self.Status == 0) and self.StatusOld == 2:
                self.charging_time["stopped_since"] = now
                logging.info("Stop Charging: Energy: %f reset after %i Seconds" % (self.Energy,self.STOP_CHARGING_COUNTER_AFTER))
                self._dbusservice['/SetCurrent'] = 0

            if self.charging_time["stopped_since"] is not None and self.STOP_CHARGING_COUNTER_AFTER < (now - self.charging_time["stopped_since"]):
                self.charging_time["start"] = None
                self.charging_time["stopped_since"] = None
                self._dbusservice["/ChargingTime"] = None
                self.Status = 1
                self._dbusservice['/Ac/Energy/ForwardStart'] = self.Energy
                logging.info("Reset Charging: Energy: %f after %i Seconds" % (self.Energy,self.STOP_CHARGING_COUNTER_AFTER))
            if self._dbusservice['/Status']  != self.Status:
                logging.info("Victron EV Status changed self.Status=%i old=%i" % (self.Status,self._dbusservice['/Status']))

            self._dbusservice['/Status']  = self.Status

            # calculate charging time if charging started
            if self.charging_time["start"] is not None:
                self._dbusservice["/ChargingTime"] = now - self.charging_time["start"]


            # easc = self.getHeidelbergChargerData("/evse/auto_start_charging")
            # if easc["auto_start_charging"]:
            #     self._dbusservice['/AutoStart'] = 1
            # else:
            #     self._dbusservice['/AutoStart'] = 0

            # if not self.enable_charging:
            #     self._dbusservice['/StartStop'] = 0
            # else:
            #     self._dbusservice['/StartStop'] = 1

            # # increment UpdateIndex - to show that new data is available
            index = self._dbusservice['/UpdateIndex'] + 1  # increment index
            if index > 255:   # maximum value of the index
                index = 0       # overflow from 255 to 0
            self._dbusservice['/UpdateIndex'] = index

            # # update lastupdate vars
            self._lastUpdate = time.time()
            self._lastUpdateOld = 0
            setcurrent = 0



            setValue = self._dbusservice['/SetCurrent']*10
            if (type(setValue) == int) or (type(setValue) == float):
                setcurrent = int(setValue)
                if(self.charging_current != setcurrent):
                    logging.debug("Curent set=%i ret=%i Heidelberg WB status=%s"   % (setcurrent, data[2],data[1]))
                    self.charging_current = setcurrent
                modbusClient.write_register(261, setcurrent ,functioncode=6) 
            else:
                logging.error("setValue type=%s"   % (type(setValue)))

            if self.ret_current != self._dbusservice['/Current']:
                logging.debug("Curent set=%i ret=%i Heidelberg WB status=%s"   % (setcurrent, data[2],data[1]))
                self.ret_current = self._dbusservice['/Current']
            if self.heidelberg_status !=  data[1]:
                logging.debug("Curent set=%i ret=%i Heidelberg WB status=%s"   % (setcurrent, data[2],data[1]))
                self.heidelberg_status =  data[1]  
              
        except minimalmodbus.NoResponseError:
            sys.exit()
            #logging.critical('minimalmodbus.NoResponseError')
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)
            sys.exit()
        return True


def main():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

    # configure logging
    logging.basicConfig(      format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=config['DEFAULT']['Logging'])


    try:
        logging.debug("Start")
        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        # formatting
        _kwh = lambda p, v: (str(round(v, 2)) + 'kWh')
        _a = lambda p, v: (str(round(v, 1)) + 'A')
        _w = lambda p, v: (str(round(v, 1)) + 'W')
        _v = lambda p, v: (str(round(v, 1)) + 'V')
        _degC = lambda p, v: (str(v) + '°C')
        _s = lambda p, v: (str(v) + 's')
        _n = lambda p, v: (str(v))

        # start our main-service
        evcharger_output = DbusHeidelbergChargerService(
          config=config,
          servicename='com.victronenergy.evcharger',
          paths={
            '/Ac/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
            '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
            '/Ac/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L1/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L2/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L3/Voltage': {'initial': 0, 'textformat': _v},
            '/Ac/L1/Current': {'initial': 0, 'textformat': _a},
            '/Ac/L2/Current': {'initial': 0, 'textformat': _a},
            '/Ac/L3/Current': {'initial': 0, 'textformat': _a},
            '/Ac/Frequency': {'initial': 0, 'textformat': _v},
            '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh},
            '/Current': {'initial': 0, 'textformat': _a},
            '/MinCurrent': {'initial': 0, 'textformat': _a},
            '/MaxCurrent': {'initial': 0, 'textformat': _a},
            '/SetCurrent': {'initial': 0, 'textformat': _a},
            '/MCU/Temperature': {'initial': 0, 'textformat': _degC},
            '/AutoStart': {'initial': 0, 'textformat': _n},
            '/ChargingTime': {'initial': 0, 'textformat': _s},
            '/Mode': {'initial': 0, 'textformat': _n},
            '/StartStop': {'initial': 0, 'textformat': _n},
            '/Status': {'initial': 0, 'textformat': _n},
          }
        )

        logging.debug('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)
        sys.exit()
if __name__ == "__main__":
    main()
