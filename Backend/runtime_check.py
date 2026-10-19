"""Reject unsupported interpreters before importing dependencies or opening data."""
import struct
import sys


def require_supported_python():
    """The backend requires a Python 3.12+ process with 32-bit pointers."""
    bits = struct.calcsize('P') * 8
    if sys.version_info < (3, 12) or bits != 32:
        raise RuntimeError(
            f'Backend exige Python 3.12 ou superior, 32 bits. '
            f'Encontrado: Python {sys.version.split()[0]}, {bits} bits '
            f'({sys.executable}). Execute Configurar-Cortae.ps1 '
            f'-PythonPath <python.exe de 32 bits> e use Backend/.venv/Scripts/python.exe.'
        )
    return bits


if __name__ == '__main__':
    require_supported_python()
    print(f'Python {sys.version.split()[0]}, 32 bits: {sys.executable}')
