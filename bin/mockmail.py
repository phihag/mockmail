#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""A test MTA for debugging purposes"""

__author__  = "Philipp Hagemeister"
__license__ = "GPL"
__version__ = "1.5"
__maintainer__ = "Philipp Hagemeister"
__status__ = "Production"
__email__ = "phihag@phihag.de"

import asyncore
import cgi
import datetime
import email.header
import email.parser
import email.utils
import grp
import json
import mimetypes
import os
import pwd
import re
import signal
import smtpd
import sys
import tempfile
import time
import threading
from optparse import OptionParser

try:
	from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError: # Python 2.x
	from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

import pystache # If this fails, install python3-pystache

_TEMPLATES = ('header', 'footer', 'index', 'mail',)
_STATIC_FILES = ('mockmail.css', 'jquery-1.7.1.min.js', 'mockmail.js', )


def _readfile(fn):
	with open(fn, 'rb') as f:
		return f.read()

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
		self._id = 0

	def add(self, mail):
		self._lock.acquire()
		mail['id'] = str(self._id)
		self._id += 1
		self._mails.append(mail)
		self._lock.release()

	@property
	def mails(self):
		self._lock.acquire()
		try:
			return self._mails[:]
		finally:
			self._lock.release()

	def getById(self, mid):
		"""
		Raises a KeyError if the id is not found
		"""
		try:
			mid_int = int(mid)
		except ValueError:
			raise KeyError('Invalid key')
		
		self._lock.acquire()
		try:
			try:
				return self._mails[mid_int]
			except IndexError:
				raise KeyError()
		finally:
			self._lock.release()

	@property
	def delete(self, filterf=None):
		self._lock.acquire()
		try:
			self._mails = filter(filterf, self._mails)
		finally:
			self._lock.release()

def _decodeMailHeader(rawVal):
	return ''.join(v if enc is None else v.decode(enc)
				   for v,enc in email.header.decode_header(rawVal))

def _parseMessage(msg):
	res = {'payload':msg.get_payload()}
	if msg.get_content_maintype() == 'text':
		enc = msg.get_content_charset()
		if enc is None:
			enc = 'ASCII'
		res['text'] = msg.get_payload(None, True).decode(enc)
	
		html = cgi.escape(res['text'], quote=True)
		html = re.sub('https?://([a-zA-Z.0-9/\-_?;=]|&amp;)+', lambda m: '<a href="' + m.group(0) + '">' + m.group(0) + '</a>', html)
		res['html'] = html
	else:
		res['html'] = '[attachment]'
	return res

def parseMail(peer, mailfrom, rcpttos, data):
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

	receivedAt = datetime.datetime.now(_Local)
	receivedAtStr = receivedAt.strftime('%Y-%m-%d %H:%M:%S %Z')

	subject = _decodeMailHeader(msg['subject'])

	res = {
		'peer_ip': peer[0],
		'peer_port': peer[1],
		'from': mailfrom,
		'simple_to': rcpttos[0] if len(rcpttos) > 0 else '<nobody>',
		'rawdata': data,
		'subject': subject,
		'rawheader': rawHeader,
		'rawbody': rawBody,
		'receivedAt': receivedAtStr,
		'receivedAt_dateTime': receivedAt,
		'bodies': [_parseMessage(submessage) for submessage in msg.walk()]
	}
	return res

class MockmailSmtpServer(smtpd.SMTPServer):
	def __init__(self, localaddr, port, ms):
		self._ms = ms
		smtpd.SMTPServer.__init__(self, (localaddr, port), None)

	def process_message(self, peer, mailfrom, rcpttos, data):
		mail = parseMail(peer, mailfrom, rcpttos, data)
		self._ms.add(mail)

class MockmailHttpServer(HTTPServer):
	def __init__(self, localaddr, port, ms, httpTemplates, staticFiles, static_cache_secs):
		self.ms = ms
		self.httpTemplates = httpTemplates
		self.staticFiles = staticFiles
		self.static_cache_secs = static_cache_secs
		HTTPServer.__init__(self, (localaddr, port), _MockmailHttpRequestHandler) # Required for Python 2.x since HTTPServer is an old-style class (uarg) there

class _MockmailPystacheTemplate(pystache.Template):
	def __init__(self, templates, *args, **kwargs):
		self._templates_markup = templates
		super(_MockmailPystacheTemplate, self).__init__(*args, **kwargs)
		self.modifiers.set('>')(_MockmailPystacheTemplate._render_partial)
	
	def _render_partial(self, template_name):
		markup = self._templates_markup[template_name]
		template = _MockmailPystacheTemplate(self._templates_markup, markup, self.view)
		return template.render()


