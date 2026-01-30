import sys
import ctypes
import os
import platform
import random
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QComboBox, QLineEdit, QFrame, QMessageBox, QCheckBox,
                             QDoubleSpinBox, QSpinBox, QGroupBox, QFormLayout, QTextEdit)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QDragEnterEvent, QDropEvent

class OptimizerWorker(QThread):
    update_signal = pyqtSignal(list, float, list)
    finished_signal = pyqtSignal()

    def __init__(self, lib, n_jobs, n_machines, means, stds, algo_code, samples, is_ctg, params):
        super().__init__()
        self.lib = lib
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.means = means
        self.stds = stds
        self.algo_code = algo_code
        self.samples = samples
        self.is_ctg = is_ctg
        self.params = params

        self.CALLBACK_FUNC = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_int), ctypes.c_double, ctypes.POINTER(ctypes.c_double))
        self.cb_instance = self.CALLBACK_FUNC(self.on_update)

    def run(self):
        c_means = (ctypes.c_double * len(self.means))(*self.means)
        c_stds = (ctypes.c_double * len(self.stds))(*self.stds)
        c_params = (ctypes.c_double * len(self.params))(*self.params)
        c_out = (ctypes.c_int * self.n_jobs)()

        self.lib.run_algorithm(
            self.n_jobs, self.n_machines, c_means, c_stds,
            self.algo_code, self.samples, self.is_ctg, 
            c_params,
            c_out,
            self.cb_instance
        )
        self.finished_signal.emit()

    def on_update(self, array_ptr, cost, sched_ptr):
        perm = [array_ptr[i] for i in range(self.n_jobs)]
        total_doubles = self.n_jobs * self.n_machines * 2
        schedule = [sched_ptr[i] for i in range(total_doubles)]
        self.update_signal.emit(perm, cost, schedule)

class GanttChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.schedule = []
        self.n_jobs = 0
        self.n_machines = 0
        self.makespan = 0
        self.job_colors = {}
        self.setFixedHeight(300)
        self.setStyleSheet("background-color: #ffffff; border: 1px solid #ccc; border-radius: 8px;")

    def update_data(self, n_jobs, n_machines, schedule, makespan):
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.schedule = schedule
        self.makespan = makespan

        if len(self.job_colors) != n_jobs:
            self.job_colors = {}
            for i in range(n_jobs):
                hue = (i * 137.508) % 360
                self.job_colors[i+1] = QColor.fromHsl(int(hue), 200, 150)
        self.update()

    def paintEvent(self, event):
        if not self.schedule or self.makespan <= 0: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 30
        margin_bottom = 20
        graph_w = w - margin_left - 10
        graph_h = h - margin_bottom - 10

        time_scale = graph_w / self.makespan
        machine_height = graph_h / self.n_machines

        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        for m in range(self.n_machines):
            y = 10 + m * machine_height
            painter.setPen(QColor("#333"))
            painter.drawText(0, int(y), margin_left - 5, int(machine_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"M{m+1}")
            painter.setPen(QColor("#eee"))
            painter.drawLine(margin_left, int(y), w, int(y))

        for j in range(self.n_jobs):
            color = self.job_colors.get(j+1, QColor("gray"))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            for m in range(self.n_machines):
                base_idx = (j * self.n_machines + m) * 2
                start_time = self.schedule[base_idx]
                end_time = self.schedule[base_idx + 1]

                x = margin_left + start_time * time_scale
                width = (end_time - start_time) * time_scale
                y = 10 + m * machine_height + 4
                height = machine_height - 8

                rect = QRectF(x, y, max(1.0, width), height)
                painter.drawRoundedRect(rect, 3, 3)

                if width > 15:
                    painter.setPen(QColor("white"))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(j+1))

