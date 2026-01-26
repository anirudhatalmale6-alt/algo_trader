"""
Pine Script Parser
Parses Pine Script v5/v6 syntax into executable strategy
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class TokenType(Enum):
    # Literals
    NUMBER = "NUMBER"
    STRING = "STRING"
    BOOL = "BOOL"
    COLOR = "COLOR"

    # Identifiers
    IDENTIFIER = "IDENTIFIER"
    KEYWORD = "KEYWORD"
    BUILTIN_FUNC = "BUILTIN_FUNC"
    BUILTIN_VAR = "BUILTIN_VAR"

    # Operators
    PLUS = "PLUS"
    MINUS = "MINUS"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    MODULO = "MODULO"
    ASSIGN = "ASSIGN"
    COLON_ASSIGN = "COLON_ASSIGN"  # :=
    EQUAL = "EQUAL"
    NOT_EQUAL = "NOT_EQUAL"
    GREATER = "GREATER"
    LESS = "LESS"
    GREATER_EQUAL = "GREATER_EQUAL"
    LESS_EQUAL = "LESS_EQUAL"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    QUESTION = "QUESTION"
    COLON = "COLON"

    # Brackets
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"

    # Other
    COMMA = "COMMA"
    DOT = "DOT"
    NEWLINE = "NEWLINE"
    INDENT = "INDENT"
    ARROW = "ARROW"  # =>
    COMMENT = "COMMENT"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    column: int


@dataclass
class ParsedStrategy:
    """Parsed Pine Script strategy"""
    version: int = 5
    name: str = ""
    description: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    indicators: List[Dict] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    entry_conditions: List[Dict] = field(default_factory=list)
    exit_conditions: List[Dict] = field(default_factory=list)
    raw_script: str = ""


class PineLexer:
    """Tokenizer for Pine Script"""

    KEYWORDS = {
        'if', 'else', 'for', 'while', 'switch', 'case', 'default',
        'var', 'varip', 'const', 'type', 'import', 'export',
        'true', 'false', 'na', 'and', 'or', 'not',
        'strategy', 'indicator', 'library'
    }

    BUILTIN_FUNCTIONS = {
        # Indicator functions
        'ta.sma', 'ta.ema', 'ta.wma', 'ta.vwma', 'ta.rma',
        'ta.rsi', 'ta.macd', 'ta.bb', 'ta.atr', 'ta.tr',
        'ta.stoch', 'ta.cci', 'ta.adx', 'ta.supertrend',
        'ta.vwap', 'ta.highest', 'ta.lowest',
        'ta.crossover', 'ta.crossunder', 'ta.change', 'ta.mom', 'ta.roc',
        # Math functions
        'math.abs', 'math.max', 'math.min', 'math.round', 'math.floor', 'math.ceil',
        'math.sqrt', 'math.pow', 'math.log', 'math.exp',
        # Strategy functions
        'strategy.entry', 'strategy.exit', 'strategy.close',
        'strategy.close_all', 'strategy.cancel', 'strategy.cancel_all',
        'strategy.order',
        # Input functions
        'input', 'input.int', 'input.float', 'input.bool',
        'input.string', 'input.source', 'input.timeframe',
        # Plot functions
        'plot', 'plotshape', 'plotchar', 'bgcolor', 'fill',
        'hline', 'plotcandle', 'plotbar',
        # Alert functions
        'alert', 'alertcondition',
        # Array functions
        'array.new_float', 'array.push', 'array.pop', 'array.get', 'array.set',
        # String functions
        'str.tostring', 'str.format',
        # Request functions
        'request.security',
        # Utility
        'nz', 'na', 'fixnan', 'barssince', 'valuewhen'
    }

    BUILTIN_VARIABLES = {
        'open', 'high', 'low', 'close', 'volume', 'time',
        'hl2', 'hlc3', 'ohlc4', 'hlcc4',
        'bar_index', 'barstate.isfirst', 'barstate.islast',
        'barstate.ishistory', 'barstate.isrealtime', 'barstate.isnew',
        'syminfo.ticker', 'syminfo.tickerid', 'syminfo.mintick',
        'timeframe.period', 'timeframe.multiplier',
        'strategy.position_size', 'strategy.position_avg_price',
        'strategy.equity', 'strategy.netprofit',
        'strategy.long', 'strategy.short',
        'color.red', 'color.green', 'color.blue', 'color.white', 'color.black'
    }

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

    def tokenize(self) -> List[Token]:
        """Convert source code into tokens"""
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break

            char = self.source[self.pos]

            # Comments
            if char == '/' and self._peek(1) == '/':
                self._skip_line_comment()
                continue

            # Newline
            if char == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\n', self.line, self.column))
                self._advance()
                self.line += 1
                self.column = 1
                continue

            # Numbers
            if char.isdigit() or (char == '.' and self._peek(1).isdigit()):
                self._read_number()
                continue

            # Strings
            if char in '"\'':
                self._read_string(char)
                continue

            # Identifiers and keywords
            if char.isalpha() or char == '_':
                self._read_identifier()
                continue

            # Operators and punctuation
            self._read_operator()

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    def _advance(self) -> str:
        char = self.source[self.pos]
        self.pos += 1
        self.column += 1
        return char

    def _peek(self, offset: int = 0) -> str:
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return ''

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
            self._advance()

    def _skip_line_comment(self):
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            self._advance()

    def _read_number(self):
        start = self.pos
        start_col = self.column

        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            self._advance()

        value = self.source[start:self.pos]
        self.tokens.append(Token(
            TokenType.NUMBER,
            float(value) if '.' in value else int(value),
            self.line, start_col
        ))

    def _read_string(self, quote: str):
        start_col = self.column
        self._advance()  # Skip opening quote
        start = self.pos

        while self.pos < len(self.source) and self.source[self.pos] != quote:
            if self.source[self.pos] == '\\':
                self._advance()  # Skip escape char
            self._advance()

        value = self.source[start:self.pos]
        self._advance()  # Skip closing quote

        self.tokens.append(Token(TokenType.STRING, value, self.line, start_col))

    def _read_identifier(self):
        start = self.pos
        start_col = self.column

        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] in '_.'):
            self._advance()

        value = self.source[start:self.pos]

        # Determine token type
        if value in ('true', 'false'):
            token_type = TokenType.BOOL
            value = value == 'true'
        elif value == 'and':
            token_type = TokenType.AND
        elif value == 'or':
            token_type = TokenType.OR
        elif value == 'not':
            token_type = TokenType.NOT
        elif value in self.KEYWORDS:
            token_type = TokenType.KEYWORD
        elif value in self.BUILTIN_FUNCTIONS:
            token_type = TokenType.BUILTIN_FUNC
        elif value in self.BUILTIN_VARIABLES:
            token_type = TokenType.BUILTIN_VAR
        else:
            token_type = TokenType.IDENTIFIER

        self.tokens.append(Token(token_type, value, self.line, start_col))

    def _read_operator(self):
        char = self.source[self.pos]
        start_col = self.column
        next_char = self._peek(1)

        # Two-character operators
        two_char = char + next_char
        two_char_ops = {
            ':=': TokenType.COLON_ASSIGN,
            '==': TokenType.EQUAL,
            '!=': TokenType.NOT_EQUAL,
            '>=': TokenType.GREATER_EQUAL,
            '<=': TokenType.LESS_EQUAL,
            '=>': TokenType.ARROW
        }

        if two_char in two_char_ops:
            self.tokens.append(Token(two_char_ops[two_char], two_char, self.line, start_col))
            self._advance()
            self._advance()
            return

        # Single-character operators
        single_char_ops = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '=': TokenType.ASSIGN,
            '>': TokenType.GREATER,
            '<': TokenType.LESS,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ',': TokenType.COMMA,
            '.': TokenType.DOT,
            ':': TokenType.COLON,
            '?': TokenType.QUESTION
        }

        if char in single_char_ops:
            self.tokens.append(Token(single_char_ops[char], char, self.line, start_col))
            self._advance()
        else:
            # Skip unknown characters
            self._advance()


class PineScriptParser:
    """
    Parser for Pine Script v5/v6
    Converts Pine Script code into a ParsedStrategy object
    """

    def __init__(self):
        self.tokens = []
        self.pos = 0
        self.strategy = ParsedStrategy()

    def parse(self, source: str) -> ParsedStrategy:
        """Parse Pine Script source code"""
        self.strategy = ParsedStrategy()
        self.strategy.raw_script = source

        # Tokenize
        lexer = PineLexer(source)
        self.tokens = lexer.tokenize()
        self.pos = 0

        try:
            self._parse_script()
            logger.info(f"Parsed strategy: {self.strategy.name}")
            return self.strategy
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return None

    def _current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, None, 0, 0)

    def _advance(self) -> Token:
        token = self._current()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        token = self._current()
        if token.type != token_type:
            raise SyntaxError(f"Expected {token_type}, got {token.type} at line {token.line}")
        return self._advance()

    def _skip_newlines(self):
        while self._current().type == TokenType.NEWLINE:
            self._advance()

    def _parse_script(self):
        """Parse the entire script"""
        self._skip_newlines()

        # Parse version indicator
        if self._current().type == TokenType.DIVIDE:
            self._parse_version()

        while self._current().type != TokenType.EOF:
            self._skip_newlines()
            if self._current().type == TokenType.EOF:
                break

            token = self._current()

            # Parse strategy/indicator declaration
            if token.type == TokenType.KEYWORD and token.value in ('strategy', 'indicator'):
                self._parse_declaration()

            # Parse variable declarations
            elif token.type == TokenType.KEYWORD and token.value == 'var':
                self._parse_var_declaration()

            # Parse input declarations
            elif token.type == TokenType.BUILTIN_FUNC and token.value.startswith('input'):
                self._parse_input()

            # Parse strategy entries/exits
            elif token.type == TokenType.BUILTIN_FUNC and token.value.startswith('strategy.'):
                self._parse_strategy_call()

            # Parse indicator calculations
            elif token.type == TokenType.BUILTIN_FUNC and token.value.startswith('ta.'):
                self._parse_indicator_call()

            # Parse conditionals
            elif token.type == TokenType.KEYWORD and token.value == 'if':
                self._parse_if_statement()

            # Parse variable assignments
            elif token.type == TokenType.IDENTIFIER:
                self._parse_assignment()

            else:
                self._advance()

    def _parse_version(self):
        """Parse //@version=5"""
        self._advance()  # skip /
        self._advance()  # skip /
        # Skip to end of line
        while self._current().type != TokenType.NEWLINE and self._current().type != TokenType.EOF:
            token = self._current()
            if token.type == TokenType.NUMBER:
                self.strategy.version = int(token.value)
            self._advance()

    def _parse_declaration(self):
        """Parse strategy() or indicator() declaration"""
        token = self._advance()  # strategy or indicator
        self._expect(TokenType.LPAREN)

        # Parse parameters
        while self._current().type != TokenType.RPAREN:
            if self._current().type == TokenType.STRING:
                # First string is usually the title
                if not self.strategy.name:
                    self.strategy.name = self._current().value
            self._advance()
            if self._current().type == TokenType.COMMA:
                self._advance()

        self._expect(TokenType.RPAREN)

    def _parse_var_declaration(self):
        """Parse var declarations"""
        self._advance()  # skip 'var'
        name = self._expect(TokenType.IDENTIFIER).value
        self._expect(TokenType.ASSIGN)
        value = self._parse_expression()
        self.strategy.variables[name] = value

    def _parse_input(self):
        """Parse input declarations"""
        input_type = self._advance().value  # input, input.int, etc.
        self._expect(TokenType.LPAREN)

        params = {}
        while self._current().type != TokenType.RPAREN:
            if self._current().type == TokenType.IDENTIFIER:
                param_name = self._advance().value
                if self._current().type == TokenType.ASSIGN:
                    self._advance()
                    params[param_name] = self._parse_expression()
            elif self._current().type in (TokenType.NUMBER, TokenType.STRING, TokenType.BOOL):
                # Positional parameter
                if 'defval' not in params:
                    params['defval'] = self._advance().value
                else:
                    self._advance()
            else:
                self._advance()

            if self._current().type == TokenType.COMMA:
                self._advance()

        self._expect(TokenType.RPAREN)

        # Extract input name and store
        input_name = params.get('title', f'input_{len(self.strategy.inputs)}')
        self.strategy.inputs[input_name] = params

    def _parse_strategy_call(self):
        """Parse strategy.entry, strategy.exit, etc."""
        func_name = self._advance().value
        self._expect(TokenType.LPAREN)

        params = {}
        while self._current().type != TokenType.RPAREN:
            if self._current().type == TokenType.IDENTIFIER:
                param_name = self._advance().value
                if self._current().type == TokenType.ASSIGN:
                    self._advance()
                    params[param_name] = self._parse_expression()
            elif self._current().type == TokenType.STRING:
                if 'id' not in params:
                    params['id'] = self._advance().value
                else:
                    self._advance()
            else:
                self._advance()

            if self._current().type == TokenType.COMMA:
                self._advance()

        self._expect(TokenType.RPAREN)

        # Store entry/exit conditions
        if 'entry' in func_name:
            self.strategy.entry_conditions.append({
                'function': func_name,
                'params': params
            })
        elif 'exit' in func_name or 'close' in func_name:
            self.strategy.exit_conditions.append({
                'function': func_name,
                'params': params
            })

    def _parse_indicator_call(self):
        """Parse ta.sma, ta.ema, etc."""
        func_name = self._advance().value
        self._expect(TokenType.LPAREN)

        params = []
        while self._current().type != TokenType.RPAREN:
            params.append(self._parse_expression())
            if self._current().type == TokenType.COMMA:
                self._advance()

        self._expect(TokenType.RPAREN)

        self.strategy.indicators.append({
            'function': func_name,
            'params': params
        })

        return {'function': func_name, 'params': params}

    def _parse_if_statement(self):
        """Parse if statements"""
        self._advance()  # skip 'if'
        condition = self._parse_expression()

        # Store condition
        cond_name = f'condition_{len(self.strategy.conditions)}'
        self.strategy.conditions[cond_name] = condition

    def _parse_assignment(self):
        """Parse variable assignments"""
        name = self._advance().value

        if self._current().type in (TokenType.ASSIGN, TokenType.COLON_ASSIGN):
            self._advance()
            value = self._parse_expression()
            self.strategy.variables[name] = value

    def _parse_expression(self) -> Any:
        """Parse an expression"""
        return self._parse_ternary()

    def _parse_ternary(self) -> Any:
        """Parse ternary expression (a ? b : c)"""
        condition = self._parse_or()

        if self._current().type == TokenType.QUESTION:
            self._advance()
            true_val = self._parse_expression()
            self._expect(TokenType.COLON)
            false_val = self._parse_expression()
            return {'ternary': True, 'condition': condition, 'true': true_val, 'false': false_val}

        return condition

    def _parse_or(self) -> Any:
        left = self._parse_and()
        while self._current().type == TokenType.OR:
            self._advance()
            right = self._parse_and()
            left = {'op': 'or', 'left': left, 'right': right}
        return left

    def _parse_and(self) -> Any:
        left = self._parse_comparison()
        while self._current().type == TokenType.AND:
            self._advance()
            right = self._parse_comparison()
            left = {'op': 'and', 'left': left, 'right': right}
        return left

    def _parse_comparison(self) -> Any:
        left = self._parse_additive()

        comp_ops = {
            TokenType.EQUAL: '==',
            TokenType.NOT_EQUAL: '!=',
            TokenType.GREATER: '>',
            TokenType.LESS: '<',
            TokenType.GREATER_EQUAL: '>=',
            TokenType.LESS_EQUAL: '<='
        }

        while self._current().type in comp_ops:
            op = comp_ops[self._advance().type]
            right = self._parse_additive()
            left = {'op': op, 'left': left, 'right': right}

        return left

    def _parse_additive(self) -> Any:
        left = self._parse_multiplicative()

        while self._current().type in (TokenType.PLUS, TokenType.MINUS):
            op = '+' if self._current().type == TokenType.PLUS else '-'
            self._advance()
            right = self._parse_multiplicative()
            left = {'op': op, 'left': left, 'right': right}

        return left

    def _parse_multiplicative(self) -> Any:
        left = self._parse_unary()

        while self._current().type in (TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            if self._current().type == TokenType.MULTIPLY:
                op = '*'
            elif self._current().type == TokenType.DIVIDE:
                op = '/'
            else:
                op = '%'
            self._advance()
            right = self._parse_unary()
            left = {'op': op, 'left': left, 'right': right}

        return left

    def _parse_unary(self) -> Any:
        if self._current().type == TokenType.MINUS:
            self._advance()
            return {'op': 'neg', 'value': self._parse_unary()}
        if self._current().type == TokenType.NOT:
            self._advance()
            return {'op': 'not', 'value': self._parse_unary()}

        return self._parse_primary()

    def _parse_primary(self) -> Any:
        token = self._current()

        # Number
        if token.type == TokenType.NUMBER:
            self._advance()
            return token.value

        # String
        if token.type == TokenType.STRING:
            self._advance()
            return token.value

        # Boolean
        if token.type == TokenType.BOOL:
            self._advance()
            return token.value

        # Built-in variable
        if token.type == TokenType.BUILTIN_VAR:
            self._advance()
            return {'var': token.value}

        # Built-in function
        if token.type == TokenType.BUILTIN_FUNC:
            return self._parse_indicator_call()

        # Identifier
        if token.type == TokenType.IDENTIFIER:
            name = self._advance().value
            # Check for function call
            if self._current().type == TokenType.LPAREN:
                return self._parse_function_call(name)
            # Check for array access
            if self._current().type == TokenType.LBRACKET:
                self._advance()
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET)
                return {'var': name, 'index': index}
            return {'var': name}

        # Parenthesized expression
        if token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr

        # Unknown - skip
        self._advance()
        return None

    def _parse_function_call(self, name: str) -> Dict:
        """Parse function call"""
        self._expect(TokenType.LPAREN)
        params = []

        while self._current().type != TokenType.RPAREN:
            params.append(self._parse_expression())
            if self._current().type == TokenType.COMMA:
                self._advance()

        self._expect(TokenType.RPAREN)
        return {'function': name, 'params': params}
