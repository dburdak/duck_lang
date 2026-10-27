# 🦆 Duck Lang Compiler (Stage 2: Front End, Semantics & LLVM)

**Duck Lang** is an emoji-based programming language compiled using Python. Its syntax replaces traditional keywords and types with duck-themed emojis and symbols.

- **Grammar Specification:** [`grammar.ebnf`](grammar.ebnf)

## 📐 Stage 2 Semantic Rules

These rules are checked at compile time unless a rule describes runtime output:

1. Every function or method call MUST provide exactly the declared number of arguments. Each argument's type MUST match the type of the corresponding parameter.
2. The expression in every `lay expr;` statement MUST have the declared return type of its function or method.
3. Inside a member function, a name is looked up among the parameters and locals, then the fields, then the globals. The first matching name is used; a name with no matching declaration is an error.
   A global variable is visible in a function or method body only if its declaration appears earlier in the source than that function (or the structure containing the method).
4. A mutating member function (`🍃 hatch`) can only be called on a mutable object (`🍃 obj`), whether or not its body assigns a field. A constant member function (`🪨 hatch`) cannot assign fields of `self` or call mutating methods of `self`.
   A mutating method that never assigns a field is valid and has `assigns_field=False` in its AST output.
5. Assignment through a field chain such as `a.b.c <- value;` requires the base object and every field along the access chain to be mutable (`🍃`).
6. Every `🔀` target MUST be an assignable variable or field. A function or method call result is a temporary, not an lvalue, and cannot be a swap target.
7. Printing an object outputs `TypeName { field: value, ... }`, with fields in declaration order and a trailing newline. Nested objects use the same format.

### Call Argument Count and Types

**Valid:**
```duck
hatch add (a : 🐥, b : 🐥) -> 🐥 🪶
    lay a + b ;
🪽
flock Box 🪶
    🍃 value : 🐥;
    🪨 hatch sum(a : 🐥, b : 🐥) -> 🐥 🪶
        lay a + b ;
    🪽
🪽
🍃 box : Box <- Box { value: 0 };
🍃 total : 🐥 <- add(2, 3) ;
🍃 method_total : 🐥 <- box.sum(2, 3) ;
finish 0 ;
```

**Invalid — wrong argument count and wrong argument type (each call is an error):**
```duck
hatch add (a : 🐥, b : 🐥) -> 🐥 🪶
    lay a + b ;
🪽
flock Box 🪶
    🍃 value : 🐥;
    🪨 hatch sum(a : 🐥, b : 🐥) -> 🐥 🪶
        lay a + b ;
    🪽
🪽
🍃 box : Box <- Box { value: 0 };
🍃 one : 🐥 <- add(2) ;
🍃 two : 🐥 <- box.sum(2, 🪺) ;
finish 0 ;
```
Expected: compilation errors because `add` requires two `🐥` arguments and `sum` requires two `🐥` arguments.

### Return Expression Type

**Valid:**
```duck
hatch size (value : 🐥) -> 🐥 🪶
    lay value + 1 ;
🪽
finish 0 ;
```

**Invalid:**
```duck
hatch size () -> 🐥 🪶
    lay 🪺 ;
🪽
finish 0 ;
```
Expected: compilation error because the returned value is `🥚`, not `🐥`.

### Member-Function Name Lookup

**Valid — the parameter shadows the field, the field shadows the global, and a local shadows the field:**
```duck
🍃 score : 🐥 <- 30 ;
flock Bird 🪶
    🍃 score : 🐥;
    🪨 hatch parameter_wins (score : 🐥) -> 🐥 🪶
        lay score ;
    🪽
    🪨 hatch field_wins () -> 🐥 🪶
        lay score ;
    🪽
    🪨 hatch local_wins () -> 🐥 🪶
        🍃 score : 🐥 <- 99 ;
        score <- score + 1 ;
        lay score ;
    🪽
🪽
🍃 bird : Bird <- Bird { score: 20 };
🔊 bird.parameter_wins(10) ;
🔊 bird.local_wins() ;
🔊 bird.field_wins() ;
🔊 score ;
finish 0 ;
```
The output is `10`, `100`, `20`, `30` on separate lines. The assignment in `local_wins` changes its local `score`, not the field.

