#!/usr/bin/env python3
"""Wrap the generic, owner-paired Windows helper in a per-user NSIS EXE."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


def nsis_quote(value):
    return str(value).replace('$', '$$').replace('"', '$\\"')


def build(archive, output):
    if not shutil.which('makensis'):
        raise RuntimeError('makensis is required to build the Windows EXE.')
    with tempfile.TemporaryDirectory(prefix='neptune-win-exe-') as temp:
        folder = Path(temp)
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if any(not name.startswith('Neptune Trainer/') or '..' in Path(name).parts for name in names):
                raise ValueError('Unexpected Windows package path.')
            if any(name.endswith('trainer-connection.json') for name in names):
                raise ValueError('The EXE must be generic; browser pairing adds the connection after installation.')
            z.extractall(folder)
        package = folder / 'Neptune Trainer'
        assert (package / 'app/neptune_trainer_entry.py').is_file()
        assert (package / 'app/Neptune.ico').is_file()
        lines = [
            'Unicode True',
            'Name "Neptune Training Helper"',
            'OutFile "' + nsis_quote(output.resolve()) + '"',
            'InstallDir "$LOCALAPPDATA\\Neptune Trainer"',
            'RequestExecutionLevel user',
            'SetCompressor /SOLID lzma',
            'ShowInstDetails show',
            'Icon "' + nsis_quote(package / 'app/Neptune.ico') + '"',
            'Page instfiles',
            'Section "Install"',
            '  InitPluginsDir',
        ]
        for path in sorted(package.rglob('*')):
            if not path.is_file(): continue
            relative = path.relative_to(package)
            target = '$PLUGINSDIR\\Neptune Trainer'
            if len(relative.parts) > 1: target += '\\' + '\\'.join(relative.parts[:-1])
            lines += ['  SetOutPath "' + target + '"',
                      '  File "' + nsis_quote(path) + '"']
        lines += [
            '  DetailPrint "Installing for this Windows user. Administrator rights are not required."',
            '  nsExec::ExecToLog \'"$SYSDIR\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$PLUGINSDIR\\Neptune Trainer\\install-neptune-trainer.ps1"\'',
            '  Pop $0',
            '  StrCmp $0 "0" done',
            '  MessageBox MB_ICONSTOP "Neptune setup could not finish. Check the details above; no training was submitted. Exit code: $0"',
            '  Abort',
            'done:',
            '  DetailPrint "Neptune Training Helper is installed. Open it from the Desktop or Start menu."',
            'SectionEnd',
        ]
        script = folder / 'setup.nsi'
        script.write_text('\n'.join(lines) + '\n')
        subprocess.run(['makensis', '-V2', str(script)], check=True)
    if output.stat().st_size < 100_000 or output.read_bytes()[:2] != b'MZ':
        raise ValueError('The Windows setup executable is invalid.')
    print(output, output.stat().st_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.archive, args.output)
