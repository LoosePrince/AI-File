import os
import sys
from file_organizer import FileOrganizer
from config import API_KEY
from PyQt5.QtWidgets import QApplication
from gui_qt import FileOrganizerGUI

def main():
    try:
        app = QApplication(sys.argv)
        window = FileOrganizerGUI()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"启动GUI失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
