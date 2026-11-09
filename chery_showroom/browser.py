"""Open the loopback panel in the host browser, including Windows from WSL."""
import platform
import shutil
import subprocess
import webbrowser
from urllib.parse import urlsplit


def open_panel(url):
    parsed=urlsplit(url)
    if parsed.scheme!='http' or not parsed.port or parsed.netloc!=f'127.0.0.1:{parsed.port}' or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Expected the local showroom panel URL.')
    if 'microsoft' in platform.release().lower():
        powershell=shutil.which('powershell.exe')
        if powershell:
            try:
                # URL is restricted above; no shell or user-controlled PowerShell code.
                result=subprocess.run([powershell,'-NoProfile','-NonInteractive','-Command',
                    "$ErrorActionPreference='Stop'; Start-Process -FilePath '"+url+"'"],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
                if result.returncode==0:return True
            except (OSError,subprocess.TimeoutExpired):pass
        print('Open the panel in your Windows browser: '+url,flush=True)
        return False
    try:
        if webbrowser.open(url):return True
    except webbrowser.Error:pass
    print('Open the panel manually in your browser: '+url,flush=True)
    return False
