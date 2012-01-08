An email (SMTP) server that accepts all emails and shows them in a web interface.

Inspired by the now apparently defunct [mockemail](http://mockemail.sourceforge.net/) project.
License: GPL3+

Installation
============

mocksmtp is written in Python 3. Legacy support for 2.6+ is maintained at the moment.
mocksmtp requires the pystache library.

To install mocksmtp on your system, run

    sudo make install

By default, mocksmtp runs a the SMTP server on port 2525. The mails received on that port can be seen on http://127.0.0.1:2580/ , from the local machine only.

To change this configuration, edit /etc/mocksmtp.conf and restart mocksmtp with `service restart mocksmtp`. Common changes are:

* Set smtpport to 25 to not require any configuration. Make sure you disable your old MTA (you can find it with $ netstat -ltpn | grep :25) before restarting.
* Set httphost to "" to allow anyone to access the web interface. Alternatively, you can let your webserver proxy mocksmtp. Currently, mocksmtp cannot serve its content over IPv6 due to a limitation in the Python HTTP server.

-----

Alternatively, you can run mocksmtp manually, like this:

    ./mocksmtp.py

Use the -c option to provide a configuration file.