class _MockmailHttpRequestHandler(BaseHTTPRequestHandler):
	def _serve_template(self, tname, context):
		templates = self.server.httpTemplates
		try:
			page = _MockmailPystacheTemplate(templates, templates[tname], context).render()
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
		if self.server.static_cache_secs is not None:
			self.send_header('Expires', email.utils.formatdate(time.time() + self.server.static_cache_secs))
			self.send_header('Cache-Control', 'public, max-age=' + str(self.server.static_cache_secs))
		self.end_headers()
		self.wfile.write(content)

	def do_GET(self):
		if self.path == '/':
			mails = sorted((m.copy() for m in self.server.ms.mails), key=lambda m: m['receivedAt_dateTime'], reverse=True)
			self._serve_template('index', {'emails': mails, 'title': 'mockmailserver'})
		elif self.path.startswith('/mails/'):
			mailid_str = self.path[len('/mails/'):]
			try:
				mail = self.server.ms.getById(mailid_str)
			except KeyError:
				self.send_error(404)
				return
			maildict = mail.copy()
			maildict['title'] = 'mockmail - ' + maildict['subject']
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

def _workaround_preload_codecs():
	""" Preload all available codecs. """
	import codecs,glob,os.path
	encs = set(os.path.splitext(os.path.basename(f))[0]
			for f in glob.glob('/usr/lib/python*/encodings/*.*'))
	for e in encs:
		try:
			codecs.lookup(e)
		except LookupError:
			pass # __init__.py or something

def _dropPrivileges(config, init_chroot=None):
	""" @param init_chroot Callback function to call before creating the chroot """
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
		if config['chroot_mkdir']:
			if not os.path.exists(config['chroot']):
				os.mkdir(config['chroot'], 0o700)

		if config['workarounds']:
			_workaround_preload_codecs()

		os.chroot(config['chroot'])
		os.chdir('/')

	if init_chroot:
		init_chroot()

	if uid is not None:
		os.setgroups([])
		os.setgid(gid)
		os.setuid(uid)

def _setupPidfile(pidfile):
	if pidfile is None:
		return
	with open(pidfile, 'w') as pidf:
		pidf.write(str(os.getpid()))

def _getPid(pidfile):
	"""
	@returns The process id of the running mockmail process, or None if it is not running.
	"""
	if not pidfile:
		raise Exception('No pidfile set! Use --pidfile or the "pidfile" configuration option')
	try:
		pidc = _readfile(pidfile)
	except (OSError, IOError):
		return None
	if not pidc:
		return None
	try:
		pid = int(pidc)
	except ValueError:
		return None
	try:
		cmdline = _readfile(os.path.join('/proc/', str(pid), 'cmdline'))
		if b'mockmail' in cmdline:
			return pid
		else: # Just another process that happens to have the same pid
			return None
	except IOError:
		return None

def _effectivePidfile(config):
	if not config['pidfile']:
		return None
	if config['chroot']:
		res = os.path.join(config['chroot'], config['pidfile'])
	else:
		res = config['pidfile']
	return os.path.abspath(res)

def mockmail(config):
	ms = MailStore()

	try:
		smtpSrv = MockmailSmtpServer(config['smtpaddr'], config['smtpport'], ms)
	except socket.error:
		if opts['smtp_grace_period'] is not None:
			time.sleep(opts['smtp_grace_period'])
			smtpSrv = MockmailSmtpServer(config['smtpaddr'], config['smtpport'], ms)
		else:
			raise

	httpTemplates = _readIds(
		_TEMPLATES,
		lambda fid: os.path.join(config['resourcedir'], 'templates', fid + '.mustache'),
		mapContent=lambda content:content.decode('UTF-8'),
		ondemand=config['static_dev'])
	httpStatic = _readIds(
		_STATIC_FILES,
		lambda fid: os.path.join(config['resourcedir'], 'static', fid),
		ondemand=config['static_dev'])
	httpSrv = MockmailHttpServer(config['httpaddr'], config['httpport'], ms, httpTemplates, httpStatic, config['static_cache_secs'])

	if config['daemonize']:
		if os.fork() != 0:
			sys.exit(0)

	_dropPrivileges(config, lambda: _setupPidfile(config['pidfile']))

	smtpThread = threading.Thread(target=asyncore.loop)
	smtpThread.daemon = True
	smtpThread.start()

	httpThread = threading.Thread(target=httpSrv.serve_forever)
	httpThread.daemon = True
	httpThread.start()

	smtpThread.join()
	httpThread.join()

