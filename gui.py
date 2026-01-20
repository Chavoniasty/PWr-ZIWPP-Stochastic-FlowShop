import sys
import ctypes
import os
import platform
import random
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFileDialog,
                             QComboBox, QLineEdit, QFrame, QMessageBox, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QDragEnterEvent, QDropEvent

# --- 1. WORKER THREAD ---
class OptimizerWorker(QThread):
    # Signal now carries: (permutation list, cost, schedule list)
    update_signal = pyqtSignal(list, float, list)
    finished_signal = pyqtSignal()

    def __init__(self, lib, n_jobs, n_machines, means, stds, algo_code, samples, is_ctg):
        super().__init__()
        self.lib = lib
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.means = means
        self.stds = stds
        self.algo_code = algo_code
        self.samples = samples
        self.is_ctg = is_ctg

        # Callback Signature: void func(int* perm, double cost, double* schedule)
        self.CALLBACK_FUNC = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_int), ctypes.c_double, ctypes.POINTER(ctypes.c_double))
        self.cb_instance = self.CALLBACK_FUNC(self.on_update)

    def run(self):
        c_means = (ctypes.c_double * len(self.means))(*self.means)
        c_stds = (ctypes.c_double * len(self.stds))(*self.stds)
        c_out = (ctypes.c_int * self.n_jobs)()

        self.lib.run_algorithm(
            self.n_jobs, self.n_machines, c_means, c_stds,
            self.algo_code, self.samples, self.is_ctg, c_out,
            self.cb_instance
        )
        self.finished_signal.emit()

    def on_update(self, array_ptr, cost, sched_ptr):
        # Extract Permutation
        perm = [array_ptr[i] for i in range(self.n_jobs)]

        # Extract Schedule (Size = n_jobs * n_machines * 2)
        total_doubles = self.n_jobs * self.n_machines * 2
        schedule = [sched_ptr[i] for i in range(total_doubles)]

        self.update_signal.emit(perm, cost, schedule)

# --- 2. GANTT CHART VISUALIZER ---
class GanttChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.schedule = []
        self.n_jobs = 0
        self.n_machines = 0
        self.makespan = 0
        self.job_colors = {}
        self.setFixedHeight(250) # Taller for detailed view
        self.setStyleSheet("background-color: #ffffff; border: 1px solid #ccc; border-radius: 8px;")

    def update_data(self, n_jobs, n_machines, schedule, makespan):
        self.n_jobs = n_jobs
        self.n_machines = n_machines
        self.schedule = schedule
        self.makespan = makespan

        # Generate consistent colors for jobs
        if len(self.job_colors) != n_jobs:
            self.job_colors = {}
            for i in range(n_jobs):
                # Pastel-like colors
                hue = (i * 137.508) % 360
                self.job_colors[i+1] = QColor.fromHsl(int(hue), 200, 150)

        self.update()

    def paintEvent(self, event):
        if not self.schedule or self.makespan <= 0: return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Margins
        margin_left = 30
        margin_bottom = 20
        graph_w = w - margin_left - 10
        graph_h = h - margin_bottom - 10

        # Scales
        time_scale = graph_w / self.makespan
        machine_height = graph_h / self.n_machines

        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        # Draw Machine Rows
        for m in range(self.n_machines):
            y = 10 + m * machine_height

            # Label
            painter.setPen(QColor("#333"))
            painter.drawText(0, int(y), margin_left - 5, int(machine_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"M{m+1}")

            # Grid line
            painter.setPen(QColor("#eee"))
            painter.drawLine(margin_left, int(y), w, int(y))

        # Draw Jobs
        # Schedule is flat: [Job0_M0_S, Job0_M0_E, Job0_M1_S, ... ]
        # Index = (JobId_0based * n_machines + MachineId) * 2

        for j in range(self.n_jobs):
            color = self.job_colors.get(j+1, QColor("gray"))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            for m in range(self.n_machines):
                base_idx = (j * self.n_machines + m) * 2
                start_time = self.schedule[base_idx]
                end_time = self.schedule[base_idx + 1]

                # Coords
                x = margin_left + start_time * time_scale
                width = (end_time - start_time) * time_scale
                y = 10 + m * machine_height + 4 # +4 padding
                height = machine_height - 8

                # Draw Rect
                rect = QRectF(x, y, max(1.0, width), height)
                painter.drawRoundedRect(rect, 3, 3)

                # Draw Job ID if wide enough
                if width > 15:
                    painter.setPen(QColor("white"))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(j+1))