**Invalid — `shade` is a `🥚` field, so it is selected before the `🐥` global:**
```duck
🍃 shade : 🐥 <- 1 ;
flock Bird 🪶
    🪨 shade : 🥚;
    🪨 hatch read_shade () -> 🐥 🪶
        lay shade ;
    🪽
🪽
finish 0 ;
```
Expected: compilation error because `lay shade;` resolves to the field of type `🥚`, which does not match the return type `🐥`.

### Member-Function Mutability

**Valid — call a mutating method on a mutable object; a constant method reads its field:**
```duck
flock Counter 🪶
    🍃 value : 🐥;
    🍃 hatch increment () -> 🐥 🪶
        value <- value + 1 ;
        lay value ;
    🪽
    🪨 hatch current () -> 🐥 🪶
        lay value ;
    🪽
🪽
🍃 counter : Counter <- Counter { value: 0 };
🍃 result : 🐥 <- counter.increment() ;
finish 0 ;
```

**Invalid — a constant receiver cannot call a mutating method:**
```duck
flock Counter 🪶
    🍃 value : 🐥;
    🍃 hatch increment () -> 🐥 🪶
        value <- value + 1 ;
        lay value ;
    🪽
🪽
🪨 counter : Counter <- Counter { value: 0 };
🍃 result : 🐥 <- counter.increment() ;
finish 0 ;
```
Expected: compilation error because `counter` is immutable.

**Invalid — a constant member function cannot assign a field or call a mutating method:**
```duck
flock Counter 🪶
    🍃 value : 🐥;
    🍃 hatch increment () -> 🐥 🪶
        value <- value + 1 ;
        lay value ;
    🪽
    🪨 hatch reset () -> 🐥 🪶
        increment() ;
        value <- 0 ;
        lay value ;
    🪽
🪽
finish 0 ;
```
Expected: compilation error because the constant method calls a mutating method; removing that call still leaves an invalid field assignment.

### Mutability Through a Field Chain

**Valid — the base object and each field in the chain are mutable:**
```duck
flock Inner 🪶
    🍃 value : 🐥;
🪽
flock Outer 🪶
    🍃 inner : Inner;
🪽
🍃 outer : Outer <- Outer { inner: Inner { value: 0 } };
outer.inner.value <- 1 ;
finish 0 ;
```

**Invalid — the immutable `inner` field breaks the chain:**
```duck
flock Inner 🪶
    🍃 value : 🐥;
🪽
flock Outer 🪶
    🪨 inner : Inner;
🪽
🍃 outer : Outer <- Outer { inner: Inner { value: 0 } };
outer.inner.value <- 1 ;
🪨 fixed : Outer <- Outer { inner: Inner { value: 0 } };
fixed.inner.value <- 2 ;
finish 0 ;
```
Expected: compilation errors because `outer.inner` is not mutable and `fixed` is an immutable base object.

### Swap Targets

**Valid — both targets are assignable locations:**
```duck
🍃 left : 🐥 <- 1 ;
🍃 right : 🐥 <- 2 ;
left 🔀 right ;
finish 0 ;
```

**Invalid — `next()` produces a temporary value:**
```duck
hatch next () -> 🐥 🪶
    lay 1 ;
🪽
🍃 value : 🐥 <- 2 ;
next() 🔀 value ;
finish 0 ;
```
Expected: compilation error because a function-call result is not an assignable swap target.

### Object Printing

**Valid — output is `Point { x: 3, y: 4 }` followed by a newline:**
```duck
flock Point 🪶
    🍃 x : 🐥;
    🍃 y : 🐥;
🪽
🍃 point : Point <- Point { x: 3, y: 4 };
🔊 point ;
finish 0 ;
```

**Invalid — the printed expression has incompatible arithmetic operands, so it has no printable value type:**
```duck
🔊 🪺 + 1 ;
finish 0 ;
```
Expected: compilation error because arithmetic requires operands of the same integer type; print is not reached with a valid expression.

## 🧩 Stage 2 Syntax Overview

