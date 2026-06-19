"""PyInstaller entry point for the packaged Windows app (CanvasAI.exe)."""

from canvas_ai import desktop

if __name__ == "__main__":
    desktop.run()
