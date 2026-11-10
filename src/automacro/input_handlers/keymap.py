"""Vocabulário neutro de teclas, independente de backend.

* Teclas imprimíveis: o próprio caractere em minúsculas (``"a"``, ``"5"``).
* Teclas especiais: ``"<nome>"`` usando os nomes do pynput (``"<f6>"``, ``"<enter>"``).
* Teclas sem nome nem caractere: ``"<vk:NN>"`` (código virtual da plataforma).
"""

from __future__ import annotations

MODIFIERS = frozenset({"<ctrl>", "<alt>", "<shift>", "<cmd>", "<alt_gr>"})

_SIDE_MAP = {
    "<ctrl_l>": "<ctrl>", "<ctrl_r>": "<ctrl>",
    "<shift_l>": "<shift>", "<shift_r>": "<shift>",
    "<alt_l>": "<alt>", "<alt_r>": "<alt>",
    "<cmd_l>": "<cmd>", "<cmd_r>": "<cmd>",
}


def canonical_key(key: str) -> str:
    """Normaliza uma tecla: minúsculas e variantes esquerda/direita unificadas."""
    k = key.lower() if (key.startswith("<") or len(key) == 1) else key
    return _SIDE_MAP.get(k, k)


def is_modifier(key: str) -> bool:
    return canonical_key(key) in MODIFIERS


# ---- nomes de exibição e aliases aceitos ao digitar/ler atalhos -----------------------

_DISPLAY: dict[str, str] = {
    "<esc>": "Esc", "<enter>": "Enter", "<space>": "Space", "<tab>": "Tab",
    "<backspace>": "Backspace", "<delete>": "Delete", "<insert>": "Insert",
    "<home>": "Home", "<end>": "End", "<page_up>": "Page Up", "<page_down>": "Page Down",
    "<up>": "Up", "<down>": "Down", "<left>": "Left", "<right>": "Right",
    "<caps_lock>": "Caps Lock", "<pause>": "Pause", "<print_screen>": "Print Screen",
    "<scroll_lock>": "Scroll Lock", "<num_lock>": "Num Lock", "<menu>": "Menu",
}
for _n in range(1, 25):
    _DISPLAY[f"<f{_n}>"] = f"F{_n}"

_MODIFIER_DISPLAY = {
    "<ctrl>": "Ctrl", "<alt>": "Alt", "<alt_gr>": "Alt Gr", "<shift>": "Shift", "<cmd>": "Win",
}
MODIFIER_ORDER = ("<ctrl>", "<alt>", "<alt_gr>", "<shift>", "<cmd>")


def _norm(token: str) -> str:
    return token.strip().lower().replace(" ", "").replace("_", "").replace("-", "")


_ALIASES: dict[str, str] = {}
for _k, _v in _DISPLAY.items():
    _ALIASES[_norm(_v)] = _k
_ALIASES.update({
    "escape": "<esc>", "return": "<enter>", "spacebar": "<space>", "bksp": "<backspace>",
    "del": "<delete>", "ins": "<insert>", "pgup": "<page_up>", "pgdown": "<page_down>",
    "pgdn": "<page_down>", "capslock": "<caps_lock>", "break": "<pause>",
    "print": "<print_screen>", "prtsc": "<print_screen>", "scrolllock": "<scroll_lock>",
    "numlock": "<num_lock>", "pageup": "<page_up>", "pagedown": "<page_down>",
    "printscreen": "<print_screen>",
})

_MODIFIER_ALIASES = {
    "ctrl": "<ctrl>", "control": "<ctrl>", "alt": "<alt>", "option": "<alt>",
    "altgr": "<alt_gr>", "shift": "<shift>", "cmd": "<cmd>", "command": "<cmd>",
    "win": "<cmd>", "windows": "<cmd>", "super": "<cmd>", "meta": "<cmd>",
}


def display_modifier(key: str) -> str:
    return _MODIFIER_DISPLAY.get(key, key)


def display_key(key: str) -> str:
    """Nome legível de uma tecla (ex.: ``"<f9>"`` -> ``"F9"``)."""
    k = canonical_key(key)
    if k in _MODIFIER_DISPLAY:
        return _MODIFIER_DISPLAY[k]
    if k in _DISPLAY:
        return _DISPLAY[k]
    if k.startswith("<vk:"):
        return "VK" + k[4:-1]
    return k.upper() if len(k) == 1 else k


def parse_modifier(token: str) -> str | None:
    return _MODIFIER_ALIASES.get(_norm(token))


def parse_main_key(token: str) -> str | None:
    """Converte o texto de uma tecla principal em chave neutra, ou None se desconhecida."""
    t = _norm(token)
    if not t:
        return None
    if t in _ALIASES:
        return _ALIASES[t]
    if len(token.strip()) == 1:
        return token.strip().lower()
    return None
