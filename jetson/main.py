'''
Loaded as API: http://localhost:7861/ ✔
Client.predict() Usage Info
---------------------------
Named API endpoints: 1

 - predict(param_0, param_1, api_name="/predict") -> similarity_scores
    Parameters:
     - [Textbox] param_0: str (required)  
     - [Textbox] param_1: str (required)  
    Returns:
     - [Json] similarity_scores: Dict[Any, Any] (any valid json)
'''
'''
Loaded as API: http://localhost:7860/ ✔
Client.predict() Usage Info
---------------------------
Named API endpoints: 3

 - predict(inputs, task, api_name="/predict") -> output
    Parameters:
     - [Audio] inputs: filepath (required)  
     - [Radio] task: Literal['transcribe', 'translate'] (not required, defaults to:   transcribe)  
    Returns:
     - [Textbox] output: str 

 - predict(inputs, task, api_name="/predict_1") -> output
    Parameters:
     - [Audio] inputs: filepath (required)  
     - [Radio] task: Literal['transcribe', 'translate'] (not required, defaults to:   transcribe)  
    Returns:
     - [Textbox] output: str 

 - predict(yt_url, task, api_name="/predict_2") -> (output_0, output_1)
    Parameters:
     - [Textbox] yt_url: str (required)  
     - [Radio] task: Literal['transcribe', 'translate'] (not required, defaults to:   transcribe)  
    Returns:
     - [Html] output_0: str 
     - [Textbox] output_1: str
'''

import gradio as gr
from gradio_client import Client

MODEL_NAME = "openai/whisper-large-v3"
BATCH_SIZE = 8
FILE_LIMIT_MB = 1000
WHISPER_SERVER_PORT = "http://localhost:7860"
TEXT_EMBEDDING_SERVER_PORT = "http://localhost:7861"
MOVEMENT = ["forward", "backward", "left", "right", "up", "down", "stop"]
TIME = ["do not move", "one second", "two seconds", "three seconds", "four seconds", "five seconds", "six seconds", "seven seconds", "eight seconds", "nine seconds", "ten seconds"]

def transcribe(inputs: str, task: str) -> str:
    if inputs == "":
        raise gr.Error(
            "No audio file submitted! Please upload or record an audio file before submitting your request."
        )
    try:
        asr_client = Client(WHISPER_SERVER_PORT)
        result = asr_client.predict(inputs=inputs, task=task, api_name="/predict")
        print(result)
        return result
    except Exception as e:
        raise gr.Error(f"An error occurred during transcription: {str(e)}")

def movement_classification(text):
    if text is None:
        raise gr.Error("No text submitted! Please provide text for classification.")

    try:
        movement_client = Client(TEXT_EMBEDDING_SERVER_PORT)
        result = movement_client.predict(param_0=text, param_1="\n".join(MOVEMENT), api_name="/predict")
        index = result.index(max(result))  # find the index of the highest value
        movement = MOVEMENT[index]
        return movement
    except Exception as e:
        raise gr.Error(f"An error occurred during movement classification: {str(e)}")

def time_classification(text):
    if text is None:
        raise gr.Error("No text submitted! Please provide text for classification.")

    try:
        time_client = Client(TEXT_EMBEDDING_SERVER_PORT)
        result = time_client.predict(param_0=text, param_1="\n".join(TIME), api_name="/predict")
        index = result.index(max(result))  # find the index of the highest value
        time = TIME[index]
        return time
    except Exception as e:
        raise gr.Error(f"An error occurred during time classification: {str(e)}")

def determine_movement_and_time(inputs, task):
    text = transcribe(inputs, task)
    print(text)
    movement = movement_classification(text)
    time = time_classification(text)
    return text, movement, time

demo = gr.Blocks()

full_demo = gr.Interface(
    fn=determine_movement_and_time,
    inputs=[
        gr.Audio(sources=["microphone"], type="filepath", label="Audio Input"),
        gr.Radio(["transcribe", "translate"], label="Task", value="transcribe"),
    ],
    outputs=["text", "text", "text"],
    title="Whisper Large V3: Movement and Time Classification",
    description=f"Transcribe long-form microphone or audio inputs with the click of a button! Demo uses the checkpoint [{MODEL_NAME}](https://huggingface.co/{MODEL_NAME}) and 🤗 Transformers to transcribe audio files of arbitrary length.",
    allow_flagging="never",
)

mf_transcribe = gr.Interface(
    fn=transcribe,
    inputs=[
        gr.Audio(sources="microphone", type="filepath", label="Microphone Input"),
        gr.Radio(["transcribe", "translate"], label="Task", value="transcribe"),
    ],
    outputs="text",
    title="Whisper Large V3: Transcribe Audio",
    description=f"Transcribe long-form microphone or audio inputs with the click of a button! Demo uses the checkpoint [{MODEL_NAME}](https://huggingface.co/{MODEL_NAME}) and 🤗 Transformers to transcribe audio files of arbitrary length.",
    allow_flagging="never",
)

file_transcribe = gr.Interface(
    fn=transcribe,
    inputs=[
        gr.Audio(sources="upload", type="filepath", label="Audio File Upload"),
        gr.Radio(["transcribe", "translate"], label="Task", value="transcribe"),
    ],
    outputs="text",
    title="Whisper Large V3: Transcribe Audio",
    description=f"Transcribe long-form microphone or audio inputs with the click of a button! Demo uses the checkpoint [{MODEL_NAME}](https://huggingface.co/{MODEL_NAME}) and 🤗 Transformers to transcribe audio files of arbitrary length.",
    allow_flagging="never",
)

with demo:
    gr.TabbedInterface([mf_transcribe, file_transcribe, full_demo], ["Microphone", "Audio File", "Full Demo"])

demo.queue()
demo.launch(server_port=7862)