from twisted.internet import reactor, protocol
import time
import struct
import os
import sys
import random
latestseq = 0
txseq = 0
tun = None
CMD_PUSH_DATA = 0x00
CMD_PUSH_WEIGHT = 0x01
CMD_AUTH_PEER = 0x02
connections = []
password = "123456789"
class PoorMansBondingProtocol(protocol.Protocol):
    def __init__(self):
        self.rxbuffer = ""
        self.remoteweight = 500
        self.localweight = 500
        self.txseq = 0
        self.rxbytes = 0
        self.txbytes = 0
        self.lastwtime = time.time() # Last time weight was sent to remote peer
        self.auth = False
    def connectionMade(self):
        self.sendPacket(CMD_AUTH_PEER, password)
    def connectionLost(self, reason):
        if self in connections:
            connections.remove(self)
    def sendPacket(self, cmd, data):
        global txseq
        self.transport.write(struct.pack(">BHI",int(cmd),len(data),txseq)+data)
        txseq += 1
    def printStatus(self):
        pass
    def dataReceived(self, data):
        global latestseq
        self.rxbuffer += data
        
        if len(self.rxbuffer) < 7:
            return
        cmd, plen, seq = struct.unpack(">BHI",self.rxbuffer[:7])
        #print(len(self.rxbuffer),plen-7,":".join("{:02x}".format(ord(c)) for c in self.rxbuffer))
        while len(self.rxbuffer) >= plen+7:
            coeff = seq-latestseq-1;
            if random.randint(0,10) == 1:
                if coeff > 0:
                    self.remoteweight += 1 # If we got a packet before other connections it means that this stream is faster so its weight can be increased , if it is behind instead it means it is too slow so the weight has to be reduced
                else:
                    self.remoteweight -= 1 
                if self.remoteweight < 1:
                    for c in connections:
                        c.remoteweight += 1
                    self.remoteweight = 1
            
            latestseq = max(latestseq,seq)
            #print (cmd,plen,seq)
            if self.auth:
                if cmd == CMD_PUSH_DATA:
                    os.write(tun.fileno(), self.rxbuffer[7:7+plen])
                if cmd == CMD_PUSH_WEIGHT:
                    self.localweight = struct.unpack(">I",self.rxbuffer[7:7+plen])[0]
                    print("%s : Weight: Local=%d Remote=%d\n"%(str(self),self.remoteweight,self.localweight))
                    #print("%s: New weight rcvd: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if cmd == CMD_AUTH_PEER:
                if self.rxbuffer[7:7+plen] == password:
                    self.auth = True
                    connections.append(self)
            self.rxbuffer = self.rxbuffer[7+plen:]
            if time.time()-self.lastwtime > 2.0:
                self.sendPacket(CMD_PUSH_WEIGHT, struct.pack(">I",self.remoteweight))
                self.lastwtime = time.time()
                #print("%s: New weight: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if len(self.rxbuffer) < 7:
                break
            cmd, plen, seq = struct.unpack(">BHI",self.rxbuffer[:7])