FROM kennethjiang/octoprint-with-slicers:1.3.2

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ADD . /app
WORKDIR /app
RUN python setup.py develop

WORKDIR /app/data
RUN if [ ! -f /app/data/config.yaml ]; then cp /app/octoprint-config.yaml /app/data/; fi
