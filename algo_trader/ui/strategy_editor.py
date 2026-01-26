"""
Strategy Editor Component
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import QRegularExpression


class PineScriptHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Pine Script"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#C678DD"))  # Purple
        keyword_format.setFontWeight(700)
        keywords = [
            "if", "else", "for", "while", "switch", "case", "default",
            "var", "varip", "const", "type", "import", "export",
            "strategy", "indicator", "library", "true", "false", "na",
            "and", "or", "not"
        ]
        for word in keywords:
            pattern = QRegularExpression(rf"\b{word}\b")
            self.highlighting_rules.append((pattern, keyword_format))

        # Built-in functions
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#61AFEF"))  # Blue
        functions = [
            r"ta\.\w+", r"strategy\.\w+", r"input\.\w+", r"math\.\w+",
            r"str\.\w+", r"array\.\w+", r"request\.\w+",
            "plot", "plotshape", "plotchar", "bgcolor", "fill", "hline",
            "alert", "alertcondition", "nz", "fixnan", "barssince", "valuewhen"
        ]
        for func in functions:
            pattern = QRegularExpression(func)
            self.highlighting_rules.append((pattern, function_format))

        # Built-in variables
        variable_format = QTextCharFormat()
        variable_format.setForeground(QColor("#E06C75"))  # Red
        variables = [
            "open", "high", "low", "close", "volume", "time",
            "hl2", "hlc3", "ohlc4", "hlcc4", "bar_index",
            r"barstate\.\w+", r"syminfo\.\w+", r"timeframe\.\w+"
        ]
        for var in variables:
            pattern = QRegularExpression(rf"\b{var}\b")
            self.highlighting_rules.append((pattern, variable_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#D19A66"))  # Orange
        self.highlighting_rules.append(
            (QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), number_format)
        )

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#98C379"))  # Green
        self.highlighting_rules.append(
            (QRegularExpression(r'"[^"]*"'), string_format)
        )
        self.highlighting_rules.append(
            (QRegularExpression(r"'[^']*'"), string_format)
        )

        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#5C6370"))  # Gray
        comment_format.setFontItalic(True)
        self.highlighting_rules.append(
            (QRegularExpression(r"//.*"), comment_format)
        )

        # Version indicator
        version_format = QTextCharFormat()
        version_format.setForeground(QColor("#56B6C2"))  # Cyan
        self.highlighting_rules.append(
            (QRegularExpression(r"//@version=\d+"), version_format)
        )

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


class StrategyEditor(QTextEdit):
    """Pine Script editor with syntax highlighting"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set font
        font = QFont("Consolas", 11)
        self.setFont(font)

        # Set dark theme colors
        self.setStyleSheet("""
            QTextEdit {
                background-color: #282C34;
                color: #ABB2BF;
                border: 1px solid #3E4451;
                padding: 10px;
            }
        """)

        # Enable syntax highlighting
        self.highlighter = PineScriptHighlighter(self.document())

        # Set tab width
        self.setTabStopDistance(40)

    def set_placeholder_text(self):
        """Set placeholder with example Pine Script"""
        self.setPlaceholderText(
            "//@version=5\n"
            "strategy('My Strategy', overlay=true)\n\n"
            "// Input parameters\n"
            "fast_length = input.int(10, 'Fast MA Length')\n"
            "slow_length = input.int(20, 'Slow MA Length')\n\n"
            "// Calculate indicators\n"
            "fast_ma = ta.sma(close, fast_length)\n"
            "slow_ma = ta.sma(close, slow_length)\n\n"
            "// Plot indicators\n"
            "plot(fast_ma, color=color.blue, title='Fast MA')\n"
            "plot(slow_ma, color=color.red, title='Slow MA')\n\n"
            "// Entry conditions\n"
            "long_condition = ta.crossover(fast_ma, slow_ma)\n"
            "short_condition = ta.crossunder(fast_ma, slow_ma)\n\n"
            "// Execute trades\n"
            "if long_condition\n"
            "    strategy.entry('Long', strategy.long)\n\n"
            "if short_condition\n"
            "    strategy.close('Long')"
        )
