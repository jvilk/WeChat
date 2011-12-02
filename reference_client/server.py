from BaseHTTPServer import *
import httplib
import random
import string

channels = {}

class ChatException(Exception):
	def donothing():
		print 'doing nothing'

class Chat:
	def __init__(self, name):
		self.name = name
		self.seq = 0
		self.events = {}
		self.members = {}
		channels[name] = self
	
	def make_directory(self):
		s = ''
		for session in self.members:
			s += self.members[session]+','
		
		return s
	
	def push_event(self, data):
		n = self.seq
		self.seq += 1
		
		data['sequence'] = str(n)
		self.events[n] = data
		
		print str(n)+': '+str(data)
		
		return n
	
	def has(self, session):
		return session in self.members
	
	def join(self, name):
		for s in self.members:
			if self.members[s] == name:
				raise ChatException('Username is already in use')
		
		session = str(random.randint(0, 999999999))
		
		while session in self.members:
			session = str(random.randint(0, 999999999))
		
		self.members[session] = name
		
		self.push_event({
			'type': 'DIR',
			'body': self.make_directory()
		})
		
		return session
	
	def leave(self, session):
		if session not in self.members:
			raise ChatException('Session is not in the channel')
		
		del self.members[session]
		
		self.push_event({
			'type': 'DIR',
			'body': self.make_directory()
		})
	
	def send_message(self, session, body):
		if session not in self.members:
			raise ChatException('Session is not in the channel')
		
		self.push_event({
			'type': 'MSG',
			'source': self.members[session],
			'body': body
		});
	
	def get_event(self, seq):
		if seq >= self.seq:
			raise ChatException('No new events')
		
		s = seq + 1
		while s not in self.events and s < self.seq:
			s += 1
		
		if s >= self.seq:
			raise ChatException('No new events')
			
		return self.events[s]

class ChatHandler(BaseHTTPRequestHandler):
	def parse_command(self, s):
		parts = s.split('/')

		if parts[0] != 'channels' or len(parts) < 3 or len(parts) > 4:
			raise ChatException('Invalid request')
		
		response = {
			'channel_name': parts[1],
			'action': parts[2]
		}
		
		if parts[1] in channels:
			response['channel'] = channels[parts[1]]
		
		if len(parts) == 4:
			response['username'] = parts[3]
			
		return response
	
	def do_GET(self):
		print 'path: '+self.path
		print 'headers: '+str(self.headers)
		
		try:
			# Unpak the command
			cmd = self.parse_command(self.path)
		except ChatException:
			# Invalid command.  Return an error.
			self.send_response(httplib.BAD_REQUEST)
			return

		# User is requesting a directory
		if cmd['action'] == 'directory' and 'channel' in cmd and 'session' in self.headers:
			if cmd['channel'].has(self.headers['session']):
				self.send_response(httplib.OK)
				self.end_headers()
				self.wfile.write(cmd['channel'].make_directory())
				
			else:
				# Session is not in the channel
				self.send_response(httplib.UNAUTHORIZED)
		
		# Users is requesting a new event	
		elif cmd['action'] == 'events' and 'channel' in cmd and 'session' in self.headers and 'sequence' in self.headers:
			try:
				seq = int(self.headers['sequence'])
			except:
				# Sequence number was not an integer
				self.send_response(httplib.BAD_REQUEST)
			
			if not cmd['channel'].has(self.headers['session']):
				self.send_response(httplib.UNAUTHORIZED)
				return
			
			try:
				e = cmd['channel'].get_event(seq)
				self.send_response(httplib.OK)
				
				for k in e:
					if k != 'body':
						self.send_header(k, e[k])
				
				self.end_headers()
				self.wfile.write(e['body'])
					
			except ChatException:
				# No events available
				self.send_response(httplib.NOT_FOUND)
		
		# Unrecognized action	
		else:
			self.send_response(httplib.BAD_REQUEST)
	
	def do_PUT(self):
		print 'path: '+self.path
		print 'headers: '+str(self.headers)
		
		try:
			# Unpack the command
			cmd = self.parse_command(self.path)
		except ChatException:
			# Invalid command.  Return an error.
			self.send_response(httplib.BAD_REQUEST)
			return
		
		# User is asking to join channel
		if cmd['action'] == 'join' and 'username' in cmd:
			if 'channel' not in cmd:
				cmd['channel'] = Chat(cmd['channel_name'])
			
			try:
				session = cmd['channel'].join(cmd['username'])
				
				self.send_response(httplib.OK)
				self.send_header('session', str(session))
				self.send_header('sequence', cmd['channel'].seq)
				
			except ChatException:
				# User name is not available
				self.send_response(httplib.CONFLICT)
			
		# User is asking to leave channel
		elif cmd['action'] == 'leave' and 'channel' in cmd and 'session' in self.headers:
			try:
				cmd['channel'].leave(self.headers['session'])
				self.send_response(httplib.OK)
				
			except ChatException:
				# Session key not valid for channel
				self.send_response(httplib.UNAUTHORIZED)
		
		# Users is sending a message to channel
		elif cmd['action'] == 'messages' and 'channel' in cmd and 'session' in self.headers and 'content-length' in self.headers:
			try:
				length = int(self.headers['content-length'])
				body = self.rfile.read(length)
				
				cmd['channel'].send_message(self.headers['session'], body)
				
				self.send_response(httplib.OK)
			
			except ChatException:
				# Session key is not valid for channel
				self.send_response(httplib.UNAUTHORIZED)
			
		# Unrecognized action.  Return an error.
		else:
			self.send_response(httplib.BAD_REQUEST)
			return

httpd = HTTPServer(('', 8000), ChatHandler)
httpd.serve_forever()
