# Smalipatcher - Documentation

## Overview

Smalipatcher is a utility for applying and generating patches for Android smali files. It supports comprehensive operations including method manipulation, field management, and context-based code patching.

---

## Installation

```bash
# Clone or download the files
# Ensure you have Python 3.7+
python3 --version

# Make scripts executable (Linux/Mac)
chmod +x smalipatcher.py
chmod +x smalipatch-generator.py
```

---

## Tool 1: smalipatcher.py (Apply Patches)

### Basic Usage

```bash
# Apply patches to smali files
python3 smalipatcher.py <work_dir> <patch_file> [options]

# Examples:
python3 smalipatcher.py ./app patches/mybundle.smalipatch
python3 smalipatcher.py ./decompiled patches/fix.smalipatch --skip-failed
python3 smalipatcher.py ./app patches/test.smalipatch --dry-run --verbose
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `--skip-failed` | Continue applying patches even if one fails |
| `--dry-run` | Preview changes without modifying files |
| `--verbose, -v` | Show detailed debug information |
| `--quiet, -q` | Only show errors |
| `--version` | Show version information |

### Exit Codes

- `0`: All patches applied successfully
- `1`: One or more patches failed
- `2`: Invalid arguments or file not found

---

## Tool 2: smalipatch-generator.py (Create Patches)

### For now , its for single files

```bash
# Usage
python3 smalipatch-generator.py MainActivity.smali

# Workflow:
# 1. Script creates backup
# 2. You modify the file
# 3. Press ENTER
# 4. Script generates .smalipatch

# Specify custom output
python3 smalipatch-generator.py MainActivity.smali my-changes.smalipatch
```

### Directory Comparison 

```bash
# Compare two directories and generate comprehensive patch
python3 smalipatch-generator.py --dir original/ modified/ output.smalipatch

# This will detect:
# - New files (CREATE)
# - Removed files (REMOVE)
# - Modified files (PATCH/REPLACE/etc.)
# - Added/removed methods and fields
```

---

## Patch File Format (.smalipatch)

### Structure

```
CREDIT Author Name
CREDIT Another Contributor

FILE path/to/File.smali
    ACTION1
    ACTION2
    ...
END

CREATE path/to/NewFile.smali
    .class public LNewClass;
    .super Ljava/lang/Object;
    ...

REMOVE path/to/OldFile.smali
```

### Available Actions

#### 1. PATCH (Context-Based Changes)

Used for in-method modifications with surrounding context.

```
FILE com/example/MainActivity.smali

PATCH .method public onCreate(Landroid/os/Bundle;)V
  .locals 1
  invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
- const-string v0, "Hello"
+ const-string v0, "Hello World"
  invoke-static {v0}, Landroid/util/Log;->d(Ljava/lang/String;)I
END
```

**Syntax:**
- Lines starting with `  ` (space space): Context (must match)
- Lines starting with `- `: Remove this line
- Lines starting with `+ `: Add this line

#### 2. REPLACE (Replace Entire Method)

Replace complete method body (excluding `.method` and `.end method`).

```
FILE com/example/Utils.smali

REPLACE .method public static getValue()I
    .locals 1
    const/4 v0, 0x2a
    return v0
.end method

END
```

#### 3. CREATE_METHOD (Add New Method)

Insert a complete new method before `.end class`.

```
FILE com/example/MainActivity.smali

CREATE_METHOD
.method private myNewMethod()V
    .locals 2
    const-string v0, "TAG"
    const-string v1, "New method"
    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method

END
```

#### 4. REMOVE_METHOD (Delete Method)

Remove entire method by signature.

```
FILE com/example/MainActivity.smali

REMOVE_METHOD .method private oldMethod()V

END
```

#### 5. ADD_FIELD (Add Class Field)

Add static or instance fields to the class.

```
FILE com/example/MainActivity.smali

ADD_FIELD
.field private static TAG:Ljava/lang/String; = "MainActivity"

ADD_FIELD
.field private myCounter:I

END
```

**Insertion Logic:**
- Inserts after last existing `.field` declaration
- If no fields exist, inserts before first `.method`
- If no methods, inserts after `.super`

#### 6. REMOVE_FIELD (Delete Field)

Remove field by name.

```
FILE com/example/MainActivity.smali

REMOVE_FIELD oldField

END
```

#### 7. CREATE (Create New File)

Create completely new smali file.

```
CREATE com/example/NewClass.smali
.class public Lcom/example/NewClass;
.super Ljava/lang/Object;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method
```

#### 8. REMOVE (Delete File)

Remove entire file.

```
REMOVE com/example/OldClass.smali
```

#### 9. FIND_REPLACE

Replaces all matching and unique titles and strings that exist in apk/jar.

```
FIND_REPLACE "Hello World" "Bye World"
```

#### 10. CREDIT (Attribution)

Add credits at the top of patch file.

```
CREDIT John Doe - Original patch author
CREDIT Jane Smith - Bug fixes and improvements
```


---

## Complete Examples

### Example 1: Simple Method Modification

**Original MainActivity.smali:**
```smali
.method public onCreate(Landroid/os/Bundle;)V
    .locals 2
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
    const-string v0, "TAG"
    const-string v1, "Original message"
    invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method
```

**Patch (changes.smalipatch):**
```
CREDIT Your Name

FILE com/example/MainActivity.smali

PATCH .method public onCreate(Landroid/os/Bundle;)V
  .locals 2
  invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
  const-string v0, "TAG"
