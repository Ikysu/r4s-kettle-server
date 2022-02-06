import pygatt
import time
from flask import Flask
app = Flask(__name__)

if len(sys.argv) > 1:
    mac = sys.argv[1]
else:
    mac = input("MAC (00:00:00:00:00:00) >")
if len(sys.argv) > 2:
    key = sys.argv[2]
else:
    key = input("HEX UUID (ffffffffffffffff)>")

handle_rx = 11 # read
handle_tx = 14 # write


ite = 0
def hh(he):
    return format(he, 'x')
def toBytes(hex):
    return [int(hex[i:i+2],16) for i in range(0,len(hex),2)]
def twoSplitter(hex):
    return [hex[i:i+2] for i in range(0,len(hex),2)]

def getIter():
    global ite
    nowite=ite
    if ite<100:
        ite=ite+1
    else:
        ite=0
    
    return nowite

def toHex(bytes):
    return ''.join('{:02x}'.format(x) for x in bytes)

def timeInvert(data):
    out = []
    li = list(hh(data))
    le = (int)(len(li)/2)
    for i in range(0,len(li),2): out.append(li[i]+""+li[i+1])
    return "".join(list(reversed(out)))

def getTMZ(id):
    return timeInvert(id*60*60)
    
def getTime():
    return timeInvert(int(time.time()))

def hexToDec(s):
    return int(s, 16)


adapter = pygatt.backends.GATTToolBackend()


