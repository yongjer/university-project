import pytest

from voice_robot.cli import main


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # no .env
    monkeypatch.setenv("ROBOT_LINK", "mock")
    monkeypatch.setenv("ROBOT_MOCK_TIME_SCALE", "0.01")


def test_run_executes_the_instruction(capsys):
    assert main(["run", "forward 2s then stop"]) == 0
    out = capsys.readouterr().out
    assert "parsed (rule): forward 2s, stop" in out
    assert "plan completed" in out


def test_dry_run_does_not_execute(capsys):
    assert main(["run", "--dry-run", "forward 2s"]) == 0
    out = capsys.readouterr().out
    assert "parsed (rule): forward 2s" in out
    assert "plan" not in out.replace("parsed", "")


def test_unrecognised_instruction_fails(capsys):
    assert main(["run", "good morning"]) == 1
    captured = capsys.readouterr()
    assert "nothing" in captured.out
    assert "no robot command recognised" in captured.err


def test_missing_serial_port_is_reported_without_a_traceback(monkeypatch, capsys):
    monkeypatch.setenv("ROBOT_LINK", "serial")
    monkeypatch.setenv("ROBOT_SERIAL_PORT", "/dev/does-not-exist")
    assert main(["run", "forward 1s"]) == 1
    assert "does-not-exist" in capsys.readouterr().err
