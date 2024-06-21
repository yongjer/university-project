"""
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
"""

"""
Loaded as API: http://localhost:7860/ ✔
Client.predict() Usage Info
---------------------------
Named API endpoints: 1

 - predict(audio_filepath, src_lang, tgt_lang, pnc, api_name="/transcribe") -> model_output
    Parameters:
     - [Audio] audio_filepath: filepath (required)  
     - [Dropdown] src_lang: Literal['English', 'Spanish', 'French', 'German'] (not required, defaults to:   English)  
     - [Dropdown] tgt_lang: Literal['English', 'Spanish', 'French', 'German'] (not required, defaults to:   English)  
     - [Checkbox] pnc: bool (not required, defaults to:   True)  
    Returns:
     - [Textbox] model_output: str
"""

"""
Loaded as API: http://localhost:7863/ ✔
Client.predict() Usage Info
---------------------------
Named API endpoints: 1

 - predict(message, api_name="/chat") -> value_1
    Parameters:
     - [Multimodaltextbox] message: Dict(text: str, files: List[filepath]) (not required, defaults to:   {'text': '', 'files': []})  
    Returns:
     - [Multimodaltextbox] value_1: Dict(text: str, files: List[filepath]) 
"""

# Importing gradio for creating web UI and gradio_client for making API requests
import gradio as gr
from gradio_client import Client
import serial # for serial communication
# Constants for the model, batch size, file limit, server ports, and possible movement and time commands
MODEL_NAME = "nvidia/canary-1b"
BATCH_SIZE = 8
FILE_LIMIT_MB = 1000
WHISPER_SERVER_PORT = "http://localhost:7860"
TEXT_EMBEDDING_SERVER_PORT = "http://localhost:7861"
MULTIMODAL_SERVER_PORT = "http://localhost:7863"
MOVEMENT = ["forward", "backward", "go left", "go right", "upward", "downward", "stop"]
TIME = [
    "zero second(s)",
    "one second(s)",
    "two second(s)",
    "three second(s)",
    "four second(s)",
    "five second(s)",
    "six second(s)",
    "seven second(s)",
    "eight second(s)",
    "nine second(s)",
    "ten second(s)",
]
ARDUINO_PORT = "/dev/ttyUSB0"



# Creating clients for ASR (Automatic Speech Recognition) and Text Embedding
asr_client = Client(WHISPER_SERVER_PORT)  # client for ASR
embedding_client = Client(TEXT_EMBEDDING_SERVER_PORT)  # client for text embedding


# Function to predict the movement and time based on the parameters
def predict(param_0, param_1) -> str:
    result = embedding_client.predict(
        param_0=param_0, param_1="\n".join(param_1), api_name="/predict"
    )  # predict the movement or time
    index = result.index(max(result))  # find the index of the highest value
    return param_1[index]  # return the corresponding movement or time


# Function to transcribe the audio input and predict the movement and time
def transcribe(inputs: str, task: str) -> str:
    if inputs == "":
        return "No audio file submitted! Please upload or record an audio file before submitting your request."
    try:
        result = asr_client.predict(
            audio_filepath=inputs,
            src_lang="English",
            tgt_lang="English",
            pnc=False,
            api_name="/transcribe",
        )  # transcribe the audio input
        print(result)
        movement = predict(result, MOVEMENT)  # predict the movement
        print(movement)
        time = predict(result, TIME)  # predict the time
        print(f"movement = {movement}, time = {time}") # return the movement and time
        # send the movement and time to the Arduino
        with serial.Serial(ARDUINO_PORT, 115200, timeout=1) as ser:
            ser.write(f"{movement} {time}".encode())

        return f"{movement} {time}"
    except Exception as e:
        return f"An error occurred during transcription: {str(e)}"  # return the error message if any exception occurs


# Creating a gradio web UI
demo = gr.Blocks()

# Creating an interface for the transcribe function
mf_transcribe = gr.Interface(
    fn=transcribe,
    inputs=[
        gr.Audio(
            sources="microphone", type="filepath", label="Microphone Input"
        ),  # input for the audio file
        gr.Radio(
            ["transcribe", "translate"], label="Task", value="transcribe"
        ),  # input for the task type
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
