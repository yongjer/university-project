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
MOVEMENT = ["forward", "backward", "go left", "go right", "upward", "downward", "stop"]
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
        movement_client = Client(TEXT_EMBEDDING_SERVER_PORT)
        movement_result = movement_client.predict(param_0=result, param_1="\n".join(MOVEMENT), api_name="/predict")
        movement_index = movement_result.index(max(movement_result))  # find the index of the highest value
        movement = str(MOVEMENT[movement_index])
        print(movement)
        time_client = Client(TEXT_EMBEDDING_SERVER_PORT)
        time_result = time_client.predict(param_0=result, param_1="\n".join(TIME), api_name="/predict")
        time_index = time_result.index(max(time_result))  # find the index of the highest value
        time = str(TIME[time_index])
        return f"movement = {movement}, time = {time}"
    except Exception as e:
        raise gr.Error(f"An error occurred during transcription: {str(e)}")

demo = gr.Blocks()

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

with demo:
    gr.TabbedInterface([mf_transcribe], ["Microphone"])

demo.queue()
demo.launch(server_port=7862, share=True)

'''
# Importing gradio for creating web UI and gradio_client for making API requests
import gradio as gr
from gradio_client import Client

# Constants for the model, batch size, file limit, server ports, and possible movement and time commands
MODEL_NAME = "openai/whisper-large-v3"
BATCH_SIZE = 8
FILE_LIMIT_MB = 1000
WHISPER_SERVER_PORT = "http://localhost:7860"
TEXT_EMBEDDING_SERVER_PORT = "http://localhost:7861"
MOVEMENT = ["forward", "backward", "go left", "go right", "upward", "downward", "stop"]
TIME = ["do not move", "one second", "two seconds", "three seconds", "four seconds", "five seconds", "six seconds", "seven seconds", "eight seconds", "nine seconds", "ten seconds"]

# Creating clients for ASR (Automatic Speech Recognition) and Text Embedding
asr_client = Client(WHISPER_SERVER_PORT)
embedding_client = Client(TEXT_EMBEDDING_SERVER_PORT)

# Function to predict the movement and time based on the parameters
def predict(param_0, param_1):
    result = embedding_client.predict(param_0=param_0, param_1="\n".join(param_1), api_name="/predict")
    index = result.index(max(result))  # find the index of the highest value
    return str(param_1[index])  # return the corresponding movement or time

# Function to transcribe the audio input and predict the movement and time
def transcribe(inputs: str, task: str) -> str:
    if inputs == "":
        return "No audio file submitted! Please upload or record an audio file before submitting your request."
    try:
        result = asr_client.predict(inputs=inputs, task=task, api_name="/predict")  # transcribe the audio input
        print(result)
        movement = predict(result, MOVEMENT)  # predict the movement
        print(movement)
        time = predict(result, TIME)  # predict the time
        return f"movement = {movement}, time = {time}"  # return the movement and time
    except Exception as e:
        return f"An error occurred during transcription: {str(e)}"  # return the error message if any exception occurs

# Creating a gradio web UI
demo = gr.Blocks()

# Creating an interface for the transcribe function
mf_transcribe = gr.Interface(
    fn=transcribe,
    inputs=[
        gr.Audio(sources="microphone", type="filepath", label="Microphone Input"),  # input for the audio file
        gr.Radio(["transcribe", "translate"], label="Task", value="transcribe"),  # input for the task type
    ],
    outputs="text",  # output type
    title="Whisper Large V3: Transcribe Audio",  # title of the interface
    description=f"Transcribe long-form microphone or audio inputs with the click of a button! Demo uses the checkpoint [{MODEL_NAME}](https://huggingface.co/{MODEL_NAME}) and 🤗 Transformers to transcribe audio files of arbitrary length.",  # description of the interface
    allow_flagging="never",  # disable flagging
)

# Adding the interface to the web UI
with demo:
    gr.TabbedInterface([mf_transcribe], ["Microphone"])

# Starting the queue for the web UI
demo.queue()

# Launching the web UI
demo.launch(server_port=7862, share=True)
'''