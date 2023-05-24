# university-project
## overview
using nvidia tao toolkit 5 to do transfer learning, focus on the inference part on the limited computability sbc

use pyserial to send serial number to adam-4000, which controls the circuit open or close, controls the relay.

set jetson nano as server,and write a program with gui by pyside6 as client to implete the remote control,targeting desktop and android platform

## potential toolkit
* [`tao toolkit`](https://developer.nvidia.com/tao-toolkit)
* [`transformers by huggingface`](https://huggingface.co/docs/transformers/index)
* [`pyserial`](https://pythonhosted.org/pyserial/)
* [`yolo-nas`](https://github.com/Deci-AI/super-gradients/blob/master/YOLONAS.md)
* [`PySide6`](https://doc.qt.io/qtforpython-6/index.html)
## FYI: create a gui for android and desktop platform by flet, which using material design
* [`flet`](https://flet.dev/docs/) 
