import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ccbackup_bot.backup_runner import create_backup_folder, run_backup_job
from ccbackup_bot.db import store_successful_backups_and_write_report
from ccbackup_bot.devices import load_credentials, load_devices_from_excel
from ccbackup_bot.gui.settings import clear_settings, load_settings, save_settings, settings_path


class BackupWorker(QThread):
    log_message = Signal(str)
    finished_with_status = Signal(bool)

    def __init__(self, devices_path: str, credentials_path: str, output_path: str, database_enabled: bool) -> None:
        super().__init__()
        self.devices_path = devices_path
        self.credentials_path = credentials_path
        self.output_path = output_path
        self.database_enabled = database_enabled

    def run(self) -> None:
        try:
            credentials = load_credentials(self.credentials_path)
            devices = load_devices_from_excel(self.devices_path, credentials)
            if not devices:
                self.log_message.emit("No devices found in the inventory.")
                self.finished_with_status.emit(False)
                return

            backup_folder = create_backup_folder(Path(self.output_path))
            self.log_message.emit(f"Backing up {len(devices)} device(s) to {backup_folder}")
            results = run_backup_job(devices, backup_folder)

            failures = 0
            for result in results:
                self.log_message.emit(result.message)
                if result.success and result.backup_path:
                    self.log_message.emit(f"  Saved to: {result.backup_path}")
                if not result.success:
                    failures += 1

            if self.database_enabled:
                report_folder = Path(self.output_path) / "reports"
                for message in store_successful_backups_and_write_report(results, report_folder):
                    self.log_message.emit(message)

            self.log_message.emit(f"All done. Successful: {len(results) - failures}, Failed: {failures}")
            self.finished_with_status.emit(failures == 0)
        except Exception as exc:
            self.log_message.emit(f"Backup failed: {exc}")
            self.finished_with_status.emit(False)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.worker: BackupWorker | None = None
        self.setWindowTitle("Cisco Backup Utility")
        self.resize(820, 520)

        self.devices_input = QLineEdit()
        self.credentials_input = QLineEdit("credentials.json")
        self.output_input = QLineEdit("backups")
        self.database_checkbox = QCheckBox("Store backups in PostgreSQL / Generate DB change report")
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.startup_warnings: list[str] = []

        devices_button = QPushButton("Browse")
        devices_button.clicked.connect(self.pick_devices_file)
        credentials_button = QPushButton("Browse")
        credentials_button.clicked.connect(self.pick_credentials_file)
        output_button = QPushButton("Browse")
        output_button.clicked.connect(self.pick_output_folder)

        self.backup_button = QPushButton("Back Up Switches")
        self.backup_button.clicked.connect(self.start_backup)
        self.reset_button = QPushButton("Reset Saved Paths")
        self.reset_button.clicked.connect(self.reset_saved_paths)

        form = QFormLayout()
        form.addRow("Device inventory", self._with_button(self.devices_input, devices_button))
        form.addRow("Credentials", self._with_button(self.credentials_input, credentials_button))
        form.addRow("Backup folder", self._with_button(self.output_input, output_button))
        form.addRow("", self.database_checkbox)

        layout = QVBoxLayout()
        title = QLabel("Cisco Backup Utility")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        safety_note = QLabel("Read-only backup mode: this tool only runs show commands and saves backups.")
        safety_note.setWordWrap(True)
        safety_note.setStyleSheet("font-weight: 600; color: #14532d;")
        layout.addWidget(title)
        layout.addWidget(safety_note)
        layout.addLayout(form)
        action_row = QHBoxLayout()
        action_row.addWidget(self.backup_button)
        action_row.addWidget(self.reset_button)
        layout.addLayout(action_row)
        layout.addWidget(self.log_output, stretch=1)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.load_saved_paths()
        QTimer.singleShot(0, self.show_startup_warnings)

    def _with_button(self, line_edit: QLineEdit, button: QPushButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, stretch=1)
        layout.addWidget(button)
        return row

    def pick_devices_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select device inventory", "", "Excel files (*.xlsx *.xls)")
        if path:
            self.devices_input.setText(path)
            self.save_current_paths()

    def pick_credentials_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select credentials file", "", "JSON files (*.json)")
        if path:
            self.credentials_input.setText(path)
            self.save_current_paths()

    def pick_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select backup folder")
        if path:
            self.output_input.setText(path)
            self.save_current_paths()

    def load_saved_paths(self) -> None:
        saved_settings, warning = load_settings()
        if warning:
            self.startup_warnings.append(warning)

        inventory_path = saved_settings.get("inventory_path", "")
        credentials_path = saved_settings.get("credentials_path", "")
        output_path = saved_settings.get("output_path", "")

        if inventory_path:
            self.devices_input.setText(inventory_path)
            if not Path(inventory_path).is_file():
                self.startup_warnings.append("The saved inventory file path no longer exists.")
        if credentials_path:
            self.credentials_input.setText(credentials_path)
            if not Path(credentials_path).is_file():
                self.startup_warnings.append("The saved credentials file path no longer exists.")
        if output_path:
            self.output_input.setText(output_path)
            if not Path(output_path).is_dir():
                self.startup_warnings.append("The saved backup folder path no longer exists.")

    def show_startup_warnings(self) -> None:
        if not self.startup_warnings:
            return

        message = "\n".join(self.startup_warnings)
        self.log_output.appendPlainText(message)
        QMessageBox.information(self, "Saved paths need attention", message)

    def save_current_paths(self) -> None:
        try:
            save_settings(
                self.devices_input.text().strip(),
                self.credentials_input.text().strip(),
                self.output_input.text().strip(),
            )
        except OSError as exc:
            self.log_output.appendPlainText(f"Saved paths could not be updated: {exc}")

    def reset_saved_paths(self) -> None:
        clear_settings()
        self.devices_input.clear()
        self.credentials_input.clear()
        self.output_input.clear()
        self.log_output.appendPlainText(f"Saved paths cleared. Settings file: {settings_path()}")

    def start_backup(self) -> None:
        devices_path = self.devices_input.text().strip()
        credentials_path = self.credentials_input.text().strip()
        output_path = self.output_input.text().strip() or "backups"

        validation_error = self.validate_inputs(devices_path, credentials_path, output_path)
        if validation_error:
            QMessageBox.warning(self, "Cannot start backup", validation_error)
            return

        self.save_current_paths()
        self.log_output.clear()
        self.backup_button.setEnabled(False)
        self.log_output.appendPlainText("Starting backup job...")

        self.worker = BackupWorker(
            devices_path,
            credentials_path,
            output_path,
            self.database_checkbox.isChecked(),
        )
        self.worker.log_message.connect(self.log_output.appendPlainText)
        self.worker.finished_with_status.connect(self.backup_finished)
        self.worker.start()

    def validate_inputs(self, devices_path: str, credentials_path: str, output_path: str) -> str:
        if not devices_path:
            return "Select a device inventory Excel file."
        if not Path(devices_path).is_file():
            return "The selected device inventory file does not exist."

        if not credentials_path:
            return "Select a credentials JSON file."
        if not Path(credentials_path).is_file():
            return "The selected credentials file does not exist."

        try:
            Path(output_path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"The backup folder could not be created or opened: {exc}"

        if not Path(output_path).is_dir():
            return "The selected backup folder is not a folder."

        return ""

    def backup_finished(self, success: bool) -> None:
        self.backup_button.setEnabled(True)
        if not success:
            QMessageBox.information(self, "Backup finished", "Backup finished with errors. Check the log for details.")


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
