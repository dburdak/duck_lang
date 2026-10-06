# 🦆 Duck Lang

**Duck Lang** is an emoji-based toy programming language compiled using Python. Its syntax replaces traditional keywords and types with duck-themed emojis and duck commands.

---

## 📌 Language Description & Features

### 1. Types
Duck Lang supports three primary data types:
- `🐥` — 32-bit Integer (`i32`)
- `🦆` — 64-bit Integer (`i64`)
- `🥚` — Boolean (`bool`)

**Boolean Literals:**
- `🪺` — `true` (Full Nest)
- `🪹` — `false` (Empty Nest)

### 2. Variable Declarations
Variables are declared as either **mutable** (`🍃`) or **immutable/constant** (`🪨`).

- **Mutable Variable (`🍃`):**
  ```duck
  🍃 count : 🐥 <- 10 ;
  ```
- **Constant Variable (`🪨`):**
  ```duck
  🪨 max_limit : 🦆 <- 1000 ;
  🪨 flag : 🥚 <- 🪺 ;
  ```

### 3. Assignment
Values of existing mutable variables are updated using the `<-` operator:
```duck
count <- count + 1 ;
```

### 4. Expressions & Operators
- **Arithmetic Operators:** `+`, `-`, `*`, `/`
- **Comparison Operators:**
  - `≡` — Equal (`==`)
  - `≢` — Not Equal (`!=`)
- **Parentheses:** `(` and `)` are supported for grouping expressions.

Example:
```duck
🍃 result : 🐥 <- (x + 5) * 2 ;
🍃 is_equal : 🥚 <- x ≡ 42 ;
```

### 5. Control Flow

#### If / Else Statements
- `🐤` — `if` keyword
- `🦢` — `else` keyword
- `🪶` ... `🪽` — Block open (`{`) and block close (`}`)

Example:
```duck
🐤 x ≡ 42 🪶
    x <- x + 1 ;
🪽 🦢 🪶
    x <- 0 ;
🪽
```

#### While Loops
- `waddle` — `while` keyword

Example:
```duck
waddle i ≢ 10 🪶
    i <- i + 1 ;
🪽
```

### 6. Program Completion (`finish`)
Every Duck Lang program must terminate with a `finish` statement specifying the exit status:
```duck
finish 0 ;
```

---

## 🛠 Building & Running the Compiler

### Prerequisites
- Python 3.8+ (no external dependencies required).

### Usage Commands

1. **Tokenize a source file (`--tokens`):**
   ```bash
   python3 src/compiler.py --tokens path/to/program.txt
   ```

2. **Generate and inspect the Abstract Syntax Tree (`--ast`):**
   ```bash
   python3 src/compiler.py --ast path/to/program.txt
   ```

3. **Example Program (`sample.txt`):**
   ```duck
   🍃 x : 🐥 <- 42 ;
   🐤 x ≡ 42 🪶
       x <- x + 1 ;
   🪽
   finish 0 ;
   ```

   **Output (`python3 src/compiler.py --ast sample.txt`):**
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

The test suite includes 38 test cases (20 happy-path valid cases and 18 error-handling invalid cases).

### Run Test Suite
Run the test runner script:
```bash
bash tests/run_tests.sh
```