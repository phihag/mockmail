#!/usr/bin/env python
# -*- coding: utf8 -*-

import BaseHTTPServer
import asyncore
import cgi
import datetime
import email.parser
import grp
import json
import mimetypes
import os
import pwd
import re
import smtpd
import tempfile
import time
import threading
from optparse import OptionParser

import pystache # If this fails, execute $ pip install pystache

_TEMPLATES = ('root', 'index', 'mail',)
_STATIC_FILES = ('mocksmtp.css', 'jquery-1.7.1.min.js', 'mocksmtp.js', )


def _readfile(fn):
	with open(fn, 'rb') as f:
		return f.read()

_BASE_DIR = os.path.dirname(__file__)

class _OnDemandIdReader(object):
	def __init__(self, ids, fnCalc, mapContent):
		self._ids = ids
		self._fnCalc = fnCalc
		self._mapContent = mapContent
	def __getitem__(self, key):
		if key not in self._ids:
			raise KeyError()
		res = _readfile(self._fnCalc(key))
		if self._mapContent:
			res = self._mapContent(res)
		return res
	def __len__(self):
		return len(self._ids)
	def __contains__(self, item):
		return item in self._ids

def _readIds(ids, fnCalc, mapContent=None, ondemand=False):
	""" Read all the files calculated by map(fnCalc, ids), and return a dictionary {id: mapContent(file content)}
	@param ondemand If this is set, do not actually return a dictionary, but a mock object that reads the contents everytime it is accessed.
	"""

	if ondemand:
		return _OnDemandIdReader(ids, fnCalc, mapContent)
	else:
		if mapContent is None:
			mapContent = lambda x:x
		return dict((fid, mapContent(_readfile(fnCalc(fid)))) for fid in ids)

# From http://docs.python.org/library/datetime.html#tzinfo-objects
# A class capturing the platform's idea of local time.
_STDOFFSET = datetime.timedelta(seconds = -time.timezone)
if time.daylight:
	_DSTOFFSET = datetime.timedelta(seconds = -time.altzone)
else:
	_DSTOFFSET = _STDOFFSET
_DSTDIFF = _DSTOFFSET - _STDOFFSET
class _LocalTimezone(datetime.tzinfo):
    def utcoffset(self, dt):
        if self._isdst(dt):
            return _DSTOFFSET
        else:
            return _STDOFFSET
    def dst(self, dt):
        if self._isdst(dt):
            return _DSTDIFF
        else:
            return datetime.timedelta(0)
    def tzname(self, dt):
        return time.tzname[self._isdst(dt)]
    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, 0)
        stamp = time.mktime(tt)
        tt = time.localtime(stamp)
        return tt.tm_isdst > 0
_Local = _LocalTimezone()									


class MailStore(object):
	""" Threadsafe mail storage class """
	def __init__(self):
		self._lock = threading.Lock()
		self._mails = []

	def add(self, mail):
		self._lock.acquire()
		self._mails.append(mail)
		self._lock.release()

	@property
	def mails(self):
		self._lock.acquire()
		try:
			return self._mails[:]
		finally:
			self._lock.release()

	@property
	def delete(self, filterf=None):
		self._lock.acquire()
		try:
			self._mails = filter(filterf, self._mails)
		finally:
			self._lock.release()

class MockSmtpServer(smtpd.SMTPServer):
	def __init__(self, localaddr, port, ms):
		self._ms = ms
		smtpd.SMTPServer.__init__(self, (localaddr, port), None)

	def process_message(self, peer, mailfrom, rcpttos, data):
		feedParser = email.parser.FeedParser()
		feedParser.feed(data)
		msg = feedParser.close()
		
		try:
			p = data.index('\r\n\r\n')
			rawHeader = data[:p]
			rawBody = data[p+4:]
		except ValueError:
			try:
				p = data.index('\n\n')
				rawHeader = data[:p]
				rawBody = data[p+2:]
			except ValueEror:
				rawHeader = data
				rawBody = ''

		htmlBody = cgi.escape(re.sub('.{80}', lambda m: m.group(0) + '\n', rawBody))
		htmlBody = re.sub('https?://([a-zA-Z.0-9/\-_?;=]|&amp;)+', lambda m: '<a href="' + m.group(0) + '">' + m.group(0) + '</a>', htmlBody)

		receivedAt = datetime.datetime.now(_Local)
		receivedAtStr = receivedAt.strftime('%Y-%m-%d %H:%M:%S %Z')

		mail = {
			'peer_ip': peer[0],
			'peer_port': peer[1],
			'from': mailfrom,
			'to': rcpttos[0] if len(rcpttos) > 0 else '<nobody>',
			'rawdata': data,
			'subject': msg['subject'],
			'rawheader': rawHeader,
			'rawbody': rawBody,
			'htmlbody': htmlBody,
			'receivedAt': receivedAtStr,
			'bodies': [{'body':submessage.get_payload()} for submessage in msg.walk()]
		}
		self._ms.add(mail)

