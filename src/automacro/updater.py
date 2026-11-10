"""Atualização automática: consulta a última versão publicada no GitHub, baixa o instalador
e o executa. Não depende de Qt (a interface só chama estas funções em uma thread).

Segurança:
* Só fala HTTPS e só aceita baixar de servidores do GitHub (lista ``ALLOWED_HOSTS``),
  inclusive depois de redirecionamentos.
* O instalador baixado só é executado se o SHA-256 bater com o publicado pelo GitHub
  (campo ``digest`` do arquivo na release ou arquivo ``AutoMacro-Setup.exe.sha256``).
* Nada é instalado sem o usuário clicar em "Atualizar agora".
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

log = logging.getLogger(__name__)

REPO = "erosxv/AutoMacro"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALLER_NAME = "AutoMacro-Setup.exe"
CHECKSUM_NAME = INSTALLER_NAME + ".sha256"

ALLOWED_HOSTS = frozenset({
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
})
TIMEOUT_S = 10
MAX_INSTALLER_BYTES = 400 * 1024 * 1024
USER_AGENT = "AutoMacro-updater"

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+){0,3})$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(Exception):
    """Falha ao verificar/baixar a atualização. A mensagem já é amigável ao usuário."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str            # "0.1.12"
    tag: str                # "v0.1.12"
    installer_url: str
    sha256: str | None
    checksum_url: str | None
    size: int
    notes: str
    page_url: str


# ---- versões ------------------------------------------------------------------------------

def parse_version(text: str) -> tuple[int, ...]:
    m = _VERSION_RE.match(text.strip())
    if not m:
        raise ValueError(f"versão inválida: {text!r}")
    parts = tuple(int(p) for p in m.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def can_self_update() -> bool:
    """A instalação automática só existe no Windows, no programa empacotado."""
    return sys.platform.startswith("win") and bool(getattr(sys, "frozen", False))


# ---- rede ---------------------------------------------------------------------------------

def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_HOSTS:
        raise UpdateError("Endereço de download não permitido (fora do GitHub).")


def _open(url: str, accept: str = "*/*"):
    _check_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise UpdateError("O GitHub limitou as consultas. Tente de novo mais tarde.") from exc
        if exc.code == 404:
            raise UpdateError("Nenhuma versão publicada foi encontrada (o repositório precisa "
                              "ser público).") from exc
        raise UpdateError(f"O GitHub respondeu com erro {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError("Sem conexão com a internet (ou o GitHub está fora do ar).") from exc
    _check_url(response.geturl())          # depois de redirecionamentos
    return response


def fetch_json(url: str) -> dict:
    with _open(url, "application/vnd.github+json") as response:
        raw = response.read(2_000_000)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise UpdateError("Resposta inválida do GitHub.") from exc
    if not isinstance(data, dict):
        raise UpdateError("Resposta inválida do GitHub.")
    return data


# ---- verificação ----------------------------------------------------------------------------

def parse_release(data: dict) -> UpdateInfo | None:
    """Converte a resposta da API em UpdateInfo, ou None se a release não for utilizável."""
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not _VERSION_RE.match(tag.strip()):
        return None
    assets = data.get("assets") if isinstance(data.get("assets"), list) else []
    installer = checksum = None
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == INSTALLER_NAME:
            installer = asset
        elif asset.get("name") == CHECKSUM_NAME:
            checksum = asset
    if installer is None or not isinstance(installer.get("browser_download_url"), str):
        return None
    digest = installer.get("digest")
    sha = None
    if isinstance(digest, str) and digest.lower().startswith("sha256:"):
        candidate = digest.split(":", 1)[1].strip()
        if _SHA256_RE.match(candidate):
            sha = candidate.lower()
    size = installer.get("size")
    page = data.get("html_url") if isinstance(data.get("html_url"), str) else RELEASES_PAGE
    notes = data.get("body") if isinstance(data.get("body"), str) else ""
    return UpdateInfo(
        version=tag.strip().lstrip("v"),
        tag=tag.strip(),
        installer_url=installer["browser_download_url"],
        sha256=sha,
        checksum_url=checksum.get("browser_download_url") if checksum else None,
        size=size if isinstance(size, int) and size > 0 else 0,
        notes=notes[:2000],
        page_url=page,
    )


def check_for_update(current: str,
                     fetch: Callable[[str], dict] = fetch_json) -> UpdateInfo | None:
    """Retorna a atualização disponível, ou None se já está na versão mais nova."""
    info = parse_release(fetch(API_URL))
    if info is None:
        return None
    try:
        return info if is_newer(info.version, current) else None
    except ValueError:
        return None


# ---- download e instalação ----------------------------------------------------------------

def _expected_sha256(info: UpdateInfo) -> str:
    if info.sha256:
        return info.sha256
    if info.checksum_url:
        with _open(info.checksum_url) as response:
            text = response.read(4096).decode("utf-8", "replace")
        token = text.strip().split()[0] if text.strip() else ""
        if _SHA256_RE.match(token):
            return token.lower()
    raise UpdateError("Não foi possível confirmar a integridade do arquivo; atualização cancelada.")


def download_installer(info: UpdateInfo, dest_dir: Path | None = None,
                       progress: Callable[[int, int], None] | None = None,
                       cancelled: Callable[[], bool] = lambda: False) -> Path:
    """Baixa o instalador e confere o SHA-256. Apaga o arquivo se algo falhar."""
    expected = _expected_sha256(info)
    folder = Path(dest_dir) if dest_dir else Path(tempfile.mkdtemp(prefix="automacro-update-"))
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / INSTALLER_NAME
    sha = hashlib.sha256()
    done = 0
    try:
        with _open(info.installer_url) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or info.size or 0)
            while True:
                if cancelled():
                    raise UpdateError("Download cancelado.")
                chunk = response.read(65536)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_INSTALLER_BYTES:
                    raise UpdateError("Arquivo grande demais; atualização cancelada.")
                sha.update(chunk)
                out.write(chunk)
                if progress:
                    progress(done, total)
        if sha.hexdigest() != expected:
            raise UpdateError("O arquivo baixado está corrompido (verificação falhou); "
                              "atualização cancelada.")
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return target


def installer_command(path: Path) -> list[str]:
    return [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            "/RELAUNCH=1"]


def launch_installer(path: Path) -> None:
    """Inicia o instalador separado do app (Windows). Depois disso o app deve encerrar."""
    if not sys.platform.startswith("win"):
        raise UpdateError("A instalação automática só está disponível no Windows.")
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        subprocess.Popen(installer_command(path), creationflags=flags, close_fds=True,
                         cwd=os.path.dirname(str(path)))
    except OSError as exc:
        raise UpdateError(f"Não foi possível iniciar o instalador: {exc}") from exc