class DragDropArea(QLabel):
    file_dropped = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setText("📂\nPrzeciągnij i upuść plik .txt tutaj\nlub kliknij, aby wybrać")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setObjectName("DropZone")
        self.setFixedHeight(100)
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.file_dropped.emit("BROWSE")
    def dragEnterEvent(self, e): e.accept() if e.mimeData().hasUrls() else e.ignore()
    def dropEvent(self, e):
        if e.mimeData().urls():
            self.file_dropped.emit(e.mimeData().urls()[0].toLocalFile())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Harmonogramowanie Flow Shop (Gantt)")
        self.resize(1100, 850)

        lib_name = "./scheduler.so" if platform.system() != "Windows" else "scheduler.dll"
        self.lib = ctypes.CDLL(os.path.abspath(lib_name))

        self.lib.run_algorithm.argtypes = [
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ctypes.c_int, ctypes.c_int, ctypes.c_bool,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_int),
            ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_int), ctypes.c_double, ctypes.POINTER(ctypes.c_double))
        ]

        self.n_jobs = 0
        self.n_machines = 0
        self.means = []
        self.stds = []
        self.final_makespan = 0.0

        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            QLabel { font-family: 'Segoe UI'; font-size: 14px; color: #333; }
            
            QLabel#DropZone { 
                border: 2px dashed #bdc3c7; 
                border-radius: 10px; 
                background: white; 
                color: #7f8c8d; 
                font-weight: bold; 
            }
            QLabel#DropZone:hover { 
                border-color: #3498db; 
                color: #3498db; 
                background: #ecf0f1; 
            }
            
            QPushButton { background-color: #2ecc71; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #27ae60; }
            QPushButton:disabled { background-color: #95a5a6; }
            
            QFrame#Control { background: white; border-radius: 10px; border: 1px solid #ddd; }
            QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { padding: 5px; border: 1px solid #ccc; border-radius: 4px; }
        """)

        self.init_ui()

    def init_ui(self):
        main = QWidget()
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)

        self.drop = DragDropArea()
        self.drop.file_dropped.connect(self.parse_file)
        layout.addWidget(self.drop)

        panel = QFrame()
        panel.setObjectName("Control")
        p_layout = QHBoxLayout(panel)

        self.combo = QComboBox()
        self.combo.addItems(["Przegląd zupełny (Brute Force)", "Symulowane Wyżarzanie", "NEH"])
        self.combo.setCurrentIndex(1)
        self.combo.currentIndexChanged.connect(self.toggle_params)

        self.inp_samples = QLineEdit("50")
        self.inp_samples.setFixedWidth(50)
        self.chk_ctg = QCheckBox("Deterministyczny")

        p_layout.addWidget(QLabel("Algorytm:"))
        p_layout.addWidget(self.combo)
        p_layout.addWidget(QLabel("Próbki MC:"))
        p_layout.addWidget(self.inp_samples)
        p_layout.addWidget(self.chk_ctg)
        
        self.grp_params = QGroupBox("Parametry SA")
        self.grp_params.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }")
        param_layout = QHBoxLayout(self.grp_params)

        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0, 10000)
        self.spin_temp.setValue(0) 
        
        self.spin_temp.setSpecialValueText("Auto")
        
        self.spin_temp.setToolTip("Temperatura początkowa (Ustaw 0 dla automatycznego obliczenia)")
        param_layout.addWidget(QLabel("Temp. Pocz.:"))
        param_layout.addWidget(self.spin_temp)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.8, 0.999)
        self.spin_alpha.setSingleStep(0.001)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.970)
        param_layout.addWidget(QLabel("Alfa:"))
        param_layout.addWidget(self.spin_alpha)

        self.spin_iter = QSpinBox()
        self.spin_iter.setRange(10, 5000)
        self.spin_iter.setValue(100)
        param_layout.addWidget(QLabel("Iter/Temp:"))
        param_layout.addWidget(self.spin_iter)

        p_layout.addWidget(self.grp_params)

        p_layout.addStretch()
        self.btn_run = QPushButton("URUCHOM")
        self.btn_run.clicked.connect(self.start)
        p_layout.addWidget(self.btn_run)
        
        layout.addWidget(panel)

        self.lbl_res = QLabel("Najlepszy Czas: ---")
        self.lbl_res.setStyleSheet("font-size: 18px; font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_res)

        self.gantt = GanttChartWidget()
        layout.addWidget(self.gantt)

        layout.addWidget(QLabel("Najlepsza sekwencja zadań:"))
        self.txt_seq = QLineEdit()
        self.txt_seq.setReadOnly(True)
        self.txt_seq.setPlaceholderText("Sekwencja pojawi się tutaj...")
        self.txt_seq.setStyleSheet("font-size: 12px; color: #2c3e50; background: #ecf0f1;")
        layout.addWidget(self.txt_seq)

        self.toggle_params()

    def toggle_params(self):
        is_sa = (self.combo.currentIndex() == 1)
        self.grp_params.setVisible(is_sa)
        self.grp_params.setEnabled(is_sa)

    def start(self):
        if not self.means: 
            QMessageBox.warning(self, "Uwaga", "Najpierw wczytaj plik z danymi")
            return
            
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Przetwarzanie...")
        
        self.txt_seq.setText("Obliczanie...")

        algo_idx = self.combo.currentIndex()
        params = [self.spin_temp.value(), self.spin_alpha.value(), float(self.spin_iter.value())]
        try: samples = int(self.inp_samples.text())
        except: samples = 50

        self.worker = OptimizerWorker(
            self.lib, self.n_jobs, self.n_machines, self.means, self.stds, 
            algo_idx, samples, self.chk_ctg.isChecked(), params
        )
        self.worker.update_signal.connect(self.on_update)
        self.worker.finished_signal.connect(self.on_execution_finished)
        self.worker.start()

    def on_update(self, perm, cost, schedule):
        self.final_makespan = cost
        self.lbl_res.setText(f"Najlepszy Czas: {cost:.2f}")
        self.gantt.update_data(self.n_jobs, self.n_machines, schedule, cost)
        
        formatted_perm = []
        for job_id in perm:
            if 1 <= job_id <= self.n_jobs:
                formatted_perm.append(str(job_id))
            else:
                formatted_perm.append("X") # Puste miejsce oznaczamy jako X
        
        seq_str = " -> ".join(formatted_perm)
        self.txt_seq.setText(seq_str)

    def on_execution_finished(self):
        self.btn_run.setText("URUCHOM")
        self.btn_run.setEnabled(True)
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Zakończono optymalizację")
        msg.setText("Algorytm zakończył działanie pomyślnie!")
        msg.setInformativeText(f"Końcowy Czas (Makespan): {self.final_makespan:.2f}\n\nSprawdź pole sekwencji dla kolejności zadań.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def parse_file(self, fn):
        if fn == "BROWSE": 
            fn, _ = QFileDialog.getOpenFileName(self, "Otwórz plik", "", "Pliki tekstowe (*.txt)")
        if not fn: return

        try:
            with open(fn, 'r') as f:
                lines = f.readlines()

            lines = [line.strip() for line in lines if line.strip()]

            if not lines: 
                raise ValueError("Plik jest pusty.")
            
            first_line = lines[0]
            header_parts = first_line.split()

            if len(header_parts) != 2:
                raise ValueError(
                    f"Błąd w pierwszym wierszu pliku (nagłówku).\n"
                    f"Wymagane są dokładnie DWIE liczby (liczba zadań i maszyn).\n"
                    f"Znaleziono {len(header_parts)} element(y): '{first_line}'"
                )

            try:
                self.n_jobs = int(header_parts[0])
                self.n_machines = int(header_parts[1])
            except ValueError:
                raise ValueError(
                    f"Błąd w nagłówku.\n"
                    f"Oczekiwano liczb całkowitych, a znaleziono tekst.\n"
                    f"Wartości w pierwszej linii: '{header_parts[0]}' i '{header_parts[1]}'"
                )

            rest_of_content = " ".join(lines[1:])
            tokens = rest_of_content.split()
            iterator = iter(tokens)

            expected_count = self.n_jobs * self.n_machines
            self.means = []
            
            for i in range(expected_count):
                try:
                    token = next(iterator)
                except StopIteration:
                    raise ValueError(
                        f"Plik skończył się niespodziewanie.\n"
                        f"Wczytano {len(self.means)} liczb, a na podstawie nagłówka ({self.n_jobs}x{self.n_machines}) oczekiwano {expected_count}.\n"
                        f"Brakuje {expected_count - len(self.means)} wartości."
                    )
                
                try:
                    if float(token) < 0:
                        raise ValueError(
                            f"Błąd danych przy wartości nr {i+1} (po nagłówku).\n"
                            f"Czasy zadań nie mogą być ujemne.\n"
                            f"Napotkano wartość: '{token}'"
                        )
                    self.means.append(float(token))
                except ValueError:
                    raise ValueError(
                        f"Błąd danych przy wartości nr {i+1} (po nagłówku).\n"
                        f"Program oczekiwał liczby (czasu zadania), a napotkał tekst:\n\n"
                        f"👉 '{token}'\n\n"
                        f"Sprawdź treść pliku poniżej pierwszego wiersza."
                    )

            self.stds = []
            remaining = list(iterator)
            
            if len(remaining) == 0:
                self.stds = [0.0] * expected_count
            elif len(remaining) == expected_count:
                for token in remaining:
                    try:
                        if float(token) < 0:
                            raise ValueError(f"Błąd w sekcji odchyleń standardowych. Odchylenia nie mogą być ujemne. Znaleziono: '{token}'")
                        self.stds.append(float(token))
                    except ValueError:
                        raise ValueError(f"Błąd w sekcji odchyleń standardowych. Znaleziono tekst: '{token}'")
            else:
                raise ValueError(
                    f"Błędna ilość danych na końcu pliku.\n"
                    f"Zostało {len(remaining)} liczb, a oczekiwano 0 (brak odchyleń) lub {expected_count} (odchylenia)."
                )

            self.drop.setText(f"✅ Wczytano: {os.path.basename(fn)}\n({self.n_jobs} Zadań, {self.n_machines} Maszyn)")
            self.drop.setStyleSheet("""
                QLabel#DropZone {
                    border: 2px solid #2ecc71;
                    background-color: #f0fff4;
                    color: #27ae60;
                    font-weight: bold;
                }
            """)

        except ValueError as e:
            self.drop.setText("❌ Błąd Danych")
            self.drop.setStyleSheet("""
                QLabel#DropZone {
                    border: 2px dashed #e74c3c;
                    background-color: #fdf0ed;
                    color: #c0392b;
                    font-weight: bold;
                }
            """)
            QMessageBox.warning(self, "Błąd w pliku", str(e))

        except Exception as e:
            QMessageBox.critical(self, "Błąd Krytyczny", f"Nieoczekiwany błąd:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())