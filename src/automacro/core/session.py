"""Sessão: único ponto de controle das atividades (gravar, reproduzir, auto clicker).

Responsabilidades:

* máquina de estados (só uma atividade por vez; ``BusyError`` caso contrário);
* uma thread por atividade, com cancelamento cooperativo (nunca se mata thread);
* parada normal, pausa e **parada de emergência**;
* salvaguardas: contagem regressiva, confirmação de macro importada, failsafe do cursor,
  tempo máximo de reprodução, liberação de teclas presas;
* atalhos globais (via ``HotkeyManager``) ligados às ações acima.

Não depende de Qt. A interface apenas chama os métodos públicos e assina o ``EventBus``.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime
from typing import Callable

from automacro.autoclicker.engine import AutoClickEngine
from automacro.core.errors import (
    AutoMacroError,
    BusyError,
    ConfirmationRequired,
    FeatureUnavailableError,
)
from automacro.core.event_bus import (
    ActivityFinished,
    Countdown,
    EventBus,
    RecordingCount,
    RecordingFinished,
    StateChanged,
)
from automacro.core.safety import CursorFailsafe, EmergencyStop
from automacro.core.timing import RunToken
from automacro.hotkeys.manager import HotkeyManager
from automacro.hotkeys.parser import HotkeyError, parse_hotkey
from automacro.input_handlers.base import InputBackend, InputInjector
from automacro.input_handlers.capabilities import BackendCapabilities, Feature
from automacro.models.events import MacroFormatError
from automacro.models.macro import Macro
from automacro.models.settings import AppSettings, AutoClickConfig, PlayerSettings
from automacro.models.state import ACTIVITY_LABELS, AppState, can_transition
from automacro.player.player import Player
from automacro.recorder.recorder import Recorder
from automacro.utils.platform_info import PlatformInfo, detect_platform

log = logging.getLogger(__name__)

ACTIVITY_AUTOCLICK = "autoclick"
ACTIVITY_RECORD = "record"
ACTIVITY_PLAY = "play"

_JOIN_TIMEOUT_S = 5.0


class Session:
    def __init__(
        self,
        backend: InputBackend,
        settings: AppSettings | None = None,
        bus: EventBus | None = None,
        platform: PlatformInfo | None = None,
    ) -> None:
        self.backend = backend
        self.settings = (settings or AppSettings()).sanitize()
        self.bus = bus or EventBus()
        self.platform = platform or detect_platform()
        self.emergency = EmergencyStop()
        self.last_recording: Macro | None = None

        self._lock = threading.RLock()
        self._state = AppState.IDLE
        self._activity: str | None = None
        self._token: RunToken | None = None
        self._thread: threading.Thread | None = None
        self._current_macro: Macro | None = None
        self._env_info: dict = {}
        self._hotkeys: HotkeyManager | None = None
        self._position_injector: InputInjector | None = None
        self._closed = False

    # ======================================================================================
    # Estado e informações
    # ======================================================================================
    @property
    def state(self) -> AppState:
        return self._state

    @property
    def activity(self) -> str | None:
        return self._activity

    @property
    def busy(self) -> bool:
        return self._state is not AppState.IDLE

    def capabilities(self) -> BackendCapabilities:
        return self.backend.capabilities()

    def set_environment_info(self, info: dict) -> None:
        """Informações que só a UI conhece (ex.: ``{"screen": [1920, 1080]}``)."""
        self._env_info = dict(info)

    def set_current_macro(self, macro: Macro | None) -> None:
        """Macro que o atalho de reprodução vai executar."""
        self._current_macro = macro

    @property
    def current_macro(self) -> Macro | None:
        return self._current_macro

    def _set_state(self, new: AppState) -> None:
        """Chamar com o lock. Transições inválidas são registradas, nunca lançadas."""
        old = self._state
        if new is old:
            return
        if not can_transition(old, new):
            log.error("Transição de estado inválida: %s -> %s", old.value, new.value)
            return
        self._state = new
        self.bus.publish(StateChanged(old, new, self._activity))

    # ======================================================================================
    # Pré-condições
    # ======================================================================================
    def _require(self, feature: Feature, what: str) -> None:
        status = self.capabilities().status(feature)
        if not self.capabilities().available(feature):
            raise FeatureUnavailableError(f"{what} indisponível neste sistema: {status.reason}")

    def _busy_message(self, wanted: str) -> str:
        current = ACTIVITY_LABELS.get(self._activity or "", "outra atividade")
        if self._state is AppState.STOPPING:
            return "Aguarde: a atividade anterior ainda está sendo encerrada."
        return (f"Não é possível iniciar {ACTIVITY_LABELS[wanted]} agora: "
                f"{current} está em andamento.")

    def _get_position_injector(self) -> InputInjector | None:
        """Injetor separado, usado só pelo failsafe (conexão própria ao servidor gráfico)."""
        if not self.capabilities().available(Feature.CURSOR_POSITION):
            return None
        if self._position_injector is None:
            try:
                self._position_injector = self.backend.create_injector()
            except Exception:
                log.exception("Não foi possível criar o leitor de posição do cursor")
                return None
        return self._position_injector

    def cursor_position(self) -> tuple[int, int] | None:
        """Posição atual do cursor, ou None se o sistema não permitir lê-la."""
        injector = self._get_position_injector()
        if injector is None:
            return None
        try:
            return injector.position()
        except Exception:
            log.debug("Falha ao ler a posição do cursor", exc_info=True)
            return None

    def _cursor_in_corner(self) -> bool:
        injector = self._get_position_injector()
        if injector is None:
            return False
        try:
            pos = injector.position()
        except Exception:
            return False
        return pos is not None and pos[0] <= 1 and pos[1] <= 1

    def _check_failsafe_start(self) -> None:
        if self.settings.safety.failsafe_corner and self._cursor_in_corner():
            raise AutoMacroError(
                "O cursor está no canto superior esquerdo, que é a zona de segurança "
                "(parada automática). Mova o cursor para outro lugar ou desative o failsafe "
                "em Configurações.")

    # ======================================================================================
    # Início de atividades
    # ======================================================================================
    def _countdown_for(self, source: str) -> float:
        s = self.settings.safety
        return s.hotkey_countdown_s if source == "hotkey" else s.countdown_s

    def _begin(self, kind: str, target_state: AppState, countdown_s: float,
               body: Callable[[RunToken, Callable[[], None]], bool]) -> None:
        with self._lock:
            if self._closed:
                raise AutoMacroError("O aplicativo está sendo encerrado.")
            if self._state is not AppState.IDLE:
                raise BusyError(self._busy_message(kind))
            token = RunToken()
            self.emergency.register(token)
            self._token = token
            self._activity = kind
            # Sempre começa em "Iniciando…"; só vira o estado final quando o backend estiver
            # realmente pronto (o corpo da atividade chama ``activate``).
            self._set_state(AppState.COUNTDOWN)
            thread = threading.Thread(
                target=self._thread_main, args=(kind, token, countdown_s, target_state, body),
                name=f"automacro-{kind}", daemon=True)
            self._thread = thread
            thread.start()

    def start_autoclick(self, config: AutoClickConfig | None = None,
                        source: str = "ui") -> None:
        self._require(Feature.INJECT, "O envio de cliques")
        cfg = (config or self.settings.autoclick).sanitize()
        if self.settings.safety.failsafe_corner:
            if cfg.use_fixed_position and cfg.x <= 1 and cfg.y <= 1:
                raise AutoMacroError(
                    "A coordenada escolhida está no canto superior esquerdo, que é a zona de "
                    "segurança (parada automática). Escolha outra posição ou desative o "
                    "failsafe em Configurações.")
            self._check_failsafe_start()

        def body(token: RunToken, activate: Callable[[], None]) -> bool:
            injector = self.backend.create_injector()
            failsafe = self._start_failsafe(token)
            try:
                activate()
                stats = AutoClickEngine(injector, self.bus.publish).run(cfg, token)
                log.info("Auto Clicker terminou: %d cliques (%s)", stats.clicks, stats.reason)
                return stats.cancelled
            finally:
                if failsafe:
                    failsafe.stop()
                injector.close()

        self._begin(ACTIVITY_AUTOCLICK, AppState.AUTOCLICKING, self._countdown_for(source), body)

    def toggle_autoclick(self, source: str = "hotkey") -> None:
        if self._activity == ACTIVITY_AUTOCLICK and self.busy:
            self.stop()
        else:
            self.start_autoclick(source=source)

    def start_recording(self, source: str = "ui") -> None:
        self._require(Feature.CAPTURE, "A gravação")

        def body(token: RunToken, activate: Callable[[], None]) -> bool:
            recorder = Recorder(
                self.backend, self.settings.recorder,
                hotkey_keys=self._hotkey_main_keys,
                on_count=lambda n: self.bus.publish(RecordingCount(n)),
                on_limit=lambda: (self.bus.notice(
                    "warning", "Limite de eventos da macro atingido; gravação encerrada."),
                    self.stop()),
            )
            recorder.start()
            try:
                activate()          # a captura já está ativa de verdade
                token.wait_cancelled()
            finally:
                macro = recorder.stop(name=datetime.now().strftime("Gravação %Y-%m-%d %H:%M:%S"),
                                      extra_info=self._recording_info())
            self.last_recording = macro
            self.bus.publish(RecordingFinished(macro))
            return False

        self._begin(ACTIVITY_RECORD, AppState.RECORDING, self._countdown_for(source), body)

    def stop_recording(self) -> None:
        if self._activity == ACTIVITY_RECORD and self.busy:
            self.stop()

    def play(self, macro: Macro, player_settings: PlayerSettings | None = None,
             source: str = "ui", confirmed: bool = False) -> None:
        self._require(Feature.INJECT, "A reprodução")
        try:
            macro.validate()
        except MacroFormatError as exc:
            raise AutoMacroError(f"Macro inválida: {exc}") from exc
        if not macro.events:
            raise AutoMacroError("A macro está vazia: não há nada para reproduzir.")
        if macro.imported and self.settings.safety.confirm_imported and not confirmed:
            raise ConfirmationRequired(
                f"A macro \"{macro.name}\" foi importada e pode executar qualquer ação de "
                "mouse e teclado. Confirme na janela do AutoMacro antes de reproduzir.")
        ps = (player_settings or self.settings.player).sanitize()
        if self.settings.safety.failsafe_corner:
            self._check_failsafe_start()
            if any(e.x is not None and e.x <= 1 and (e.y or 0) <= 1 for e in macro.events):
                self.bus.notice("warning", "Esta macro passa pelo canto superior esquerdo, "
                                "que aciona a parada automática (failsafe).")
        self._warn_screen_mismatch(macro)
        max_minutes = self.settings.safety.max_playback_minutes

        def body(token: RunToken, activate: Callable[[], None]) -> bool:
            injector = self.backend.create_injector()
            failsafe = self._start_failsafe(token)
            limiter = None
            if max_minutes > 0:
                def on_limit() -> None:
                    self.bus.notice("warning", "Tempo máximo de reprodução atingido.")
                    token.cancel()
                limiter = threading.Timer(max_minutes * 60.0, on_limit)
                limiter.daemon = True
                limiter.start()
            try:
                activate()
                stats = Player(injector, self.bus.publish).run(macro, ps, token)
                log.info("Reprodução terminou: %d eventos, %d repetições, atraso máx. %.1f ms",
                         stats.events_played, stats.loops_completed, stats.max_late_ms)
                return stats.cancelled
            finally:
                if limiter:
                    limiter.cancel()
                if failsafe:
                    failsafe.stop()
                injector.close()

        self._begin(ACTIVITY_PLAY, AppState.PLAYING, self._countdown_for(source), body)

    def play_current(self, source: str = "hotkey") -> None:
        if self._current_macro is None:
            raise AutoMacroError("Nenhuma macro selecionada. Escolha uma na aba Reprodutor.")
        self.play(self._current_macro, source=source)

    # ======================================================================================
    # Controle: pausar, parar, emergência
    # ======================================================================================
    def pause_playback(self) -> bool:
        with self._lock:
            if self._state is not AppState.PLAYING or self._token is None:
                return False
            self._token.pause()
            self._set_state(AppState.PAUSED)
            return True

    def resume_playback(self) -> bool:
        with self._lock:
            if self._state is not AppState.PAUSED or self._token is None:
                return False
            self._token.resume()
            self._set_state(AppState.PLAYING)
            return True

    def toggle_pause(self) -> None:
        if not self.pause_playback():
            self.resume_playback()

    def stop(self, wait: bool = False, timeout: float = _JOIN_TIMEOUT_S) -> bool:
        """Para a atividade atual de forma ordenada. Retorna False se não havia nenhuma."""
        with self._lock:
            if self._state in (AppState.IDLE, AppState.STOPPING) or self._token is None:
                thread = self._thread
                stopped = False
            else:
                self._token.cancel()
                self._set_state(AppState.STOPPING)
                thread = self._thread
                stopped = True
        if wait and thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
        return stopped

    def emergency_stop(self) -> None:
        """Cancela tudo imediatamente. Barata e segura de chamar de qualquer thread."""
        count = self.emergency.trigger()
        with self._lock:
            if self._state not in (AppState.IDLE, AppState.STOPPING):
                self._set_state(AppState.STOPPING)
        if count:
            self.bus.notice("warning", "Parada de emergência acionada.")
        else:
            log.info("Parada de emergência acionada sem atividade em andamento")

    # ======================================================================================
    # Thread da atividade
    # ======================================================================================
    def _thread_main(self, kind: str, token: RunToken, countdown_s: float,
                     target_state: AppState,
                     body: Callable[[RunToken, Callable[[], None]], bool]) -> None:
        cancelled = False
        error: str | None = None
        try:
            if countdown_s > 0:
                ticks = math.ceil(countdown_s)
                for i in range(ticks):
                    self.bus.publish(Countdown(ticks - i, kind))
                    if not token.sleep_for(min(1.0, countdown_s - i)):
                        cancelled = True
                        return
            if token.cancelled:
                cancelled = True
                return

            def activate() -> None:
                with self._lock:
                    if not token.cancelled:
                        self._set_state(target_state)

            cancelled = bool(body(token, activate))
        except Exception as exc:
            log.exception("Falha na atividade %s", kind)
            error = str(exc) if isinstance(exc, AutoMacroError) else \
                f"Erro inesperado: {exc} (detalhes no arquivo de log)"
            self.bus.notice("error", error)
        finally:
            self.emergency.unregister(token)
            with self._lock:
                self._set_state(AppState.STOPPING)
                self._token = None
                self._set_state(AppState.IDLE)
                self._activity = None
            self.bus.publish(ActivityFinished(kind, cancelled, error))

    def _start_failsafe(self, token: RunToken) -> CursorFailsafe | None:
        if not self.settings.safety.failsafe_corner:
            return None
        injector = self._get_position_injector()
        if injector is None:
            return None
        failsafe = CursorFailsafe(injector.position, on_trigger=self.emergency_stop)
        failsafe.start()
        return failsafe

    # ======================================================================================
    # Informações auxiliares
    # ======================================================================================
    def _recording_info(self) -> dict:
        info = {"os": self.platform.os, "session": self.platform.session_type}
        info.update(self._env_info)
        return info

    def _warn_screen_mismatch(self, macro: Macro) -> None:
        recorded = macro.recorded_on.get("screen")
        current = self._env_info.get("screen")
        if recorded and current and list(recorded) != list(current):
            self.bus.notice(
                "warning",
                f"A macro foi gravada em uma tela de {recorded[0]}×{recorded[1]} e esta tem "
                f"{current[0]}×{current[1]}: as coordenadas dos cliques podem não coincidir.")

    # ======================================================================================
    # Atalhos globais
    # ======================================================================================
    def _hotkey_main_keys(self) -> set[str]:
        keys: set[str] = set()
        for text in self.settings.hotkeys.as_dict().values():
            try:
                keys.add(parse_hotkey(text).key)
            except HotkeyError:
                pass
        return keys

    def _guarded(self, fn: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                fn()
            except AutoMacroError as exc:
                self.bus.notice("warning", str(exc))
            except Exception as exc:
                log.exception("Erro em ação de atalho")
                self.bus.notice("error", f"Erro inesperado: {exc}")
        return run

    def start_hotkeys(self) -> bool:
        """Liga os atalhos globais. Retorna False (com aviso claro) se o sistema impedir."""
        status = self.capabilities().status(Feature.HOTKEYS)
        if not self.capabilities().available(Feature.HOTKEYS):
            self.bus.notice("warning", f"Atalhos globais indisponíveis: {status.reason}")
            return False
        if self._hotkeys is None:
            manager = HotkeyManager(self.backend.create_listener())
            hk = manager.register_action
            hk("record_start", self._guarded(lambda: self.start_recording(source="hotkey")))
            hk("record_stop", self._guarded(self.stop_recording))
            hk("play_start", self._guarded(self.play_current))
            hk("stop", self._guarded(self.stop))
            hk("emergency", self.emergency_stop, immediate=True)
            hk("autoclick_toggle", self._guarded(self.toggle_autoclick))
            hk("play_pause", self._guarded(self.toggle_pause))
            self._hotkeys = manager
        self._hotkeys.set_bindings(self.settings.hotkeys.as_dict())
        try:
            self._hotkeys.start()
        except Exception as exc:
            log.exception("Falha ao iniciar atalhos globais")
            self.bus.notice("error", f"Não foi possível iniciar os atalhos globais: {exc}")
            return False
        return True

    @property
    def hotkeys(self) -> HotkeyManager | None:
        return self._hotkeys

    def apply_settings(self, settings: AppSettings) -> None:
        """Aplica novas configurações. Levanta HotkeyError se os atalhos forem inválidos."""
        settings.sanitize()
        if self._hotkeys is not None:
            self._hotkeys.set_bindings(settings.hotkeys.as_dict())   # valida antes de aplicar
        self.settings = settings

    # ======================================================================================
    # Encerramento
    # ======================================================================================
    def shutdown(self) -> None:
        """Para tudo, libera listeners e threads. Idempotente."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.emergency_stop()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(_JOIN_TIMEOUT_S)
        if self._hotkeys is not None:
            self._hotkeys.stop()
        if self._position_injector is not None:
            try:
                self._position_injector.close()
            except Exception:
                log.exception("Erro ao fechar leitor de posição")
        try:
            self.backend.close()
        except Exception:
            log.exception("Erro ao fechar o backend")
