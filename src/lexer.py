from typing import List

try:
    from errors import compilation_error
except ImportError:
    from src.errors import compilation_error


class EmojiEntry:
    def __init__(self, seq: bytes, kind: str, text: str, codepoint: str, desc: str):
        self.seq = seq
        self.kind = kind
        self.text = text
        self.codepoint = codepoint
        self.desc = desc


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
    EmojiEntry(b"\xF0\x9F\x94\x81", "keyword", "🔁", "U+1F501", "While loop"),
    EmojiEntry(b"\xF0\x9F\x94\x80", "swap", "🔀", "U+1F500", "Swap operator"),
    EmojiEntry(b"\xF0\x9F\x94\x8A", "print", "🔊", "U+1F50A", "Print statement"),
    EmojiEntry(b"\xF0\x9F\x91\x82", "read", "👂", "U+1F442", "Read expression"),
    EmojiEntry(b"\xF0\x9F\x8F\x81", "statement", "finish", "U+1F3C1", "Finish statement"),
]

EMOJI_UTF8_TABLE.sort(key=lambda entry: len(entry.seq), reverse=True)

KEYWORD_MAP = {
    b"waddle": ("keyword", "🔁"),
    b"finish": ("statement", "finish"),
    b"fly": ("statement", "finish"),
    b"duck32": ("typename", "🐥"),
    b"duck64": ("typename", "🦆"),
    b"pond_bool": ("typename", "🥚"),
    b"hatch": ("hatch", "hatch"),
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
    b"flock": ("flock", "flock"),
    b"lay": ("lay", "lay"),
    b"read": ("read", "read"),
}


class Token:
    def __init__(self, kind: str, text: str, line: int, col: int, value=None):
        self.kind = kind
        self.text = text
        self.line = line
        self.col = col
        self.value = value


def is_alpha(byte: int) -> bool:
    return ord("A") <= byte <= ord("Z") or ord("a") <= byte <= ord("z") or byte == ord("_")


def is_digit(byte: int) -> bool:
    return ord("0") <= byte <= ord("9")


def is_operator(byte: int) -> bool:
    return byte in (ord("*"), ord("/"), ord("+"), ord("-"))


def utf8_text(data: bytes) -> str:
    characters = []
    index = 0
    while index < len(data):
        first = data[index]
        if first < 0x80:
            codepoint = first
            width = 1
        elif first <= 0xDF:
            codepoint = first & 0x1F
            width = 2
        elif first <= 0xEF:
            codepoint = first & 0x0F
            width = 3
        else:
            codepoint = first & 0x07
            width = 4
        for continuation in data[index + 1 : index + width]:
            codepoint = (codepoint << 6) | (continuation & 0x3F)
        characters.append(chr(codepoint))
        index += width
    return "".join(characters)


def lex(data: bytes) -> List[Token]:
    tokens: List[Token] = []
    line, col = 1, 1
    i = 0
    size = len(data)

    while i < size:
        byte = data[i]
        if byte in (32, 9, 13):
            i += 1
            col += 1
        elif byte == 10:
            line += 1
            col = 1
            i += 1
        elif is_alpha(byte):
            start, start_col = i, col
            while i < size and (is_alpha(data[i]) or is_digit(data[i])):
                i += 1
                col += 1
            word = data[start:i]
            if word in KEYWORD_MAP:
                kind, text = KEYWORD_MAP[word]
                tokens.append(Token(kind, text, line, start_col))
            else:
                text = word.decode("ascii")
                tokens.append(Token("ident", text, line, start_col))
        elif is_digit(byte):
            start, start_col = i, col
            while i < size and is_digit(data[i]):
                i += 1
                col += 1
            if i < size and is_alpha(data[i]):
                bad = data[i]
                shown = chr(bad) if 32 <= bad <= 126 else f"0x{bad:02X}"
                compilation_error(line, col, f"unexpected byte '{shown}'")
            text = data[start:i].decode("ascii")
            tokens.append(Token("constant", text, line, start_col))
        elif byte == ord('"'):
            start, start_col = i, col
            i += 1
            col += 1
            value = bytearray()
            while i < size and data[i] != ord('"'):
                if data[i] in (10, 13):
                    compilation_error(line, start_col, "unterminated string literal")
                if data[i] == ord("\\") and i + 1 < size:
                    value.extend(data[i : i + 2])
                    i += 2
                    col += 2
                elif data[i] >= 128:
                    first = data[i]
                    width = 2 if first <= 0xDF else 3 if first <= 0xEF else 4
                    if i + width > size or any(not 0x80 <= part <= 0xBF for part in data[i + 1 : i + width]):
                        compilation_error(line, col, "invalid UTF-8 byte in string literal")
                    value.extend(data[i : i + width])
                    i += width
                    col += 1
                else:
                    value.append(data[i])
                    i += 1
                    col += 1
            if i >= size:
                compilation_error(line, start_col, "unterminated string literal")
            i += 1
            col += 1
            shown = utf8_text(data[start:i])
            tokens.append(Token("string", shown, line, start_col, bytes(value)))
        elif byte == ord("("):
            tokens.append(Token("lparen", "(", line, col))
            i += 1
            col += 1
        elif byte == ord(")"):
            tokens.append(Token("rparen", ")", line, col))
            i += 1
            col += 1
        elif byte == ord(":"):
            tokens.append(Token("colon", ":", line, col))
            i += 1
            col += 1
        elif byte == ord(";"):
            tokens.append(Token("semicolon", ";", line, col))
            i += 1
            col += 1
        elif byte == ord(","):
            tokens.append(Token("comma", ",", line, col))
            i += 1
            col += 1
        elif byte == ord("."):
            tokens.append(Token("dot", ".", line, col))
            i += 1
            col += 1
        elif byte == ord("{"):
            tokens.append(Token("object_lbrace", "{", line, col))
            i += 1
            col += 1
        elif byte == ord("}"):
            tokens.append(Token("object_rbrace", "}", line, col))
            i += 1
            col += 1
        elif byte == ord("<"):
            if i + 1 < size and data[i + 1] == ord("-"):
                tokens.append(Token("assignment", "<-", line, col))
                i += 2
                col += 2
            else:
                compilation_error(line, col, "unexpected byte '<'")
        elif byte == ord("-") and i + 1 < size and data[i + 1] == ord(">"):
            tokens.append(Token("arrow", "->", line, col))
            i += 2
            col += 2
        elif is_operator(byte):
            tokens.append(Token("operator", chr(byte), line, col))
            i += 1
            col += 1
        elif byte >= 128:
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
                if 0x80 <= byte <= 0xBF or byte == 0xFF or byte < 0xC0 or byte > 0xF7:
                    compilation_error(line, col, f"invalid UTF-8 byte 0x{byte:02X}")
                width = 2 if byte <= 0xDF else 3 if byte <= 0xEF else 4
                if i + width > size:
                    compilation_error(line, col, "truncated UTF-8 sequence at end of file")
                sequence = data[i : i + width]
                for continuation in sequence[1:]:
                    if continuation < 0x80 or continuation > 0xBF:
                        compilation_error(line, col, f"invalid UTF-8 byte 0x{continuation:02X}")
                hex_text = " ".join(f"0x{part:02X}" for part in sequence)
                compilation_error(line, col, f"unexpected byte sequence {hex_text}")
        else:
            shown = chr(byte) if 32 <= byte <= 126 else f"0x{byte:02X}"
            compilation_error(line, col, f"unexpected byte '{shown}'")

    return tokens
