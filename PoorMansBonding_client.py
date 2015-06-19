import sys
import os
TUNSETIFF = 0x400454ca
TUNSETOWNER = TUNSETIFF + 2
IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000

CMD_PUSH_DATA = 0x00
CMD_PUSH_WEIGHT = 0x01

from twisted.internet import reactor, protocol
import struct
import subprocess
import fcntl
import time
import thread
import random
import PoorMansBondingProtocol
if len(sys.argv) < 3:
    print("Usage PoorMansBonding.py dev host1:port1 [host2:port2] ...")
    sys.exit(1)
    

PoorMansBondingProtocol.tun = open("/dev/net/tun", "r+b")
PoorMansBondingProtocol.password = sys.argv[2]
ifr = struct.pack("16sH", sys.argv[1], IFF_TUN | IFF_NO_PI)
fcntl.ioctl(PoorMansBondingProtocol.tun , TUNSETIFF, ifr)

subprocess.check_call("ifconfig %s 192.168.10.2 pointopoint 192.168.10.1 up"%(sys.argv[1]),shell=True)

factory = protocol.ClientFactory()
factory.protocol = PoorMansBondingProtocol.PoorMansBondingProtocol

for x in sys.argv[3:]:
    hostport = x.split(":")
    host = hostport[0]
    port = int(hostport[1])
    reactor.connectTCP(host,port, factory)
def pushPacket(data):
    totalW = 0
    cS = list(PoorMansBondingProtocol.connections)
    if len(cS) == 0:
        print("No streams connected")
        return
    for c in cS:
        totalW += c.localweight
    currW = 0
    pick = random.randint(0,totalW)
    choosen = None
    for c in cS:
        if pick < currW+c.localweight and pick >= currW:
            choosen = c
            break
        currW += c.localweight
    if choosen == None:
        choosen = cS[len(cS)-1]
    
    choosen.sendPacket(CMD_PUSH_DATA, data)
def tunReadThread():
    while True:
        data = os.read(PoorMansBondingProtocol.tun.fileno(), 2048)
        #print("RDATA",len(data))
        reactor.callFromThread(pushPacket, data)
thread.start_new_thread(tunReadThread,())
reactor.run()