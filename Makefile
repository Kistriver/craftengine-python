.PHONY: build docker clean

CE_VER := $(shell git describe --always --tag)

build:
	-rm -rf build.tmp
	cp -R pycraftengine build.tmp
	cp LICENSE build.tmp/LICENSE
	cp requirements.txt build.tmp/requirements.txt
	echo $(CE_VER) > build.tmp/VERSION

docker: build
	if ! [ -e libs.tmp/ddp ]; then git clone git@git.kistriver.com:kistriver/ddp.git libs.tmp/ddp; fi
	cp Dockerfile Dockerfile.tmp
	sed -i "s|##CE_VER##|$(CE_VER)|" Dockerfile.tmp
	docker build -t kistriver/ce-python:$(CE_VER) -f Dockerfile.tmp .
	docker tag -f kistriver/ce-python:$(CE_VER) kistriver/ce-python

clean:
	-rm -rf */__pycache__
	-rm -r *.tmp
