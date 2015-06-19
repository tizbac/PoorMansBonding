from twisted.internet import reactor, protocol
import time
import struct
import os
import sys
import random
from Crypto.Cipher import AES
import hashlib

latestseq = 0
txseq = 0
tun = None
CMD_PUSH_DATA = 0x00
CMD_PUSH_WEIGHT = 0x01
CMD_AUTH_PEER = 0x02
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
        self.lastwtime = time.time() # Last time weight was sent to remote peer
        self.auth = False
        self.incomingcipher = AES.new(hashlib.sha256(password).digest(), AES.MODE_CBC, hashlib.sha256(password).digest()[:16])
        self.outgoingcipher = AES.new(hashlib.sha256(password).digest(), AES.MODE_CBC, hashlib.sha256(password).digest()[:16])

    def connectionMade(self):
        self.sendPacket(CMD_AUTH_PEER, password)
    def connectionLost(self, reason):
        if self in connections:
            connections.remove(self)
    def sendPacket(self, cmd, data):
        global txseq
        datapadded = data+"\x00"*(16-(len(data)%16))
        #CMD,PADDING,LEN,SEQ
        self.transport.write(struct.pack(">BBHI",int(cmd),16-len(data)%16,len(datapadded),txseq)+self.outgoingcipher.encrypt(datapadded))
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
            
            decdata = self.incomingcipher.decrypt(self.rxbuffer[8:8+plen])
            decdata = decdata[:len(decdata)-pad]
            
            if self.auth:
                if cmd == CMD_PUSH_DATA:
                    sendqueue.append((seq,decdata))
                    #os.write(tun.fileno(), decdata)
                    while True:
                        sent = False
                        for x in list(sendqueue):
                            if x[0] == lastsentseq+1:
                                if len(x[1]) > 0:
                                    os.write(tun.fileno(), x[1])
                                lastsentseq = x[0]
                                sendqueue.remove(x)
                                sent = True
                        if not sent:
                            break
                if cmd == CMD_PUSH_WEIGHT:
                    sendqueue.append((seq,""))
                    self.localweight = struct.unpack(">I",decdata)[0]
                    print("%s : Weight: Local=%d Remote=%d\n"%(str(self.transport),self.remoteweight,self.localweight))
                    #print("%s: New weight rcvd: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if cmd == CMD_AUTH_PEER:
                sendqueue.append((seq,""))
                if decdata == password:
                    self.auth = True
                    connections.append(self)
                else:
                    print("Invalid password: "+password)
            self.rxbuffer = self.rxbuffer[8+plen:]
            if time.time()-self.lastwtime > 2.0:
                self.sendPacket(CMD_PUSH_WEIGHT, struct.pack(">I",self.remoteweight))
                self.lastwtime = time.time()
                #print("%s: New weight: %d,%d"%(str(self),self.remoteweight,self.localweight))
            if len(self.rxbuffer) < 8:
                break
            cmd, pad, plen, seq = struct.unpack(">BBHI",self.rxbuffer[:8])