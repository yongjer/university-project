# Robot firmware (Arduino Uno)

Drives two DC motors (differential drive, pins 2-5) and the elevator stepper
(pins 6-7) from line-based serial commands at 115200 baud.

The hardware-independent logic lives in [`lib/robot_core`](lib/robot_core/src) and is
unit-tested on the host. [`src/main.cpp`](src/main.cpp) only adapts it to the pins and
the serial port.

```bash
pio test -e native            # unit tests on this computer
pio run -e uno                # build
pio run -e uno -t upload      # flash
pio device monitor -b 115200  # talk to the robot by hand
```

## Design

- **Non-blocking loop.** Input is assembled one character at a time by `LineBuffer`, and
  motions end by comparing `millis()` timestamps, so the loop never waits. `STOP` is
  therefore handled while a motion is running, and the stepper gets its pulses on every
  pass. v1 blocked in `readStringUntil()` and `delay()`, which made both impossible.
- **Rollover-safe timing.** Elapsed time uses unsigned subtraction, which stays correct
  across the `millis()` rollover after about 49.7 days.
- **No heap allocation.** Parsing works on fixed buffers, with no `String` objects.
- **Hard limits.** A motion lasts at most 10 s, and every motion ends on its own even if
  the host disappears.

## Wire protocol

One command per line, case-insensitive, terminated by `\n`.

| Command | Meaning |
| :--- | :--- |
| `FORWARD <ms>`, `BACKWARD <ms>` | Drive straight |
| `LEFT <ms>`, `RIGHT <ms>` | Rotate in place |
| `UP <ms>`, `DOWN <ms>` | Move the elevator |
| `STOP` | Stop everything immediately |
| `PING` | Connection check |
| `STATUS` | Report the current motion |

`<ms>` is an integer from 0 to 10000. A new motion replaces the one in progress.

The v1 format is still accepted: `forward three second(s)`, `stop zero second(s)`.

| Reply | Meaning |
| :--- | :--- |
| `READY voice-robot-fw/2.0.0` | Board has booted |
| `ACK <ACTION> <ms>` | Motion started |
| `DONE <ACTION>` | Motion ran to the end |
| `ABORTED <ACTION>` | Motion was replaced by a new one |
| `STOPPED <ACTION>` or `STOPPED IDLE` | `STOP` handled, naming what it interrupted |
| `PONG` | Answer to `PING` |
| `STATUS IDLE` or `STATUS <ACTION> <remaining ms>` | Answer to `STATUS` |
| `ERR <CODE>` | `LINE_TOO_LONG`, `UNKNOWN_ACTION`, `MISSING_DURATION`, `BAD_DURATION`, `DURATION_TOO_LONG` or `TRAILING_INPUT` |

## Build options

Set these with `build_flags` in [`platformio.ini`](platformio.ini).

| Flag | Default | Meaning |
| :--- | :--- | :--- |
| `SERIAL_BAUD` | `115200` | Must match `ROBOT_BAUDRATE` on the Jetson (v1 used 9600) |
| `STEPPER_SPEED_SPS` | `3000` | Elevator speed in steps per second |
| `STEPPER_MODE` | `0` | `0`: AccelStepper `FULL2WIRE`. `1`: CW/CCW two-pulse driver input |
