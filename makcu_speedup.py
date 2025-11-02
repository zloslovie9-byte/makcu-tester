# test_makcu.py

import sys
import os
import time
import threading
import webbrowser
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTextEdit, QPushButton, QLabel, QFrame, QScrollArea,
                             QMessageBox, QFileDialog, QDialog)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QPalette, QColor
import serial.tools.list_ports

# Добавляем путь к модулям
sys.path.append(os.path.dirname(__file__))

try:
    from makcu import create_controller, MouseButton

    MAKCU_AVAILABLE = True
except ImportError:
    MAKCU_AVAILABLE = False


    # Создаем заглушку для MouseButton
    class MouseButton:
        LEFT = 1
        RIGHT = 2
        MIDDLE = 4


    print("⚠️ Модуль makcu не найден, используется эмуляция")


class ClickTestWindow(QMainWindow):
    def __init__(self, makcu_controller, parent=None):
        super().__init__(parent)
        self.makcu = makcu_controller
        self.main_window = parent  # Сохраняем ссылку на главное окно
        self.current_language = "RU"
        self.autoclick_active = False
        self.click_count = 0
        self.manual_clicks = 0
        self.init_ui()

        # Таймер для отслеживания кликов MAKCU
        self.click_monitor_timer = QTimer()
        self.click_monitor_timer.timeout.connect(self.check_makcu_clicks)
        self.click_monitor_timer.start(50)  # Проверяем каждые 50ms
        self.last_button_mask = 0

    def set_language(self, language):
        """Установка языка из главного окна"""
        self.current_language = language
        self.update_ui_texts()

    def init_ui(self):
        self.setWindowTitle("Тест кликов MAKCU / MAKCU Click Test")
        self.setFixedSize(600, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        self.title_label = QLabel("🖱️ Тестирование кликов / Click Testing")
        self.title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 18px;
                font-weight: bold;
                font-family: 'Segoe UI';
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 8px;
                border: 2px solid #3498db;
            }
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # Область для тестовой кнопки
        self.test_button_area = QLabel()
        self.test_button_area.setFixedSize(200, 200)
        self.test_button_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.test_button_area.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                border-radius: 100px;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #2980b9;
            }
        """)
        self.test_button_area.mousePressEvent = self.on_circle_click
        self.update_button_text()

        # Центрируем кнопку
        button_container = QWidget()
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.test_button_area)
        button_layout.addStretch()
        button_container.setLayout(button_layout)
        layout.addWidget(button_container)

        # Информация о button_mask
        mask_frame = QFrame()
        mask_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        mask_layout = QVBoxLayout()

        self.mask_info_label = QLabel()
        self.mask_info_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 14px;
                font-family: 'Consolas', 'Monospace';
                font-weight: bold;
            }
        """)
        self.mask_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mask_layout.addWidget(self.mask_info_label)

        # Детальная информация о кнопках
        self.detail_info_label = QLabel()
        self.detail_info_label.setStyleSheet("""
            QLabel {
                color: #bdc3c7;
                font-size: 12px;
                font-family: 'Consolas', 'Monospace';
            }
        """)
        self.detail_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mask_layout.addWidget(self.detail_info_label)

        mask_frame.setLayout(mask_layout)
        layout.addWidget(mask_frame)

        # Счетчики кликов
        clicks_layout = QHBoxLayout()

        # Счетчик автокликов
        self.click_counter_label = QLabel()
        self.click_counter_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 16px;
                font-weight: bold;
                font-family: 'Segoe UI';
                background-color: #ecf0f1;
                padding: 10px;
                border-radius: 6px;
                border: 2px solid #3498db;
            }
        """)
        self.click_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_click_counter()
        clicks_layout.addWidget(self.click_counter_label)

        # Счетчик ручных кликов
        self.manual_click_counter_label = QLabel()
        self.manual_click_counter_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 16px;
                font-weight: bold;
                font-family: 'Segoe UI';
                background-color: #d5dbdb;
                padding: 10px;
                border-radius: 6px;
                border: 2px solid #7f8c8d;
            }
        """)
        self.manual_click_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_manual_click_counter()
        clicks_layout.addWidget(self.manual_click_counter_label)

        layout.addLayout(clicks_layout)

        # Панель управления
        controls_frame = QFrame()
        controls_layout = QHBoxLayout()

        # Кнопка автокликера
        self.autoclick_btn = QPushButton("▶️ Автоклик 5 раз / Autoclick 5 times")
        self.autoclick_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.autoclick_btn.clicked.connect(self.start_autoclick)
        controls_layout.addWidget(self.autoclick_btn)

        # Кнопка сброса счетчика
        self.reset_btn = QPushButton("🔄 Сброс / Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_counter)
        controls_layout.addWidget(self.reset_btn)

        # Кнопка закрытия
        self.close_btn = QPushButton("❌ Закрыть / Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        controls_layout.addWidget(self.close_btn)

        controls_frame.setLayout(controls_layout)
        layout.addWidget(controls_frame)

        central_widget.setLayout(layout)

        # Таймер для обновления button_mask
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_mask)
        self.update_timer.start(50)

        self.update_button_mask()

    def update_ui_texts(self):
        """Обновление текстов интерфейса в зависимости от языка"""
        if self.current_language == "RU":
            self.setWindowTitle("Тест кликов MAKCU")
            self.title_label.setText("🖱️ Тестирование кликов")
            self.autoclick_btn.setText("▶️ Автоклик 5 раз")
            self.reset_btn.setText("🔄 Сброс")
            self.close_btn.setText("❌ Закрыть")
            self.update_button_text()
            self.update_click_counter()
            self.update_manual_click_counter()
        else:
            self.setWindowTitle("MAKCU Click Test")
            self.title_label.setText("🖱️ Click Testing")
            self.autoclick_btn.setText("▶️ Autoclick 5 times")
            self.reset_btn.setText("🔄 Reset")
            self.close_btn.setText("❌ Close")
            self.update_button_text()
            self.update_click_counter()
            self.update_manual_click_counter()

    def check_makcu_clicks(self):
        """Отслеживание кликов MAKCU и визуальная обратная связь"""
        try:
            if self.makcu:
                button_mask = self.makcu.get_button_mask()

                # Определяем ЛКМ (бит 0) и ПКМ (бит 1)
                left_pressed = (button_mask & (1 << 0)) != 0
                left_was_pressed = (self.last_button_mask & (1 << 0)) != 0

                right_pressed = (button_mask & (1 << 1)) != 0
                right_was_pressed = (self.last_button_mask & (1 << 1)) != 0

                # Если ЛКМ только что нажалась - показываем визуальную обратную связь
                if left_pressed and not left_was_pressed:
                    self.highlight_circle("left")
                    QTimer.singleShot(150, self.normal_circle)

                    # Если автокликер активен - считаем клик
                    if self.autoclick_active:
                        self.click_count += 1
                        self.update_click_counter()
                        if self.current_language == "RU":
                            print(f"Автоклик {self.click_count}/5")
                        else:
                            print(f"Autoclick {self.click_count}/5")

                # Если ПКМ только что нажалась - показываем визуальную обратную связь
                if right_pressed and not right_was_pressed:
                    self.highlight_circle("right")
                    QTimer.singleShot(150, self.normal_circle)

                    if self.current_language == "RU":
                        print(f"Правый клик MAKCU!")
                    else:
                        print(f"Right click MAKCU!")

                self.last_button_mask = button_mask

        except Exception as e:
            pass  # Игнорируем ошибки в мониторинге

    def start_autoclick(self):
        """Автокликер без многопоточности - используем только QTimer"""
        if self.autoclick_active:
            return

        if self.current_language == "RU":
            QMessageBox.information(self, "Инструкция",
                                    "Автокликер запущен!\n\n"
                                    "1. Нажмите ОК\n"
                                    "2. MAKCU сделает 5 кликов\n"
                                    "3. Кружок будет мигать при каждом клике\n\n"
                                    )
        else:
            QMessageBox.information(self, "Instruction",
                                    "Autoclicker started!\n\n"
                                    "1. Move cursor to the circle\n"
                                    "2. MAKCU will make 5 clicks\n"
                                    "3. Circle will flash on each click\n\n"
                                    "Make sure cursor is over the circle!")

        self.autoclick_active = True
        self.autoclick_btn.setEnabled(False)

        if self.current_language == "RU":
            self.autoclick_btn.setText("⏹️ Выполняется...")
        else:
            self.autoclick_btn.setText("⏹️ Running...")

        # Сбрасываем счетчик для нового запуска
        self.click_count = 0
        self.autoclick_remaining = 5
        self.update_click_counter()

        # Запускаем первый клик через QTimer
        QTimer.singleShot(500, self.perform_autoclick)

    def perform_autoclick(self):
        """Выполнение одного клика автокликера"""
        if not self.autoclick_active or self.autoclick_remaining <= 0:
            self.finish_autoclick()
            return

        try:
            # Левый клик через MAKCU
            self.makcu.click(MouseButton.LEFT)

            # Увеличиваем счетчик
            self.click_count += 1
            self.autoclick_remaining -= 1
            self.update_click_counter()

            # Визуальная обратная связь
            self.highlight_circle("left")
            QTimer.singleShot(150, self.normal_circle)

            if self.current_language == "RU":
                print(f"Автоклик {self.click_count}/5")
            else:
                print(f"Autoclick {self.click_count}/5")

            # Запускаем следующий клик через 300ms
            if self.autoclick_remaining > 0:
                QTimer.singleShot(300, self.perform_autoclick)
            else:
                # Если это был последний клик, завершаем
                QTimer.singleShot(300, self.finish_autoclick)

        except Exception as e:
            print(f"Autoclick error: {e}")
            self.finish_autoclick()

    def highlight_circle(self, button_type="left"):
        """Подсветка кружка при клике"""
        if button_type == "left":
            # Зеленый для левого клика
            self.test_button_area.setStyleSheet("""
                QLabel {
                    background-color: #2ecc71;
                    border-radius: 100px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    border: 4px solid #27ae60;
                }
            """)
        else:
            # Фиолетовый для правого клика
            self.test_button_area.setStyleSheet("""
                QLabel {
                    background-color: #9b59b6;
                    border-radius: 100px;
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    border: 4px solid #8e44ad;
                }
            """)

    def normal_circle(self):
        """Нормальный вид кружка"""
        self.test_button_area.setStyleSheet("""
            QLabel {
                background-color: #3498db;
                border-radius: 100px;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: 4px solid #2980b9;
            }
        """)

    def on_circle_click(self, event):
        """Обработчик ручного клика по кружку"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.manual_clicks += 1
            self.update_manual_click_counter()

            # Визуальная обратная связь
            self.highlight_circle("left")
            QTimer.singleShot(150, self.normal_circle)

            if self.current_language == "RU":
                print(f"Ручной клик по кружку! Всего: {self.manual_clicks}")
            else:
                print(f"Manual click on circle! Total: {self.manual_clicks}")

        elif event.button() == Qt.MouseButton.RightButton:
            # Визуальная обратная связь для правого клика
            self.highlight_circle("right")
            QTimer.singleShot(150, self.normal_circle)

            if self.current_language == "RU":
                print(f"Правый клик по кружку!")
            else:
                print(f"Right click on circle!")

    def update_button_text(self):
        """Обновление текста на тестовой кнопке"""
        if self.current_language == "RU":
            self.test_button_area.setText("Тестовая кнопка\n(Кликните для теста)")
        else:
            self.test_button_area.setText("Test Button\n(Click to test)")

    def update_click_counter(self):
        """Обновление счетчика автокликов"""
        if self.current_language == "RU":
            self.click_counter_label.setText(f"🎯 Автокликов: {self.click_count}/5")
        else:
            self.click_counter_label.setText(f"🎯 Autoclicks: {self.click_count}/5")

    def update_manual_click_counter(self):
        """Обновление счетчика ручных кликов"""
        if self.current_language == "RU":
            self.manual_click_counter_label.setText(f"🖱️ Ручные клики: {self.manual_clicks}")
        else:
            self.manual_click_counter_label.setText(f"🖱️ Manual clicks: {self.manual_clicks}")

    def finish_autoclick(self):
        """Завершение автоклика"""
        self.autoclick_active = False
        self.autoclick_btn.setEnabled(True)

        if self.current_language == "RU":
            self.autoclick_btn.setText("▶️ Автоклик 5 раз")
            QMessageBox.information(self, "Готово", f"Автоклик завершен!\nСделано кликов: {self.click_count}/5")
        else:
            self.autoclick_btn.setText("▶️ Autoclick 5 times")
            QMessageBox.information(self, "Done", f"Autoclick completed!\nClicks made: {self.click_count}/5")

    def reset_counter(self):
        """Сброс счетчиков"""
        self.click_count = 0
        self.manual_clicks = 0
        self.update_click_counter()
        self.update_manual_click_counter()

        if self.current_language == "RU":
            print("Счетчики сброшены")
        else:
            print("Counters reset")

    def update_button_mask(self):
        """Обновление информации о button_mask"""
        try:
            if self.makcu:
                button_mask = self.makcu.get_button_mask()

                # Декодируем битовую маску
                left_pressed = (button_mask & (1 << 0)) != 0
                right_pressed = (button_mask & (1 << 1)) != 0
                middle_pressed = (button_mask & (1 << 2)) != 0

                if self.current_language == "RU":
                    status_text = f"button_mask: {button_mask:08b} (dec: {button_mask})"
                    detail_text = f"ЛКМ: {'НАЖАТА' if left_pressed else 'отпущена'} | ПКМ: {'НАЖАТА' if right_pressed else 'отпущена'}"
                else:
                    status_text = f"button_mask: {button_mask:08b} (dec: {button_mask})"
                    detail_text = f"Left: {'PRESSED' if left_pressed else 'released'} | Right: {'PRESSED' if right_pressed else 'released'}"

                self.mask_info_label.setText(status_text)
                self.detail_info_label.setText(detail_text)

        except Exception as e:
            pass

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        try:
            self.autoclick_active = False
            self.update_timer.stop()
            self.click_monitor_timer.stop()
        except:
            pass
        event.accept()


class LogSignal(QObject):
    new_log = pyqtSignal(str, str)  # message, type


class MAKCUTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.makcu = None
        self.test_running = False
        self.log_signal = LogSignal()
        self.log_signal.new_log.connect(self.add_log)
        self.current_language = "RU"  # RU - русский, EN - английский
        self.current_speed = "Unknown"
        self.connection_type = "not_connected"  # "standard", "4mbps", "not_connected"
        self.click_test_window = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MAKCU Diagnostic Tool / Диагностика MAKCU")
        self.setFixedSize(1000, 750)

        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Основной layout
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Заголовок и переключатель языка
        header_layout = QHBoxLayout()

        title = QLabel("🔧 ДИАГНОСТИКА MAKCU / MAKCU DIAGNOSTICS")
        title.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 20px;
                font-weight: bold;
                font-family: 'Segoe UI';
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 8px;
                border: 2px solid #3498db;
            }
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        # Кнопка переключения языка
        self.lang_btn = QPushButton("EN/RU")
        self.lang_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.lang_btn.clicked.connect(self.toggle_language)
        header_layout.addWidget(self.lang_btn)

        layout.addLayout(header_layout)

        # Панель статуса
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #34495e;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        status_layout = QHBoxLayout()

        self.status_label = QLabel("🔍 Готов к диагностике / Ready for diagnostics")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
        """)

        self.connection_status = QLabel("MAKCU: ❓ Не проверено / Not checked")
        self.connection_status.setStyleSheet("""
            QLabel {
                color: #f39c12;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Segoe UI';
                background-color: rgba(243, 156, 18, 0.2);
                padding: 5px 10px;
                border-radius: 5px;
            }
        """)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.connection_status)
        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)

        # Панель основных кнопок
        main_buttons_frame = QFrame()
        main_buttons_layout = QHBoxLayout()

        # Кнопка проверки портов
        self.scan_ports_btn = QPushButton("🔍 Сканировать порты / Scan Ports")
        self.scan_ports_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.scan_ports_btn.clicked.connect(self.scan_ports)
        main_buttons_layout.addWidget(self.scan_ports_btn)

        # Кнопка стандартного подключения
        self.standard_connect_btn = QPushButton("🔌 Стандартное подключение / Standard Connect")
        self.standard_connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.standard_connect_btn.clicked.connect(self.standard_connect)
        main_buttons_layout.addWidget(self.standard_connect_btn)

        # Кнопка теста скорости
        self.speed_test_btn = QPushButton("⚡ Тест скорости / Speed Test")
        self.speed_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #ba4a00;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.speed_test_btn.clicked.connect(self.speed_test)
        main_buttons_layout.addWidget(self.speed_test_btn)

        main_buttons_frame.setLayout(main_buttons_layout)
        layout.addWidget(main_buttons_frame)

        # Панель тестов
        test_buttons_frame = QFrame()
        test_buttons_layout = QHBoxLayout()

        # Кнопка теста движения
        self.test_move_btn = QPushButton("🎯 Тест движения / Movement Test")
        self.test_move_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.test_move_btn.clicked.connect(self.test_movement)
        self.test_move_btn.setEnabled(False)
        test_buttons_layout.addWidget(self.test_move_btn)

        # Кнопка теста кликов
        self.test_click_btn = QPushButton("🖱️ Тест кликов / Click Test")
        self.test_click_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
        """)
        self.test_click_btn.clicked.connect(self.test_clicks)
        self.test_click_btn.setEnabled(False)
        test_buttons_layout.addWidget(self.test_click_btn)

        # Кнопка отключения
        self.disconnect_btn = QPushButton("🔌 Отключить / Disconnect")
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #636e72;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.disconnect_btn.clicked.connect(self.disconnect_makcu)
        self.disconnect_btn.setEnabled(False)
        test_buttons_layout.addWidget(self.disconnect_btn)

        test_buttons_frame.setLayout(test_buttons_layout)
        layout.addWidget(test_buttons_frame)

        # Панель информации о скорости
        speed_info_frame = QFrame()
        speed_info_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        speed_layout = QHBoxLayout()

        self.speed_info_label = QLabel("📊 Скорость: Не подключено / Speed: Not connected")
        self.speed_info_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 12px;
                font-family: 'Segoe UI';
                font-weight: bold;
            }
        """)
        speed_layout.addWidget(self.speed_info_label)

        # Добавляем индикатор типа подключения
        self.connection_type_label = QLabel("🔌 Тип: Не подключено / Type: Not connected")
        self.connection_type_label.setStyleSheet("""
            QLabel {
                color: #ecf0f1;
                font-size: 12px;
                font-family: 'Segoe UI';
                font-weight: bold;
                background-color: #7f8c8d;
                padding: 3px 8px;
                border-radius: 4px;
            }
        """)
        speed_layout.addWidget(self.connection_type_label)

        speed_info_frame.setLayout(speed_layout)
        layout.addWidget(speed_info_frame)

        # Область логов
        log_label = QLabel("📋 Логи диагностики / Diagnostic Logs:")
        log_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Segoe UI';
            }
        """)
        layout.addWidget(log_label)

        # Текстовое поле для логов
        self.log_text = QTextEdit()
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Consolas', 'Monospace';
                font-size: 11px;
                border: 2px solid #34495e;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Панель управления логами и доната
        bottom_controls_frame = QFrame()
        bottom_controls_layout = QHBoxLayout()

        # Левая часть - управление логами
        log_controls_layout = QHBoxLayout()

        # Кнопка очистки логов
        self.clear_logs_btn = QPushButton("🗑️ Очистить логи / Clear Logs")
        self.clear_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        log_controls_layout.addWidget(self.clear_logs_btn)

        # Кнопка сохранения логов
        self.save_logs_btn = QPushButton("💾 Сохранить логи / Save Logs")
        self.save_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.save_logs_btn.clicked.connect(self.save_logs)
        log_controls_layout.addWidget(self.save_logs_btn)

        log_controls_layout.addStretch()

        # Правая часть - донат и автопрокрутка
        right_controls_layout = QHBoxLayout()

        # Кнопка благодарности (донат)
        self.donate_btn = QPushButton("❤️ Поддержать проект / Support Project")
        self.donate_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ee5a52;
            }
        """)
        self.donate_btn.clicked.connect(self.open_donate)
        right_controls_layout.addWidget(self.donate_btn)

        # Статус автопрокрутки
        self.auto_scroll = True
        self.auto_scroll_btn = QPushButton("📜 Автопрокрутка: ВКЛ / Auto-scroll: ON")
        self.auto_scroll_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.auto_scroll_btn.clicked.connect(self.toggle_auto_scroll)
        right_controls_layout.addWidget(self.auto_scroll_btn)

        # Объединяем левую и правую части
        bottom_controls_layout.addLayout(log_controls_layout)
        bottom_controls_layout.addStretch()
        bottom_controls_layout.addLayout(right_controls_layout)

        bottom_controls_frame.setLayout(bottom_controls_layout)
        layout.addWidget(bottom_controls_frame)

        central_widget.setLayout(layout)

        # Таймер для автообновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)

        # Начальное сканирование портов
        self.scan_ports()

    def toggle_language(self):
        """Переключение языка интерфейса"""
        if self.current_language == "RU":
            self.current_language = "EN"
        else:
            self.current_language = "RU"

        self.update_ui_texts()

        # Обновляем язык в окне тестирования кликов, если оно открыто
        if self.click_test_window and self.click_test_window.isVisible():
            self.click_test_window.set_language(self.current_language)

    def update_ui_texts(self):
        """Обновление текстов интерфейса в зависимости от языка"""
        if self.current_language == "RU":
            self.setWindowTitle("Диагностика MAKCU")
            self.status_label.setText("🔍 Готов к диагностике")
            self.connection_status.setText("MAKCU: ❓ Не проверено")
            self.scan_ports_btn.setText("🔍 Сканировать порты")
            self.standard_connect_btn.setText("🔌 Стандартное подключение")
            self.speed_test_btn.setText("⚡ Тест скорости")
            self.test_move_btn.setText("🎯 Тест движения")
            self.test_click_btn.setText("🖱️ Тест кликов")
            self.disconnect_btn.setText("🔌 Отключить")
            self.update_speed_display()
            self.clear_logs_btn.setText("🗑️ Очистить логи")
            self.save_logs_btn.setText("💾 Сохранить логи")
            self.donate_btn.setText("❤️ Поддержать проект")
            if self.auto_scroll:
                self.auto_scroll_btn.setText("📜 Автопрокрутка: ВКЛ")
            else:
                self.auto_scroll_btn.setText("📜 Автопрокрутка: ВЫКЛ")
        else:
            self.setWindowTitle("MAKCU Diagnostic Tool")
            self.status_label.setText("🔍 Ready for diagnostics")
            self.connection_status.setText("MAKCU: ❓ Not checked")
            self.scan_ports_btn.setText("🔍 Scan Ports")
            self.standard_connect_btn.setText("🔌 Standard Connect")
            self.speed_test_btn.setText("⚡ Speed Test")
            self.test_move_btn.setText("🎯 Movement Test")
            self.test_click_btn.setText("🖱️ Click Test")
            self.disconnect_btn.setText("🔌 Disconnect")
            self.update_speed_display()
            self.clear_logs_btn.setText("🗑️ Clear Logs")
            self.save_logs_btn.setText("💾 Save Logs")
            self.donate_btn.setText("❤️ Support Project")
            if self.auto_scroll:
                self.auto_scroll_btn.setText("📜 Auto-scroll: ON")
            else:
                self.auto_scroll_btn.setText("📜 Auto-scroll: OFF")

    def update_speed_display(self):
        """Обновление отображения скорости и типа подключения"""
        if self.current_language == "RU":
            if self.connection_type == "standard":
                self.speed_info_label.setText("📊 Скорость: Автоматическая (4Mbps) ⚡")
                self.connection_type_label.setText("🔌 Тип: Автоматический")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #27ae60;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)
            elif self.connection_type == "4mbps":
                self.speed_info_label.setText("📊 Скорость: 4 Mbps (высокая) ⚡")
                self.connection_type_label.setText("🔌 Тип: Высокоскоростной")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #e67e22;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)
            else:
                self.speed_info_label.setText("📊 Скорость: Не подключено")
                self.connection_type_label.setText("🔌 Тип: Не подключено")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #7f8c8d;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)
        else:
            # English version
            if self.connection_type == "standard":
                self.speed_info_label.setText("📊 Speed: Automatic (4Mbps) ⚡")
                self.connection_type_label.setText("🔌 Type: Automatic")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #27ae60;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)
            elif self.connection_type == "4mbps":
                self.speed_info_label.setText("📊 Speed: 4 Mbps (high) ⚡")
                self.connection_type_label.setText("🔌 Type: High-speed")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #e67e22;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)
            else:
                self.speed_info_label.setText("📊 Speed: Not connected")
                self.connection_type_label.setText("🔌 Type: Not connected")
                self.connection_type_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 12px;
                        font-weight: bold;
                        background-color: #7f8c8d;
                        padding: 3px 8px;
                        border-radius: 4px;
                    }
                """)

    def add_log(self, message, log_type="INFO"):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        if log_type == "ERROR":
            color = "#ff4444"
            prefix = "❌ ОШИБКА / ERROR"
        elif log_type == "SUCCESS":
            color = "#00ff00"
            prefix = "✅ УСПЕХ / SUCCESS"
        elif log_type == "WARNING":
            color = "#ffaa00"
            prefix = "⚠️ ПРЕДУПРЕЖДЕНИЕ / WARNING"
        else:
            color = "#3498db"
            prefix = "ℹ️ ИНФО / INFO"

        log_entry = f'<font color="{color}">[{timestamp}] {prefix}: {message}</font><br>'

        # Сохраняем позицию скролла
        scrollbar = self.log_text.verticalScrollBar()
        was_at_bottom = scrollbar.value() == scrollbar.maximum()

        # Добавляем текст
        self.log_text.append(log_entry)

        # Автопрокрутка если была внизу
        if was_at_bottom and self.auto_scroll:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def log_info(self, message):
        self.log_signal.new_log.emit(message, "INFO")

    def log_error(self, message):
        self.log_signal.new_log.emit(message, "ERROR")

    def log_success(self, message):
        self.log_signal.new_log.emit(message, "SUCCESS")

    def log_warning(self, message):
        self.log_signal.new_log.emit(message, "WARNING")

    def scan_ports(self):
        """Сканирование COM-портов"""
        if self.current_language == "RU":
            self.log_info("Сканирование COM-портов...")
        else:
            self.log_info("Scanning COM ports...")

        try:
            ports = list(serial.tools.list_ports.comports())
            makcu_ports = []

            for port in ports:
                port_info = f"{port.device} - {port.description}"
                if self.current_language == "RU":
                    self.log_info(f"Найден порт: {port_info}")
                else:
                    self.log_info(f"Found port: {port_info}")

                # Проверяем признаки MAKCU
                if any(keyword in port.description.upper() for keyword in
                       ['MAKCU', 'CH340', 'CH341', 'CH343', 'USB-SERIAL']):
                    makcu_ports.append(port)
                    if self.current_language == "RU":
                        self.log_success(f"Возможный MAKCU: {port.device} - {port.description}")
                    else:
                        self.log_success(f"Possible MAKCU: {port.device} - {port.description}")

            if not makcu_ports:
                if self.current_language == "RU":
                    self.log_warning("MAKCU не обнаружен на COM-портах")
                    self.connection_status.setText("MAKCU: ❌ Не найден")
                else:
                    self.log_warning("MAKCU not found on COM ports")
                    self.connection_status.setText("MAKCU: ❌ Not found")
            else:
                if self.current_language == "RU":
                    self.connection_status.setText(f"MAKCU: 🔍 Найдено {len(makcu_ports)} порт(ов)")
                else:
                    self.connection_status.setText(f"MAKCU: 🔍 Found {len(makcu_ports)} port(s)")

        except Exception as e:
            if self.current_language == "RU":
                self.log_error(f"Ошибка сканирования портов: {e}")
            else:
                self.log_error(f"Port scanning error: {e}")

    def standard_connect(self):
        """Стандартное подключение"""
        if not MAKCU_AVAILABLE:
            if self.current_language == "RU":
                self.log_error("Модуль makcu не доступен")
            else:
                self.log_error("makcu module not available")
            return

        if self.current_language == "RU":
            self.log_info("Стандартное подключение к MAKCU...")
        else:
            self.log_info("Standard connection to MAKCU...")

        def connect_thread():
            try:
                # Сначала отключаем предыдущее подключение если есть
                if self.makcu:
                    try:
                        self.makcu.disconnect()
                        time.sleep(1)
                    except:
                        pass

                # Подключаемся через MAKCU библиотеку (без параметра baudrate)
                self.makcu = create_controller(debug=True, auto_reconnect=True)
                device_info = self.makcu.get_device_info()

                # Определяем скорость на основе логов библиотеки
                # Библиотека автоматически переключается на 4Mbps
                self.current_speed = "4Mbps"
                self.connection_type = "standard"

                if self.current_language == "RU":
                    self.log_success("✅ Успешное подключение!")
                    self.log_success(f"Информация об устройстве: {device_info}")
                    self.log_success("⚡ Библиотека автоматически установила скорость 4Mbps")
                else:
                    self.log_success("✅ Successful connection!")
                    self.log_success(f"Device info: {device_info}")
                    self.log_success("⚡ Library automatically set speed to 4Mbps")

                # Обновляем UI в основном потоке
                self.update_connection_ui()

            except Exception as e:
                if self.current_language == "RU":
                    self.log_error(f"Ошибка подключения: {e}")
                    self.connection_status.setText("MAKCU: ❌ Ошибка подключения")
                else:
                    self.log_error(f"Connection error: {e}")
                    self.connection_status.setText("MAKCU: ❌ Connection error")

        # Запускаем в отдельном потоке
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()

    def speed_test(self):
        """Тест скорости работы"""
        if not self.makcu:
            if self.current_language == "RU":
                self.log_error("MAKCU не подключен")
            else:
                self.log_error("MAKCU not connected")
            return

        if self.current_language == "RU":
            self.log_info("Запуск теста скорости...")
        else:
            self.log_info("Starting speed test...")

        def speed_test_thread():
            try:
                start_time = time.time()
                movements_count = 100

                # Выполняем быстрые движения для теста скорости
                for i in range(movements_count):
                    self.makcu.move(5, 5)
                    self.makcu.move(-5, -5)

                end_time = time.time()
                total_time = end_time - start_time
                speed = movements_count / total_time  # движений в секунду

                if self.current_language == "RU":
                    self.log_success(f"Тест скорости завершен: {movements_count} движений за {total_time:.2f} сек")
                    self.log_success(f"Скорость: {speed:.1f} движений/сек")
                    if speed > 50:
                        self.log_success("⚡ Отличная скорость! Работает на 4Mbps")
                    else:
                        self.log_warning("⚠️ Скорость ниже ожидаемой")
                else:
                    self.log_success(f"Speed test completed: {movements_count} movements in {total_time:.2f} sec")
                    self.log_success(f"Speed: {speed:.1f} movements/sec")
                    if speed > 50:
                        self.log_success("⚡ Excellent speed! Running at 4Mbps")
                    else:
                        self.log_warning("⚠️ Speed lower than expected")

            except Exception as e:
                if self.current_language == "RU":
                    self.log_error(f"Ошибка теста скорости: {e}")
                else:
                    self.log_error(f"Speed test error: {e}")

        thread = threading.Thread(target=speed_test_thread, daemon=True)
        thread.start()

    def update_connection_ui(self):
        """Обновление UI после подключения"""
        self.standard_connect_btn.setEnabled(False)
        self.speed_test_btn.setEnabled(True)
        self.test_move_btn.setEnabled(True)
        self.test_click_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(True)
        self.update_speed_display()

        if self.current_language == "RU":
            self.connection_status.setText("MAKCU: ✅ Подключен (4Mbps)")
            self.status_label.setText("✅ MAKCU подключен на высокой скорости")
        else:
            self.connection_status.setText("MAKCU: ✅ Connected (4Mbps)")
            self.status_label.setText("✅ MAKCU connected at high speed")

    def disconnect_makcu(self):
        """Отключение MAKCU"""
        if self.makcu:
            try:
                self.makcu.disconnect()
                if self.current_language == "RU":
                    self.log_info("MAKCU отключен")
                else:
                    self.log_info("MAKCU disconnected")
            except Exception as e:
                if self.current_language == "RU":
                    self.log_error(f"Ошибка отключения: {e}")
                else:
                    self.log_error(f"Disconnection error: {e}")

            self.makcu = None

        # Обновляем UI
        self.standard_connect_btn.setEnabled(True)
        self.speed_test_btn.setEnabled(True)
        self.test_move_btn.setEnabled(False)
        self.test_click_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.current_speed = "Unknown"
        self.connection_type = "not_connected"
        self.update_speed_display()

        if self.current_language == "RU":
            self.connection_status.setText("MAKCU: 🔌 Отключен")
            self.status_label.setText("🔍 Готов к диагностике")
        else:
            self.connection_status.setText("MAKCU: 🔌 Disconnected")
            self.status_label.setText("🔍 Ready for diagnostics")

    def test_movement(self):
        """Тест движения курсора"""
        if not self.makcu:
            if self.current_language == "RU":
                self.log_error("MAKCU не подключен")
            else:
                self.log_error("MAKCU not connected")
            return

        if self.current_language == "RU":
            self.log_info("Запуск теста движения...")
        else:
            self.log_info("Starting movement test...")

        def movement_test():
            try:
                # Движение вправо-вниз
                self.makcu.move(50, 50)
                if self.current_language == "RU":
                    self.log_success("Движение: +50, +50")
                else:
                    self.log_success("Movement: +50, +50")
                time.sleep(0.5)

                # Движение влево-вверх
                self.makcu.move(-50, -50)
                if self.current_language == "RU":
                    self.log_success("Движение: -50, -50")
                else:
                    self.log_success("Movement: -50, -50")
                time.sleep(0.5)

                # Круговое движение
                movements = [(30, 0), (0, 30), (-30, 0), (0, -30)]
                for dx, dy in movements:
                    self.makcu.move(dx, dy)
                    if self.current_language == "RU":
                        self.log_success(f"Движение: {dx}, {dy}")
                    else:
                        self.log_success(f"Movement: {dx}, {dy}")
                    time.sleep(0.3)

                if self.current_language == "RU":
                    self.log_success("✅ Тест движения завершен успешно!")
                else:
                    self.log_success("✅ Movement test completed successfully!")

            except Exception as e:
                if self.current_language == "RU":
                    self.log_error(f"Ошибка теста движения: {e}")
                else:
                    self.log_error(f"Movement test error: {e}")

        thread = threading.Thread(target=movement_test, daemon=True)
        thread.start()

    def test_clicks(self):
        """Тест кликов мыши в отдельном окне"""
        if not self.makcu:
            if self.current_language == "RU":
                self.log_error("MAKCU не подключен")
                QMessageBox.warning(self, "Ошибка", "MAKCU не подключен!\nСначала подключите устройство.")
            else:
                self.log_error("MAKCU not connected")
                QMessageBox.warning(self, "Error", "MAKCU not connected!\nPlease connect device first.")
            return

        if self.current_language == "RU":
            self.log_info("Запуск расширенного теста кликов...")
        else:
            self.log_info("Starting advanced click test...")

        # Создаем и показываем окно тестирования кликов
        self.click_test_window = ClickTestWindow(self.makcu, self)
        self.click_test_window.set_language(self.current_language)  # Устанавливаем текущий язык
        self.click_test_window.show()

        if self.current_language == "RU":
            self.log_success("✅ Окно тестирования кликов открыто")
            self.log_info("🔍 Наблюдайте за изменением button_mask в реальном времени")
        else:
            self.log_success("✅ Click testing window opened")
            self.log_info("🔍 Watch button_mask changes in real-time")

    def open_donate(self):
        """Открытие страницы доната"""
        donate_url = "https://oplata.info/asp2/pay_wm.asp?id_d=5035969&lang=ru-RU"
        webbrowser.open(donate_url)
        if self.current_language == "RU":
            self.log_info("Открыта страница поддержки проекта")
        else:
            self.log_info("Support page opened")

    def update_status(self):
        """Обновление статуса подключения"""
        if self.makcu:
            try:
                # Проверяем что подключение еще живо
                self.makcu.get_device_info()
            except:
                # Если подключение разорвано
                self.makcu = None
                self.standard_connect_btn.setEnabled(True)
                self.speed_test_btn.setEnabled(True)
                self.test_move_btn.setEnabled(False)
                self.test_click_btn.setEnabled(False)
                self.disconnect_btn.setEnabled(False)
                self.current_speed = "Unknown"
                self.connection_type = "not_connected"
                self.update_speed_display()
                if self.current_language == "RU":
                    self.connection_status.setText("MAKCU: ❌ Соединение потеряно")
                    self.log_warning("Соединение с MAKCU потеряно")
                else:
                    self.connection_status.setText("MAKCU: ❌ Connection lost")
                    self.log_warning("MAKCU connection lost")

    def clear_logs(self):
        """Очистка логов"""
        self.log_text.clear()
        if self.current_language == "RU":
            self.log_info("Логи очищены")
        else:
            self.log_info("Logs cleared")

    def save_logs(self):
        """Сохранение логов в файл"""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if self.current_language == "RU":
                filename = f"Логи MAKCU {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.txt"
            else:
                filename = f"MAKCU Logs {datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.txt"
            filepath = os.path.join(desktop, filename)

            # Получаем plain text из HTML
            plain_text = self.log_text.toPlainText()

            with open(filepath, 'w', encoding='utf-8') as f:
                if self.current_language == "RU":
                    f.write(f"=== ЛОГИ ДИАГНОСТИКИ MAKCU ===\n")
                    f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Скорость: {self.current_speed}\n")
                    f.write(f"Тип подключения: {self.connection_type}\n")
                else:
                    f.write(f"=== MAKCU DIAGNOSTIC LOGS ===\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Speed: {self.current_speed}\n")
                    f.write(f"Connection type: {self.connection_type}\n")
                f.write(f"================================\n\n")
                f.write(plain_text)

            if self.current_language == "RU":
                self.log_success(f"Логи сохранены: {filepath}")
                QMessageBox.information(self, "Успех", f"Логи сохранены на рабочий стол:\n{filename}")
            else:
                self.log_success(f"Logs saved: {filepath}")
                QMessageBox.information(self, "Success", f"Logs saved to desktop:\n{filename}")

        except Exception as e:
            if self.current_language == "RU":
                self.log_error(f"Ошибка сохранения логов: {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить логи: {e}")
            else:
                self.log_error(f"Error saving logs: {e}")
                QMessageBox.critical(self, "Error", f"Failed to save logs: {e}")

    def toggle_auto_scroll(self):
        """Переключение автопрокрутки"""
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            if self.current_language == "RU":
                self.auto_scroll_btn.setText("📜 Автопрокрутка: ВКЛ")
            else:
                self.auto_scroll_btn.setText("📜 Auto-scroll: ON")
            self.auto_scroll_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 11px;
                }
            """)
        else:
            if self.current_language == "RU":
                self.auto_scroll_btn.setText("📜 Автопрокрутка: ВЫКЛ")
            else:
                self.auto_scroll_btn.setText("📜 Auto-scroll: OFF")
            self.auto_scroll_btn.setStyleSheet("""
                QPushButton {
                    background-color: #95a5a6;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 11px;
                }
            """)

    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.makcu:
            try:
                self.makcu.disconnect()
            except:
                pass
        event.accept()


def main():
    app = QApplication(sys.argv)

    # Устанавливаем стиль
    app.setStyle('Fusion')

    window = MAKCUTestWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()