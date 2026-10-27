import sys
from typing import List

try:
    from errors import compilation_error
except ImportError:
    from src.errors import compilation_error


# ── Emoji & Symbol UTF-8 Table ─────────────────────────────────────────
class EmojiEntry:
    def __init__(self, seq: bytes, kind: str, text: str, codepoint: str, desc: str):
        self.seq = seq
        self.kind = kind
        self.text = text
        self.codepoint = codepoint
        self.desc = desc

    @property
    def utf8_hex(self) -> str:
        return " ".join(f"0x{b:02X}" for b in self.seq)


# Single source of truth for non-ASCII symbols in Duck Lang
EMOJI_UTF8_TABLE: List[EmojiEntry] = [
    EmojiEntry(b"\xF0\x9F\x90\xA5", "typename", "🐥", "U+1F425", "Integer (32-bit)"),
    EmojiEntry(b"\xF0\x9F\xA6\x86", "typename", "🦆", "U+1F986", "Integer (64-bit)"),
    EmojiEntry(b"\xF0\x9F\xA5\x9A", "typename", "🥚", "U+1F95A", "Boolean type"),
    EmojiEntry(b"\xF0\x9F\x8D\x83", "specifier", "🍃", "U+1F343", "Mutable variable"),
    EmojiEntry(b"\xF0\x9F\xAA\xA8", "specifier", "🪨", "U+1FAA8", "Constant variable"),
    EmojiEntry(b"\xF0\x9F\xAA\xBA", "bool_literal", "🪺", "U+1FABA", "Boolean true"),
    EmojiEntry(b"\xF0\x9F\xAA\xB9", "bool_literal", "🪹", "U+1FAB9", "Boolean false"),
    EmojiEntry(b"\xF0\x9F\x90\xA4", "keyword", "🐤", "U+1F424", "If keyword"),
    EmojiEntry(b"\xF0\x9F\xA6\xA2", "keyword", "🦢", "U+1F9A2", "Else keyword"),
    EmojiEntry(b"\xF0\x9F\xAA\xB6", "lbrace", "🪶", "U+1FAB6", "Block open"),
    EmojiEntry(b"\xF0\x9F\xAA\xBD", "rbrace", "🪽", "U+1FABD", "Block close"),
    EmojiEntry(b"\xE2\x89\xA1", "comparison", "≡", "U+2261", "Equal comparison"),
    EmojiEntry(b"\xE2\x89\xA2", "comparison", "≢", "U+2262", "Not equal comparison"),
    EmojiEntry(b"\xF0\x9F\x94\x81", "keyword", "🔁", "U+1F501", "While loop (repeat)"),
    EmojiEntry(b"\xF0\x9F\x94\x80", "swap", "🔀", "U+1F500", "Swap operator"),
    EmojiEntry(b"\xF0\x9F\x94\x8A", "print", "🔊", "U+1F50A", "Print statement (speaker)"),
    EmojiEntry(b"\xF0\x9F\x8F\x81", "statement", "finish", "U+1F3C1", "Finish statement (chequered flag)"),
]

# Sort table entries by sequence length descending
EMOJI_UTF8_TABLE.sort(key=lambda e: len(e.seq), reverse=True)

# Reserved text keywords and their (kind, canonical_text)
KEYWORD_MAP = {
    b"waddle": ("keyword", "🔁"),
    b"finish": ("statement", "finish"),
    b"fly": ("statement", "finish"),
    b"duck32": ("typename", "🐥"),
    b"duck64": ("typename", "🦆"),
    b"pond_bool": ("typename", "🥚"),
    b"hatch": ("specifier", "🍃"),
    b"leaf": ("specifier", "🍃"),
    b"stone": ("specifier", "🪨"),
    b"rock": ("specifier", "🪨"),
    b"nest_full": ("bool_literal", "🪺"),
    b"nest_empty": ("bool_literal", "🪹"),
    b"peck": ("keyword", "🐤"),
    b"swan": ("keyword", "🦢"),
    b"feather": ("lbrace", "🪶"),
    b"wing": ("rbrace", "🪽"),
    b"swap": ("swap", "🔀"),
    b"quack": ("print", "🔊"),
    b"eq": ("comparison", "≡"),
    b"neq": ("comparison", "≢"),
}


class Token:
    def __init__(self, kind: str, text: str, line: int, col: int):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col


