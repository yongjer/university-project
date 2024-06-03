import gradio as gr

gr.load("models/sentence-transformers/all-MiniLM-L6-v2").launch(server_port = 7862)