Functions are declared with `hatch`; `lay` returns a value whose type matches the function's declared return type:
```duck
hatch double (value : 🐥) -> 🐥 🪶
    lay value * 2 ;
🪽
```

Structures use `flock`, `🪶`, and `🪽`. Fields use `🍃` when mutable and `🪨` when constant:
```duck
flock Point 🪶
    🍃 x : 🐥;
    🪨 label : 🐥;
🪽
```

Member functions use `🍃 hatch` when mutating and `🪨 hatch` when read-only:
```duck
flock Counter 🪶
    🍃 value : 🐥;
    🍃 hatch increment () -> 🐥 🪶
        value <- value + 1 ;
        lay value ;
    🪽
    🪨 hatch current () -> 🐥 🪶
        lay value ;
    🪽
🪽
```

Objects are instantiated with named field values. Dot notation accesses fields and calls methods:
```duck
🍃 point : Point <- Point { x: 3, label: 0 };
point.x <- 4 ;
flock Counter 🪶
    🍃 value : 🐥;
    🪨 hatch current () -> 🐥 🪶
        lay value ;
    🪽
🪽
🍃 counter : Counter <- Counter { value: 1 };
🍃 next_value : 🐥 <- counter.current() ;
```

`👂 type` (or `read type`) reads an integer of the requested type from standard input. `🔊` (or `quack`) prints a string, expression, or object. Strings support `\n`, `\r`, `\t`, `\\`, and `\"` escapes:
```duck
🍃 count : 🐥 <- 👂 🐥 ;
🔊 count ;
🔊 "A string literal" ;
```

Every `🔊` call appends exactly one trailing newline, including when printing integers, booleans (`true`/`false`), strings, and objects. For example:
```duck
🔊 7 ;
🔊 🪺 ;
🔊 "hello" ;
flock Point 🪶
    🍃 x : 🐥;
🪽
🔊 Point { x: 3 } ;
```
This prints `7\n`, `true\n`, `hello\n`, and `Point { x: 3 }\n`, respectively.

### Тіло звичайної функції

A regular function sees its parameters, its own locals after their declarations, and global variables declared earlier in the source than that function. It can call any function and use any structure declared anywhere in the program, including declarations later in the source. It cannot see local variables of its caller; function bodies do not inherit the caller's scope.

A global declared below a function is not visible in that function:
```duck
hatch read_later () -> 🐥 🪶
    lay later ;
🪽
🍃 later : 🐥 <- 4 ;
```
Expected: `undeclared name 'later'` at its use in `read_later`.

**Valid — the parameter, local, earlier global, later function, and later structure are all visible:**
```duck
🍃 base : 🐥 <- 4 ;
hatch calculate (input : 🐥) -> 🐥 🪶
    🍃 local : 🐥 <- input + base ;
    🍃 box : Box <- Box { value: local };
    lay helper(box.value) ;
🪽
hatch helper (value : 🐥) -> 🐥 🪶
    lay value + 1 ;
🪽
flock Box 🪶
    🍃 value : 🐥;
🪽
```

**Invalid — a callee cannot resolve a local declared only by its caller:**
```duck
hatch caller () -> 🐥 🪶
    🍃 caller_local : 🐥 <- 1 ;
    lay callee() ;
🪽
hatch callee () -> 🐥 🪶
    lay caller_local ;
🪽
```
Expected: `undeclared name 'caller_local'` at its use in `callee`.

---

## 📋 Emoji & Keyword Mapping (UTF-8)

| Requirement | Duck Lang construct | Emoji / Symbol | Text synonym | Code point | UTF-8 hex bytes |
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
| **Function declaration / return** | Keyword / Statement | `hatch` / `lay` | `hatch` / `lay` | ASCII | — |
| **Structure declaration** | Keyword | `flock` | `flock` | ASCII | — |
| **Mutable / constant member** | Field / method specifier | 🍃 / 🪨 | `leaf` / `stone` | `U+1F343` / `U+1FAA8` | See rows above |
| **Read expression** | Built-in | 👂 | `read` | `U+1F442` | `0xF0 0x9F 0x91 0x82` |
| **Function arrow** | Punctuation | `->` | `->` | ASCII | `0x2D 0x3E` |
| **Block Open** | Lbrace | 🪶 | `feather` | `U+1FAB6` | `0xF0 0x9F 0xAA 0xB6` |
| **Block Close** | Rbrace | 🪽 | `wing` | `U+1FABD` | `0xF0 0x9F 0xAA 0xBD` |