class MocksmtpHttpServer(BaseHTTPServer.HTTPServer):
	def __init__(self, localaddr, port, ms, httpTemplates, staticFiles):
		self.ms = ms
		self.httpTemplates = httpTemplates
		self.staticFiles = staticFiles
		BaseHTTPServer.HTTPServer.__init__(self, (localaddr, port), _MocksmtpHttpRequestHandler)


class _MocksmtpHttpRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def _serve_template(self, tname, context):
		templates = self.server.httpTemplates
		try:
			body = pystache.render(templates[tname], context)
			page = pystache.render(templates['root'], {'title': context['title'], 'body': body})
			pageBlob = page.encode('utf-8')
		except:
			self.send_error(500)
			raise

		self.send_response(200)
		self.send_header('Content-Type', 'text/html; charset=utf-8')
		self.end_headers()
		self.wfile.write(pageBlob)

	def _serve_static(self, fn, files):
		if fn not in files:
			self.send_error(404)
			return
		content = files[fn]
		contentType = mimetypes.guess_type(fn)[0]
		
		self.send_response(200)
		self.send_header('Content-Type', contentType)
		self.send_header('Content-Length', str(len(content)))
		self.end_headers()
		self.wfile.write(content)

	def do_GET(self):
		if self.path == '/':
			mails = [m.copy() for m in self.server.ms.mails]
			for i,m in enumerate(mails):
				m['id'] = str(i)
			self._serve_template('index', {'emails': mails, 'title': 'mocksmtpserver'})
		elif self.path.startswith('/mails/'):
			mailid_str = self.path[len('/mails/'):]
			try:
				mail = self.server.ms.mails[int(mailid_str)]
			except (KeyError, IndexError, ValueError):
				self.send_error(404)
				return
			maildict = mail.copy()
			maildict['title'] = maildict['subject'] + ' - mocksmtp'
			self._serve_template('mail', maildict)
		elif self.path.startswith('/static/'):
			fn = self.path[len('/static/'):]
			self._serve_static(fn, self.server.staticFiles)
		else:
			self.send_error(404)

	def log_request(self, code='-', size='-'):
		pass
	def log_error(*args, **kwargs):
		pass

def _dropPrivileges(config):
	uid = None
	if config['dropuser'] is not None:
		uname = config['dropuser']
		gname = config['dropgroup']

		if isinstance(uname, int):
			uid = uname
			if gname is None:
				gname = pwd.getpwuid(uid).pw_gid
		else:
			pw = pwd.getpwnam(uname)
			uid = pw.pw_uid
			if gname is None:
				gname = pw.pw_gid

		if isinstance(gname, int):
			gid = gname
		else:
			gid = grp.getgrnam(gname).gr_gid

	if config['chroot']:
		if config['chroot'] == True: # chroot into a temporary directory
			chrootDir = tempfile.mkdtemp('mocksmtp')
			try:
				os.chroot(chrootDir)
			except OSError:
				os.rmdir(chrootDir)
				raise
		else: # chroot into a regular directory
			os.chroot(config['chroot'])
		os.chdir('/')

	if uid is not None:
		os.setgroups([])
		os.setgid(gid)
		os.setuid(uid)

def mockSMTP(config):
	ms = MailStore()

	smtpSrv = MockSmtpServer(config['smtpaddr'], config['smtpport'], ms)

	httpTemplates = _readIds(
		_TEMPLATES,
		lambda fid: os.path.join(_BASE_DIR, 'templates', fid + '.mustache'),
		mapContent=lambda content:content.decode('UTF-8'),
		ondemand=config['static_dev'])
	httpStatic = _readIds(
		_STATIC_FILES,
		lambda fid: os.path.join(_BASE_DIR, 'static', fid),
		ondemand=config['static_dev'])
	httpSrv = MocksmtpHttpServer(config['httpaddr'], config['httpport'], ms, httpTemplates, httpStatic)

	_dropPrivileges(config)

	smtpThread = threading.Thread(target=asyncore.loop)
	smtpThread.daemon = True
	smtpThread.start()

	httpThread = threading.Thread(target=httpSrv.serve_forever)
	httpThread.daemon = True
	httpThread.start()

	smtpThread.join()

def main():
	parser = OptionParser()
	parser.add_option('-c', '--config', dest='configfile', metavar='FILE')
	opts,args = parser.parse_args()

	if len(args) != 0:
		parser.error('Did not expect any arguments. Use -c to specify a configuration file.')

	config = {
		'smtpaddr': '', # IP address to bind the SMTP port on
		'smtpport': 25, # SMTP port number. On unixoid systems, you will need superuser privileges to bind to a port < 1024
		'httpaddr': '',
		'httpport': 2580,
		'chroot': False,     # Set to True to chroot into a temporary directory. Alternatively, specify the directory to chroot into.
		'dropuser': None,    # User account (name or uid) to drop to, None to not drop privileges
		'dropgroup': None,   # User group (name or gid) to drop into. By default, this is the primary group of the user.
		'static_dev': False, # Read static files on demand. Good for development (a reload will update the file), but should not be set in production
	}
	if opts.configfile:
		with open(opts.configfile , 'r') as cfgf:
			config.update(json.load(cfgf))

	mockSMTP(config)

if __name__ == '__main__':
	main()
