FROM python:3.7
ADD . /src
RUN pip install -r /src/requirements.txt
CMD kopf run /src/operator.py --verbose