- const-string v1, "Original message"
+ const-string v1, "Modified message"
  invoke-static {v0, v1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

END
```

**Apply:**
```bash
python3 smalipatcher.py ./app changes.smalipatch
```

---

### Example 2: Add Static Field and Method

**Patch:**
```
FILE com/example/Utils.smali

ADD_FIELD
.field private static counter:I

CREATE_METHOD
.method public static incrementCounter()V
    .locals 2
    sget v0, Lcom/example/Utils;->counter:I
    add-int/lit8 v0, v0, 0x1
    sput v0, Lcom/example/Utils;->counter:I
    return-void
.end method

END
```

---

### Example 3: Replace Method Completely

**Patch:**
```
FILE com/example/Calculator.smali

REPLACE .method public add(II)I
    .locals 1
    add-int v0, p1, p2
    mul-int/lit8 v0, v0, 0x2
    return v0

END
```

---

### Example 4: Complex Multi-Action Patch

**Patch:**
```
CREDIT Developer Name
CREDIT Testing Team

FILE com/example/MainActivity.smali

ADD_FIELD
.field private static DEBUG:Z = true

REMOVE_METHOD .method private oldDebugMethod()V

CREATE_METHOD
.method private newDebugMethod(Ljava/lang/String;)V
    .locals 2
    sget-boolean v0, Lcom/example/MainActivity;->DEBUG:Z
    if-eqz v0, :cond_0
    const-string v1, "DEBUG"
    invoke-static {v1, p1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I
    :cond_0
    return-void
.end method

PATCH .method public onCreate(Landroid/os/Bundle;)V
  .locals 1
  invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V
+ const-string v0, "Activity created"
+ invoke-direct {p0, v0}, Lcom/example/MainActivity;->newDebugMethod(Ljava/lang/String;)V
  return-void

END
```

---

## Best Practices

### 1. Context in PATCH Operations

Always provide sufficient context (3-5 lines) around changes:

**Good:**
```
PATCH .method public myMethod()V
  .locals 2
  const-string v0, "before"
- const-string v1, "old"
+ const-string v1, "new"
  invoke-static {v0, v1}, ...
  return-void
```

**Bad (too little context):**
```
PATCH .method public myMethod()V
- const-string v1, "old"
+ const-string v1, "new"
```

### 2. Use Appropriate Action Types

- **PATCH**: Small, localized changes within methods
- **REPLACE**: When most of method body changes
- **CREATE_METHOD**: For completely new methods
- **REMOVE_METHOD**: When removing methods entirely

### 3. Field Naming

When using `REMOVE_FIELD`, specify just the field name:

```
REMOVE_FIELD myField
```

Not the full signature.

### 4. Testing

Always test with `--dry-run` first:

```bash
python3 smalipatcher.py ./app test.smalipatch --dry-run --verbose
```

### 5. Version Control

- Keep `.smalipatch` files in version control
- Add meaningful CREDIT lines
- Comment complex patches

---

## Troubleshooting

### "Context not found" Error

**Problem:** PATCH action can't find matching context.

**Solutions:**
1. Add more context lines
2. Check for typos in context
3. Verify the method signature is correct
4. Use `--verbose` to see what's being searched

### "Method not found" Error

**Problem:** REPLACE/REMOVE_METHOD can't find method.

**Solutions:**
1. Copy exact method signature from smali file
2. Include full parameter types
3. Check for extra spaces in signature

### Field Not Added

**Problem:** ADD_FIELD doesn't work.

**Solutions:**
1. Ensure `.field` syntax is correct
2. Check if field already exists
3. Verify file structure has `.super` or other fields

---

## Advanced Usage

### Multiple Files in One Patch

```
CREDIT Batch Update

FILE com/example/Class1.smali
PATCH .method public method1()V
  # changes
END

FILE com/example/Class2.smali
PATCH .method public method2()V
  # changes
END

CREATE com/example/Class3.smali
# content
```

### Generating Patches from Git Diff

```bash
# 1. Checkout original version
git checkout main

# 2. Generate patch
python3 smalipatch-generator.py --dir ./smali ./smali-modified output.smalipatch

# This will detect all changes between versions
```

---

## Tips & Tricks

1. **Use meaningful patch names**: `fix-login-bug.smalipatch` not `patch1.smalipatch`

2. **Break large patches into logical units**: One patch per feature/fix

3. **Test incrementally**: Apply patches one at a time during development

4. **Keep backups**: Generator creates backups automatically, but keep your own too

5. **Use comments**: Add `#` or `//` comments in patch files for clarity

6. **Version your patches**: Include version in filename: `feature-v1.0.smalipatch`

---

## Exit Codes Reference

### smalipatcher.py
- `0`: Success - all patches applied
- `1`: Failure - one or more patches failed
- `2`: Invalid arguments

### smalipatch-generator.py
- `0`: Success - patch generated
- `1`: Failure - error during generation
- `2`: Invalid arguments

---

## Support & Contributing

For issues, feature requests, or contributions, please visit the project repository.



## Quick Guide

```bash
# Apply patches
smalipatcher.py <dir> <patch>           # Apply
smalipatcher.py <dir> <patch> --dry-run # Preview
smalipatcher.py <dir> <patch> -v        # Verbose

# Generate patches
smalipatch-generator.py <file>          # Interactive
smalipatch-generator.py <file> <out>    # Custom output
smalipatch-generator.py --dir <o> <m> <out>  # Directories
```

### Patch Actions Quick Reference

| Action | Purpose | Example |
|--------|---------|---------|
| `PATCH` | Modify within method | In-method changes |
| `REPLACE` | Replace method body | Complete method rewrite |
| `CREATE_METHOD` | Add new method | New functionality |
| `REMOVE_METHOD` | Delete method | Remove old code |
| `ADD_FIELD` | Add field | New class variable |
| `REMOVE_FIELD` | Delete field | Remove old variable |
| `CREATE` | New file | Create class |
| `REMOVE` | Delete file | Remove class |
| `FIND_REPLACE` | Replaces string | Unique classes |
| `CREDIT` | Attribution | Author credits |
