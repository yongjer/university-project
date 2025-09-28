# University Project
<div align="center">

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/yongjer/university-project)

</div>
## Introduction

This project is a university project focused on creating a voice-controlled robotic system. The system is comprised of the following key components:

- **AI Server (`ai_server/`)**: Hosts various Artificial Intelligence models, primarily for speech recognition (converting voice commands to text) and potentially other AI tasks like vision or advanced command understanding.
- **Jetson (`jetson/`)**: Acts as the main control unit. It likely captures audio, uses the AI server to interpret voice commands, and then translates these commands into actions for the robotic hardware.
- **Arduino (`arduino/`)**: Manages the low-level control of the robot's hardware, such as motors for movement and other actuators, based on instructions received from the Jetson.

## Structure

The project is structured as follows:

- `ai_server/`: Contains various AI models and scripts to run them. The primary models and their purposes are:
    - **ASR Models:** Used for Automatic Speech Recognition to convert spoken commands into text.
        - Canary-1B ASR (`canary-1b/`)
        - Distil-Whisper ASR (`distil-whisper/`)
        - Whisper Large v3 ASR (`whisper-large-v3/`)
    - **Vision Model:**
        - Phi-3 Vision (`Phi-3-vision-128k-instruct/`): Capable of understanding and interpreting visual information.
    - **Sentence Transformers:**
        - BAAI/bge-m3 (`sentence-transformers/`): Used to create numerical representations (embeddings) of text, enabling semantic understanding of commands.
    - **Running the Models:**
        - Most models are run using Docker via `run.sh` scripts in their respective directories (e.g., `cd ai_server/MODEL_DIRECTORY && ./run.sh`).
        - The `sentence-transformers` model is run using `python app.py` in its directory and utilizes Gradio for its interface.
