docker run -it -p 7860:7860 --platform=linux/amd64 --gpus all \
	registry.hf.space/distil-whisper-whisper-vs-distil-whisper:latest python app.py