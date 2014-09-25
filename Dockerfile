############################################################
# Dockerfile to run Memcached Containers
# Based on Ubuntu Image
############################################################

FROM ubuntu
MAINTAINER Chris Wilcox <ckwilcox@gmail.com>

RUN apt-get update && apt-get install -y python python-pip
RUN pip install requests beautifulsoup4 redis Flask supervisor

WORKDIR /opt

ADD server.py /opt/server.py
ADD crawler.py /opt/crawler.py
ADD supervisord.conf /etc/supervisord.conf

EXPOSE 80

# ENTRYPOINT ??
CMD ["supervisord"]  

