FROM nvcr.io/nvidia/isaac/ros:x86_64-ros2_humble_f70fbf3e86d9ae99b527f8cc2c40007b
# Update all packages
RUN apt-get update && apt-get upgrade -y
RUN pip install --upgrade pip
RUN pip install -U torch transformers pyserial