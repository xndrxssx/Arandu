FROM nginx:1.31.8
LABEL maintainer="Admin Projeto SD <admin@projetosd.local>"

RUN DEBIAN_FRONTEND=noninteractive \
    apt-get update -q --fix-missing && \
    apt-get -y install --no-install-recommends \
        ctpl \
        inotify-tools \
        openssh-server

COPY files /
COPY templates /templates
RUN  chmod +x /entrypoint.sh
RUN  chmod -f 400 /root/.ssh/id_ecdsa || true

ENTRYPOINT [ "/entrypoint.sh" ]
