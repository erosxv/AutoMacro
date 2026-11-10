import threading
import time

from automacro.core.timing import RunToken, calibrate_wait_margin


def test_wait_reaches_deadline_with_precision():
    token = RunToken()
    errors = []
    for _ in range(10):
        deadline = time.perf_counter_ns() + 20_000_000
        got = token.sleep_until(deadline)
        errors.append((time.perf_counter_ns() - deadline) / 1e6)
        assert got == deadline
    assert min(errors) >= 0
    assert sorted(errors)[len(errors) // 2] < 3.0     # mediana: poucos ms de erro


def test_cancel_interrupts_long_wait_immediately():
    token = RunToken()
    result = []
    t = threading.Thread(target=lambda: result.append(token.sleep_for(30)))
    t.start()
    time.sleep(0.05)
    started = time.perf_counter()
    token.cancel()
    t.join(1.0)
    assert not t.is_alive()
    assert time.perf_counter() - started < 0.2
    assert result == [False]


def test_pause_extends_deadline_and_resume_continues():
    token = RunToken()
    out = []
    deadline = time.perf_counter_ns() + 100_000_000

    def run():
        out.append(token.sleep_until(deadline))
        out.append(time.perf_counter_ns())

    t = threading.Thread(target=run)
    t.start()
    time.sleep(0.02)
    token.pause()
    time.sleep(0.2)                                    # pausado por 200 ms
    token.resume()
    t.join(2.0)
    effective, finished = out
    assert effective > deadline + 150_000_000          # prazo deslocado pela pausa
    assert finished >= effective


def test_cancel_during_pause():
    token = RunToken()
    token.pause()
    result = []
    t = threading.Thread(target=lambda: result.append(token.sleep_until(time.perf_counter_ns() + 1)))
    t.start()
    time.sleep(0.05)
    token.cancel()
    t.join(1.0)
    assert result == [None]


def test_calibration_in_sane_range():
    assert 1_000_000 <= calibrate_wait_margin() <= 25_000_000
