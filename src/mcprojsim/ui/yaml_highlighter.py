"""YAML syntax highlighter for QPlainTextEdit (P1-17)."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression  # type: ignore[import-untyped]
from PySide6.QtGui import (  # type: ignore[import-untyped]
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from mcprojsim.ui.theme import (
    COLOUR_YAML_BOOL,
    COLOUR_YAML_COMMENT,
    COLOUR_YAML_KEY,
    COLOUR_YAML_NUMBER,
    COLOUR_YAML_STRING,
    COLOUR_YAML_TEXT,
)


def _fmt(colour: str, bold: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    return fmt


class YAMLSyntaxHighlighter(QSyntaxHighlighter):
    """Minimal YAML syntax highlighter."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self._build_rules()

    def _build_rules(self) -> None:
        # Comments
        self._rules.append((
            QRegularExpression(r"#[^\n]*"),
            _fmt(COLOUR_YAML_COMMENT),
        ))
        # Keys (word characters followed by colon, possibly quoted)
        self._rules.append((
            QRegularExpression(r'^\s*[\w\-]+\s*(?=:)'),
            _fmt(COLOUR_YAML_KEY, bold=True),
        ))
        # Double-quoted strings
        self._rules.append((
            QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'),
            _fmt(COLOUR_YAML_STRING),
        ))
        # Single-quoted strings
        self._rules.append((
            QRegularExpression(r"'[^']*'"),
            _fmt(COLOUR_YAML_STRING),
        ))
        # Numbers (integer or float)
        self._rules.append((
            QRegularExpression(r'\b-?\d+(\.\d+)?\b'),
            _fmt(COLOUR_YAML_NUMBER),
        ))
        # Booleans and null
        self._rules.append((
            QRegularExpression(r'\b(true|false|yes|no|null|~)\b'),
            _fmt(COLOUR_YAML_BOOL, bold=True),
        ))
        # Unquoted string values (after ': ')
        self._rules.append((
            QRegularExpression(r'(?<=:\s)[A-Za-z][A-Za-z0-9 \-_/\.]*'),
            _fmt(COLOUR_YAML_TEXT),
        ))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
