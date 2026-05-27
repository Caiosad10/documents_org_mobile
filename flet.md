# Flet

Este projeto agora usa Flet como camada visual.

Motivo da troca:

- Kivy apresentou atrito de instalacao no Windows com Python 3.14.
- Flet requer Python 3.10+ e o pacote principal e distribuido como wheel `py3-none-any`.
- Flet tambem possui comando de build para Android (`apk`/`aab`), web e desktop.
- O acesso ao Supabase foi mantido via HTTP direto com `httpx`, evitando SDKs que puxam dependencias nativas como `pyiceberg`.

Comandos principais:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Build Android, em etapa posterior:

```powershell
.\.venv\Scripts\flet.exe build apk
```
