
PREFIX=/usr/local

default: install

test:
	python -c 'import pystache' # If this fails, install pystache

create-user:
	adduser --system --disabled-login --group --no-create-home --quiet mockmail

install: test
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

pystache-install:
	export TMPDIR=$$(mktemp -d) && \
		git clone git://github.com/defunkt/pystache.git $${TMPDIR}/pystache-git && \
		2to3 -w -n --no-diffs $${TMPDIR}/pystache-git/pystache/*.py && \
		sudo cp -R $${TMPDIR}/pystache-git/pystache -t /usr/lib/python3/dist-packages/ && \
		rm -rf $${TMPDIR}

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