def is_alpha(b: int) -> bool:
    return (ord("A") <= b <= ord("Z")) or (ord("a") <= b <= ord("z")) or b == ord("_")


def is_digit(b: int) -> bool:
    return ord("0") <= b <= ord("9")


def is_operator(b: int) -> bool:
    return b in (ord("*"), ord("/"), ord("+"), ord("-"))


def lex(data: bytes) -> List[Token]:
    tokens: List[Token] = []
    line, col = 1, 1
    i = 0
    n = len(data)

    while i < n:
        b = data[i]

        # Whitespace
        if b in (32, 9, 13):  # space, tab, \r
            i += 1
            col += 1
        elif b == 10:  # \n
            line += 1
            col = 1
            i += 1
        # Identifiers and text keywords
        elif is_alpha(b):
            start = i
            start_col = col
            while i < n and (is_alpha(data[i]) or is_digit(data[i])):
                i += 1
                col += 1
            word_bytes = data[start:i]
            if word_bytes in KEYWORD_MAP:
                kind, text = KEYWORD_MAP[word_bytes]
                tokens.append(Token(kind, text, line, start_col))
            else:
                text = word_bytes.decode("ascii")
                tokens.append(Token("ident", text, line, start_col))
        # Number Literals
        elif is_digit(b):
            start = i
            start_col = col
            while i < n and is_digit(data[i]):
                i += 1
                col += 1
            if i < n and is_alpha(data[i]):
                bad_b = data[i]
                char_disp = chr(bad_b) if 32 <= bad_b <= 126 else f"0x{bad_b:02X}"
                compilation_error(line, col, f"unexpected byte '{char_disp}'")
            num_bytes = data[start:i]
            num_str = num_bytes.decode("ascii")
            tokens.append(Token("constant", num_str, line, start_col))
        # Single-byte ASCII punctuation and operators
        elif b == ord("("):
            tokens.append(Token("lparen", "(", line, col))
            i += 1
            col += 1
        elif b == ord(")"):
            tokens.append(Token("rparen", ")", line, col))
            i += 1
            col += 1
        elif b == ord(":"):
            tokens.append(Token("colon", ":", line, col))
            i += 1
            col += 1
        elif b == ord(";"):
            tokens.append(Token("semicolon", ";", line, col))
            i += 1
            col += 1
        elif b == ord("<"):
            if i + 1 < n and data[i + 1] == ord("-"):
                tokens.append(Token("assignment", "<-", line, col))
                i += 2
                col += 2
            else:
                compilation_error(line, col, "unexpected byte '<'")
        elif is_operator(b):
            tokens.append(Token("operator", chr(b), line, col))
            i += 1
            col += 1
        # Multibyte UTF-8 matching via EMOJI_UTF8_TABLE
        elif b >= 128:
            start_col = col
            matched = False
            for entry in EMOJI_UTF8_TABLE:
                if data.startswith(entry.seq, i):
                    tokens.append(Token(entry.kind, entry.text, line, start_col))
                    i += len(entry.seq)
                    col += 1
                    matched = True
                    break

            if not matched:
                # UTF-8 byte sequence error handling
                if 0x80 <= b <= 0xBF:
                    compilation_error(line, col, f"invalid UTF-8 byte 0x{b:02X}")
                elif b == 0xFF or b < 0xC0 or b > 0xF7:
                    compilation_error(line, col, f"invalid UTF-8 byte 0x{b:02X}")

                if 0xC0 <= b <= 0xDF:
                    expected_len = 2
                elif 0xE0 <= b <= 0xEF:
                    expected_len = 3
                elif 0xF0 <= b <= 0xF7:
                    expected_len = 4
                else:
                    expected_len = 1

                if i + expected_len > n:
                    compilation_error(line, col, "truncated UTF-8 sequence at end of file")

                seq_bytes = data[i : i + expected_len]
                for cb in seq_bytes[1:]:
                    if cb < 0x80 or cb > 0xBF:
                        compilation_error(line, col, f"invalid UTF-8 byte 0x{cb:02X}")

                hex_str = " ".join(f"0x{cb:02X}" for cb in seq_bytes)
                compilation_error(line, col, f"unexpected byte sequence {hex_str}")
        else:
            char_disp = chr(b) if 32 <= b <= 126 else f"0x{b:02X}"
            compilation_error(line, col, f"unexpected byte '{char_disp}'")

    return tokens
