#
# This example Dockerfile illustrates a method to install
# additional packages on top of NVIDIA's PyTorch container image.
#
# To use this Dockerfile, use the `docker build` command.
# See https://docs.docker.com/engine/reference/builder/
# for more information.
#
FROM nvcr.io/nvidia/pytorch:23.06-py3

# Install my-extra-package-1 and my-extra-package-2
RUN apt-get update && pip install \
        transformers \
        datasets \
        accelerate \
        optimum[onnxruntime-gpu, exporters] \
        diffusers \
        evaluate \
        jupyter \
        notebook \
      && \
    rm -rf /var/lib/apt/lists/
