"""
Broker Configuration Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QGroupBox, QMessageBox, QTextEdit
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
import webbrowser

from algo_trader.core.config import Config
from algo_trader.brokers import UpstoxBroker, AliceBlueBroker, ZerodhaBroker, AngelOneBroker

from loguru import logger


class BrokerConfigDialog(QDialog):
    """Dialog for configuring broker connections"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.broker_instance = None

        self._init_ui()

    def _init_ui(self):
        """Initialize dialog UI"""
        self.setWindowTitle("Configure Broker")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Broker selection
        broker_group = QGroupBox("Select Broker")
        broker_layout = QFormLayout(broker_group)

        self.broker_combo = QComboBox()
        self.broker_combo.addItems(["Upstox", "Alice Blue", "Zerodha", "Angel One"])
        self.broker_combo.currentTextChanged.connect(self._on_broker_changed)
        broker_layout.addRow("Broker:", self.broker_combo)

        layout.addWidget(broker_group)

        # Credentials
        creds_group = QGroupBox("API Credentials")
        creds_layout = QFormLayout(creds_group)

        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("Enter API Key")
        creds_layout.addRow("API Key:", self.api_key)

        self.api_secret = QLineEdit()
        self.api_secret.setPlaceholderText("Enter API Secret")
        self.api_secret.setEchoMode(QLineEdit.EchoMode.Password)
        creds_layout.addRow("API Secret:", self.api_secret)

        self.user_id = QLineEdit()
        self.user_id.setPlaceholderText("User ID (for Alice Blue)")
        creds_layout.addRow("User ID:", self.user_id)

        self.redirect_uri = QLineEdit()
        self.redirect_uri.setText("http://127.0.0.1:5000/callback")
        creds_layout.addRow("Redirect URI:", self.redirect_uri)

        # Password field (for Angel One)
        self.password_label = QLabel("Password:")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password (for Angel One)")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        creds_layout.addRow(self.password_label, self.password)
        self.password_label.setVisible(False)
        self.password.setVisible(False)

        # TOTP Secret field (for Angel One)
        self.totp_label = QLabel("TOTP Secret:")
        self.totp_secret = QLineEdit()
        self.totp_secret.setPlaceholderText("TOTP Secret (for Angel One 2FA)")
        self.totp_secret.setEchoMode(QLineEdit.EchoMode.Password)
        creds_layout.addRow(self.totp_label, self.totp_secret)
        self.totp_label.setVisible(False)
        self.totp_secret.setVisible(False)

        layout.addWidget(creds_group)

        # Authentication
        auth_group = QGroupBox("Authentication")
        auth_layout = QVBoxLayout(auth_group)

        self.get_login_url_btn = QPushButton("Get Login URL")
        self.get_login_url_btn.clicked.connect(self._get_login_url)
        auth_layout.addWidget(self.get_login_url_btn)

        self.login_url_display = QTextEdit()
        self.login_url_display.setReadOnly(True)
        self.login_url_display.setMaximumHeight(80)
        self.login_url_display.setPlaceholderText("Login URL will appear here...")
        auth_layout.addWidget(self.login_url_display)

        self.open_browser_btn = QPushButton("Open in Browser")
        self.open_browser_btn.clicked.connect(self._open_browser)
        self.open_browser_btn.setEnabled(False)
        auth_layout.addWidget(self.open_browser_btn)

        auth_layout.addWidget(QLabel("After login, paste the authorization code below:"))

        self.auth_code = QLineEdit()
        self.auth_code.setPlaceholderText("Paste authorization code here")
        auth_layout.addWidget(self.auth_code)

        self.authenticate_btn = QPushButton("Authenticate")
        self.authenticate_btn.clicked.connect(self._authenticate)
        auth_layout.addWidget(self.authenticate_btn)

        layout.addWidget(auth_group)

        # Buttons
        btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save Credentials")
        self.save_btn.clicked.connect(self._save_credentials)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        # Load existing credentials
        self._load_existing_credentials()

    def _on_broker_changed(self, broker: str):
        """Handle broker selection change"""
        # Reset all optional fields
        self.user_id.setEnabled(False)
        self.user_id.setPlaceholderText("Not required")
        self.api_secret.setPlaceholderText("Enter API Secret")
        self.api_secret.setEnabled(True)
        self.password_label.setVisible(False)
        self.password.setVisible(False)
        self.totp_label.setVisible(False)
        self.totp_secret.setVisible(False)

        if broker == "Alice Blue":
            self.user_id.setEnabled(True)
            self.user_id.setPlaceholderText("User ID (required)")
            self.api_secret.setPlaceholderText("Not required for Alice Blue")
            self.api_secret.setEnabled(False)
        elif broker == "Zerodha":
            self.user_id.setEnabled(True)
            self.user_id.setPlaceholderText("User ID (required)")
        elif broker == "Angel One":
            self.user_id.setEnabled(True)
            self.user_id.setPlaceholderText("Client ID (required)")
            self.password_label.setVisible(True)
            self.password.setVisible(True)
            self.totp_label.setVisible(True)
            self.totp_secret.setVisible(True)
            if AngelOneBroker is None:
                QMessageBox.warning(self, "Missing Package",
                    "Angel One requires 'pyotp' package.\n\nInstall with: pip install pyotp")

        self._load_existing_credentials()

    def _load_existing_credentials(self):
        """Load existing credentials for selected broker"""
        broker = self.broker_combo.currentText().lower().replace(" ", "_")
        creds = self.config.get_broker_credentials(broker)

        if creds:
            self.api_key.setText(creds.get('api_key', ''))
            self.api_secret.setText(creds.get('api_secret', ''))
            self.user_id.setText(creds.get('user_id', ''))

    def _get_login_url(self):
        """Get OAuth login URL"""
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()
        redirect_uri = self.redirect_uri.text().strip()

        broker = self.broker_combo.currentText()

        # Alice Blue doesn't need API Secret
        if broker != "Alice Blue" and (not api_key or not api_secret):
            QMessageBox.warning(self, "Error", "Please enter API Key and Secret")
            return
        elif broker == "Alice Blue" and not api_key:
            QMessageBox.warning(self, "Error", "Please enter API Key")
            return

        try:
            if broker == "Upstox":
                self.broker_instance = UpstoxBroker(api_key, api_secret, redirect_uri)
            elif broker == "Alice Blue":
                user_id = self.user_id.text().strip()
                if not user_id:
                    QMessageBox.warning(self, "Error", "User ID is required for Alice Blue")
                    return
                self.broker_instance = AliceBlueBroker(api_key, "", user_id, redirect_uri)
            elif broker == "Zerodha":
                user_id = self.user_id.text().strip()
                if not user_id:
                    QMessageBox.warning(self, "Error", "User ID is required for Zerodha")
                    return
                self.broker_instance = ZerodhaBroker(api_key, api_secret, user_id, redirect_uri)
            elif broker == "Angel One":
                user_id = self.user_id.text().strip()
                password = self.password.text().strip()
                totp_secret = self.totp_secret.text().strip()
                if not user_id or not password:
                    QMessageBox.warning(self, "Error", "Client ID and Password are required for Angel One")
                    return
                if AngelOneBroker is None:
                    QMessageBox.warning(self, "Error", "Angel One requires 'pyotp' package.\n\nInstall with: pip install pyotp")
                    return
                self.broker_instance = AngelOneBroker(api_key, api_secret, user_id, password, totp_secret)
                # Angel One doesn't use OAuth URL - directly authenticate
                if self.broker_instance.generate_session():
                    QMessageBox.information(self, "Success", "Angel One authenticated successfully!")
                    self._save_credentials()
                    return
                else:
                    QMessageBox.warning(self, "Error", "Angel One authentication failed")
                    return

            login_url = self.broker_instance.get_login_url()
            self.login_url_display.setText(login_url)
            self.open_browser_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to generate login URL: {e}")

    def _open_browser(self):
        """Open login URL in browser"""
        url = self.login_url_display.toPlainText()
        if url:
            webbrowser.open(url)

    def _authenticate(self):
        """Authenticate with authorization code"""
        auth_code = self.auth_code.text().strip()
        if not auth_code:
            QMessageBox.warning(self, "Error", "Please enter authorization code")
            return

        if not self.broker_instance:
            QMessageBox.warning(self, "Error", "Please get login URL first")
            return

        try:
            logger.info(f"Attempting authentication with code: {auth_code[:10]}...")
            if self.broker_instance.generate_session(auth_code):
                logger.info(f"generate_session returned True, is_authenticated = {self.broker_instance.is_authenticated}")
                QMessageBox.information(self, "Success", "Authentication successful!")
                # Save and close - skip validation since we just authenticated
                self._save_credentials_and_close()
            else:
                logger.warning("generate_session returned False")
                QMessageBox.warning(self, "Error", "Authentication failed. Check your credentials.")
        except Exception as e:
            logger.error(f"Authentication exception: {e}")
            QMessageBox.warning(self, "Error", f"Authentication failed: {e}")

    def _save_credentials_and_close(self):
        """Save credentials after successful authentication and close dialog"""
        try:
            api_key = self.api_key.text().strip()
            api_secret = self.api_secret.text().strip()
            broker = self.broker_combo.currentText().lower().replace(" ", "_")

            kwargs = {}
            if broker in ["alice_blue", "zerodha", "angel_one"]:
                kwargs['user_id'] = self.user_id.text().strip()
            if broker == "angel_one":
                kwargs['password'] = self.password.text().strip()
                kwargs['totp_secret'] = self.totp_secret.text().strip()

            self.config.save_broker_credentials(broker, api_key, api_secret, **kwargs)
            logger.info(f"Credentials saved for {broker}")
            self.accept()  # Close dialog with Accepted status
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
            self.accept()  # Still close so broker gets added

    def _save_credentials(self):
        """Save broker credentials"""
        api_key = self.api_key.text().strip()
        api_secret = self.api_secret.text().strip()

        broker = self.broker_combo.currentText().lower().replace(" ", "_")

        # Alice Blue doesn't need API Secret
        if broker != "alice_blue" and (not api_key or not api_secret):
            QMessageBox.warning(self, "Error", "Please enter API Key and Secret")
            return
        elif broker == "alice_blue" and not api_key:
            QMessageBox.warning(self, "Error", "Please enter API Key")
            return

        kwargs = {}
        if broker == "alice_blue":
            user_id = self.user_id.text().strip()
            if not user_id:
                QMessageBox.warning(self, "Error", "User ID is required for Alice Blue")
                return
            kwargs['user_id'] = user_id
            api_secret = ""  # Not needed for Alice Blue
        elif broker == "zerodha":
            user_id = self.user_id.text().strip()
            if not user_id:
                QMessageBox.warning(self, "Error", "User ID is required for Zerodha")
                return
            kwargs['user_id'] = user_id
        elif broker == "angel_one":
            user_id = self.user_id.text().strip()
            password = self.password.text().strip()
            totp_secret = self.totp_secret.text().strip()
            if not user_id or not password:
                QMessageBox.warning(self, "Error", "Client ID and Password are required for Angel One")
                return
            kwargs['user_id'] = user_id
            kwargs['password'] = password
            kwargs['totp_secret'] = totp_secret

        self.config.save_broker_credentials(broker, api_key, api_secret, **kwargs)
        QMessageBox.information(self, "Success", f"Credentials saved for {self.broker_combo.currentText()}")
        self.accept()
