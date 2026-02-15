#!/usr/bin/env python3
"""
K3s System Tray Indicator für KDE Plasma
Benötigt: pip install PyQt6
Für SVG: ggf. zusätzlich python3-pyqt6.qtsvg (Debian/Ubuntu)
"""

import os
import sys
import subprocess

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtCore import QTimer, Qt, QByteArray
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor

try:
    from PyQt6.QtSvg import QSvgRenderer
    HAS_SVG = True
except Exception:
    HAS_SVG = False


class K3sTrayIcon(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Logo-Pfad relativ zum Script (assets/k3s.png oder assets/k3s.svg)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.logo_path = os.path.join(base_dir, "k3s-status-tray.svg")  # <-- anpassen (png oder svg)

        # Fallback-Starticon (falls Logo fehlt)
        self.setIcon(QIcon.fromTheme("kubernetes", QIcon.fromTheme("network-server")))

        # Menu erstellen
        self.menu = QMenu()

        # Status Action
        self.status_action = QAction("Status: Checking...", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        # Start Action
        start_action = QAction("Start K3s", self.menu)
        start_action.triggered.connect(self.start_k3s)
        self.menu.addAction(start_action)

        # Stop Action
        stop_action = QAction("Stop K3s", self.menu)
        stop_action.triggered.connect(self.stop_k3s)
        self.menu.addAction(stop_action)

        # Restart Action
        restart_action = QAction("Restart K3s", self.menu)
        restart_action.triggered.connect(self.restart_k3s)
        self.menu.addAction(restart_action)

        self.menu.addSeparator()

        # Quit Action
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(QApplication.quit)
        self.menu.addAction(quit_action)

        self.setContextMenu(self.menu)

        # Timer für Status-Updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)

        self.update_status()
        self.show()

    def get_k3s_status(self):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "k3s"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def load_logo_pixmap(self, path: str, size: int, tint: str | None = None) -> QPixmap:
        """Lädt SVG/PNG. Bei SVG kann optional per `tint` eingefärbt werden (fill/stroke ersetzen)."""
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)

        if not path or not os.path.exists(path):
            return pm

        # SVG
        if path.lower().endswith(".svg"):
            if not HAS_SVG:
                return pm

            try:
                with open(path, "r", encoding="utf-8") as f:
                    svg = f.read()

                if tint:
                    import re

                    # fill/stroke ersetzen – aber "none" in Ruhe lassen
                    svg = re.sub(r'fill="(?!none)[^"]*"', f'fill="{tint}"', svg)
                    svg = re.sub(r"fill='(?!none)[^']*'", f"fill='{tint}'", svg)
                    svg = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{tint}"', svg)
                    svg = re.sub(r"stroke='(?!none)[^']*'", f"stroke='{tint}'", svg)

                    # optional: wenn gar kein fill/stroke existiert, global setzen
                    if 'fill="' not in svg and "fill='" not in svg:
                        svg = svg.replace("<svg", f'<svg fill="{tint}"', 1)

                renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
                painter = QPainter(pm)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(painter)
                painter.end()
                return pm
            except Exception:
                return pm

        # PNG / ICO / etc.
        src = QPixmap(path)
        if src.isNull():
            return pm

        return src.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def create_status_icon(
        self,
        cow_color: str,
        size: int = 22,
        overlay_dot_color: str | None = None,
    ) -> QIcon:
        """Tray-Icon: Kuh-SVG wird eingefärbt; optional Status-Punkt unten rechts."""
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Kuh-Logo (eingefärbt)
        logo_size = int(size * 1.35)
        logo = self.load_logo_pixmap(self.logo_path, logo_size, tint=cow_color)
        x = (size - logo.width()) // 2
        y = (size - logo.height()) // 2
        painter.drawPixmap(x, y, logo)

        painter.end()
        return QIcon(pm)


    def update_status(self):
        status = self.get_k3s_status()

        if status == "active":
            self.status_action.setText("Status: 🟢 Running")
            self.setToolTip("K3s: Running")
            # Kuh grün
            self.setIcon(self.create_status_icon(cow_color="#255BA3"))

        elif status == "inactive":
            self.status_action.setText("Status: 🔴 Stopped")
            self.setToolTip("K3s: Stopped")
            # Kuh grau + roter Punkt
            self.setIcon(self.create_status_icon(cow_color="#000000", overlay_dot_color="#F44336"))

        else:
            self.status_action.setText(f"Status: 🟡 {status}")
            self.setToolTip(f"K3s: {status}")
            # Kuh schwarz (default)
            self.setIcon(self.create_status_icon(cow_color="#000000"))


    def start_k3s(self):
        try:
            subprocess.run(["pkexec", "systemctl", "start", "k3s"], check=True)
            self.showMessage("K3s", "K3s was started", QSystemTrayIcon.MessageIcon.Information)
            self.update_status()
        except subprocess.CalledProcessError:
            self.showMessage("K3s", "Error while starting", QSystemTrayIcon.MessageIcon.Critical)

    def stop_k3s(self):
        try:
            subprocess.run(["pkexec", "systemctl", "stop", "k3s"], check=True)
            self.showMessage("K3s", "K3s was stopped", QSystemTrayIcon.MessageIcon.Information)
            self.update_status()
        except subprocess.CalledProcessError:
            self.showMessage("K3s", "Error while stopping", QSystemTrayIcon.MessageIcon.Critical)

    def restart_k3s(self):
        try:
            subprocess.run(["pkexec", "systemctl", "restart", "k3s"], check=True)
            self.showMessage("K3s", "K3s was restarted", QSystemTrayIcon.MessageIcon.Information)
            self.update_status()
        except subprocess.CalledProcessError:
            self.showMessage("K3s", "Error while restarting", QSystemTrayIcon.MessageIcon.Critical)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    tray = K3sTrayIcon()
    sys.exit(app.exec())
