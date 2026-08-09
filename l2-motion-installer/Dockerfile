ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY integration /integration
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
