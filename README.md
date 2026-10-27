# 🦆 Duck Lang Compiler (Stage 1: Lexer & Parser)

**Duck Lang** is an emoji-based programming language compiled using Python. Its syntax replaces traditional keywords and types with duck-themed emojis and symbols.

- **Grammar Specification:** [`grammar.ebnf`](grammar.ebnf)

---

## 📋 Emoji & Keyword Mapping (UTF-8)

| Вимога з ТЗ | Конструкція Duck Lang | Emoji / Symbol | Text Synonym | Code Point | UTF-8 Hex Bytes |
| --- | --- | --- | --- | --- | --- |
| **Integer (32-bit)** | Typename | 🐥 | `duck32` | `U+1F425` | `0xF0 0x9F 0x90 0xA5` |
| **Integer (64-bit)** | Typename | 🦆 | `duck64` | `U+1F986` | `0xF0 0x9F 0xA6 0x86` |
| **Boolean type** | Typename | 🥚 | `pond_bool` | `U+1F95A` | `0xF0 0x9F 0xA5 0x9A` |
| **Boolean true** | Bool literal | 🪺 | `nest_full` | `U+1FABA` | `0xF0 0x9F 0xAA 0xBA` |
| **Boolean false** | Bool literal | 🪹 | `nest_empty` | `U+1FAB9` | `0xF0 0x9F 0xAA 0xB9` |
| **Mutable variable** | Specifier | 🍃 | `hatch` / `leaf` | `U+1F343` | `0xF0 0x9F 0x8D 0x83` |
| **Constant (immutable)** | Specifier | 🪨 | `stone` / `rock` | `U+1FAA8` | `0xF0 0x9F 0xAA 0xA8` |
| **Assignment** | Operator | `<-` | `<-` | ASCII | `0x3C 0x2D` |
| **Swap** | Operator | 🔀 | `swap` | `U+1F500` | `0xF0 0x9F 0x94 0x80` |
| **Print Statement** | Statement | 🔊 | `quack` | `U+1F50A` | `0xF0 0x9F 0x94 0x8A` |
| **Comparison (Equal)** | Comparison | ≡ | `eq` | `U+2261` | `0xE2 0x89 0xA1` |
| **Comparison (Not Eq)** | Comparison | ≢ | `neq` | `U+2262` | `0xE2 0x89 0xA2` |
| **If Keyword** | Keyword | 🐤 | `peck` | `U+1F424` | `0xF0 0x9F 0x90 0xA4` |
| **Else Keyword** | Keyword | 🦢 | `swan` | `U+1F9A2` | `0xF0 0x9F 0xA6 0xA2` |
| **While Keyword** | Keyword | 🔁 | `waddle` | `U+1F501` | `0xF0 0x9F 0x94 0x81` |
| **Finish Statement** | Statement | 🏁 | `finish` / `fly` | `U+1F3C1` | `0xF0 0x9F 0x8F 0x81` |
| **Block Open** | Lbrace | 🪶 | `feather` | `U+1FAB6` | `0xF0 0x9F 0xAA 0xB6` |
| **Block Close** | Rbrace | 🪽 | `wing` | `U+1FABD` | `0xF0 0x9F 0xAA 0xBD` |

---

## 📌 Language Description & Features

### 1. Types
Duck Lang supports three data types:
- `🐥` / `duck32` — 32-bit Integer (`i32`, range: $-2^{31}$ to $2^{31}-1$, max $2147483647$)
- `🦆` / `duck64` — 64-bit Integer (`i64`, range: $-2^{63}$ to $2^{63}-1$, max $9223372036854775807$)
- `🥚` / `pond_bool` — Boolean (`bool`)

**Boolean Literals:**
- `🪺` / `nest_full` — `true` (Full Nest)
- `🪹` / `nest_empty` — `false` (Empty Nest)

### 2. Variable Declarations
Variables are declared as either **mutable** (`🍃` / `hatch`) or **immutable/constant** (`🪨` / `stone`):
```duck
🍃 count : 🐥 <- 10 ;
🪨 max_limit : 🦆 <- 9223372036854775807 ;
🪨 flag : 🥚 <- 🪺 ;
finish 0 ;
```

### 3. Assignment & Swap Statements
- **Assignment (`<-`):**
  ```duck
  🍃 count : 🐥 <- 0 ;
  count <- count + 1 ;
  ```
- **Swap & Rotation (`🔀` / `swap`):**
  Swap two variables or rotate multiple variables:
  ```duck
  a 🔀 b ;
  a 🔀 b 🔀 c ;
  ```
  In a chained swap `a 🔀 b 🔀 c ;`, values rotate: `a` gets `b`, `b` gets `c`, and `c` gets the previous value of `a`.