---

## 📌 Language Description & Features

### 1. Types
Duck Lang supports three built-in types and user-declared structure types:
- `🐥` / `duck32` — 32-bit Integer (`i32`, range: $-2^{31}$ to $2^{31}-1$, max $2147483647$)
- `🦆` / `duck64` — 64-bit Integer (`i64`, range: $-2^{63}$ to $2^{63}-1$, max $9223372036854775807$)
- `🥚` / `pond_bool` — Boolean (`bool`)
- A declared structure name, such as `Point` — an object with its declared fields and methods.

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

### 7. Program Completion (`finish`)
- Every program MUST end with a top-level `finish` statement followed by an integer expression and `;`.
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

## ⚠️ Stage 2 Integer and Arithmetic Checks

During semantic analysis, a nonnegative integer literal is assigned its contextual `🐥` or `🦆` type and must be in the range `0` through that type's maximum (`2147483647` for `🐥`, `9223372036854775807` for `🦆`). Negative values are written as `0 - n`, and the resulting subtraction is checked at runtime. Signed addition, subtraction, and multiplication use LLVM overflow intrinsics; division checks for zero and the signed minimum divided by `-1`. A runtime arithmetic overflow or invalid division calls the C `abort()` function.

## ⚙ Lexer & Parser Architecture

- **Byte-level Lexing:** The lexer operates directly over source `bytes` without decoding the entire source file. Emojis (`🐥`, `🦆`, `🍃`, `🪶`, etc.) are matched directly against raw UTF-8 byte sequences stored in `EMOJI_UTF8_TABLE`.
- **Hand-written State Machine:** The lexer recognizes Stage 1 and Stage 2 tokens, including strings, arrows, member access, object initializers, functions, structures, and reads.
- **Column Calculation:** Columns are counted in characters (emojis count as 1 column width).
- **Error Position for Missing `finish`:** If a top-level `finish` is missing at end-of-file, the error position is placed immediately after the last token (`line`, `col + len(text)`).
- **Recursive Descent Parser:** One parser function per grammar rule.
- **Semantic Pass:** Before IR generation, the compiler builds symbol tables for global variables, functions, structures, ordered fields, and member functions. It validates declaration scopes, types, return values, calls, field access, mutability, and integer ranges.
- **LLVM Builder:** `llvmlite.ir` builds the module. Checked integer arithmetic branches to `abort()` on signed overflow or invalid division; `printf` and `scanf` are declared as C runtime functions.

---

## 🛠 Building & Running the Compiler

### Install the dependency
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Command Line Interface
`--ast` prints the parsed tree. To compile a program, pass the input and output paths; the IR file is created only after parsing, semantic analysis, and IR generation succeed:

```bash
python3 compiler.py --ast path/to/program.txt
python3 compiler.py path/to/program.txt program.ll
clang program.ll -o program
./program
```

`--ir input.txt` remains available as a legacy form that writes IR to standard output.

`hatch` is both the function-declaration keyword and a text synonym for the mutable-variable specifier `🍃`. At the top level, the parser treats `hatch ident (` as a function declaration; otherwise it parses `hatch` as a variable specifier.

Functions are emitted with a `duck_fn_` prefix; member functions use `duck_method_<Struct>_<name>`. Structures are identified LLVM types, and fields use their declaration-order index for `getelementptr`. Runtime input and output use `scanf` and `printf`.

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

The test suite preserves the Stage 1 AST and lexer/parser error checks, exercises semantic errors with exact line-and-column diagnostics, and runs end-to-end programs through LLVM IR generation, `clang`, and output comparison. `read_input.in` supplies standard input for its corresponding end-to-end test.

### Run Test Suite
```bash
bash tests/run_tests.sh
```