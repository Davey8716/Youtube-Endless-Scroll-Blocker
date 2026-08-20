from __future__ import annotations


TRAY_MENU_STYLESHEET = """
QMenu {
    background-color: #0b1f3a;
    color: #f4f7fb;
    border: 1px solid #294867;
    padding: 6px;
}
QMenu::item {
    padding: 7px 28px 7px 26px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #1d4f7a;
}
QMenu::item:disabled {
    color: #6b7f93;
}
QMenu::item:checked {
    background-color: #163f66;
}
QMenu::indicator {
    width: 12px;
    height: 12px;
    border: 1px solid #8aa4bf;
    border-radius: 2px;
}
QMenu::indicator:checked {
    background-color: #38bdf8;
    border-color: #bae6fd;
}
QMenu::separator {
    height: 1px;
    background-color: #294867;
    margin: 5px 8px;
}
"""
