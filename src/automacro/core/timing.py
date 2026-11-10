"""Temporização precisa e cancelável.

Princípios:

* **Prazos absolutos.** Cada evento tem um instante-alvo calculado a partir do início da
  execução; os erros de um evento não se acumulam nos seguintes (sem *drift*).
* **Espera híbrida.** Uma espera em ``Condition.wait`` (interrompível na hora por cancelar
  ou pausar) cobre a maior parte do intervalo; o trecho final é uma espera ativa curta com
  ``sleep(0)`` (libera o GIL), porque a precisão do ``wait`` depende do sistema (≈15 ms no
  Windows sem ajuste de timer). A margem é calibrada medindo o sistema real.
* **Nada de matar threads.** Parar significa levantar o cancelamento; toda espera acorda.
"""

from __future__ import annotations

import threading
import time

_MIN_MARGIN_NS = 1_000_000        # 1 ms
_MAX_MARGIN_NS = 25_000_000       # 25 ms
_margin_ns: int | None = None
_margin_lock = threading.Lock()


def calibrate_wait_margin(samples: int = 6) -> int:
    """Mede o atraso típico de ``Condition.wait(1 ms)`` e devolve a margem de espera ativa."""
    cond = threading.Condition()
    worst = 0
    for _ in range(samples):
        start = time.perf_counter_ns()
        with cond:
            cond.wait(0.001)
        overshoot = time.perf_counter_ns() - start - 1_000_000
        worst = max(worst, overshoot)
    margin = int(worst * 1.5) + 500_000
    return max(_MIN_MARGIN_NS, min(_MAX_MARGIN_NS, margin))


def wait_margin_ns() -> int:
    global _margin_ns
    if _margin_ns is None:
        with _margin_lock:
            if _margin_ns is None:
                _margin_ns = calibrate_wait_margin()
    return _margin_ns


def set_wait_margin_ns(value: int | None) -> None:
    """Para testes: fixa (ou limpa, com None) a margem de espera ativa."""
    global _margin_ns
    _margin_ns = value


class RunToken:
    """Controle de uma execução: cancelar, pausar, continuar e esperar com prazo."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._cancelled = False
        self._paused = False

    # ---- estado ---------------------------------------------------------------------
    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def paused(self) -> bool:
        return self._paused

    def cancel(self) -> None:
        with self._cond:
            self._cancelled = True
            self._cond.notify_all()

    def pause(self) -> None:
        with self._cond:
            self._paused = True
            self._cond.notify_all()

    def resume(self) -> None:
        with self._cond:
            self._paused = False
            self._cond.notify_all()

    # ---- esperas --------------------------------------------------------------------
    def wait_cancelled(self, timeout: float | None = None) -> bool:
        """Bloqueia até cancelar (ou até o timeout). Retorna True se foi cancelado."""
        with self._cond:
            if not self._cancelled:
                self._cond.wait_for(lambda: self._cancelled, timeout)
            return self._cancelled

    def sleep_until(self, deadline_ns: int) -> int | None:
        """Espera até ``deadline_ns`` (relógio ``perf_counter_ns``).

        Retorna o prazo efetivo (deslocado pelo tempo em que ficou pausado) ou ``None`` se
        a execução foi cancelada. Pausar durante a espera estende o prazo.
        """
        margin = wait_margin_ns()
        while True:
            with self._cond:
                if self._cancelled:
                    return None
                if self._paused:
                    started = time.perf_counter_ns()
                    while self._paused and not self._cancelled:
                        self._cond.wait()
                    if self._cancelled:
                        return None
                    deadline_ns += time.perf_counter_ns() - started
                    continue
                remaining = deadline_ns - time.perf_counter_ns()
                if remaining > margin:
                    self._cond.wait((remaining - margin) / 1e9)
                    continue
            # Trecho final: espera ativa curta, reagindo a cancelar/pausar.
            while True:
                if self._cancelled or self._paused:
                    break
                if time.perf_counter_ns() >= deadline_ns:
                    return deadline_ns
                time.sleep(0)

    def sleep_for(self, seconds: float) -> bool:
        """Espera relativa. Retorna True se completou, False se foi cancelado."""
        deadline = time.perf_counter_ns() + int(seconds * 1e9)
        return self.sleep_until(deadline) is not None
