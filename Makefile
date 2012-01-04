
PREFIX=/usr/local

install:
	cp mocksmtp.py "${PREFIX}/bin/mocksmtp"
	chmod a+x "${PREFIX}/bin/mocksmtp"

	cp -n config.production /etc/mocksmtp.conf
	sed "s#^PREFIX=.*#PREFIX=${PREFIX}#" <mocksmtp.init >/etc/init.d/mocksmtp
	chmod a+x /etc/init.d/mocksmtp
	update-rc.d mocksmtp defaults

uninstall:
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