- `arduino/`: This directory contains the project for the microcontroller that directly controls the robot's hardware.
    - **Purpose:** Manages the physical operation of the robot, including:
        - Movement: Controls DC motors for forward, backward, left, and right motions.
        - Elevator Mechanism: Controls a stepper motor for upward and downward movements.
    - **Development:** The project is developed using PlatformIO.
    - **Main Code:** The core logic for hardware control is located in `src/main.cpp`.
    - **Command Interface:** The Arduino receives commands from the Jetson via serial communication. Commands are strings with the format `MOVEMENT DURATION`. Examples:
        - `forward five second(s)`
        - `backward two second(s)`
        - `left one second(s)`
        - `right three second(s)`
        - `upward four second(s)`
        - `downward one second(s)`
        - `stop zero second(s)` (duration is often ignored for stop, as it's immediate)
- `jetson/`: This directory houses the software for the Jetson device, which acts as the central processing unit or "brain" of the robotic system.
    - **Role:** Orchestrates the overall operation of the robot by processing inputs and sending commands to the hardware controllers.
    - **Workflow:**
        - Captures audio input (likely via a microphone).
        - Communicates with the `ai_server` to perform Automatic Speech Recognition (ASR) on the audio, converting it to text.
        - Processes the recognized text command. The `jetson/similarity/app.py` script suggests it may use sentence embeddings (potentially from an `ai_server` model) to compare the command against known commands or understand variations in phrasing.
        - Sends appropriate serial commands to the `arduino` to actuate the robot's motors and elevator.
    - **Subdirectories:**
        - `jetson/client/`: Contains client application code. (Note: Its `README.md` is currently a template and requires further details specific to this client).
        - `jetson/similarity/`: Contains code related to command processing and similarity matching, as evidenced by `app.py`.
    - **Dockerfile:** Contains a `Dockerfile` (`jetson/Dockerfile`), likely for containerizing the Jetson application environment, ensuring consistency and ease of deployment.

## Setup and Installation

### `ai_server`
-   **Prerequisites:** Docker must be installed and running. Ensure your system supports GPU passthrough for Docker if using GPU-accelerated models.
-   **Models:**
    -   Most models are run via Docker. The `run.sh` script in each model's directory (e.g., `ai_server/canary-1b/run.sh`) should attempt to pull the required Docker image from a registry (e.g., Hugging Face Spaces).
    -   If a `run.sh` script fails to pull an image, you may need to manually pull it using `docker pull <image_name>`. The specific image names can be found within the `run.sh` scripts.
    -   The `sentence-transformers` model (`ai_server/sentence-transformers/`) is run directly with Python. It requires Python and Gradio to be installed (`pip install gradio`). Dependencies for the model itself (e.g., `BAAI/bge-m3`) are usually downloaded automatically by the `gradio.load()` command on first run.

### `arduino`
-   **Prerequisites:** PlatformIO IDE or PlatformIO Core must be installed.
-   **Building and Uploading:**
    1.  Open the `arduino/` directory in PlatformIO IDE or navigate to it in your terminal.
    2.  Build the project using the PlatformIO build command (e.g., `pio run`).
    3.  Upload the compiled firmware to the Arduino board using the PlatformIO upload command (e.g., `pio run --target upload`). Ensure the Arduino is connected to your computer.

### `jetson`
-   **Prerequisites:**
    -   Python 3 installed.
    -   Consider setting up a Python virtual environment.
-   **Dependencies:**
    -   Install Python dependencies, such as `gradio_client`. Check individual scripts or subdirectories like `jetson/client/` for specific `requirements.txt` files.
    -   Ensure any Jetson-specific SDKs or libraries (e.g., NVIDIA JetPack components) required for hardware interaction or accelerated computing are installed.
-   **Hardware Connection:** Ensure the Arduino is connected to the Jetson (e.g., via USB) for serial communication.

## Usage

Follow these steps to operate the voice-controlled robotic system:

1.  **Start AI Services (`ai_server`):**
    *   Navigate to the directory of the desired AI model(s) within `ai_server/`. For instance, to use an ASR model: `cd ai_server/canary-1b` (or `distil-whisper`, `whisper-large-v3`).
    *   Execute the `run.sh` script: `./run.sh`. This will typically start a Docker container serving the model. Note the port it's running on (e.g., 7860, found in the `run.sh` or script output).
    *   If using the `sentence-transformers` model for command similarity, navigate to `ai_server/sentence-transformers/` and run `python app.py`. Note its port (e.g., 7861).
    *   *Ensure the IP address and port of these AI services are correctly configured in the Jetson application(s) that will call them.* (The example `jetson/similarity/app.py` uses `127.0.0.1:7860`, implying it might run on the same machine or requires configuration if `ai_server` is remote).

2.  **Prepare Arduino (`arduino`):**
    *   Ensure the Arduino board is flashed with the latest firmware from the `arduino/` directory (as per Setup instructions).
    *   Connect the Arduino to the Jetson device (typically via USB). Note the serial port on the Jetson that the Arduino connects to (e.g., `/dev/ttyUSB0` or `/dev/ttyACM0`). This may need to be configured in the Jetson application.

3.  **Run Jetson Application (`jetson`):**
    *   Navigate to the main Jetson application directory (e.g., this could be within `jetson/client/src` or a specific project directory).
    *   Execute the main Python script (e.g., `python main_control_script.py` - replace `main_control_script.py` with the actual name of the script).
    *   Ensure the Jetson application is configured with:
        *   The correct IP address(es) and port(s) for the AI services running on `ai_server`.
        *   The correct serial port for communicating with the Arduino.

4.  **Operate the System:**
    *   Once all components are running and connected, you should be able to issue voice commands.
    *   Speak clearly into the microphone connected to the Jetson system.
    *   The Jetson application will process the voice command using the AI server, determine the intended action (possibly using similarity matching), and send the corresponding command to the Arduino to control the robot.

## Contributing

We welcome contributions to this project! If you'd like to contribute, please follow these general guidelines:

1.  **Fork the Repository:** Start by forking the project to your own GitHub account.
2.  **Create a Branch:** Create a new branch in your fork for your feature or bug fix. Use a descriptive name (e.g., `feature/new-voice-command` or `fix/arduino-motor-bug`).
3.  **Make Your Changes:** Implement your changes, additions, or fixes in your branch.
    *   Ensure your code is well-commented.
    *   If adding new features, consider if documentation or examples need updating.
    *   If applicable, add tests for your changes.
4.  **Test Your Changes:** Make sure your changes work as expected and do not break existing functionality.
5.  **Commit Your Changes:** Commit your work with clear and descriptive commit messages.
6.  **Push to Your Fork:** Push your changes to your branch on your fork.
7.  **Submit a Pull Request:** Open a pull request from your branch to the main project's `main` (or `master`) branch. Provide a clear description of your changes in the pull request.

If you're planning a larger contribution, it's a good idea to open an issue first to discuss your ideas.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.
