FROM jenkins/jenkins:lts
USER root
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
USER jenkins
