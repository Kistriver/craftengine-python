FROM debian:8
MAINTAINER Alexey Kachalov <kachalov@kistriver.com>

LABEL \
Vendor="Kistriver" \
Version="##CE_VER##" \
Description="This image is used to connect with CRAFTEngine core"

RUN \
apt-get update && \
apt-get upgrade -y && \
apt-get install -y python3 python3-dev python3-pip

WORKDIR /home/craftengine
COPY libs.tmp /usr/lib/ce-deps
COPY build.tmp /usr/lib/ce-deps/pycraftengine
RUN pip3 install -r /usr/lib/ce-deps/pycraftengine/requirements.txt

CMD PYTHONPATH="/usr/lib/ce-deps/":"${PYTHONPATH}" python3 -u __main__.py
