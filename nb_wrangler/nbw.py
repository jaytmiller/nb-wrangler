from pathlib import Path
import subprocess
import sys


def main():
    script = Path(__file__).with_name("nb-wrangler")
    raise SystemExit(subprocess.call(["bash", str(script), *sys.argv[1:]]))
