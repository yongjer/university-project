docker run -it -p 7860:7860 --platform=linux/amd64 --gpus all \
	registry.hf.space/nvidia-canary-1b:latest python app.py