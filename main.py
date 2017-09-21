#!/usr/bin/python3

import socket  
import time
import fcntl
import re
import os
import errno
import struct
import threading
from time import sleep
from collections import OrderedDict
import datetime

testing = datetime.datetime.now()
times = [
	# ((testing+datetime.timedelta(seconds=10)).time(),(4000,80)),
	# ((testing+datetime.timedelta(seconds=20)).time(),(2000,80))
	(datetime.time(6, 0, 0),(4000, 80)),
	(datetime.time(22, 0, 0),(2000, 40))
]
alarm_time = datetime.time(6, 50, 0)
color = (2000, 1)
movie = False

event = threading.Event()
event.clear()
lock = threading.Lock()

detected_bulbs = {}
bulb_idx2ip = {}
DEBUGGING = False
RUNNING = True
current_command_id = 0
MCAST_GRP = '239.255.255.250'
scan_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
fcntl.fcntl(scan_socket, fcntl.F_SETFL, os.O_NONBLOCK)
listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
listen_socket.bind(("", 1982))
fcntl.fcntl(listen_socket, fcntl.F_SETFL, os.O_NONBLOCK)
mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
listen_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

def debug(msg):
	if DEBUGGING:
		print(msg)

def next_cmd_id():
	global current_command_id
	current_command_id += 1
	return current_command_id
		
def send_search_broadcast():
	'''
	multicast search request to all hosts in LAN, do not wait for response
	'''
	multicase_address = (MCAST_GRP, 1982) 
	debug("send search request")
	msg = "M-SEARCH * HTTP/1.1\r\n" 
	msg = msg + "HOST: 239.255.255.250:1982\r\n"
	msg = msg + "MAN: \"ssdp:discover\"\r\n"
	msg = msg + "ST: wifi_bulb"
	scan_socket.sendto(msg.encode(), multicase_address)

def bulbs_detection_loop():
	'''
	a standalone thread broadcasting search request and listening on all responses
	'''
	debug("bulbs_detection_loop running")
	search_interval=5000
	read_interval=100
	time_elapsed=0

	while RUNNING:
		if time_elapsed%search_interval == 0:
			send_search_broadcast()

		# scanner
		while True:
			try:
				data = scan_socket.recv(2048)
			except socket.error as e:
				err = e.args[0]
				if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
						break
				else:
						print(e)
						sys.exit(1)
			handle_search_response(data.decode())

		# passive listener 
		while True:
			try:
				data, addr = listen_socket.recvfrom(2048)
			except socket.error as e:
				err = e.args[0]
				if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
						break
				else:
						print(e)
						sys.exit(1)
			handle_search_response(data.decode())

		time_elapsed+=read_interval
		sleep(read_interval/1000.0)
	scan_socket.close()
	listen_socket.close()

def get_param_value(data, param):
	'''
	match line of 'param = value'
	'''
	param_re = re.compile(param+":\s*([ -~]*)") #match all print(able characters)
	match = param_re.search(data)
	value=""
	if match != None:
		value = match.group(1)
		return value
		
def handle_search_response(data):
	'''
	Parse search response and extract all interested data.
	If new bulb is found, insert it into dictionary of managed bulbs. 
	'''
	location_re = re.compile("Location.*yeelight[^0-9]*([0-9]{1,3}(\.[0-9]{1,3}){3}):([0-9]*)")
	match = location_re.search(data)
	if match == None:
		debug( "invalid data received: " + data )
		return 

	host_ip = match.group(1)
	if host_ip in detected_bulbs:
		bulb_id = detected_bulbs[host_ip][0]
	else:
		bulb_id = len(detected_bulbs)
	host_port = match.group(3)
	model = get_param_value(data, "model")
	power = get_param_value(data, "power") 
	bright = get_param_value(data, "bright")
	rgb = get_param_value(data, "rgb")
	# use two dictionaries to store index->ip and ip->bulb map
	detected_bulbs[host_ip] = [bulb_id, model, power, bright, rgb, host_port]
	bulb_idx2ip[bulb_id] = host_ip
	# if event.is_set(): #not startup
	# 	set_day(0, 110, color[0], color[1]);
	if(len(detected_bulbs)>0):
		event.set()


def display_bulb(idx):
	if not idx in bulb_idx2ip:
		print("error: invalid bulb idx")
		return
	bulb_ip = bulb_idx2ip[idx]
	model = detected_bulbs[bulb_ip][1]
	power = detected_bulbs[bulb_ip][2]
	bright = detected_bulbs[bulb_ip][3]
	rgb = detected_bulbs[bulb_ip][4]
	print (str(idx) + ": ip=" \
		+bulb_ip + ",model=" + model \
		+",power=" + power + ",bright=" \
		+ bright + ",rgb=" + rgb)

def display_bulbs():
	print(str(len(detected_bulbs)) + " managed bulbs")
	for i in range(0, len(detected_bulbs)):
		display_bulb(i)