# --- 3. DRAG DROP AREA (Unchanged) ---
class DragDropArea(QLabel):
    file_dropped = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setText("📂\nDrag & Drop .txt file here\nor click to browse")
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

# --- 4. MAIN WINDOW ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flow Shop Gantt Solver")
        self.resize(1000, 700)

        self.lib = ctypes.CDLL(os.path.abspath("./scheduler.so" if platform.system() != "Windows" else "scheduler.dll"))

        # Defines
        self.lib.run_algorithm.argtypes = [
            ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ctypes.c_int, ctypes.c_int, ctypes.c_bool,
            ctypes.POINTER(ctypes.c_int),
            ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_int), ctypes.c_double, ctypes.POINTER(ctypes.c_double))
        ]

        self.n_jobs = 0
        self.n_machines = 0
        self.means = []
        self.stds = []

        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            QLabel { font-family: 'Segoe UI'; font-size: 14px; color: #333; }
            QLabel#DropZone { border: 2px dashed #bdc3c7; border-radius: 10px; background: white; color: #7f8c8d; font-weight: bold; }
            QPushButton { background-color: #2ecc71; color: white; border: none; padding: 10px; font-weight: bold; border-radius: 5px; }
            QPushButton:hover { background-color: #27ae60; }
            QFrame#Control { background: white; border-radius: 10px; border: 1px solid #ddd; }
        """)
        self.init_ui()

    def init_ui(self):
        main = QWidget()
        self.setCentralWidget(main)
        layout = QVBoxLayout(main)

        # Drop Zone
        self.drop = DragDropArea()
        self.drop.file_dropped.connect(self.parse_file)
        layout.addWidget(self.drop)

        # Controls
        panel = QFrame()
        panel.setObjectName("Control")
        p_layout = QHBoxLayout(panel)

        self.combo = QComboBox()
        self.combo.addItems(["Brute Force", "Simulated Annealing", "NEH"])
        self.combo.setCurrentIndex(1)

        self.inp_samples = QLineEdit("50")
        self.inp_samples.setFixedWidth(50)
        self.chk_ctg = QCheckBox("Deterministic")

        self.btn_run = QPushButton("RUN")
        self.btn_run.clicked.connect(self.start)

        p_layout.addWidget(QLabel("Algorithm:"))
        p_layout.addWidget(self.combo)
        p_layout.addWidget(QLabel("Samples:"))
        p_layout.addWidget(self.inp_samples)
        p_layout.addWidget(self.chk_ctg)
        p_layout.addStretch()
        p_layout.addWidget(self.btn_run)
        layout.addWidget(panel)

        # Results
        self.lbl_res = QLabel("Best Makespan: ---")
        self.lbl_res.setStyleSheet("font-size: 18px; font-weight: bold; color: #e74c3c;")
        layout.addWidget(self.lbl_res)

        # Gantt Visualizer
        self.gantt = GanttChartWidget()
        layout.addWidget(self.gantt)

    def parse_file(self, fn):
        if fn == "BROWSE": fn, _ = QFileDialog.getOpenFileName(self, "Open", "", "*.txt")
        if not fn: return
        try:
            with open(fn) as f: d = f.read().split()
            it = iter(d)
            self.n_jobs = int(next(it))
            self.n_machines = int(next(it))
            self.means = [float(next(it)) for _ in range(self.n_jobs*self.n_machines)]
            self.stds = []
            try:
                for _ in range(self.n_jobs*self.n_machines): self.stds.append(float(next(it)))
            except: self.stds = [0.0]*len(self.means)
            self.drop.setText(f"✅ Loaded: {os.path.basename(fn)}")
            self.drop.setStyleSheet("border: 2px solid #2ecc71; color: green;")
        except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def start(self):
        if not self.means: return QMessageBox.warning(self, "Warn", "Load file first")
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Running...")

        algo = {"Brute Force": 0, "Simulated Annealing": 1, "NEH": 2}[self.combo.currentText()]

        self.worker = OptimizerWorker(self.lib, self.n_jobs, self.n_machines, self.means, self.stds, algo, int(self.inp_samples.text()), self.chk_ctg.isChecked())
        self.worker.update_signal.connect(self.on_update)
        self.worker.finished_signal.connect(lambda: self.btn_run.setText("RUN") or self.btn_run.setEnabled(True))
        self.worker.start()

    def on_update(self, perm, cost, schedule):
        self.lbl_res.setText(f"Best Makespan: {cost:.2f}")
        self.gantt.update_data(self.n_jobs, self.n_machines, schedule, cost)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
