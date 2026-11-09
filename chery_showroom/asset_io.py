"""Atomic, content-stable writes for assets shared by concurrent showroom launches."""
import io,os,tempfile
from pathlib import Path
import xml.etree.ElementTree as E

def write_bytes(path,data):
    path=Path(path)
    if path.exists() and path.read_bytes()==data:return
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:stream.write(data)
        os.replace(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)

def save_image(image,path):
    buffer=io.BytesIO();image.save(buffer,format='PNG');write_bytes(path,buffer.getvalue())

def write_xml(root,path):write_bytes(path,E.tostring(root,encoding='utf-8'))
