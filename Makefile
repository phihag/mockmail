
PREFIX=/usr/local

default: install

test:
	python3 -m unittest
	flake8 bin/mockmail.py test/*.py

create-user:
	adduser --system --disabled-login --group --no-create-home --quiet mockmail

install:
	$(MAKE) create-user
	cp bin/mockmail.py "${PREFIX}/bin/mockmail"
	chmod a+x "${PREFIX}/bin/mockmail"

	mkdir -p "${PREFIX}" "${PREFIX}/bin" "${PREFIX}/share"
	cp -r -t "${PREFIX}/share" share/mockmail

	cp -n config.production /etc/mockmail.conf
	sed "s#^PREFIX=.*#PREFIX=${PREFIX}#" <mockmail.init >/etc/init.d/mockmail
	chmod a+x /etc/init.d/mockmail
	update-rc.d mockmail defaults
	/etc/init.d/mockmail restart

uninstall:
	-/etc/init.d/mockmail stop
	update-rc.d mockmail remove
	rm -f "${PREFIX}/bin/mockmail"
	@if [ -f /etc/mockmail.conf ]; then \
		if diff -q config.production /etc/mockmail.conf > /dev/null 2>&1; then \
			rm -f /etc/mockmail.conf; \
		else \
			echo "/etc/mockmail.conf has been changed. Keeping it .."; \
		fi; \
	fi
	rm -f "/etc/init.d/mockmail"
	rm -rf /usr/share/mockmail

.PHONY: default test create-user install uninstall

