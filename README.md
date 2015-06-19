# PoorMansBonding
A tool designed to create a bond over TCP tunnel with crap connections ( ADSL , wimax, HSPA and stuff like that )


What you need
=============
A Remote Linux server ( a VPS from OVH is ok, before buying check if tun/tap is available )
A Router with multiwan capabilities, like OpenWrt 15.05 with MWAN3
A Machine or a board to use as an access concentrator, like a raspberry pi

Usage
=====
On the server , start the program with python PoorMansBonding.py pmb0 yoursupersecurepassword port0 port1 port2
For example: python PoorMansBonding.py pmb0 yoursupersecurepassword 100 101 102
And then add an iptables rule to do NAT for the vpn

iptables -t nat -A POSTROUTING -s 192.168.10.0/24 -j MASQUERADE

On the concentrator 

python PoorMansBonding_client.py pmb0 yoursupersecurepassword yourserver:100 yourserver:101 yourserver:102

and the add the default route to 192.168.10.1

route add default gw 192.168.10.1

