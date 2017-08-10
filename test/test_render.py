#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin')))
import mockmail

import unittest

class MustacheTestCase(unittest.TestCase):
	def test_basics(self):
		r = mockmail.MustacheRenderer({})
		self.assertEqual(r.render('x', {}), 'x')
		self.assertEqual(r.render('x {{a}}b', {}), 'x b')
		self.assertEqual(r.render('x {{a}}b', {
			'a': 42,
		}), 'x 42b')

		self.assertEqual(r.render('x {{{a}}}b', {
			'a': '\'"<ä>&',
		}), 'x \'"<ä>&b')
		self.assertEqual(r.render('x {{a}}b', {
			'a': 'z\'y"<ä>&',
		}), 'x z&#x27;y&quot;&lt;ä&gt;&amp;b')
		self.assertEqual(r.render('a={{a}} b={{b}} c={{c}} u_s={{under_score}}', {
			'a': 1,
			'b': 2,
			'c': 3,
			'under_score': 4,
		}), 'a=1 b=2 c=3 u_s=4')


	def test_include(self):
		r = mockmail.MustacheRenderer({
			't1': 'this is t1.\n{{>t2}}/t1',
			't2': 'this is t2:{{val}}/t2',
		})
		self.assertEqual(r.render('> {{>t1}} <', {
				'val': 42,
			}),
			'> this is t1.\nthis is t2:42/t2/t1 <'
		)

	def test_loop(self):
		r = mockmail.MustacheRenderer({})
		self.assertEqual(
			r.render('invis{{#emptyloop}}none{{/emptyloop}}ible', {}),
			'invisible'
		)
		render_res = r.render('{{#x}}loop:{{a}}{{y}}\n{{/x}} invis{{#emptyloop}}none{{/emptyloop}}ible', {
			'a': 'a',
			'x': [
				{'y': '1'},
				{'y': '2'},
				{'y': '3'},
				{'y': '4', 'a': 'b'},
			],
		})
		self.assertEqual(
			render_res,
			(
				'loop:a1\n'
				'loop:a2\n'
				'loop:a3\n'
				'loop:b4\n'
				' invisible'
			)
		)
