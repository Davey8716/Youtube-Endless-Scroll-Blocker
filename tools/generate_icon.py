from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "assets" / "app.ico"
    target.parent.mkdir(parents=True, exist_ok=True)

    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#171717"))
    painter.drawRoundedRect(QRectF(20, 20, 216, 216), 32, 32)

    painter.setBrush(QColor("#f4f4f5"))
    painter.drawRoundedRect(QRectF(48, 55, 160, 105), 10, 10)
    painter.setBrush(QColor("#dc2626"))
    triangle = [QPointF(108, 79), QPointF(108, 137), QPointF(158, 108)]
    painter.drawPolygon(triangle)

    painter.setPen(QPen(QColor("#dc2626"), 24, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(58, 202), QPointF(198, 62))
    painter.end()

    if not image.save(str(target), "ICO"):
        raise RuntimeError(f"Could not write {target}")


if __name__ == "__main__":
    main()
