#
# A tool designed to create a bond over TCP tunnel with crap connections ( ADSL , wimax, HSPA and stuff like that )
# Copyright (C) 2015  Tiziano Bacocco <tiziano@tizbac.ovh>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
#

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
    print("Usage PoorMansBonding.py dev password port1 [port2] ...")
    sys.exit(1)

PoorMansBondingProtocol.tun = open("/dev/net/tun", "r+b")
PoorMansBondingProtocol.password = sys.argv[2]
ifr = struct.pack("16sH", sys.argv[1], IFF_TUN | IFF_NO_PI)
fcntl.ioctl(PoorMansBondingProtocol.tun , TUNSETIFF, ifr)

subprocess.check_call("ifconfig %s 192.168.10.1 pointopoint 192.168.10.2 up"%(sys.argv[1]),shell=True)

factory = protocol.ServerFactory()
factory.protocol = PoorMansBondingProtocol.PoorMansBondingProtocol

for x in sys.argv[3:]:
    print("Listening on %d"%int(x))
    reactor.listenTCP(int(x),factory)
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