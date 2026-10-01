"""啟動本機 ABS 挑戰勝率決策介面，並開啟預設瀏覽器。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from abs_challenge.web_ui import main  # noqa: E402


if __name__ == "__main__":
    if "--open-browser" not in sys.argv:
        sys.argv.append("--open-browser")
    raise SystemExit(main())
