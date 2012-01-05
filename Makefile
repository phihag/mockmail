
PREFIX=/usr/local

default: install

test:
	python -c 'import pystache' # If this fails, install pystache

create-user:
	adduser --system --disabled-login --group --no-create-home --quiet mocksmtp

install: test
	$(MAKE) create-user
	cp mocksmtp.py "${PREFIX}/bin/mocksmtp"
	chmod a+x "${PREFIX}/bin/mocksmtp"

	cp -n config.production /etc/mocksmtp.conf
	sed "s#^PREFIX=.*#PREFIX=${PREFIX}#" <mocksmtp.init >/etc/init.d/mocksmtp
	chmod a+x /etc/init.d/mocksmtp
	update-rc.d mocksmtp defaults
	/etc/init.d/mocksmtp start

uninstall:
	/etc/init.d/mocksmtp stop
	update-rc.d mocksmtp remove
	rm -f "${PREFIX}/bin/mocksmtp"
	@if [ -f /etc/mocksmtp.conf ]; then \
		if diff -q config.production /etc/mocksmtp.conf > /dev/null 2>&1; then \
			rm -f /etc/mocksmtp.conf; \
		else \
			echo "/etc/mocksmtp.conf has been changed. Keeping it .."; \
		fi; \
	fi
	rm -f "/etc/init.d/mocksmtp"

.PHONY: install uninstall

