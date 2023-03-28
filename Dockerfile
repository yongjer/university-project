FROM nvcr.io/nvidia/l4t-base:r32.7.1
RUN apt-get update && apt-get dist-upgrade && apt-get install python3-pip
RUN pip3 install autokeras && pip3 install pyserial
CMD [ "python3", "main.py" ]