def main():
	parser = OptionParser()
	parser.add_option('-c', '--config', dest='configfile', metavar='FILE', help='JSON configuration file to load')
	parser.add_option('-d', '--daemonize', action='store_const', const=True, dest='daemonize', default=None, help='Run mockmail in the background. Overwrites configuration')
	parser.add_option('-i', '--interactive', action='store_const', const=True, dest='daemonize', default=None, help='Run mockmail in the foreground. Overwrites configuration')
	parser.add_option('--resourcedir', dest='resourcedir', metavar='DIR', help='Load resources and templates from this directrory')
	parser.add_option('--pidfile', dest='pidfile', default=None, help='Set pidfile to use. Overwrites configuration')
	parser.add_option('--ctl-status', action='store_const', dest='ctl', const='status', default=None, help='Check whether mockmail service is running.')
	parser.add_option('--ctl-start',  action='store_const', dest='ctl', const='start',  default=None, help='Start mockmail service.')
	parser.add_option('--ctl-stop',   action='store_const', dest='ctl', const='stop',   default=None, help='Stop mockmail  service.')
	parser.add_option('--quiet-ctl', action='store_true', dest='quiet_ctl', default=False, help='Do not print announcement in --ctl-* operations.')
	parser.add_option('--dumpconfig', action='store_true', dest='dumpconfig', help='Do not run mockmail, but dump the effective configuration')
	parser.add_option('--version', action='store_true', dest='dumpversion', help='Do not run mockmail, but output the version')
	parser.add_option('--check-resourcedir', action='store_true', dest='check_resourcedir', help='Do not run mockmail, but check that the resource directory is set correctly')
	opts,args = parser.parse_args()

	if len(args) != 0:
		parser.error('Did not expect any arguments. Use -c to specify a configuration file.')

	if opts.dumpversion:
		print(__version__)
		return

	config = {
		'smtpaddr': '',       # IP address to bind the SMTP port on
		'smtpport': 2525,     # SMTP port number. On unixoid systems, you will need superuser privileges to bind to a port < 1024
		'httpaddr': '',       # IP address to bind the web interface on. The default allows anyone to see your mail.
		'httpport': 2580,     # Port to bind the web interface on. You may want to configure your webserver on port 80 to proxy the connection.
		'chroot': None,       # Specify the directory to chroot into.
		'chroot_mkdir': False,# Automatically create the chroot directory if it doesn't exist, and chroot is set.
		'dropuser': None,     # User account (name or uid) to drop to, None to not drop privileges
		'dropgroup': None,    # User group (name or gid) to drop into. By default, this is the primary group of the user.
		'static_dev': False,  # Read static files on demand. Good for development (a reload will update the file), but should not be set in production
		'daemonize': False,   # Whether mockmail should go into the background after having started
		'pidfile': None,      # File to write the process ID of mockmail to (relative to the chroot)
		'resourcedir': None,  # Directory to load templates and resources
		'workarounds': True,  # Work around platform bugs
		'static_cache_secs': 0# Cache duration for static files
		'smtp_grace_period':None# Set to a number to wait that long to open a port
	}
	if opts.configfile:
		with open(opts.configfile , 'r') as cfgf:
			config.update(json.load(cfgf))
	if opts.daemonize is not None:
		config['daemonize'] = opts.daemonize
	if opts.pidfile is not None:
		config['pidfile'] = opts.pidfile
	if opts.resourcedir is not None:
		config['resourcedir'] = opts.resourcedir

	if opts.dumpconfig:
		json.dump(config, sys.stdout, indent=4)
		sys.stdout.write('\n')
		return

	if config['resourcedir'] is None:
		config['resourcedir'] = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'share', 'mockmail'))

	if opts.check_resourcedir:
		print('Loading resources from ' + os.path.abspath(config['resourcedir']) + ' ...')

		httpTemplates = _readIds(
			_TEMPLATES,
			lambda fid: os.path.join(config['resourcedir'], 'templates', fid + '.mustache'),
			mapContent=lambda content:content.decode('UTF-8'),
			ondemand=False)
		httpStatic = _readIds(
			_STATIC_FILES,
			lambda fid: os.path.join(config['resourcedir'], 'static', fid),
			ondemand=False)
		sys.exit(0)

	ctl_print = (lambda s: 0) if opts.quiet_ctl else sys.stdout.write
	if opts.ctl == 'status':
		pid = _getPid(_effectivePidfile(config))
		if pid:
			ctl_print('mockmail is running.\n')
			sys.exit(0)
		else:
			ctl_print('mockmail is NOT running.\n')
			sys.exit(3)
	elif opts.ctl == 'start':
		pid = _getPid(_effectivePidfile(config))
		ctl_print('Starting Test MTA: mockmail')
		if pid:
			sys.stdout.write(' (pid ' + str(pid) + ') already running.\n')
			sys.exit(0)
		else:
			config['daemonize'] = True
			mockmail(config)
			ctl_print('.\n')
			return
	elif opts.ctl == 'stop':
		pidfn = _effectivePidfile(config)
		pid = _getPid(pidfn)
		ctl_print('Stopping Test MTA: mockmail ...')
		if pid:
			os.kill(pid, signal.SIGTERM)
			try:
				os.unlink(pidfn)
			except OSError:
				pass
		ctl_print('.\n')
		sys.exit(0)

	if config['pidfile']:
		pid = _getPid(_effectivePidfile(config))
		if pid:
			raise Exception('mockmail is already running (pid ' + str(pid) + ', read from ' + _effectivePidfile(config) + ')')

	mockmail(config)

if __name__ == '__main__':
	main()
