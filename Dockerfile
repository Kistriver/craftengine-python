FROM python:3
MAINTAINER Alexey Kachalov <kachalov@kistriver.com>

LABEL \
Vendor="Kistriver" \
Version="##CE_VER##" \
Description="This image is used to connect with CRAFTEngine core"

WORKDIR /home/craftengine
COPY libs.tmp /usr/lib/ce-deps
COPY build.tmp /usr/lib/ce-deps/pycraftengine
RUN pip3 install -r /usr/lib/ce-deps/pycraftengine/requirements.txt

CMD PYTHONPATH="/usr/lib/ce-deps/":"${PYTHONPATH}" python3 -u __main__.py
