"""TU02: seed a missing default avatar, preserving an existing MEDIA file."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def seed_default_media(media_root):
    source = ROOT / 'static' / 'images' / 'profile_pics' / 'default.jpg'
    target = Path(media_root) / 'profile_pics' / 'default.jpg'
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('xb') as output:
            output.write(source.read_bytes())
    except FileExistsError:
        pass


if __name__ == '__main__':
    seed_default_media(os.environ.get('MEDIA_ROOT', ROOT / 'media'))
