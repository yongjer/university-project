FROM nvcr.io/nvidia/isaac/ros:x86_64-ros2_humble_1930bbec7e7704243656b695b9df7844
# Update all packages
RUN apt-get update && apt-get upgrade -y
RUN pip install --upgrade pip
RUN pip install -U transformers
# Source the ROS setup file
RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" >> ~/.bashrc
