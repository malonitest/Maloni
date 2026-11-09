"""Prepare/cache exact English demo cues, or import user-supplied PCM WAV files."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
import numpy as np
from .arrival_script import SCRIPT
from .credentials import api_key

CACHE=Path(__file__).with_name('assets')/'arrival_audio_en'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def script_hash():
    return hashlib.sha256(json.dumps(dict(language='en',script=SCRIPT),ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def inspect_wav(path):
    try:
        with wave.open(str(path),'rb') as f:
            if f.getcomptype()!='NONE' or f.getsampwidth()!=2 or f.getnchannels()!=1 or f.getframerate()!=24000:
                raise ValueError('Expected mono 24 kHz 16-bit PCM WAV: '+str(path))
            count=f.getnframes();samples=np.frombuffer(f.readframes(count),dtype='<i2')
            duration=count/f.getframerate()
    except (wave.Error,EOFError,OSError) as exc:raise ValueError('Invalid/missing WAV: '+str(path)) from exc
    if duration<.08 or not len(samples) or np.max(np.abs(samples.astype(float)))<16:
        raise ValueError('Empty/silent audio cue: '+str(path))
    return duration


def validate(directory=CACHE):
    directory=Path(directory)
    try:manifest=json.loads((directory/'manifest.json').read_text())
    except (OSError,ValueError):raise ValueError('English audio is not prepared. Run voice_assets --generate or --import-dir.') from None
    if manifest.get('language')!='en':raise ValueError('Audio cache is not English.')
    if manifest.get('script_sha256')!=script_hash():raise ValueError('Audio cache belongs to an older script.')
    for cue in SCRIPT['cues']:
        item=manifest.get('cues',{}).get(cue['id'],{})
        path=directory/(cue['id']+'.wav')
        duration=inspect_wav(path)
        if digest(path)!=item.get('sha256'):raise ValueError('Audio checksum mismatch: '+cue['id'])
        if duration>cue['end']-cue['start']+.0001:raise ValueError('Audio exceeds its time slot: '+cue['id'])
    return manifest


def fit(source,destination,limit):
    import imageio_ffmpeg
    # Normalize imported/generated audio with ffmpeg; bounded tempo adjustment, never truncate speech.
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    temporary=destination.with_suffix('.normalized.wav')
    subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',str(source),'-ac','1','-ar','24000',
                    '-c:a','pcm_s16le',str(temporary)],check=True,capture_output=True)
    duration=inspect_wav(temporary);factor=max(1.,duration/max(.1,limit-.04))
    if factor>1.25:
        temporary.unlink(missing_ok=True)
        raise ValueError(f'Cue needs {duration:.2f}s but has {limit:.2f}s; record a shorter/faster version (max tempo adjustment 1.25).')
    if factor>1:
        subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',str(temporary),'-af',f'atempo={factor:.8f}',
                        '-ac','1','-ar','24000','-c:a','pcm_s16le',str(destination)],check=True,capture_output=True)
        temporary.unlink()
    else:temporary.replace(destination)
    actual=inspect_wav(destination)
    if actual>limit:raise ValueError('Fitted audio still exceeds slot: '+destination.name)
    return actual,factor


def prepare(directory=CACHE,source_dir=None,generate=False):
    directory=Path(directory)
    key=api_key() if generate else ''
    if generate and not key:raise ValueError('No configured key. Reuse the Buddha key file, set OPENAI_API_KEY, or use --import-dir.')
    directory.mkdir(parents=True,exist_ok=True)
    try:old=validate(directory)
    except ValueError:old=None
    if old and not source_dir:return old
    manifest=dict(language='en',script_sha256=script_hash(),model='gpt-4o-mini-tts' if generate else 'imported',cues={},ai_generated=generate)
    for cue in SCRIPT['cues']:
        destination=directory/(cue['id']+'.wav');source=directory/(cue['id']+'.source.wav')
        if source_dir:
            shutil.copyfile(Path(source_dir)/(cue['id']+'.wav'),source)
            source.with_suffix('.request.sha256').unlink(missing_ok=True)
        elif generate:
            body=dict(model='gpt-4o-mini-tts',voice=cue['voice'],input=cue['en'],response_format='wav',speed=1.12,
                      instructions='Speak English clearly, naturally and briskly as a friendly professional. Read exactly the supplied text without additions.')
            source_key=hashlib.sha256(json.dumps(body,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            fingerprint=source.with_suffix('.request.sha256')
            if not (source.exists() and fingerprint.exists() and fingerprint.read_text()==source_key):
                req=Request('https://api.openai.com/v1/audio/speech',data=json.dumps(body).encode(),headers={
                    'Authorization':'Bearer '+key,'Content-Type':'application/json'})
                try:
                    with urlopen(req,timeout=60) as response:payload=response.read()
                except HTTPError as exc:raise RuntimeError(f'Speech service rejected cue {cue["id"]} (HTTP {exc.code}).') from None
                except (OSError,URLError):raise RuntimeError('Speech service unavailable; cached assets were preserved.') from None
                with tempfile.NamedTemporaryFile(dir=directory,delete=False,suffix='.wav') as f:f.write(payload);temp=Path(f.name)
                temp.replace(source);fingerprint.write_text(source_key)
        else:raise ValueError('Choose --generate or --import-dir.')
        duration,tempo=fit(source,destination,cue['end']-cue['start'])
        manifest['cues'][cue['id']]=dict(file=destination.name,sha256=digest(destination),duration=duration,
                                        voice=cue['voice'] if generate else 'imported',tempo=tempo)
        print(f'{cue["id"]}: {duration:.3f}s / {cue["end"]-cue["start"]:.1f}s',flush=True)
    (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    return validate(directory)


def mix(destination,directory=CACHE):
    validate(directory)
    timeline=np.zeros(int(SCRIPT['duration']*24000),dtype=np.int32)
    for cue in SCRIPT['cues']:
        with wave.open(str(Path(directory)/(cue['id']+'.wav')),'rb') as source:
            samples=np.frombuffer(source.readframes(source.getnframes()),dtype='<i2').astype(np.int32)
        start=round(cue['start']*24000);timeline[start:start+len(samples)]+=samples
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(destination),'wb') as output:
        output.setparams((1,2,24000,0,'NONE','not compressed'))
        output.writeframes(np.clip(timeline,-32768,32767).astype('<i2').tobytes())
    return destination


def main():
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--generate',action='store_true');group.add_argument('--import-dir',type=Path);group.add_argument('--check',action='store_true')
    p.add_argument('--directory',type=Path,default=CACHE);args=p.parse_args()
    try:
        if args.check:validate(args.directory)
        else:prepare(args.directory,args.import_dir,args.generate)
        print('English cue cache verified.')
    except (ValueError,RuntimeError,OSError,subprocess.SubprocessError) as exc:p.exit(1,str(exc)+'\n')
if __name__=='__main__':main()
