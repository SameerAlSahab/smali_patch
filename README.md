Prerequisites
This script requires Python 3.

#!/usr/bin/env python3

Usage

The script is executed via the command line and requires two arguments: the working directory (root of the decompiled APK) and the patch file.

python3 smalipatch.py <work_dir> <patch_file.smalipatch>

Example Execution
If your disassembled application files are located in apk_unpacked/ and your patch is in a subdirectory:

python3 smalipatch.py ./apk_unpacked ./patches/no-signature-check.smalipatch

Success Output:

SUCCESS: Replaced method in target/smali/com/example/PackageVerification.smali

There is a example .smalipatch file for you !!
_________________________________________________________
Check the apk_signature_disable.smalipatch as example  
__________________________________________________________
Happy Modding ;D
