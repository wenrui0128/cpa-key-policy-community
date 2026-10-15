ARG PYTHON_IMAGE=python:3.13-alpine
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY *.py *.html *.js *.css ./
COPY examples/ ./examples/
ENV BIND=0.0.0.0 PORT=18765 DATA_DIR=/data
USER 10001:10001
EXPOSE 18765
CMD ["python", "-B", "app.py"]
