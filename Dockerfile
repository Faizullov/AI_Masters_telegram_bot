FROM ubuntu:20.04
LABEL maintainer="Airat"
RUN apt-get update -y && apt-get install -y python3-pip python-dev build-essential
ADD . /bot-app
WORKDIR /bot-app
RUN pip3 install -r requirements.txt
ENTRYPOINT ["python3", "bot-app.py"]
