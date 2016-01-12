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

COPY requirements.txt /home/craftengine/craftengine/requirements.txt
WORKDIR /home/craftengine
RUN pip3 install -r craftengine/requirements.txt

COPY VERSION.tmp /home/craftengine/craftengine/VERSION
COPY LICENSE /home/craftengine/craftengine/LICENSE
COPY craftengine /home/craftengine/craftengine
COPY src /home/craftengine

CMD python3 -u __main__.py
