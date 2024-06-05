docker run -it -p 7863:7860 --platform=linux/amd64 --gpus all \
	registry.hf.space/ysharma-microsoft-phi-3-vision-128k:latest python app.py