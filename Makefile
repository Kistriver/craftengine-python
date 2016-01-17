.PHONY: build clean

CE_VER := $(shell git describe --always --tag)

build:
	if ! [ -e craftengine/ddp ]; then git clone git@bitbucket.org:Kistriver/darkdist-protocol.git craftengine/ddp; fi
	echo $(CE_VER) > VERSION.tmp
	cp Dockerfile Dockerfile.tmp
	sed -i "s|##CE_VER##|$(CE_VER)|" Dockerfile.tmp
	docker build -t kistriver/ce-python:$(CE_VER) -f Dockerfile.tmp .
	docker tag -f kistriver/ce-python:$(CE_VER) kistriver/ce-python
	rm -f Dockerfile.tmp VERSION.tmp

clean:
	-rm -rf */__pycache__
	-rm -rf craftengine/ddp
	-rm -r *.tmp
