(smalipatch.py)
A lightweight Python 3 utility designed for applying method body replacements to disassembled Android Smali files using a clean, human-readable patch format. Ideal for automation in reverse engineering workflows.

 GETTING STARTED
Prerequisites
This script requires Python 3.

File header:
#!/usr/bin/env python3

Usage
The script is executed via the command line and requires two arguments: the working directory (root of the decompiled APK) and the patch file.

Command:
python3 smalipatch.py <work_dir> <patch_file.smalipatch>

Example Execution
If your disassembled application files are located in 'apk_unpacked/' and your patch is in a subdirectory:

python3 smalipatch.py ./apk_unpacked ./patches/no-signature-check.smalipatch

Success Output:
SUCCESS: Replaced method in target/smali/com/example/PackageVerification.smali

 .SMALIPATCH FORMAT SPECIFICATION
A patch file must define three mandatory sections in order: the target file, the action/method signature, and the new patch content.

Line 1: Target File
Specify the relative path to the Smali file from your <work_dir>.

Directive: FILE
Example: FILE smali_classes2/com/app/core/Signer.smali

Line 2: Action and Method Signature
Specify the action and the full, unambiguous signature of the method you wish to target.

Action: REPLACE
Description: Replaces the entire method body (everything between the .method and .end method lines) with the new patch content.
Status: Implemented

Action: MODIFY
Description: Reserved for future line-by-line insertion/deletion logic.
Status: Pending

Example Signature:
REPLACE .method public static blacklist getMinimumSignatureSchemeVersionForTargetSdk(I)I

Lines 3+: Patch Content
This section contains the new Smali instructions. DO NOT include the .method ... or .end method lines here; the script handles those boundaries.

 PRACTICAL EXAMPLE
This example demonstrates how to use the patcher to disable a strict signature check by forcing the method to always return '1' (Signature Scheme v1).

no-signature-check.smalipatch
FILE android/util/apk/PackageVerification.smali
REPLACE .method public static blacklist getMinimumSignatureSchemeVersionForTargetSdk(I)I
.locals 1
.param p0, "targetSdk"    # I

.line 573
const/4 v0, 0x1
return v0

📝 Resulting Smali File Content (Excerpt)
The target file is successfully modified to contain only the patch code within the method block:

.method public static blacklist getMinimumSignatureSchemeVersionForTargetSdk(I)I
.locals 1
.param p0, "targetSdk"    # I

.line 573
const/4 v0, 0x1
return v0

.end method
