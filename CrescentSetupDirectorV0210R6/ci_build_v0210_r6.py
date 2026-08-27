from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('ci_build_v0210_r6_chunks.py')), run_name='__main__')
