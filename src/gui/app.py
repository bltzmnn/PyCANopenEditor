"""GUI 应用程序入口"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def run_gui() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PyCANopenEditor")

    from .views.main_window import MainWindow
    from .viewmodels.main_window_vm import MainWindowVM

    vm = MainWindowVM()
    window = MainWindow(vm)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
