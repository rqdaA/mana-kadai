FROM ubuntu:22.04
RUN apt update && apt install -y python3 python3-pip
RUN pip install -r requirements.txt
WORKDIR /opt/mana-kadai
COPY *.py .
COPY requirements.txt .
CMD ["python3", "main.py"]
