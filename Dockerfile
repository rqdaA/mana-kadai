FROM ubuntu:22.04
WORKDIR /opt/mana-kadai
RUN apt update && apt install -y python3 python3-pip
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py .
CMD ["python3", "main.py"]
