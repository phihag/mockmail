An email (SMTP) server that accepts all emails and shows them in a web interface.

Inspired by the now apparently defunct [mockemail](http://mockemail.sourceforge.net/) project.
License: GPL3+

Installation
============

mockmail is written in Python 3. Legacy support for 2.6+ is maintained at the moment.
mockmail requires the pystache library.

To install mockmail on your system, run

    sudo make install

By default, mockmail runs a the SMTP server on port 2525. The mails received on that port can be seen on http://127.0.0.1:2580/ , from the local machine only.

To change this configuration, edit /etc/mockmail.conf and restart mockmail with `service restart mockmail`. Common changes are:

* Set smtpport to 25 to not require any configuration. Make sure you disable your old MTA (you can find it with $ netstat -ltpn | grep :25) before restarting.
* Set httphost to "" to allow anyone to access the web interface. Alternatively, you can let your webserver proxy mockmail. Currently, mockmail cannot serve its content over IPv6 due to a limitation in the Python HTTP server.

-----

Alternatively, you can run mockmail manually, like this:

    ./bin/mockmail.py

Use the -c option to provide a configuration file.
