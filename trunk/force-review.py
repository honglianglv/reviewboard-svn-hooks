#!/usr/bin/python
# -*- coding:utf8 -*-

import sys
import subprocess
import urllib2
import cookielib
import base64
import re
import json
from urlparse import urljoin

RB_SERVER = r'http://192.168.0.109:9000'
COOKIE_FILE = '/tmp/review-board-cookies.txt'
USERNAME = 'admin'
PASSWORD = 'how1982'

def debug(s):
	f = open('/tmp/svn-hook.log', 'at')
	print >>f, s
	f.close()

class SvnError(StandardError):
	pass

class Opener(object):
	def __init__(self, server, username, password, cookie_file = None):
		self._server = server
		if cookie_file is None:
			cookie_file = COOKIE_FILE
		self._auth = base64.b64encode(username + ':' + password)
		cookie_jar = cookielib.MozillaCookieJar(cookie_file)
		cookie_handler = urllib2.HTTPCookieProcessor(cookie_jar)
		self._opener = urllib2.build_opener(cookie_handler)

	def open(self, path, ext_headers, *a, **k):
		url = urljoin(self._server, path)
		return self.abs_open(url, ext_headers, *a, **k)

	def abs_open(self, url, ext_headers, *a, **k):
		debug('url open:%s' % url)
		r = urllib2.Request(url)
		for k, v in ext_headers:
			r.add_header(k, v)
		r.add_header('Authorization', 'Basic ' + self._auth)
		try:
			rsp = self._opener.open(r)
			return rsp.read()
		except urllib2.URLError, e:
			raise SvnError(str(e))

def make_svnlook_cmd(directive, repos, txn):
	return ['svnlook', directive, '-t',  txn, repos]

def get_cmd_output(cmd):
	return subprocess.Popen(cmd, stdout = subprocess.PIPE).communicate()[0]



def get_review_id(repos, txn):
	svnlook = make_svnlook_cmd('log', repos, txn)
	log = get_cmd_output(svnlook)
	rid = re.search(r'review:([0-9]+)', log, re.M | re.I)
	if rid:
		return rid.group(1)
	raise SvnError('No review id.')

MIN_SHIP_IT_COUNT = 2
MIN_KEY_USER_SHIP_IT_COUNT = 1
KEY_SHIP_IT_USERS = set(['see', 'admin', 'hookehu', 'zhongjianneng'])

def check_rb(repos, txn):
	rid = get_review_id(repos, txn)
	path = 'api/review-requests/' + str(rid) + '/reviews/'
	opener = Opener(RB_SERVER, USERNAME, PASSWORD)
	rsp = opener.open(path, {})
	reviews = json.loads(rsp)
	if reviews['stat'] != 'ok':
		raise SvnError, "get reviews error."
	ship_it_users = set()
	for item in reviews['reviews']:
		ship_it = int(item['ship_it'])
		if ship_it:
			ship_it_users.add(item['links']['user']['title'])
	
	if len(ship_it_users) < MIN_SHIP_IT_COUNT:
		raise SvnError, "not enough of ship_it."
	key_user_count = 0
	for user in ship_it_users:
		if user in KEY_SHIP_IT_USERS:
			key_user_count += 1
	if key_user_count < MIN_KEY_USER_SHIP_IT_COUNT:
		raise SvnError, 'not enough of key user ship_it.'

def main():
	debug('command:' + str(sys.argv))

	repos = sys.argv[1]
	txn = sys.argv[2]

	svnlook = make_svnlook_cmd('changed', repos, txn)
	changed = get_cmd_output(svnlook)
	for line in changed.split('\n'):
		f = line[4:]
		debug(type(f))
		# 有提交到主干分枝的代码，触发检测。
		if 'trunk/src/server/test-hook' in f:
			check_rb(repos, txn)
			return
	return

try:
	main()
except SvnError, e:
	print >> sys.stderr, str(e)
	exit(1)
except Exception, e:
	print >> sys.stderr, str(e)
	import traceback
	traceback.print_exc(file=sys.stderr)
	exit(1)
else:
	exit(0)
