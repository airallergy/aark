FROM mcr.microsoft.com/devcontainers/python:3.14

RUN apt-get update && apt-get install -y --no-install-recommends \
    unixodbc \
    unixodbc-dev \
    mdbtools \
    odbc-mdbtools

RUN pipx install uv==0.11.*