# FlowRemote Windows Demo

Download:

- [FlowRemoteDemo.exe](dist/FlowRemoteDemo.exe)
- [SHA-256 checksum](dist/FlowRemoteDemo.exe.sha256)

Version: `0.5.0`

## Run

1. Download `FlowRemoteDemo.exe`.
2. Double-click it.
3. Wait for the local services to start.
4. The default browser opens the `/demo` page.
5. Use **Create account** for registration and AI-RPA onboarding, or click
   **Quick demo login**.

Quick demo account:

```text
Email: alex.morgan@example.com
Password: 123456
```

Runtime data is stored outside the executable:

```text
%LOCALAPPDATA%\FlowRemoteDemo
```

The application uses only a loopback HTTP server. No Python installation is
required.

## Verify the download

PowerShell:

```powershell
Get-FileHash .\FlowRemoteDemo.exe -Algorithm SHA256
```

Expected:

```text
51FC56930D7DEDB7D4F3DC37BDEBF5336E52FFAE6A3452FBB0CE3FD64CA83879
```

## Compatibility

Expected to run on Windows 10/11 x64 with a modern default browser. The file is
not code-signed, so Windows SmartScreen may show an unknown publisher warning.

## Rebuild

```powershell
uv sync
powershell -ExecutionPolicy Bypass -File scripts\build_demo_exe.ps1
```

The executable includes FastAPI, Uvicorn, SQLite support, templates, static
assets, migrations, the local launcher and demonstration data generation.
