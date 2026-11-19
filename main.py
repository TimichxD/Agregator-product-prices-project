"""Точка входа приложения «Выгодно»."""

import sys
from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from forms.main_window import MainWindow

BASE_DIR = Path(__file__).resolve().parent


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Выгодно")
    app.setFont(QFont("Segoe UI", 10))

    stylesheet_path = BASE_DIR / "styles" / "premium.qss"
    if stylesheet_path.is_file():
        app.setStyleSheet(stylesheet_path.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
