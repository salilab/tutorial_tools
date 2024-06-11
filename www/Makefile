SUBDIRS=
.PHONY: install ${SUBDIRS}
WEB=/guitar3/home/www/IMP
SYSWEB=/guitar3/home/www/html/imp/tutorials/bin
FILES=${SYSWEB}/showall.py ${SYSWEB}/README

install: ${FILES} ${SUBDIRS}

${SUBDIRS}:
	${MAKE} -C $@

${SYSWEB}/README: ${WEB}/README
	cp -f $< $@
	chmod go-rwx $@

${SYSWEB}/%: %
	cp -f $< $@
	chmod a-w $@
	chmod a+rx $@
	/sbin/restorecon $@
