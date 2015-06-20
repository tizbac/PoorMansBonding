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

from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall
import time
import struct
import os
import sys
import random
from Crypto.Cipher import AES
import hashlib
import zlib
latestseq = 0
txseq = 0
tun = None
CMD_PUSH_DATA = 0x00
CMD_PUSH_WEIGHT = 0x01
CMD_AUTH_PEER = 0x02
CMD_PING = 0x03
CMD_PONG = 0x04
CMD_AUTH_CHALLENGE = 0x05
connections = []
password = "123456789"
sendqueue = []
lastsentseq = 0
class PoorMansBondingProtocol(protocol.Protocol):
    def __init__(self):
        self.rxbuffer = ""
        self.remoteweight = 10
        self.localweight = 10
        self.txseq = 0
        self.rxbytes = 0
        self.txbytes = 0
        self.lastwtime = time.time() # Last time weight was sent to remote peer and updated
        self.auth = False
        self.incomingcipher = AES.new(hashlib.sha256(password).digest(), AES.MODE_CBC, hashlib.sha256(password).digest()[:16])
        self.outgoingcipher = AES.new(hashlib.sha256(password).digest(), AES.MODE_CBC, hashlib.sha256(password).digest()[:16])
        self.pingcall = LoopingCall(self.ping)
        self.timeoutcheck_call = LoopingCall(self.timeoutcheck)
        self.lastpong = time.time()
        self.challenge = "".join([ chr(ord("a")+random.randint(0,25)) for i in range(0,16) ])
        
        self.wsum = 0
        self.wcount = 0
    def timeoutcheck(self):
        if time.time() - self.lastpong > 10.0:
            print("Ping timeout on %s"%(str(self.transport)))
            self.transport.loseConnection()
            
    def ping(self):
        self.sendPacket(CMD_PING,"@"*16)
    def connectionMade(self):
        self.sendPacket(CMD_AUTH_CHALLENGE, self.challenge)
        print("%s: Sent auth challenge"%(str(self.transport)))
        self.pingcall.start(5.0)
        self.timeoutcheck_call.start(1.0)
        self.transport.setTcpKeepAlive(True)
        
        
        
    def connectionLost(self, reason):
        self.timeoutcheck_call.stop()
        self.pingcall.stop()
        #for x in list(sendqueue):
            #if x[2] == self:
                #sendqueue.remove(x)
        #if len(sendqueue) > 0:
            #self.lastsentseq = 2**31
            #for x in list(sendqueue):
                #if x[0] < self.lastsentseq:
                    #self.lastsentseq = x[0]
            #self.lastsentseq -= 1
        
        if self in connections:
            connections.remove(self)
    def sendPacket(self, cmd, data):
        global txseq
        comp = True
        datac = zlib.compress(data)
        if len(datac) >= len(data):
            datac = data #Not worth it
            comp = False
        
        datapadded = datac+"\x00"*(16-(len(datac)%16))
        #CMD,PADDING,LEN,SEQ
        pad = 16-len(datac)%16
        if comp:
            pad |= 0x80
        self.transport.write(struct.pack(">BBHI",int(cmd),pad,len(datapadded),txseq)+self.outgoingcipher.encrypt(datapadded))
        txseq += 1
    def printStatus(self):
        pass
    def dataReceived(self, data):
        global latestseq
        global lastsentseq
        global sendqueue
        self.rxbuffer += data
        
        if len(self.rxbuffer) < 8:
            return
        cmd, pad, plen, seq = struct.unpack(">BBHI",self.rxbuffer[:8])
        #print(len(self.rxbuffer),plen-8,":".join("{:02x}".format(ord(c)) for c in self.rxbuffer))
        while len(self.rxbuffer) >= plen+8:
            coeff = seq-latestseq-1;
            self.wsum += coeff
            self.wcount += 1
            latestseq = max(latestseq,seq)
            #print (cmd,plen,seq)
            
            decdata = self.incomingcipher.decrypt(self.rxbuffer[8:8+plen])
            decdata = decdata[:len(decdata)-(pad&0x7f)]
            
            if pad & 0x80:
                decdata = zlib.decompress(decdata)
            
            if self.auth:
                if cmd == CMD_PUSH_DATA:
                    #sendqueue.append((seq,decdata,self))
                    #print(sendqueue)
                    os.write(tun.fileno(), decdata)
                    #while True:
                        #sent = False
                        #for x in list(sendqueue):
                            #if x[0] == lastsentseq+1:
                                #if len(x[1]) > 0:
                                    #os.write(tun.fileno(), x[1])
                                #lastsentseq = x[0]
                                #sendqueue.remove(x)
                                #sent = True
                        #if not sent:
                            #break
                if cmd == CMD_PUSH_WEIGHT:
                    #sendqueue.append((seq,"",self))
                    self.localweight = struct.unpack(">I",decdata)[0]
                    print("%s : Weight: Local=%d Remote=%d\n"%(str(self.transport),self.remoteweight,self.localweight))
                    #print("%s: New weight rcvd: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if cmd == CMD_AUTH_PEER:
                #sendqueue.append((seq,"",self))
                if decdata == self.challenge+password:
                    self.auth = True
                    connections.append(self)
                    print("%s: Authentication successful"%str(self.transport))
                else:
                    print("Invalid password: "+password)
            if cmd == CMD_PING:
                #sendqueue.append((seq,"",self))
                self.sendPacket(CMD_PONG,decdata)
            if cmd == CMD_PONG:
                #sendqueue.append((seq,"",self))
                self.lastpong = time.time()
            if cmd == CMD_AUTH_CHALLENGE:
                print("%s: Received auth challenge"%(str(self.transport)))
                self.sendPacket(CMD_AUTH_PEER, decdata+password)
            self.rxbuffer = self.rxbuffer[8+plen:]
            if time.time()-self.lastwtime > 2.0:
                avg = float(self.wsum)/float(self.wcount)
                
                self.remoteweight = min(60,max(1,30+avg))
                self.wcount = 0
                self.wsum = 0
                self.sendPacket(CMD_PUSH_WEIGHT, struct.pack(">I",self.remoteweight))
                self.lastwtime = time.time()
                #print("%s: New weight: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if len(self.rxbuffer) < 8:
                break
            cmd, pad, plen, seq = struct.unpack(">BBHI",self.rxbuffer[:8])