try:
    adapter.start()
    device = adapter.connect(mac, address_type=pygatt.BLEAddressType.random, auto_reconnect=True)


    def auth():
        try:
            print("Отправляем авторизацию")
            device.char_write_handle(12, toBytes("0100"))
            print("Авторизуемся")
            au = call(bytearray([0x55, getIter(), 0xff] + toBytes(key) + [ 0xaa ]))
            if au != "ERR" and len(au) == 5 and au[3]=="01":
                print("Авторизованно")
                sync = call(bytearray([0x55, getIter(), 0x6e] + toBytes(getTime()+getTMZ(5)) + [0x00, 0x00, 0xaa]))
                return True
            else:
                print("Ошибка авторизации", au)
                return False
        except:
            print("Ошибка авторизации EXPECT")
            return False


    def tryAuth(trys=5):
        print("REAUTH", trys)
        try: # 1
            eAuth = auth()
            if eAuth: # 1
                print("REAUTH", trys, "RETURN 11", True)
                return True
            else: # 2
                if trys <= 1: # 1
                    print("REAUTH", trys, "RETURN 121", False)
                    return False
                else: # 2
                    print("REAUTH", trys, "RETURN 122", "WAIT")
                    time.sleep(5)
                    return tryAuth(trys-1)
        except: # 2
            if trys <= 1: # 1
                print("REAUTH", trys, "RETURN 21", False)
                return False
            else: # 2
                print("REAUTH", trys, "RETURN 22", "WAIT")
                time.sleep(5)
                return tryAuth(trys-1)

    def tryReconnect(trys=5):
        print("RECONNECT", trys)
        try:
            global device
            device = adapter.connect(mac, address_type=pygatt.BLEAddressType.random, auto_reconnect=True)
            out = tryAuth()
            print("RECONNECT", trys, "RETURN", out)
            return out
        except:
            if trys <= 1:
                print("RECONNECT EXCEPT", trys, "RETURN FALSE")
                return False
            else:
                print("RECONNECT EXCEPT", trys, "WAIT")
                time.sleep(5)
                return tryReconnect(trys-1)

    def tryCall(cmd):
        print("TRYCALL", cmd)
        try: # 1
            device.char_write_handle(14, cmd)
            out = twoSplitter(toHex(device.char_read_handle(11)))
            print("TRYCALL", cmd, "RETURN 1", out)
            return out
        except: # 2
            if tryReconnect():
                try:
                    device.char_write_handle(14, cmd)
                    out = twoSplitter(toHex(device.char_read_handle(11)))
                    print("TRYCALL", cmd, "RETURN 2", out)
                    return out
                except:
                    return "ERR"
                
            else:
                return "ERR"

    def call(cmd):
        print("CALL", cmd)
        try:
            device.char_write_handle(14, cmd)
            out = twoSplitter(toHex(device.char_read_handle(11)))
            print("CALL", cmd, "RETURN", out)
            return out
        except:
            print("CALL EXCEPT", cmd, "RETURN ERR")
            return "ERR"



    # Commands 
    def getStatus():
        status = tryCall(bytearray([0x55, getIter(), 0x06, 0xaa]))
        if status!= "ERR" and len(status) == 19:
            # Четвертый байт — режим работы (mode): 00 — кипячение, 01 — нагрев до температуры, 03 — ночник. 
            # Шестой байт — hex температура, до которой нужно нагревать в режиме работы «нагрев», в режиме кипячения равен 00. 
            # Девятый байт — hex текущая температура воды (2a=42 по Цельсию). 
            # Двенадцатый байт — это состояние чайника: 00 — выключен, 02 — включен. 
            # Семнадцатый байт — это продолжительность работы чайника после достижения нужной температуры, по умолчанию равна 80 в hex 
            # (видимо, это какие то относительные единицы, точно не секунды).
            return status[3]+"-"+status[5]+"-"+status[8]+"-"+status[11]
        else:
            return status

    def setSettings(mode, temp):
        if mode == 0:
            temp = 0
        # 55    00      05    00      00    00      00 00 00 00 00 00 00 00 00 00    50             00 00 aa
        # 55" + iter + "05" + mode + "00" + temp + "00 00 00 00 00 00 00 00 00 00" + howMuchBoil + "00 00 aa
        # mode: 00 — кипячение, 01 — нагрев до температуры, 03 — ночник. 
        # temp — hex температура, до которой нужно нагревать в режиме работы «нагрев», в режиме кипячения он равен 00. 
        # howMuchBoil — это продолжительность работы чайника после достижения нужной температуры, по умолчанию равна 80 в hex 
        # (видимо, это какие то относительные единицы, точно не секунды).
        sets = tryCall(bytearray([0x55, getIter(), 0x05, mode, 0x00, temp, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 80, 0x00, 0x00, 0xaa]))
        if sets!= "ERR" and len(sets) == 5 and sets[3]=="01":
            return "OK"
        else:
            return "ERR"

    def runKettle():
        try:
            runK = call(bytearray([0x55, getIter(), 0x03, 0xaa]))
            if runK!= "ERR" and len(runK) == 5 and runK[3]=="01":
                return "OK"
            else:
                return "ERR"
        except:
            return "ERR"

    def stopKettle():
        try:
            stopK = call(bytearray([0x55, getIter(), 0x04, 0xaa]))
            if stopK!= "ERR" and len(stopK) == 5 and stopK[3]=="01":
                return "OK"
            else:
                return "ERR"
        except:
            return "ERR"

    # Init
    #tryAuth() пре-авторизация

    @app.route('/<passwd>/status')
    def status(passwd):
        if passwd == key:
            return getStatus()
        else:
            return "ERR"

    @app.route('/<passwd>/set/<int:mode>/<int:tmp>')
    def setMode(passwd, mode, tmp):
        if passwd == key:
            if mode == 0 and tmp == 0:
                return setSettings(mode, tmp)
            elif mode>=1 and mode<=2 and tmp>=35 and tmp<=90:
                return setSettings(mode, tmp)
            else:
                return "ERR"
        else:
            return "ERR"
    
    @app.route('/<passwd>/run')
    def runKet(passwd):
        if passwd == key:
            return runKettle()
        else:
            return "ERR"

    @app.route('/<passwd>/stop')
    def stopKet(passwd):
        if passwd == key:
            return stopKettle()
        else:
            return "ERR"
    

    if __name__ == '__main__':
        app.run(host = "10.0.0.6", port = 5000, debug=True)
    
    
finally:
    print("fin")
    adapter.stop()