def operate_on_bulb(idx, method, params):
	'''
	Operate on bulb; no gurantee of success.
	Input data 'params' must be a compiled into one string.
	E.g. params="1"; params="\"smooth\"", params="1,\"smooth\",80"
	'''
	if not idx in bulb_idx2ip:
		print("error: invalid bulb idx")
		return
	
	bulb_ip=bulb_idx2ip[idx]
	port=detected_bulbs[bulb_ip][5]
	lock.acquire()
	try:
		tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# print("connect ",bulb_ip, port ,"...")
		tcp_socket.connect((bulb_ip, int(port)))
		msg="{\"id\":" + str(next_cmd_id()) + ",\"method\":\""
		msg += method + "\",\"params\":[" + params + "]}\r\n"
		# print(msg[:-2], datetime.datetime.now().replace(microsecond=0), flush=True)
		tcp_socket.send(msg.encode())
		tcp_socket.close()
	except Exception as e:
		print("Unexpected error:", e)
	lock.release()

def set_day(idx, dur, temp, bright):
	cmd = "1,1,\""+str(dur)+",2,"+str(temp)+","+str(bright)+"\""
	operate_on_bulb(idx, "start_cf", cmd)

def toggle_bulb(idx):
	global movie
	bulb_ip = bulb_idx2ip[idx]
	power = detected_bulbs[bulb_ip][2]
	if power == "on":
		set_day(0, 100, 2000, 1)
		sleep(0.2)
		movie = False
		detected_bulbs[bulb_ip][2] = "off"
		operate_on_bulb(idx, "toggle", "")
	else:
		detected_bulbs[bulb_ip][2] = "on"
		operate_on_bulb(idx, "toggle", "")
		sleep(0.1)

def alarm_day(alarm_time):
	now = datetime.datetime.now()
	alarm = datetime.datetime.combine(datetime.date.today(),alarm_time)
	if now > alarm:
		alarm = datetime.datetime.combine(datetime.date.today()+datetime.timedelta(days=1),alarm_time)
	return alarm
	
def day_loop():
	i = 0
	global color
	global alarm
	while RUNNING:
		now = datetime.datetime.now()
		soon = datetime.datetime.combine(datetime.date.today(),times[i][0])
		while now > soon:
			i += 1
			if i == len(times):
				i = 0;
				soon = datetime.datetime.combine(datetime.date.today()+datetime.timedelta(days=1),times[i][0])
				break;
			soon = datetime.datetime.combine(datetime.date.today(),times[i][0])
		color = times[i-1][1]
		set_day(0, 60000, color[0], color[1])
		alarm = alarm_day(alarm_time)
		while RUNNING and now < soon:
			if detected_bulbs[bulb_idx2ip[0]][2] == "off" and (alarm-now).total_seconds() < 5:
				toggle_bulb(0)
				set_day(0, 60000, 6000, 100)
			sleep(1) # killable
			now = datetime.datetime.now()

def control_loop():
	control_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
	control_socket.bind(("", 23232))
	global alarm
	global movie
	while RUNNING:
		data, addr = control_socket.recvfrom(4096)
		if addr[0] != "127.0.0.1":
			data = data.decode()
			global alarm_time
			if data == 't':
				toggle_bulb(0)
				set_day(0, 1000, color[0], color[1])
				sleep(1)
				movie = False
			elif data == 'm':
				if detected_bulbs[bulb_idx2ip[0]][2] == "off":
					toggle_bulb(0)
					movie = True
				else:
					if movie:
						set_day(0, 1000, color[0], color[1]);
					else:
						set_day(0, 1000, 2000, 1);
					movie = not movie
			elif data == 'u':
				control_socket.sendto(alarm_time.strftime("%H%M").encode(),addr)
			else:
				h = int(data[1:3])
				m = int(data[3:])
				alarm_time = datetime.time(h, m, 0)
				alarm = alarm_day(alarm_time)
	control_socket.close()

def handle_user_input():
	while True:
		command_line = input("Enter a command: ")
		command_line.lower() # convert all user input to lower case, i.e. cli is caseless
		argv = command_line.split() # i.e. don't allow parameters with space characters
		if len(argv) == 0:
			continue
		if argv[0] == "q":
			print("Bye!")
			return
		elif argv[0] == "l":
			display_bulbs()
		elif argv[0] == "t":
			toggle_bulb(0)
		elif len(argv) == 2:
			try:
				temp = int(float(argv[0]))
				bright = int(float(argv[1]))
				set_day(0, 1000, temp, bright)
			except:
				pass

detection_thread = threading.Thread(target=bulbs_detection_loop)
detection_thread.start()

event.wait()
print("Ready")

control_thread = threading.Thread(target=control_loop)
control_thread.start()

timer_thread = threading.Thread(target=day_loop)
timer_thread.start()

# user interaction loop
handle_user_input()
# user interaction end, tell detection thread to quit and wait
RUNNING = False
kill_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
kill_socket.sendto("".encode(), ("localhost", 23232))
kill_socket.close()
detection_thread.join()
control_thread.join()
timer_thread.join()
# done
