/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-stop-check.json
 * Evidence: ev_f10ed10d9391f53b5511d81458484f6ecdb738eddc182e11a14f2f83530905e4
 */


bool FUN_140deac70(longlong param_1)

{
  if (*(char *)(param_1 + 0x11c) == '\0') {
    return true;
  }
  return *(uint *)(param_1 + 0x128) < 10;
}


