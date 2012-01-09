

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin')))
import mockmail

def test_parseMail():
	data = '''To: Philipp Hagemeister <otherto@phihag.de>
Subject: =?UTF-8?B?w5xtbMOkdXRlIDI=?=moar
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: base64

w5xtbMOkdTx0ZQ=='''
	res = mockmail.parseMail(('::1', 4242), 'from@phihag.de', ['to@phihag.de'], data)

	assert res['peer_ip'] == '::1'
	assert res['peer_port'] == 4242
	
	assert res['from'] == 'from@phihag.de'
	assert res['simple_to'] == 'to@phihag.de'
	
	assert res['subject'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4ute 2moar'
	assert res['bodies'][0]['text'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4u<te'
	assert res['bodies'][0]['html'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4u&lt;te'
	assert len(res['bodies']) == 1