### 4. Print Statement (`🔊` / `quack`)
Outputs the result of an expression:
```duck
🔊 count + 1 ;
quack flag ;
```

### 5. Expressions & Operators
- **Arithmetic Operators:** `+`, `-`, `*`, `/`
- **Comparison Operators:** `≡` / `eq` (equal), `≢` / `neq` (not equal)
- **Parentheses:** `(` and `)` for grouping expressions.

Example:
```duck
🍃 result : 🐥 <- (x + 5) * 2 ;
🍃 is_equal : 🥚 <- x ≡ 42 ;
finish 0 ;
```

### 6. Control Flow
- `🐤` / `peck` ... `🪶` ... `🪽` `🦢` / `swan` — `if` / `else` conditional blocks (`🪶` / `feather` opens, `🪽` / `wing` closes)
- `🔁` / `waddle` ... `🪶` ... `🪽` — `while` loop

Example:
```duck
🍃 x : 🐥 <- 0 ;
🐤 x ≡ 0 🪶
    x <- 1 ;
🪽 🦢 🪶
    x <- 2 ;
🪽
waddle x ≢ 10 🪶
    x <- x + 1 ;
🪽
finish x ;
```

### 6. Program Completion (`finish`)
- Every program MUST end with a top-level `finish` statement followed by an exit operand and `;`.
- No statements are allowed after the final top-level `finish`.
- `finish` statements may also be placed inside blocks (`🪶` ... `🪽`).

```duck
finish 0 ;
```

---

## 🔢 Integer Literal Overflow Checks (Stage 1)

In Duck Lang (Stage 1), integer literal bounds are checked at the parser level during variable declarations (`parse_decl`):

1. **Syntax Check for 🐥 (`i32` Declarations):**
   When initializing a `🐥` (`i32`) variable (with `🍃` or `🪨`) using a bare integer literal exceeding `2147483647`, a syntax error is raised:
   ```text
   compilation error: line L:C: integer literal N is out of range for 🐥 (i32 max 2147483647)
   ```

2. **Syntax Check for 🦆 (`i64` Declarations):**
   When initializing a `🦆` (`i64`) variable (with `🍃` or `🪨`) using a bare integer literal exceeding `9223372036854775807`, a syntax error is raised:
   ```text
   compilation error: line L:C: integer literal N is out of range for 🦆 (i64 max 9223372036854775807)
   ```

---

## 🚫 Semantics Deferred to Stage 2

The following semantic checks are intentionally **not performed in Stage 1** and will be implemented in Stage 2:
- Integer literal overflow in `finish` statements, assignments, and complex expressions (e.g. `finish 99999999999999999999 ;`).
- Assigning to immutable (`🪨`) variables.
- Variable re-declaration in the same scope.
- Use of undeclared variables.
- Type checking (e.g. assigning boolean expression to `🐥` variable, or using `🐥` in `if` condition).
- Runtime or static arithmetic result overflow (e.g. `2000000000 + 2000000000`).

---

## ⚙ Lexer & Parser Architecture

- **Byte-level Lexing:** The lexer operates directly over source `bytes` without decoding the entire source file. Emojis (`🐥`, `🦆`, `🍃`, `🪶`, etc.) are matched directly against raw UTF-8 byte sequences stored in `EMOJI_UTF8_TABLE`.
- **Column Calculation:** Columns are counted in characters (emojis count as 1 column width).
- **Error Position for Missing `finish`:** If a top-level `finish` is missing at end-of-file, the error position is placed immediately after the last token (`line`, `col + len(text)`).
- **Recursive Descent Parser:** One parser function per grammar rule.

---

## 🛠 Building & Running the Compiler

### Command Line Interface
The compiler requires the `--ast` flag:

```bash
python3 src/compiler.py --ast path/to/program.txt
```

#### Example Usage:
Given `sample.txt`:
```duck
🍃 x : 🐥 <- 42 ;
🐤 x ≡ 42 🪶
    x <- x + 1 ;
🪽
finish 0 ;
```

Output:
```text
Program
  Decl x 🐥 mut
    Const 42
  If
    BinOp ≡
      Var x
      Const 42
    Block
      Assign x
        BinOp +
          Var x
          Const 1
  Exit
    Const 0
```

---

## 🧪 Running Tests

The test suite validates both valid AST generation and exact single-line error output for syntax/lexical errors.

### Run Test Suite
```bash
bash tests/run_tests.sh
```