#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
try:
    from . import tutils
except (ImportError, ValueError):  # direct exection
    import tutils  # NOQA

import mockmail

import unittest


class MailparseTestCase(unittest.TestCase):
    def test_parseHeader(self):
        res = mockmail._decodeMailHeader('=?UTF-8?B?w5xtbMOkdXRlIDI=?=')
        assert res.encode('UTF-8') == b'\xc3\x9cml\xc3\xa4ute 2'

        inp = '=?utf-8?q?Registrierungsversuch_fehlgeschlagen_=28phihag=40phihag=2Ede=29?='
        assert mockmail._decodeMailHeader(inp) == 'Registrierungsversuch fehlgeschlagen (phihag@phihag.de)'

    def test_parseMail(self):
        data = '''To: Philipp Hagemeister <otherto@phihag.de>
Subject: =?UTF-8?B?w5xtbMOkdXRlIDI=?=
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: base64

w5xtbMOkdTx0ZQ=='''
        res = mockmail.parseMail(('::1', 4242), 'from@phihag.de', ['to@phihag.de'], data)

        assert res['peer_ip'] == '::1'
        assert res['peer_port'] == 4242

        assert res['from'] == 'from@phihag.de'
        assert res['simple_to'] == 'to@phihag.de'

        assert res['subject'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4ute 2'
        assert res['bodies'][0]['text'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4u<te'
        assert res['bodies'][0]['html'].encode('UTF-8') == b'\xc3\x9cml\xc3\xa4u&lt;te'
        assert len(res['bodies']) == 1


if __name__ == '__main__':
    unittest.main()
