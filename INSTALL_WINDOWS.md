# Instalacao no Windows

O projeto agora usa Flet em vez de Kivy para evitar o atrito de dependencias nativas no Windows.

## 1. Confira a versao da venv

```powershell
cd "C:\Users\Citra LTDA\OneDrive\Desktop\CODEX\documents_org_mobile"
.\.venv\Scripts\python.exe --version
```

Flet requer Python 3.10 ou superior.

## 2. Instale as dependencias sem ativar a venv

```powershell
.\.venv\Scripts\python.exe -m pip cache purge
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel --no-cache-dir
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --no-cache-dir
```

## 3. Rode o app

```powershell
.\.venv\Scripts\python.exe main.py
```

## 4. Build Android futuramente

```powershell
.\.venv\Scripts\flet.exe build apk
```
