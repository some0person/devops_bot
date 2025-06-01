FROM python:3-alpine

RUN mkdir -p /usr/src/bot

WORKDIR /usr/src/bot

RUN pip3 install --upgrade pip

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY main.py .

CMD ["python3", "main.py"]
