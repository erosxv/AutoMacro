# AutoMacro

Auto Clicker e Gravador/Reprodutor de Macros para **Windows 10/11** e **Linux** (X11; Wayland com limitações).

## Windows: instalador pronto (recomendado)

Baixe **`AutoMacro-Setup.exe`** na página de [Releases](../../releases/latest) e abra. Ele instala só
para o seu usuário (não pede administrador) e cria atalhos. O Windows pode mostrar "O Windows
protegeu seu PC" porque o programa não tem assinatura digital paga: clique em *Mais informações* e
*Executar assim mesmo*. Também há `AutoMacro-windows.zip` (versão portátil, sem instalar).

**Atualização automática:** ao abrir, o programa consulta se há versão nova (dá para desligar em
*Configurações → Atualizações*) e mostra um aviso com o botão **Atualizar agora**. Ele baixa o
instalador, confere o SHA-256, fecha, instala e abre de novo. Nada é instalado sem você clicar, e
só são aceitos downloads de servidores do GitHub.

Cada atualização enviada ao ramo `main` gera sozinha uma versão numerada (`v0.1.N`) no GitHub
Actions, que roda os testes, monta o executável e o instalador e publica.

## Instalação a partir do código-fonte (automática)

Você não precisa instalar bibliotecas manualmente.

| Sistema | Instalar e verificar | Abrir |
|---|---|---|
| Windows | duplo clique em `setup.bat` | duplo clique em `run.bat` |
| Linux | `./setup.sh` | `./run.sh` |

O script cria um ambiente virtual (`.venv`), instala todas as dependências e roda um diagnóstico.
`run.sh` / `run.bat` também chamam o setup sozinhos se o ambiente ainda não existir.

Único pré-requisito: **Python 3.11 ou superior** (no Windows: <https://www.python.org/downloads/>,
marcando "Add python.exe to PATH").

**Linux:** nenhum compilador é necessário (todas as dependências Python vêm prontas). O único
item que pode faltar no sistema são as bibliotecas gráficas do Qt (ex.: `libxcb-cursor0`); se o
diagnóstico apontar isso, o `setup.sh` oferece instalá-las na hora (ou rode
`./setup.sh --install-system-deps`; usa `sudo` e funciona com apt, dnf e pacman).

**Compatibilidade verificada** (resolução de dependências só com pacotes prontos, sem compilar):
Windows x64 e Linux x86_64, com Python 3.11, 3.12 e 3.13. Linux com glibc 2.34 ou mais novo
(Ubuntu 22.04+, Debian 12+, Fedora atual) recebe o PySide6 6.12; distribuições mais antigas
(glibc 2.28+, ex.: Debian 10 / RHEL 8) recebem automaticamente o 6.9. Linux ARM não é alvo.

Para checar o ambiente a qualquer momento: `python -m automacro.doctor` (ou `run.sh --doctor`).

## Estrutura

```
src/automacro/
  main.py            inicialização (instância única, logs, composição)
  models/            eventos, macro, configurações, estados (puros, sem Qt)
  input_handlers/    abstração de entrada: pynput, backend falso (testes), capacidades por SO
  hotkeys/           parser de atalhos e gerenciador com um único listener
  core/              Session (máquina de estados), timing, safety, event bus  — sem Qt
  autoclicker/       motor de cliques
  recorder/          gravador
  player/            reprodutor
  storage/           biblioteca JSON, escrita atômica, migrações, configurações
  ui/                PySide6 (única camada que importa Qt)
  utils/             plataforma, caminhos, logs
tests/               pytest (backend falso + backend real em X11 virtual)
```

Regra de dependência: `ui → core → motores → input_handlers/models`. O `core` nunca importa Qt.

## Onde ficam os dados

Macros, configurações e logs ficam na pasta de dados do usuário (`%APPDATA%\AutoMacro` no Windows,
`~/.local/share/AutoMacro` e `~/.config/AutoMacro` no Linux). Defina `AUTOMACRO_HOME=<pasta>`
para usar uma pasta própria (modo portátil).

## Atalhos padrão (configuráveis)

| Ação | Atalho |
|---|---|
| Iniciar gravação | F6 |
| Finalizar gravação | F7 |
| Iniciar reprodução | F8 |
| Interromper execução | F9 |
| **Parada de emergência** | Ctrl+Shift+F9 |
| Auto Clicker (iniciar/parar) | F4 |
| Pausar/continuar reprodução | Ctrl+F8 |

Segurança: parada de emergência (atalho + botão), failsafe (mouse no canto superior esquerdo),
contagem regressiva, confirmação antes de reproduzir macros importadas, limite de tempo.

## Limitações por sistema

- **Windows:** programas executados como administrador (e a tela do UAC) ignoram entrada simulada
  por um programa comum; execute o AutoMacro como administrador para controlá-los. Alguns jogos com
  anti-cheat bloqueiam entrada simulada.
- **Linux X11:** funcionalidade completa.
- **Linux Wayland:** o sistema isola a entrada entre aplicativos; só janelas via XWayland são
  alcançadas e atalhos globais podem não funcionar. O app mostra o motivo exato na janela. Para
  suporte completo, entre em uma sessão X11 (Xorg) na tela de login.
- **macOS:** não é alvo oficial.

## Desenvolvimento

```bash
.venv/bin/python -m pytest -m "not x11"            # núcleo (backend falso) + teste de fumaça da UI
xvfb-run -a .venv/bin/python -m pytest             # tudo, incluindo o backend real (pynput) em X11 virtual
```

Capturas de tela da interface durante os testes: `AUTOMACRO_SHOTS=pasta pytest tests/test_ui_smoke.py`.

## Gerar executável

`build.sh` (Linux) ou `build.bat` (Windows) geram uma pasta em `dist/AutoMacro/` com PyInstaller
(modo *onedir*, sem UPX, para reduzir falsos positivos de antivírus). Os scripts preparam o ambiente sozinhos
se ainda não existir. É preciso compilar em cada sistema (não há compilação cruzada).

A receita fica em `packaging/automacro.spec`. Ela lista à mão os submódulos do `pynput` porque ele
escolhe o backend por import dinâmico e só importa com servidor gráfico ativo (o que não existe
durante o build). Se o executável abrir mas o diagnóstico (`AutoMacro --doctor`) disser que os
recursos de captura estão indisponíveis, comece por aí.

Antivírus podem sinalizar executáveis de auto clicker não assinados; só a assinatura de código
resolve isso.

## O que foi e o que não foi testado

| Item | Situação |
|---|---|
| Núcleo (estados, temporização, cancelamento, gravação, reprodução, storage, atalhos) | Testes automáticos com backend falso |
| Captura e envio reais de mouse/teclado | Testado em Linux X11 (Xvfb) com o pynput real |
| Interface | Teste de fumaça com Qt offscreen: abas, gravar → salvar → reproduzir, botão de emergência |
| Executável Linux (PyInstaller) | Gerado e aberto; diagnóstico mostra todos os recursos disponíveis |
| **Windows** (execução, atalhos, UAC, DPI, multimonitor, executável) | **Não testado** (sem máquina Windows no ambiente de desenvolvimento); só a resolução de dependências foi verificada |
| **Linux Wayland** | **Não testado**; o app detecta e avisa as limitações |
| Precisão de temporização em hardware real | Medida apenas em Linux virtualizado |
