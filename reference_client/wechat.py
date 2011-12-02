#!/Library/Frameworks/Python.framework/Versions/2.7/bin/python
import argparse, signal, sys, httplib, threading, Queue, time, thread

class ChatError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

def setup_parser():
	parser = argparse.ArgumentParser(description='Like "wall", but better.')
	parser.add_argument('username', help="Your username.")
	parser.add_argument('server', help="The server name for the chat.")
	parser.add_argument('channel', help="The channel name for the chat.")
	return parser

def process_args(parser):
	args = parser.parse_args()
	username = args.username
	server = args.server
	url = "channels/" + args.channel
	return (username, server, url)
	
def sigint_handler(signal, frame):
	print
	print "Winners never quit and quitters never win!"
	leavechat(0)
	sys.exit(0)
	
def leavechat(type):
	global server, port, url, username, session_key
	h = httplib.HTTPConnection(server, port)
	h.request('PUT', url + "/leave/" + username, "", {'session': session_key})
	sys.exit(type)

class NetworkTalker(threading.Thread):
	def __init__(self, termq, netq, username, server, url, port):
		global session_key
		threading.Thread.__init__(self)
		self.termq = termq
		self.q = netq
		self.username = username
		self.server = server
		self.url = url
		self.port = port
		self.pollint = 1
		self.seqnr = 0
			
	def run(self):
		self.try_join(self.empty_response())
		while(True):
			try:
				event = self.q.get(True, 1)
				if (event['command'] == 'putmsg'):
					self.putmsg(event['data'])
			except Queue.Empty:
				try:
					r = self.getevt()
					if r['headers']['type'] == 'DIR':
						self.termq.put(r['headers']['sequence'] + ": New directory: " + "> " + r['body'] + "\n")
					else:
						self.termq.put(r['headers']['sequence'] + ": " + r['headers']['source'] + "> " + r['body'] + "\n")
				except ChatError as ce:
					if ce.value == httplib.NOT_FOUND:
						"NOP"
			except Exception as e:
				print "exception happened in net!: " + str(e)
				
	def joinchat(self):
		h = httplib.HTTPConnection(self.server, self.port)
		h.request('PUT', self.url + "/join/" + self.username, "", {})
		return self.process_data(h.getresponse())
	
	def putmsg(self, msg):
		h = httplib.HTTPConnection(self.server, self.port)
		h.request('PUT', self.url + "/messages", msg, {'session': session_key})
		return self.process_data(h.getresponse())
		
	def getevt(self):
		h = httplib.HTTPConnection(self.server, self.port)
		h.request('GET', self.url + "/events", "", {'session': session_key, 'sequence': self.seqnr})
		return self.process_data(h.getresponse())
	
	def try_join(self, response):
		joined = False
		while joined == False:
			self.server = response['body']
			try:
				response = self.joinchat()
			except ChatError as ce:
				if ce.value == httplib.CONFLICT:
					print "\nERROR: Username taken for channel."
					thread.interrupt_main()
					sys.exit(1)
					thread.exit()
				elif ce.value == httplib.MOVED_PERMANENTLY:
					print "\nERROR: Server moved. Redirecting..."
			session_key = response['headers']['session']
			joined = True
			
	def empty_response(self):
		return {'status': '', 'headers': '', 'body': ''}
			
	def process_data(self, resp):
		global session_key
		headers = {}
		for k,v in resp.getheaders():
			headers[k] = v
		r = {'status': resp.status, 'headers': headers, 'body': resp.read()}
		if 'session' in r['headers']:
			session_key = r['headers']['session']
		if 'sequence' in r['headers']:
			self.seqnr = r['headers']['sequence']
		if r['status'] == httplib.NOT_FOUND:
			raise ChatError(httplib.NOT_FOUND)
		if r['status'] == httplib.MOVED_PERMANENTLY:
			raise ChatError(httplib.MOVED_PERMANENTLY)
		if r['status'] == httplib.CONFLICT:
			raise ChatError(httplib.CONFLICT)
		if r['status'] == httplib.UNAUTHORIZED:
			raise ChatError(httplib.UNAUTHORIZED)
		# print " DEBUG RESPONSE: " + str(r)
		return r
	
class Terminal(threading.Thread):
	def __init__(self, termq):
		threading.Thread.__init__(self)
		print "Welcome to WeChat! Type 'Ctrl-C' to quit."
		self.q = termq
	
	def run(self):
		while(True):
			line = self.q.get()
			sys.stdout.write("\n" + line)
			sys.stdout.flush()
			
class Keyboard(threading.Thread):
	def __init__(self, termq, netq):
		threading.Thread.__init__(self)
		self.q = termq
		self.netq = netq
	
	def run(self):
		self.q.put(username + "> ")
		while(True):
			self.netq.put({'command': 'putmsg', 'data': raw_input()})
			self.q.put(username + "> ")
			
# MAIN
# handle Ctrl-C
signal.signal(signal.SIGINT, sigint_handler)
# process args
(username, server, url) = process_args(setup_parser())
port = 8000
session_key = ""
# setup queues
termq = Queue.Queue()
netq = Queue.Queue()

# start threads
nt = NetworkTalker(termq, netq, username, server, url, port)
nt.daemon = True
nt.start()
t = Terminal(termq)
t.daemon = True
t.start()
k = Keyboard(termq, netq)
k.daemon = True
k.start()

while(True):
	time.sleep(1)